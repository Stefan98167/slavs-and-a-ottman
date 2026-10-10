import json
from pathlib import Path

from arena_kit.agents import PackageAgent
from arena_kit.play import play
from arena_kit.sim import SimTable
from negotiator.intelligence import build_supplier_context, load_evidence
from negotiator.package_policy import CLAIM_ADJUSTMENT_CAP_PCT, plan_packages
from negotiator.packages import generate_packages

CASES = Path(__file__).parents[1] / "arena_kit" / "sim_cases"


def load_case(name: str) -> dict:
    return json.loads((CASES / name).read_text())


def test_unknown_profile_uses_a_bounded_price_only_ladder():
    case = load_case("S01.json")
    offer = {"unit_price": 20.0, "payment_days": 30}
    plan = plan_packages(case, offer)

    assert plan["candidate_unit_prices"] == [19.0, 19.4, 19.8]
    assert plan["term_constraints_by_price"] == {
        19.0: {"payment_days": 30},
        19.4: {"payment_days": 30},
        19.8: {"payment_days": 30},
    }
    assert plan["profile_used"] == {
        "cash_sensitive": False, "capacity_sensitive": False, "quality_sensitive": False, "price_rigid": False
    }

    packages = generate_packages(
        case, offer, plan["candidate_unit_prices"], term_constraints_by_price=plan["term_constraints_by_price"]
    )
    assert {package["terms"]["payment_days"] for package in packages["packages"]} == {30}


def test_profile_contract_uses_only_explicit_likely_state_and_never_reads_evidence():
    case = load_case("S01.json")
    offer = {"unit_price": 20.0, "payment_days": 30}
    profile = {
        # State is trusted; the policy validates provenance links but does not
        # reinterpret their evidence content.
        "cash_sensitive": {
            "state": "likely", "confidence": 0.9,
            "evidence": [{"id": "doc:cash", "source": "supplier email"}],
        },
        "capacity_sensitive": {
            "state": "unknown", "confidence": 0.0, "evidence": [{"claim": "ignored"}]
        },
        "quality_sensitive": {
            "state": "likely", "confidence": 0.7,
            "evidence": [{"id": "sc:quality", "source": "scorecard"}],
        },
        # Legacy/free-form values are not Jonas's contract and are unknown.
        "price_rigid": True,
    }

    plan = plan_packages(case, offer, profile)

    assert plan["profile_used"] == {
        "cash_sensitive": True, "capacity_sensitive": False, "quality_sensitive": True, "price_rigid": False
    }
    assert plan["candidate_unit_prices"] == [19.0, 19.4, 19.8]
    assert plan["term_constraints_by_price"][19.0] == {"payment_days": 30}
    assert plan["term_constraints_by_price"][19.4] == {"payment_days": 14}
    assert plan["term_constraints_by_price"][19.8] == {"payment_days": 14}
    assert [item["profile_dimension"] for item in plan["trade_hypotheses"]] == ["cash_sensitive"]
    assert plan["unmapped_profile_dimensions"] == ["quality_sensitive"]


def test_jonas_profile_output_drives_a_cited_package_trade():
    case = load_case("S01.json")
    profile = build_supplier_context(
        load_evidence([{
            "Information": {"supplier_id": "sup:1", "notes": "We require earlier payment."},
            "Source": "supplier.csv:2",
        }]),
        "sup:1",
    )["supplier_profile"]

    plan = plan_packages(case, {"unit_price": 20.0, "payment_days": 30}, profile)

    assert plan["profile_used"]["cash_sensitive"]
    assert plan["profile_evidence"]["cash_sensitive"] == [
        {"id": "supplier.csv:2", "source": "supplier.csv:2"}
    ]
    assert plan["term_constraints_by_price"][plan["candidate_unit_prices"][1]]["payment_days"] == 14


def test_malformed_likely_profile_contract_stays_conservative():
    case = load_case("S01.json")
    offer = {"unit_price": 20.0, "payment_days": 30}
    profiles = [
        {"cash_sensitive": {"state": "likely", "evidence": [{"id": "doc:x", "source": "mail"}]}},
        {"cash_sensitive": {
            "state": "likely", "confidence": 0.9, "evidence": [{"id": "doc:x"}]
        }},
        {"cash_sensitive": {
            "state": "likely", "confidence": 1.1, "evidence": [{"id": "doc:x", "source": "mail"}]
        }},
    ]

    for profile in profiles:
        plan = plan_packages(case, offer, profile)
        assert not plan["profile_used"]["cash_sensitive"]
        assert all(terms == {"payment_days": 30} for terms in plan["term_constraints_by_price"].values())


def test_cash_and_capacity_profile_adds_explicit_reciprocal_terms():
    case = load_case("S03.json")
    plan = plan_packages(
        case,
        {"unit_price": 300.0, "contract_months": 12},
        {
            "cash_sensitive": {
                "state": "likely", "confidence": 0.9, "evidence": [{"id": "doc:cash", "source": "mail"}]
            },
            "capacity_sensitive": {
                "state": "likely", "confidence": 0.8,
                "evidence": [{"id": "sc:capacity", "source": "scorecard"}],
            },
        },
    )

    for price in plan["candidate_unit_prices"][1:]:
        assert plan["term_constraints_by_price"][price] == {
            "payment_days": 14, "contract_months": 24, "incoterm": "EXW"
        }
        assert "earlier payment in return for a less aggressive price" in plan["rationales_by_price"][price]
    assert {item["profile_dimension"] for item in plan["trade_hypotheses"]} == {
        "cash_sensitive", "capacity_sensitive"
    }


def test_capacity_trade_never_commits_beyond_buyer_need_or_horizon():
    case = load_case("S03.json")
    case["buyer"]["horizon_years"] = 1
    case["term_options"]["volume_per_year"] = [8490, 10000]
    case["negotiable"].append("volume_per_year")
    profile = {
        "capacity_sensitive": {
            "state": "likely", "confidence": 0.9,
            "evidence": [{"id": "doc:capacity", "source": "schedule"}]
        }
    }

    plan = plan_packages(case, {"unit_price": 300.0, "contract_months": 12, "volume_per_year": 8000}, profile)

    for price in plan["candidate_unit_prices"][1:]:
        assert plan["term_constraints_by_price"][price]["contract_months"] == 12
        assert plan["term_constraints_by_price"][price]["volume_per_year"] == 8490


def test_price_rigid_profile_softens_the_ladder():
    plan = plan_packages(
        load_case("S01.json"), {"unit_price": 20.0},
        {"price_rigid": {
            "state": "likely", "confidence": 0.8,
            "evidence": [{"id": "doc:price", "source": "email"}],
        }},
    )

    assert plan["candidate_unit_prices"] == [19.6, 19.8, 20.0]


def test_claim_cost_impact_changes_only_the_discount_and_is_capped_at_two_points():
    case = load_case("S01.json")
    offer = {"unit_price": 100.0, "payment_days": 30}

    softened = plan_packages(case, offer, claimed_cost_impact_pct=50)
    strengthened = plan_packages(case, offer, claimed_cost_impact_pct=-50)

    assert CLAIM_ADJUSTMENT_CAP_PCT == 2.0
    assert softened["claim_adjustment_pct"] == 2.0
    assert softened["candidate_unit_prices"] == [97.0, 98.2, 99.4]
    assert strengthened["claim_adjustment_pct"] == -2.0
    assert strengthened["candidate_unit_prices"] == [93.0, 95.8, 98.6]
    assert all(terms == {"payment_days": 30} for terms in softened["term_constraints_by_price"].values())


def test_package_agent_sends_up_to_three_costed_term_sheets_and_can_finish_a_simulated_case():
    agent = PackageAgent()
    result = play(SimTable(), "case:S01", agent)

    assert result["ended"] and result["deal"]
    first = agent.decision_history[0]
    sheets = first["message"]["term_sheets"]
    assert 1 <= len(sheets) <= 3
    assert all(set(sheet["terms"]) == {"unit_price", "payment_days"} for sheet in sheets)
