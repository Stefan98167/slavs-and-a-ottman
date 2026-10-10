"""Supplier-only adapter to the existing decide(case, threads) interface.

The case argument is deliberately never read. Prices, identity and standard
terms come only from supplier events, supplier attachments and supplied records.
The target is a policy discount from the supplier's opening quote.
"""

from copy import deepcopy

from ..decision_engine import decide as decide_records
from ..docs import standard_terms
from ..play import latest, live_threads, standing


class DummyAgent:
    def __init__(self, records=None, *, counter_discount_pct=5, max_rounds=10):
        self.records = deepcopy(records if records is not None else [])
        decide_records(self.records, counter_discount_pct=counter_discount_pct)
        if type(max_rounds) is not int or max_rounds < 1:
            raise ValueError("max_rounds must be a positive integer")
        self.counter_discount_pct = counter_discount_pct
        self.max_rounds = max_rounds
        self.decision_history = []

    def decide(self, case, threads):
        return self._decide(threads)

    def close(self, case, threads):
        """Deadline handling also uses only supplier information."""
        return self._decide(threads, closing=True)

    def _decide(self, threads, closing=False):
        suppliers = live_threads(threads)
        if not suppliers:
            raise ValueError("No live supplier thread")
        quoting = [sid for sid in suppliers if standing(threads[sid])[1].get("unit_price") is not None]
        if not quoting:
            sid = suppliers[0]
            events = threads[sid]
            stop = closing or latest(events).get("status") == "final_offer" or sum(
                event.get("from") == "buyer" for event in events
            ) >= self.max_rounds
            message = ({"action": {"type": "walk_away"}} if stop else
                       {"body": "Please provide a unit price, currency, price unit and applicable terms.",
                        "term_sheets": []})
            return {"supplier_id": sid, "message": message}
        # No cost comparison between different parts/currencies without supplier
        # evidence establishing comparability. Process live threads in order.
        sid = quoting[0]
        events = threads[sid]
        offer_id, terms = standing(events)
        supplier_records = [r for r in self.records if r["Information"].get("supplier_id") == sid]
        part = terms.get("part_id")
        if not part:
            parts = {r["Information"].get("part_id") for r in supplier_records
                     if isinstance(r["Information"].get("part_id"), str) and r["Information"]["part_id"]}
            part = next(iter(parts)) if len(parts) == 1 else None
        evidence = [r for r in supplier_records if part and r["Information"].get("part_id") == part]
        opening = next((event["term_sheets"][0] for event in events
                        if event.get("from") != "buyer" and event.get("term_sheets")
                        and event["term_sheets"][0].get("terms", {}).get("unit_price") is not None), None)
        opening_record = {"Information": {"unit_price": opening["terms"]["unit_price"]},
                          "Source": opening["term_sheet_id"], "Priority (Argument wise)": 1}
        target = decide_records([opening_record], counter_discount_pct=self.counter_discount_pct)["decisions"][0][
            "proposed_unit_price"
        ]
        live = {"Information": {"supplier_id": sid, "part_id": part, "unit_price": terms["unit_price"]},
                "Source": offer_id, "Priority (Argument wise)": 3 if evidence else 1}
        report = decide_records([*evidence, live], target_price=target,
                                counter_discount_pct=self.counter_discount_pct)
        decision = next(d for d in report["decisions"] if d["Source"] == offer_id
                        and d["Information"] == live["Information"])
        decision["target_source"] = {"Source": opening_record["Source"],
                                     "opening_unit_price": opening_record["Information"]["unit_price"],
                                     "discount_pct": self.counter_discount_pct, "target_unit_price": target}
        decision["reason"] = (f"Policy target is {target}, derived from the supplier's opening quote "
                              f"using a {self.counter_discount_pct}% discount. " + decision["reason"])
        std = standard_terms(events)
        required = set(terms)
        for event in events:
            if event.get("from") != "buyer":
                required.update(event.get("missing_fields") or [])
        supplied_terms = {**std, **terms}
        missing = sorted(field for field in required if field not in supplied_terms)
        rounds = sum(event.get("from") == "buyer" for event in events)
        if decision["action"] == "accept" and not missing:
            message = {"action": {"type": "accept", "term_sheet_id": offer_id}}
        elif closing or latest(events).get("status") == "final_offer" or rounds >= self.max_rounds:
            message = {"action": {"type": "walk_away"}}
        elif missing:
            message = {"body": f"Please provide the missing terms: {', '.join(missing)}.", "term_sheets": []}
        elif decision["proposed_unit_price"] is None:
            message = {"body": "Please clarify the unit price and price unit.", "term_sheets": []}
        else:
            proposed = {field: supplied_terms[field] for field in required}
            proposed["unit_price"] = decision["proposed_unit_price"]
            message = {"subject": latest(events).get("subject", "Supplier quote"),
                       "body": (decision["message"] + " " + decision["reason"])[:8000],
                       "term_sheets": [{"terms": proposed}]}
        self.decision_history.append({"supplier_id": sid, "offer_id": offer_id, "evidence_count": len(evidence),
                                      "input_policy": "supplier_only", "decision": decision, "message": message})
        return {"supplier_id": sid, "message": message}
