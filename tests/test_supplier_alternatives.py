from copy import deepcopy

import pytest
from test_kit import CASE
from test_unified import supplier

from arena_kit.agents.unified import UnifiedAgent
from negotiator.supplier_alternatives import ALTERNATIVE_MARKER


def scenario():
    case = deepcopy(CASE)
    message = supplier("open", 42)
    alternative = {"unit_price": 40.5, "payment_days": 60}
    message["term_sheets"].append({"term_sheet_id": "offer:alternative", "terms": alternative})
    return case, message, alternative


def test_promote_cheapest_complete_alternative_then_accept_only_standing_id():
    case, message, alternative = scenario()
    agent = UnifiedAgent()
    out = agent.decide(case, {"sup:A": [message]})
    assert out["message"]["term_sheets"] == [{"terms": alternative}]
    assert "action" not in out["message"]
    assert ALTERNATIVE_MARKER in out["message"]["body"]
    assert agent.decision_history[-1]["supplier_alternative"]
    confirmed = supplier("agreed", 40.5, payment_days=60)
    result = agent.decide(case, {"sup:A": [message, {**out["message"], "from": "buyer"}, confirmed]})
    assert result["message"]["action"]["term_sheet_id"] == "offer:40.5"


@pytest.mark.parametrize("bad", [
    {"unit_price": 30},  # Incomplete: do not invent the missing alternative term.
    {"unit_price": 40, "payment_days": 77},
    {"unit_price": 44, "payment_days": 30},
    {"unit_price": 40, "payment_days": 60, "invented": 1},
])
def test_invalid_incomplete_or_worse_alternatives_are_not_promoted(bad):
    case, message, _ = scenario()
    message["term_sheets"][1]["terms"] = bad
    agent = UnifiedAgent()
    agent.decide(case, {"sup:A": [message]})
    assert not agent.decision_history[-1].get("supplier_alternative")


def test_must_haves_and_reservation_still_filter_alternatives():
    case, message, _ = scenario()
    case["buyer"]["must_haves"] = [{"field": "payment_days", "op": "<=", "value": 30}]
    agent = UnifiedAgent()
    agent.decide(case, {"sup:A": [message]})
    assert not agent.decision_history[-1].get("supplier_alternative")
    case["buyer"]["must_haves"] = []
    case["buyer"]["fallback_unit_price"] = 20
    assert UnifiedAgent().decide(case, {"sup:A": [message]})["message"]["action"]["type"] == "walk_away"


def test_no_stale_prose_only_or_repeated_alternative():
    case, message, _ = scenario()
    agent = UnifiedAgent()
    first = agent.decide(case, {"sup:A": [message]})
    repeated = agent.decide(case, {"sup:A": [message, {**first["message"], "from": "buyer"}, message]})
    assert ALTERNATIVE_MARKER not in repeated["message"].get("body", "")
    later = supplier("open", 42, body="We previously discussed 40.50, but only 42.00 stands now.")
    agent.decide(case, {"sup:A": [message, later]})
    assert not agent.decision_history[-1].get("supplier_alternative")


def test_choose_by_total_cost_not_price_and_only_one_message_per_supplier():
    case, message, _ = scenario()
    message["term_sheets"] += [{"term_sheet_id": "offer:another", "terms": {"unit_price": 40.6, "payment_days": 90}}]
    decisions = UnifiedAgent().decide_batch(case, {"sup:A": [message], "sup:B": [supplier("final_offer", 43)]})
    assert len(decisions) == 1
    assert decisions[0]["message"]["term_sheets"][0]["terms"]["unit_price"] == 40.6


def test_concrete_saving_is_not_discarded_by_speculative_improvement_threshold():
    case, message, _ = scenario()
    message["term_sheets"][1]["terms"] = {"unit_price": 41.99, "payment_days": 30}
    agent = UnifiedAgent()
    out = agent.decide(case, {"sup:A": [message]})
    assert out["message"]["term_sheets"][0]["terms"]["unit_price"] == 41.99
    assert agent.decision_history[-1]["supplier_alternative"]


def test_runner_gets_standing_confirmation_before_closing():
    from arena_kit.play import play

    case, message, alternative = scenario()

    class Table:
        def open(self, case_id):
            return case, {"sup:A": [message]}

        def send(self, sid, msg):
            assert msg["term_sheets"] == [{"terms": alternative}]
            return supplier("agreed", 40.5, payment_days=60)

        def close(self, sid, msg):
            assert msg["action"]["term_sheet_id"] == "offer:40.5"
            return {"deal": True, "terms": alternative}

    assert play(Table(), case["case_id"], UnifiedAgent())["terms"] == alternative
