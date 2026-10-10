from copy import deepcopy

import pytest
from test_kit import CASE
from test_unified import supplier

from arena_kit.agents.unified import UnifiedAgent
from negotiator.response_signal import response_signal
from scripts.validate_mvp import audit_decisions


def history(prices, days=None):
    events = []
    for index, price in enumerate(prices):
        if index:
            events.append({"from": "buyer", "body": "Please review our proposal.",
                           "term_sheets": [{"terms": {"unit_price": prices[0] * .95, "payment_days": 30}}]})
        msg = supplier("open", price, payment_days=(days or [30] * len(prices))[index])
        msg["message_id"] = f"msg:observation-{index}"
        msg["term_sheets"][0]["term_sheet_id"] = f"offer:observation-{index}"
        events.append(msg)
    return events


@pytest.mark.parametrize("scale", [1, 10, 100])
def test_tentative_signal_is_scale_independent_and_not_a_profile(scale):
    events = history([42 * scale, 41.98 * scale, 41.96 * scale])
    signal = response_signal(CASE, events)
    assert signal["kind"] == "diminishing_progress"
    assert len(signal["sources"]) == 3
    assert "supplier_profile" not in signal


def test_sparse_repeated_changed_basis_or_renewed_progress_do_not_establish_stall():
    for events in (history([42, 41.98]), history([42, 41.98, 40]),
                   history([42, 41.98, 41.96], [30, 30, 60]),
                   [history([42])[0]] * 3):
        assert response_signal(CASE, events) is None


@pytest.mark.parametrize("body", ['You wrote: "our price is fixed."', 'If we cannot reduce our price, we could talk.',
                                  'Our price is not fixed.', 'We cannot reduce quality.'])
def test_quote_conditional_negation_and_other_refusal_do_not_become_price_freeze(body):
    assert response_signal(CASE, [supplier("open", 42, body=body)]) is None


def test_explicit_price_constraint_is_cleared_by_explicit_revision():
    events = history([42, 42])
    events[0]["body"] = "Our price is fixed."
    assert response_signal(CASE, events)["kind"] == "explicit_price_constraint"
    events[-1]["body"] = "We can reduce our price now."
    assert response_signal(CASE, events) is None


def test_stall_allows_one_costed_payment_experiment_without_changing_profile():
    events = history([42, 41.98, 41.96])
    # Last numeric proposal now repeats, so the ordinary ladder has stalled.
    events[-2]["term_sheets"][0]["terms"]["unit_price"] = 39.91
    agent = UnifiedAgent()
    out = agent.decide(CASE, {"sup:A": events})
    # A tiny latest price move still has a new price counter; another hold
    # supplies the third negligible observation without inventing a floor.
    events += [{**out["message"], "from": "buyer"}, supplier("open", 41.96)]
    events[-1]["message_id"] = "msg:observation-3"
    out = agent.decide(CASE, {"sup:A": events})
    trace = agent.decision_history[-1]
    assert trace["response_trade"]
    terms = out["message"]["term_sheets"][0]["terms"]
    assert terms["unit_price"] > 41.96 and terms["payment_days"] > 30
    assert not any(trace["profile_used"].values())
    assert "replaces the quoted 30 days" in out["message"]["body"]
    assert "threshold" not in out["message"]["body"]
    assert audit_decisions(CASE, agent.decision_history) == []
    events += [{**out["message"], "from": "buyer"}, supplier("open", 41.96)]
    followup = agent.decide(CASE, {"sup:A": events})
    assert "term_sheets" not in followup["message"]


def test_index_invitation_asks_for_complete_clause_once_not_an_invented_agreement():
    case = deepcopy(CASE)
    case["negotiable"].append("index_clause")
    case["term_options"]["index_clause"] = [None]
    events = history([42, 41.98])
    for event in events:
        if event.get("term_sheets"):
            event["term_sheets"][0]["terms"]["index_clause"] = None
    events[-1]["body"] = "We can offer an index clause on a metal series."
    agent = UnifiedAgent()
    out = agent.decide(case, {"sup:A": events})
    assert "series, material share, base month, deadband" in out["message"]["body"]
    assert "term_sheets" not in out["message"]
    events += [{**out["message"], "from": "buyer"}, deepcopy(events[-1])]
    agent.decide(case, {"sup:A": events})
    assert agent.decision_history[-1]["action"] != "clarify_trade"


@pytest.mark.parametrize("price", [10, 40, 400])
def test_valid_delivery_repair_can_receive_bounded_movement_even_if_price_increases(price):
    case = deepcopy(CASE)
    case["negotiable"].append("lead_time_days")
    case["fixed_terms"].pop("lead_time_days")
    case["term_options"]["lead_time_days"] = [35, 52]
    case["buyer"]["fallback_unit_price"] = price * 2
    case["buyer"]["must_haves"] = [{"field": "lead_time_days", "op": "<=", "value": 35}]
    opening, current = supplier("open", price), supplier("open", price * 1.05)
    opening["term_sheets"][0]["terms"]["lead_time_days"] = 52
    current["term_sheets"][0]["terms"]["lead_time_days"] = 35
    prior = {"unit_price": price * .95, "payment_days": 30, "lead_time_days": 35}
    events = [opening, {"from": "buyer", "term_sheets": [{"terms": prior}]}, current]
    agent = UnifiedAgent()
    out = agent.decide(case, {"sup:A": events})
    terms = out["message"]["term_sheets"][0]["terms"]
    assert prior["unit_price"] < terms["unit_price"] <= price
    assert terms["lead_time_days"] == 35
    assert agent.decision_history[-1]["progress_credit"]["kind"] == "feasibility_repair"
    assert audit_decisions(case, agent.decision_history) == []


def test_lower_unit_price_with_worse_total_cost_does_not_earn_movement():
    events = history([42, 41.99], [90, 14])
    events[1]["term_sheets"][0]["terms"] = {"unit_price": 40, "payment_days": 90}
    agent = UnifiedAgent()
    out = agent.decide(CASE, {"sup:A": events})
    for sheet in out["message"].get("term_sheets", []):
        assert sheet["terms"]["unit_price"] <= 40
