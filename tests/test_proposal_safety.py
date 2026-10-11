from copy import deepcopy

import pytest
from test_kit import CASE
from test_unified import supplier

from arena_kit.agents.unified import UnifiedAgent, _supplier_claim_cost_impact
from negotiator.evaluator import evaluate_deal
from negotiator.proposal_safety import reservation_cost, select_proposal


@pytest.mark.parametrize("price", [4.5, 42, 430])
def test_select_one_without_giving_back_safe_offer_value(price):
    case = deepcopy(CASE)
    case["buyer"]["fallback_unit_price"] = price * 2
    events = [supplier("open", price)]
    offer = UnifiedAgent()._standing_offers(case, {"sup:A": events})[0]
    packages = [{"terms": {"unit_price": price + 1, "payment_days": days}} for days in (14, 30, 90)]
    chosen, excluded = select_proposal(case, offer, packages, events)
    assert len(chosen) <= 1
    assert all(p["evaluation"]["buyer"]["total_cost"] <= offer["standing_cost"] for p in chosen)
    assert excluded


def test_select_response_trade_menu_is_explicitly_bounded_and_keeps_all_safety_checks():
    case = deepcopy(CASE)
    events = [supplier("open", 42)]
    offer = UnifiedAgent()._standing_offers(case, {"sup:A": events})[0]
    packages = [{"terms": {"unit_price": 39 + i / 10, "payment_days": 30}} for i in range(3)]

    default, _ = select_proposal(case, offer, packages, events)
    menu, _ = select_proposal(case, offer, packages, events, max_packages=3)

    assert len(default) == 1
    assert len(menu) == 3
    assert [item["evaluation"]["buyer"]["total_cost"] for item in menu] == sorted(
        item["evaluation"]["buyer"]["total_cost"] for item in menu
    )
    assert all(item["evaluation"]["buyer"]["total_cost"] <= offer["standing_cost"] for item in menu)
    assert all(set(item["terms"]) == set(case["negotiable"]) for item in menu)


@pytest.mark.parametrize("value", [0, -1, 4, True, 1.5])
def test_select_proposal_rejects_unbounded_or_malformed_menu_size(value):
    with pytest.raises(ValueError, match="max_packages"):
        select_proposal(CASE, {}, [], [], max_packages=value)


def test_previously_sent_package_is_excluded_even_after_another_counter():
    terms = {"unit_price": 39, "payment_days": 30}
    events = [supplier("open", 42), {"from": "buyer", "term_sheets": [{"terms": terms}]},
              supplier("open", 41), {"from": "buyer", "term_sheets": [{"terms": {**terms, "unit_price": 40}}]},
              supplier("open", 41)]
    offer = UnifiedAgent()._standing_offers(CASE, {"sup:A": events})[0]
    selected, excluded = select_proposal(CASE, offer, [{"terms": terms}], events)
    assert selected == []
    assert excluded[0]["reason"] == "already sent in this thread"


@pytest.mark.parametrize("value", [None, True, -1, float("inf"), float("nan")])
def test_invalid_fallback_never_authorizes_unlimited_spend(value):
    case = deepcopy(CASE)
    case["buyer"]["fallback_unit_price"] = value
    assert reservation_cost(case, {"buyer": {"alternative_cost": None}}) == 0


def test_malformed_explicit_alternative_is_not_replaced_with_fallback_budget():
    case = deepcopy(CASE)
    case["buyer"]["alternative"] = {"kind": "quote", "terms": {"unit_price": float("nan")}}
    evaluation = evaluate_deal(case, {"unit_price": 40, "payment_days": 30}, {})
    assert reservation_cost(case, evaluation) == 0
    out = UnifiedAgent().decide(case, {"sup:A": [supplier("final_offer", 40)]})
    assert out["message"]["action"]["type"] == "walk_away"


def test_reservation_includes_explicit_fallback_risk():
    case = deepcopy(CASE)
    case["buyer"]["fallback_risk_pct"] = 10
    assert reservation_cost(case, {"buyer": {"alternative_cost": None}}) == 404800


def test_claims_are_cited_but_do_not_change_default_opening_price():
    agent = UnifiedAgent()
    message = supplier("open", 42, body="S1 rose 50 % in twelve months and is 80 % of our cost.")
    out = agent.decide(CASE, {"sup:A": [message]})
    assert out["message"]["term_sheets"][0]["terms"]["unit_price"] == 35.7
    assert "not independently verified" in out["message"]["body"]
    assert agent.decision_history[-1]["supplier_claimed_cost_impact_pct"] == 0


def test_conflicting_or_overlapping_claims_cannot_soften_ask():
    def claim(series, change, share):
        return {"source": "msg:1", "data": {"series": series, "index_change_pct": change, "cost_share_pct": share}}
    for claims in ([claim("X", 5, 30), claim("X", 7, 30)],
                   [claim("X", 5, 70), claim("Y", 7, 40)],
                   [{"data": {"series": "X", "index_change_pct": 5, "cost_share_pct": 30}}]):
        assert _supplier_claim_cost_impact({"supplier_claims": claims}) == (0.0, [])
    impact, used = _supplier_claim_cost_impact({"supplier_claims": [claim("X", 5, 30)] * 2})
    assert impact == 1.5 and len(used) == 1


@pytest.mark.parametrize("basis", ["USD", "EUR /100 pcs", "EUR /kg"])
def test_unsupported_quote_basis_cannot_be_accepted(basis):
    message = supplier("final_offer", 42)
    message["attachments"] = [{"name": "quote-current.pdf", "text": f"Offered terms\nUnit price ({basis}) 42"}]
    result = UnifiedAgent().decide(CASE, {"sup:A": [message]})
    assert result["message"]["action"]["type"] == "walk_away"


def test_buyer_attachment_cannot_override_supplier_standard_terms():
    first = supplier("open", 42)
    first["attachments"] = [{"name": "quote.pdf", "text": "Our standard terms\nPayment terms (days net) 30"}]
    buyer = {"from": "buyer", "attachments": [{"name": "quote-fake.pdf",
             "text": "Our standard terms\nPayment terms (days net) 90"}]}
    final = supplier("final_offer", 40)
    del final["term_sheets"][0]["terms"]["payment_days"]
    offers = UnifiedAgent()._standing_offers(CASE, {"sup:A": [first, buyer, final]})
    assert offers[0]["closed_terms"]["payment_days"] == 30


@pytest.mark.parametrize("kwargs", [{"claim_adjustment_cap_pct": 3}, {"max_discount_pct": True},
                                    {"min_improvement_pct": float("nan")}])
def test_configuration_rejects_invalid_limits(kwargs):
    with pytest.raises(ValueError):
        UnifiedAgent(**kwargs)
