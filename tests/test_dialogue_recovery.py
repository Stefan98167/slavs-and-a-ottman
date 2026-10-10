from copy import deepcopy

import pytest
from test_kit import CASE
from test_unified import supplier

from arena_kit.agents.unified import UnifiedAgent
from negotiator.dialogue_recovery import (
    can_clarify,
    capacity_refused,
    indicative_alternative,
    recovery_message,
    unasked_trade_terms,
)
from scripts.validate_mvp import select_cases


def test_new_trade_field_can_be_asked_but_questions_are_bounded():
    events = [{"from": "buyer", "body": "You invited a change to payment days. "
               "Which concrete values and matching price could you approve?"}]
    assert unasked_trade_terms(events, ["payment_days", "index_clause"]) == ["index_clause"]
    events.append({"from": "buyer", **recovery_message("capacity")})
    assert unasked_trade_terms(events, ["index_clause"]) == []
    assert not can_clarify(events, "incomplete_offer")


@pytest.mark.parametrize("price", [3.7, 42, 365])
def test_incomplete_standing_gets_one_question_never_fabricated_payment(price):
    case = deepcopy(CASE)
    case["buyer"]["fallback_unit_price"] = price * 2
    opening = supplier("open", price)
    del opening["term_sheets"][0]["terms"]["payment_days"]
    agent = UnifiedAgent()
    out = agent.decide(case, {"sup:A": [opening]})
    assert agent.decision_history[-1]["issue"] == "incomplete_offer"
    assert "term_sheets" not in out["message"]
    events = [opening, {"from": "buyer", **out["message"]}, opening]
    assert agent.decide(case, {"sup:A": events})["message"]["action"]["type"] == "walk_away"
    events.append(supplier("agreed", price, payment_days=30))
    assert agent.decide(case, {"sup:A": events})["message"]["action"]["type"] == "accept"


def test_no_structured_offer_requests_complete_quote_once_and_deadline_closes():
    message = {"from": "supplier", "status": "open", "body": "Quote to follow."}
    agent = UnifiedAgent()
    result = agent.decide(CASE, {"sup:A": [message]})
    assert "EUR per item" in result["message"]["body"]
    assert agent.close(CASE, {"sup:A": [message]})["message"]["action"]["type"] == "walk_away"
    assert UnifiedAgent().decide({**CASE, "round_limit": 0}, {"sup:A": [message]})[
        "message"]["action"]["type"] == "walk_away"


def test_explicit_capacity_refusal_gets_one_nonbinding_question():
    opening = supplier("open", 42)
    agent = UnifiedAgent()
    first = agent.decide(CASE, {"sup:A": [opening]})
    response = supplier("open", 42, body="We cannot supply the requested volume.")
    events = [opening, {"from": "buyer", **first["message"]}, response]
    out = agent.decide(CASE, {"sup:A": events})
    assert agent.decision_history[-1]["issue"] == "capacity"
    assert "term_sheets" not in out["message"]
    assert not can_clarify([*events, {"from": "buyer", **out["message"]}], "capacity")


@pytest.mark.parametrize("body", [
    "You said: we cannot supply the requested volume.",
    "If we cannot supply the requested volume, we will tell you.",
    "We can supply the requested volume.",
])
def test_capacity_refusal_is_not_guessed_from_quotes_or_conditionals(body):
    assert not capacity_refused(supplier("open", 42, body=body))


def test_incomplete_current_alternative_is_clarified_not_promoted_or_accepted():
    message = supplier("open", 42)
    message["term_sheets"].append({"terms": {"unit_price": 40}})
    out = UnifiedAgent().decide(CASE, {"sup:A": [message]})
    assert "indicative alternative" in out["message"]["body"]
    assert "term_sheets" not in out["message"]
    message["status"] = "final_offer"
    assert UnifiedAgent().decide(CASE, {"sup:A": [message]})["message"]["action"] == {
        "type": "accept", "term_sheet_id": "offer:42"}
    assert not indicative_alternative(supplier("open", 42, body="You proposed an alternative package."),
                                      CASE["negotiable"])


def test_infeasible_requirement_gets_question_then_explained_walk():
    case = deepcopy(CASE)
    case["buyer"]["must_haves"] = [{"field": "payment_days", "op": ">=", "value": 999}]
    message = supplier("open", 42)
    agent = UnifiedAgent()
    first = agent.decide(case, {"sup:A": [message]})
    assert agent.decision_history[-1]["issue"] == "feasibility"
    assert "must-haves" in " ".join(agent.decision_history[-1]["validation_warnings"])
    second = agent.decide(case, {"sup:A": [message, {"from": "buyer", **first["message"]}, message]})
    assert second["message"]["action"]["type"] == "walk_away"
    assert "buyer must-haves are not satisfied" in agent.decision_history[-1]["validation_warnings"]
    assert "999" not in str(first)  # No indiscriminate dump of buyer input.


def test_full_suite_is_all_ten_unique_hosted_cases_and_no_replacement_selection():
    cases = [{"case_id": f"case:X{i}", "hosted": i < 10} for i in range(19)]
    eligible, selected = select_cases(cases, 12, "all")
    assert selected == eligible and len(selected) == 10
    assert select_cases(cases, 987, "all")[1] == selected
    with pytest.raises(ValueError, match="exactly ten"):
        select_cases(cases[1:], 12, "all")
    with pytest.raises(ValueError, match="duplicate"):
        select_cases(cases + [cases[0]], 12, "all")
