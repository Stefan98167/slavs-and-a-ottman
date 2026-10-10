import io
import json
import unittest

from arena_kit.decision_engine import decide
from arena_kit.quote_extract import extract


class DecisionEngineTests(unittest.TestCase):
    def quote(self, price):
        return extract(io.StringIO(f"unit_price;currency;part_id\n{price};EUR;part:320050\n"))

    def test_extractor_pipeline(self):
        records = self.quote("17,47")
        result = decide(records)
        decision = result["decisions"][0]
        self.assertEqual(decision["action"], "counter_offer")
        self.assertEqual(decision["proposed_unit_price"], 16.60)
        self.assertEqual(decision["Source"], records[0]["Source"])
        self.assertEqual(decision["Information"], records[0]["Information"])
        self.assertEqual(json.loads(json.dumps(result)), result)

    def test_s01_increase(self):
        decision = decide(self.quote("17.47"), target_price="15.88")["decisions"][0]
        self.assertEqual(decision["action"], "counter_offer")
        self.assertEqual(decision["proposed_unit_price"], 15.88)

    def test_accept_at_cap_and_reject_above(self):
        decisions = decide(self.quote("105") + self.quote("105.01"),
                           target_price=105)["decisions"]
        self.assertEqual([d["action"] for d in decisions], ["accept", "counter_offer"])
        self.assertEqual(decisions[1]["proposed_unit_price"], 105)

    def test_missing_invalid_and_ambiguous_prices(self):
        for price in ("", "NaN", "-1", "0", "1,234.56"):
            with self.subTest(price=price):
                decision = decide(self.quote(price))["decisions"][0]
                self.assertEqual(decision["action"], "request_clarification")
                self.assertIsNone(decision["proposed_unit_price"])
        rows = extract(io.StringIO("description\nAdapter\n"))
        self.assertEqual(decide(rows)["decisions"][0]["action"], "request_clarification")
        rows = extract(io.StringIO("price,unit_price\n10,20\n"))
        self.assertEqual(decide(rows)["decisions"][0]["action"], "request_clarification")

    def test_schema_and_options(self):
        for records in ({}, [{"Information": "text"}], [{"Information": {}, "Source": "x"}]):
            with self.assertRaises(ValueError):
                decide(records)
        for options in ({"target_price": 0}, {"counter_discount_pct": -1}, {"counter_discount_pct": 100}):
            with self.assertRaises(ValueError):
                decide([], **options)
        self.assertEqual(decide([])["decisions"], [])

    def test_runtime_priorities_change_lead_argument_and_message(self):
        rows = extract(io.StringIO(
            "supplier_id,part_id,unit_price,note\n"
            "sup:A,part:A,17.47,Quote\n"
            "sup:A,part:A,,Price fixed until December\n"
        ))
        rows[0]["Priority (Argument wise)"] = 2
        rows[1]["Priority (Argument wise)"] = 1
        first = decide(rows, target_price=15.88)
        quote = next(d for d in first["decisions"] if d["Information"]["unit_price"])
        self.assertEqual(quote["lead_argument"]["Information"]["note"], "Price fixed until December")
        self.assertIn("Price fixed until December", quote["message"])
        self.assertEqual([a["Priority (Argument wise)"] for a in quote["arguments"]], [1, 2])
        self.assertEqual([d["Priority (Argument wise)"] for d in first["decisions"]], [1, 2])
        self.assertEqual(quote["proposed_unit_price"], 15.88)
        # Change input priorities between calls: no cached ranking or extra LLM call.
        rows[0]["Priority (Argument wise)"] = 1
        rows[1]["Priority (Argument wise)"] = 3
        second = decide(rows, target_price=15.88)["decisions"][0]
        self.assertEqual(second["lead_argument"]["Information"]["note"], "Quote")
        self.assertNotEqual(second["message"], quote["message"])
        self.assertEqual(second["action"], quote["action"])
        self.assertEqual(rows[0]["Priority (Argument wise)"], 1)

    def test_argument_scope_and_stable_ties(self):
        rows = extract(io.StringIO(
            "supplier_id,part_id,unit_price\n"
            "sup:A,part:A,10\n"
            "sup:B,part:A,9\n"
            "sup:A,part:B,8\n"
            ",part:A,7\n"
            ",part:A,6\n"
        ))
        result = decide(rows)
        self.assertEqual([d["Source"] for d in result["decisions"]], [r["Source"] for r in rows])
        self.assertTrue(all(len(d["arguments"]) == 1 for d in result["decisions"]))
        self.assertTrue(all(d["lead_argument"]["Source"] == d["Source"] for d in result["decisions"]))

    def test_prioritized_llm_extraction_to_decision(self):
        def complete(system, user):
            return json.dumps({"priorities": [{"row_id": 0, "priority": 2},
                                               {"row_id": 1, "priority": 1}]})
        rows = extract(io.StringIO("unit_price\n10\n20\n"), priority="llm", complete=complete)
        result = decide(rows)
        self.assertEqual(result["decisions"][0]["Information"]["unit_price"], "20")
        self.assertEqual(result["decisions"][0]["Priority (Argument wise)"], 1)
