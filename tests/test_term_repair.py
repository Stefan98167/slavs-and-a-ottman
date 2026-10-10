from copy import deepcopy

import pytest
from test_kit import CASE
from test_unified import supplier

from arena_kit.agents.unified import UnifiedAgent
from negotiator.term_repair import REPAIR_MARKER


@pytest.mark.parametrize("standing_payment", [14, 30])
def test_price_target_does_not_hide_worse_payment(standing_payment):
    case = deepcopy(CASE)
    events = [supplier("open", 42),
              {"from": "buyer", "term_sheets": [{"terms": {"unit_price": 40, "payment_days": 60}}]},
              supplier("open", 39, payment_days=standing_payment)]
    agent = UnifiedAgent()
    decision = agent.decide(case, {"sup:A": events})
    terms = decision["message"]["term_sheets"][0]["terms"]
    assert terms["payment_days"] == 60
    assert 39 < terms["unit_price"] <= 40
    assert REPAIR_MARKER in decision["message"]["body"]
    assert agent.decision_history[-1]["term_restoration"]
    # Rejection does not cause an endless repeated restoration attempt.
    events.extend([{**decision["message"], "from": "buyer"}, supplier("open", 39, payment_days=standing_payment)])
    assert "term_sheets" not in agent.decide(case, {"sup:A": events})["message"]


def test_price_target_with_unchanged_terms_accepts_without_new_demand():
    events = [supplier("open", 42),
              {"from": "buyer", "term_sheets": [{"terms": {"unit_price": 40, "payment_days": 30}}]},
              supplier("open", 39)]
    assert UnifiedAgent().decide(CASE, {"sup:A": events})["message"]["action"]["type"] == "accept"


def test_restoration_cannot_break_must_haves():
    case = deepcopy(CASE)
    case["buyer"]["must_haves"] = [{"field": "payment_days", "op": "<=", "value": 30}]
    events = [supplier("open", 42),
              {"from": "buyer", "term_sheets": [{"terms": {"unit_price": 40, "payment_days": 60}}]},
              supplier("open", 39)]
    assert UnifiedAgent().decide(case, {"sup:A": events})["message"]["action"]["type"] == "accept"


def test_added_index_risk_can_be_exchanged_for_bounded_price_increase():
    case = deepcopy(CASE)
    clause = {"series": "TEST", "material_share": 0.4, "deadband_pct": 0, "base_month": "2026-09"}
    case["negotiable"].append("index_clause")
    case["term_options"]["index_clause"] = [None, clause]
    case["buyer"]["index_paths"] = {"TEST": 0.08}
    opening, counter = supplier("open", 42), supplier("open", 39)
    opening["term_sheets"][0]["terms"]["index_clause"] = None
    counter["term_sheets"][0]["terms"]["index_clause"] = clause
    prior = {"unit_price": 40, "payment_days": 30, "index_clause": None}
    events = [opening, {"from": "buyer", "term_sheets": [{"terms": prior}]}, counter]
    agent = UnifiedAgent()
    out = agent.decide(case, {"sup:A": events})
    terms = out["message"]["term_sheets"][0]["terms"]
    assert terms["index_clause"] is None
    assert 39 < terms["unit_price"] <= 40
    trace = agent.decision_history[-1]
    assert trace["best_package_total_cost"] < trace["standing_total_cost"] < trace["reservation_cost"]
