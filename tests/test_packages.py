import json
from pathlib import Path

import pytest

from negotiator.packages import PackageInputError, generate_packages

CASES = Path(__file__).parents[1] / "arena_kit" / "sim_cases"


def load_case(name: str) -> dict:
    return json.loads((CASES / name).read_text())


def test_packages_are_valid_distinct_and_price_diverse():
    result = generate_packages(
        load_case("S02.json"),
        {"unit_price": 20.0, "payment_days": 30, "lead_time_days": 35},
        [18.0, 19.0, 20.0],
        {"payment_days": 30, "lead_time_days": 35},
    )

    assert result["generated_candidates"] == 75
    assert result["valid_candidates"] == 75
    assert [package["terms"]["unit_price"] for package in result["packages"]] == [18.0, 19.0, 20.0]
    assert [package["rank"] for package in result["packages"]] == [1, 2, 3]
    assert all(package["evaluation"]["valid_for_negotiation"] for package in result["packages"])
    expected_fields = {"unit_price", "payment_days", "lead_time_days"}
    assert all(set(package["terms"]) == expected_fields for package in result["packages"])
    assert json.loads(json.dumps(result)) == result


def test_must_haves_filter_generated_packages_before_selection():
    case = load_case("S01.json")
    case["buyer"]["must_haves"] = [{"field": "payment_days", "op": ">=", "value": 60}]

    result = generate_packages(case, {"unit_price": 20.0}, [18.0, 19.0], {"payment_days": 30})

    assert result["generated_candidates"] == 10
    assert result["valid_candidates"] == 4
    assert all(package["terms"]["payment_days"] in {60, 90} for package in result["packages"])


def test_packages_that_do_not_beat_an_available_alternative_are_excluded_by_default():
    case = load_case("S01.json")
    case["buyer"]["alternative"] = {
        "kind": "quote",
        "terms": {"unit_price": 1.0, "payment_days": 90},
    }

    result = generate_packages(case, {"unit_price": 20.0}, [18.0, 19.0], {"payment_days": 30})

    assert result["packages"] == []
    assert result["valid_candidates"] == 0
    assert result["excluded_worse_than_alternative"] == 10


def test_generator_can_keep_valid_packages_above_the_alternative_for_exploration():
    case = load_case("S01.json")
    case["buyer"]["alternative"] = {
        "kind": "quote",
        "terms": {"unit_price": 1.0, "payment_days": 90},
    }

    result = generate_packages(
        case,
        {"unit_price": 20.0},
        [18.0],
        {"payment_days": 30},
        require_beats_alternative=False,
    )

    assert len(result["packages"]) == 3
    assert all(not package["evaluation"]["buyer"]["beats_alternative"] for package in result["packages"])


@pytest.mark.parametrize(
    ("prices", "max_packages", "message"),
    [([], 3, "must not be empty"), ([0], 3, "finite positive"), ([18], 4, "from 1 to 3")],
)
def test_generator_rejects_ambiguous_or_invalid_policy_inputs(prices, max_packages, message):
    with pytest.raises(PackageInputError, match=message):
        generate_packages(load_case("S01.json"), {}, prices, max_packages=max_packages)


def test_supplier_economics_is_evaluated_without_being_invented():
    case = load_case("S01.json")
    economics = {"interest_rate": 0.12, "full_cost": 14.1}

    result = generate_packages(
        case,
        {"unit_price": 20.0},
        [18.0],
        {"payment_days": 30},
        supplier_economics=economics,
    )

    assert all(package["evaluation"]["supplier"]["assessment_available"] for package in result["packages"])
    assert economics == {"interest_rate": 0.12, "full_cost": 14.1}


def test_price_specific_term_constraints_create_a_real_reciprocal_package():
    result = generate_packages(
        load_case("S01.json"),
        {"unit_price": 20.0},
        [19.0, 19.8],
        {"payment_days": 30},
        term_constraints_by_price={19.8: {"payment_days": 14}},
    )

    constrained = next(package for package in result["packages"] if package["terms"]["unit_price"] == 19.8)
    assert constrained["terms"]["payment_days"] == 14


def test_term_constraints_reject_unknown_prices_and_invalid_options():
    with pytest.raises(PackageInputError, match="not in candidate_unit_prices"):
        generate_packages(load_case("S01.json"), {}, [18.0], term_constraints_by_price={19.0: {}})
    with pytest.raises(PackageInputError, match="not an allowed case option"):
        generate_packages(
            load_case("S01.json"), {}, [18.0], term_constraints_by_price={18.0: {"payment_days": 17}}
        )
