from copy import deepcopy

import pytest
from test_kit import CASE
from test_unified import supplier

from arena_kit.agents.unified import UnifiedAgent
from negotiator.response_trades import RESPONSE_TRADE_MARKER, response_trade_packages


def stalled_events():
    return [supplier("open", 42),
            {"from": "buyer", "term_sheets": [{"terms": {"unit_price": 39.9, "payment_days": 30}}]},
            supplier("open", 42, body="Extension of payment terms would require a higher price.")]


def test_explicit_payment_invitation_can_buy_lower_total_cost_at_higher_price():
    events = stalled_events()
    agent = UnifiedAgent()
    out = agent.decide(CASE, {"sup:A": events})
    trace = agent.decision_history[-1]
    assert trace["response_trade"]
    assert all(item["terms"]["unit_price"] > 42 and item["terms"]["payment_days"] > 30
               for item in out["message"]["term_sheets"])
    assert trace["best_package_total_cost"] < trace["standing_total_cost"]
    assert RESPONSE_TRADE_MARKER in out["message"]["body"]
    events += [{**out["message"], "from": "buyer"}, supplier("open", 42)]
    assert "term_sheets" not in agent.decide(CASE, {"sup:A": events})["message"]


def test_no_invitation_keeps_unknown_profile_price_only():
    events = stalled_events()
    events[-1]["body"] = "Our price is unchanged."
    out = UnifiedAgent().decide(CASE, {"sup:A": events})
    assert "term_sheets" not in out["message"]


@pytest.mark.parametrize("path", [0.06, -0.06, 0])
def test_index_trade_preserves_supplier_index_and_only_proposes_cost_saving_bands(path):
    case = deepcopy(CASE)
    clause = {"series": "X", "material_share": 0.45, "deadband_pct": 0, "base_month": "2026-08"}
    case["negotiable"].append("index_clause")
    case["term_options"]["index_clause"] = [None, clause, {**clause, "deadband_pct": 3},
                                             {**clause, "deadband_pct": 5}, {**clause, "series": "Y"}]
    case["buyer"]["index_paths"] = {"X": path}
    events = stalled_events()
    events[-1]["body"] = "Indexation is required."
    events[-1]["term_sheets"][0]["terms"]["index_clause"] = clause
    offer = UnifiedAgent()._standing_offers(case, {"sup:A": events})[0]
    packages = response_trade_packages(case, offer, events, [])
    assert bool(packages) == (path > 0)
    for package in packages:
        terms = package["terms"]
        assert terms["index_clause"]["series"] == "X"
        assert terms["index_clause"]["deadband_pct"] in {3, 5}
        assert terms["unit_price"] > 42
        assert package["evaluation"]["buyer"]["total_cost"] < offer["standing_cost"]


def test_response_trade_still_obeys_must_haves_and_reservation():
    case = deepcopy(CASE)
    case["buyer"]["must_haves"] = [{"field": "payment_days", "op": "<=", "value": 30}]
    events = stalled_events()
    offer = UnifiedAgent()._standing_offers(case, {"sup:A": events})[0]
    assert response_trade_packages(case, offer, events, ["payment_days"]) == []
    case["buyer"]["must_haves"] = []
    offer["reservation_cost"] = 1
    assert response_trade_packages(case, offer, events, ["payment_days"]) == []
