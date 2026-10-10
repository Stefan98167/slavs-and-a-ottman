import json
from pathlib import Path

from negotiator.evaluator import evaluate_deal

CASES = Path(__file__).parents[1] / "arena_kit" / "sim_cases"


def load_case(name: str) -> dict:
    return json.loads((CASES / name).read_text())


def test_valid_package_has_buyer_cost_and_breakdown():
    result = evaluate_deal(load_case("S01.json"), {"unit_price": 16.2, "payment_days": 60}, {"payment_days": 30})

    assert result["valid_for_negotiation"]
    assert json.loads(json.dumps(result)) == result
    assert result["buyer"]["total_cost"] > 0
    assert result["buyer"]["cost_breakdown"]["price"] > 0
    assert result["final_terms"] == {"unit_price": 16.2, "payment_days": 60}


def test_must_have_violation_is_not_valid_for_negotiation():
    case = load_case("S01.json")
    case["buyer"]["must_haves"] = [{"field": "payment_days", "op": ">=", "value": 60}]

    result = evaluate_deal(case, {"unit_price": 16.2, "payment_days": 30}, {"payment_days": 30})

    assert not result["buyer"]["must_haves_ok"]
    assert not result["valid_for_negotiation"]


def test_incomplete_supplier_assumptions_do_not_invent_assessment():
    result = evaluate_deal(
        load_case("S01.json"),
        {"unit_price": 16.2, "payment_days": 60},
        {"payment_days": 30},
        {"interest_rate": 0.12},
    )

    assert not result["supplier"]["assessment_available"]
    assert result["supplier"]["value_per_unit"] is None
    assert "full_cost" in result["supplier"]["reason_unavailable"]


def test_complete_supplier_assumptions_produce_value_and_margin():
    result = evaluate_deal(
        load_case("S01.json"),
        {"unit_price": 16.2, "payment_days": 60},
        {"payment_days": 30},
        {"interest_rate": 0.12, "full_cost": 14.1},
    )

    assert result["supplier"]["assessment_available"]
    assert result["supplier"]["value_per_unit"] > 0
    assert isinstance(result["supplier"]["estimated_margin_pct"], float)


def test_available_alternative_is_compared_and_only_warns_when_worse():
    result = evaluate_deal(
        load_case("S03.json"),
        {"unit_price": 300.0, "payment_days": 30, "contract_months": 24, "incoterm": "DAP"},
        {"payment_days": 30},
    )

    assert result["buyer"]["alternative_cost"] is not None
    assert not result["buyer"]["beats_alternative"]
    assert result["valid_for_negotiation"]
    assert any("worse than the available alternative" in warning for warning in result["warnings"])


def test_supplier_standard_outside_options_is_valid_and_is_not_silently_snapped():
    case = load_case("S01.json")
    result = evaluate_deal(case, {"unit_price": 16.2, "payment_days": 21}, {"payment_days": 21})
    assert result["valid_for_negotiation"]
    assert result["final_terms"]["payment_days"] == 21
    omitted = evaluate_deal(case, {"unit_price": 16.2}, {"payment_days": 21})
    assert omitted["final_terms"]["payment_days"] == 21
    invalid = evaluate_deal(case, {"unit_price": 16.2, "payment_days": 22}, {"payment_days": 21})
    assert not invalid["valid_for_negotiation"]
    assert 21 not in case["term_options"]["payment_days"]  # Do not mutate shared cases.


def test_explicit_no_index_clause_is_preserved_when_it_is_an_allowed_option():
    case = load_case("S01.json")
    clause = {"series": "S1", "material_share": 0.5, "deadband_pct": 2, "base_month": "2026-09"}
    case["negotiable"].append("index_clause")
    case["term_options"]["index_clause"] = [clause, None]
    result = evaluate_deal(case, {"unit_price": 16.2, "payment_days": 30, "index_clause": None}, {})
    assert result["valid_for_negotiation"]
    assert result["final_terms"]["index_clause"] is None
