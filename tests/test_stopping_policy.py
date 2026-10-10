from copy import deepcopy

import pytest
from test_kit import CASE
from test_unified import supplier

from arena_kit.agents.unified import UnifiedAgent
from negotiator.buyer_arguments import price_evidence_reply
from scripts.validate_mvp import audit_decisions, reconcile_cost


def test_threshold_does_not_stop_after_just_one_supplier_reply():
    agent = UnifiedAgent(claim_adjustment_cap_pct=2)
    events = [supplier("open", 42, body="X rose 5 % in twelve months and is 40 % of our cost.")]
    first = agent.decide(CASE, {"sup:A": events})
    events += [{**first["message"], "from": "buyer"}, supplier("open", 40.8)]
    out = agent.decide(CASE, {"sup:A": events})
    assert out["message"]["term_sheets"]
    assert audit_decisions(CASE, agent.decision_history) == []
    events += [{**out["message"], "from": "buyer"}, supplier("final_offer", 40.8)]
    assert agent.decide(CASE, {"sup:A": events})["message"]["action"]["type"] == "accept"


def test_aspiration_does_not_move_when_counters_or_supplier_standards_change():
    agent = UnifiedAgent()
    opening = supplier("open", 42)
    opening["attachments"] = [{"name": "quote.pdf", "text": "Our standard terms\nPayment terms (days net) 30"}]
    first = agent.decide(CASE, {"sup:A": [opening]})
    target = agent.decision_history[-1]["opening_goal"]
    response = supplier("open", 41)
    response["attachments"] = [{"name": "quote.pdf", "text": "Our standard terms\nPayment terms (days net) 14"}]
    agent.decide(CASE, {"sup:A": [opening, {**first["message"], "from": "buyer"}, response]})
    assert agent.decision_history[-1]["opening_goal"] == target
    for item in agent.decision_history:
        assert "opening_goal" not in item["message"].get("body", "")
        assert str(target) not in item["message"].get("body", "")


def test_goal_cache_is_scoped_to_case_supplier_and_opening():
    agent = UnifiedAgent()
    agent.decide(CASE, {"sup:A": [supplier("open", 42)]})
    first = agent.decision_history[-1]["opening_goal"]
    for case, sid in (({**CASE, "case_id": "case:unseen"}, "sup:A"), (CASE, "sup:B"), (CASE, "sup:A")):
        agent.decide(case, {sid: [supplier("open", 40)]})
        assert agent.decision_history[-1]["opening_goal"] < first


def test_final_offer_and_deadline_are_not_blocked_by_minimum_rounds():
    for events, case in (([supplier("final_offer", 40)], CASE),
                         ([supplier("open", 40)], {**CASE, "round_limit": 0})):
        agent = UnifiedAgent(minimum_rounds=100)
        assert agent.decide(case, {"sup:A": events})["message"]["action"]["type"] == "accept"


def test_goal_does_not_discard_a_cheaper_concrete_supplier_alternative():
    current = supplier("open", 39.8)
    current["term_sheets"].append({"term_sheet_id": "offer:alternative",
                                   "terms": {"unit_price": 39.7, "payment_days": 30}})
    events = [supplier("open", 42), {"from": "buyer", "term_sheets": [
        {"terms": {"unit_price": 39.9, "payment_days": 30}}]}, supplier("open", 41),
        {"from": "buyer", "body": "Please confirm."}, current]
    agent = UnifiedAgent()
    out = agent.decide(CASE, {"sup:A": events})
    assert out["message"]["term_sheets"][0]["terms"]["unit_price"] == 39.7
    assert agent.decision_history[-1]["supplier_alternative"]


def test_breakdown_request_is_not_repeated_when_supplier_ignores_it():
    agent = UnifiedAgent()
    events = [supplier("open", 42)]
    first = agent.decide(CASE, {"sup:A": events})
    assert "supporting cost breakdown" in first["message"]["body"]
    events += [{**first["message"], "from": "buyer"}, supplier("open", 41.9)]
    second = agent.decide(CASE, {"sup:A": events})
    assert "supporting cost breakdown" not in second["message"]["body"]


@pytest.mark.parametrize("body", ["Which figures is that based on? Please send us the data.",
                                  "Please provide the data."])
def test_direct_request_receives_honest_evidence_response_without_invented_benchmark(body):
    reply = price_evidence_reply(CASE, "sup:A", [supplier("open", 42, body=body)])
    assert reply["kind"] == "commercial_proposal"
    assert reply["refs"] == []


def test_secondary_rfq_counter_cannot_exceed_existing_safe_competitor():
    agent = UnifiedAgent()
    result = agent.decide_batch(CASE, {"sup:A": [supplier("open", 40)], "sup:B": [supplier("open", 43)]})
    assert [item["supplier_id"] for item in result] == ["sup:A"]
    assert len(agent.decision_history) == 1


def test_post_run_reconciliation_reports_unknown_cost_without_inventing_supplier_economics():
    before = {"action": "accept", "standing_total_cost": 100,
              "predicted_cost_breakdown": {"price": 100, "relationship": 0}}
    result = {"deal": True, "c_deal": 103, "cost_breakdown": {"price": 100, "relationship": 3}}
    snapshot = deepcopy((before, result))
    diff = reconcile_cost(result, [before])
    assert diff["difference"] == 3
    assert diff["component_differences"] == {"price": 0, "relationship": 3}
    assert (before, result) == snapshot


@pytest.mark.parametrize("value", [-1, 1.5, True])
def test_invalid_minimum_rounds_are_rejected(value):
    with pytest.raises(ValueError):
        UnifiedAgent(minimum_rounds=value)
