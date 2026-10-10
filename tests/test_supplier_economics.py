from copy import deepcopy

from test_kit import CASE

from arena_kit.agents.unified import UnifiedAgent
from negotiator.packages import generate_packages
from negotiator.supplier_economics import estimate_supplier_economics, supplier_cost_fact


def _case():
    return {
        **deepcopy(CASE),
        "buyer": {
            **CASE["buyer"],
            "category_goal": "stabilise",
            "interest_rate": 0.08,
            "sustainable_margin_pct": 10,
            "relationship_eur_per_point": 3000,
        },
    }


def _cost(part, unit_cost, price_unit=1):
    return {"part": part, "unit_cost": unit_cost, "price_unit": price_unit}


def test_supplier_specific_cost_wins_and_converts_units():
    case = _case()
    facts = {
        "cost:T1-A": _cost("part:T1", 90, 6),
        "cost:T1": _cost("part:T1", 150, 3),
    }

    assert supplier_cost_fact(case, "sup:A", facts)[0] == "cost:T1-A"
    assert estimate_supplier_economics(case, "sup:A", facts) == {
        "interest_rate": 0.08,
        "full_cost": 15,
    }


def test_unusable_specific_cost_falls_back_to_generic_but_unscoped_cost_does_not():
    case = _case()
    facts = {
        "cost:T1-A": _cost("part:OTHER", 90),
        "cost:T1": _cost("part:T1", 125, 5),
    }
    assert estimate_supplier_economics(case, "sup:A", facts)["full_cost"] == 25
    assert estimate_supplier_economics(case, "sup:A", {"cost:T1": _cost("part:OTHER", 125)}) is None


def test_non_strategic_or_multi_part_case_has_no_supplier_economics():
    case = _case()
    facts = {"cost:T1-A": _cost("part:T1", 30)}
    assert estimate_supplier_economics(
        {**case, "buyer": {**case["buyer"], "category_goal": "reduce_cost"}}, "sup:A", facts
    ) is None
    assert estimate_supplier_economics({**case, "parts": ["part:T1", "part:T2"]}, "sup:A", facts) is None


def test_flag_off_preserves_price_only_cost_and_flag_on_supplies_scoped_economics(monkeypatch):
    case = _case()
    case["facts"] = {"cost:T1-A": _cost("part:T1", 50)}
    events = [{
        "from": "sales@example.test",
        "status": "open",
        "attachments": [{
            "name": "quote-offer.pdf",
            "text": "Our standard terms\nPayment terms (days net): 30\nIncoterm: DAP",
        }],
        "term_sheets": [{"term_sheet_id": "offer:A-1", "terms": {"unit_price": 42, "payment_days": 30}}],
    }]

    monkeypatch.delenv("SUPPLIER_ECONOMICS", raising=False)
    off = UnifiedAgent()._standing_offers(case, {"sup:A": events})[0]
    assert off["supplier_economics"] is None
    assert off["evaluation"]["buyer"]["cost_breakdown"]["relationship"] == 0

    monkeypatch.setenv("SUPPLIER_ECONOMICS", "1")
    on = UnifiedAgent()._standing_offers(case, {"sup:A": events})[0]
    assert on["supplier_economics"] == {"interest_rate": 0.08, "full_cost": 50}
    assert on["evaluation"]["buyer"]["cost_breakdown"]["relationship"] > 0


def test_relationship_economics_can_rank_a_healthier_supplier_margin_first():
    case = _case()
    standard = {"payment_days": 30, "incoterm": "DAP"}
    offered = {"unit_price": 40, "payment_days": 30}
    without_economics = generate_packages(
        case, offered, [35, 40], standard, require_beats_alternative=False
    )["packages"]
    with_economics = generate_packages(
        case,
        offered,
        [35, 40],
        standard,
        supplier_economics={"interest_rate": 0.08, "full_cost": 36},
        require_beats_alternative=False,
    )["packages"]

    assert without_economics[0]["terms"]["unit_price"] == 35
    assert with_economics[0]["terms"]["unit_price"] == 40
    assert without_economics[0]["evaluation"]["buyer"]["cost_breakdown"]["relationship"] == 0
    low_price = next(package for package in with_economics if package["terms"]["unit_price"] == 35)
    assert low_price["evaluation"]["buyer"]["cost_breakdown"]["relationship"] > 0
