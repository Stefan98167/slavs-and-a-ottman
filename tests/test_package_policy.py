import json
from pathlib import Path

from arena_kit.agents import PackageAgent
from arena_kit.play import play
from arena_kit.sim import SimTable
from negotiator.intelligence import build_supplier_context, load_evidence
from negotiator.package_policy import CLAIM_ADJUSTMENT_CAP_PCT, plan_packages, recheck_buyer_terms
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


def test_unknown_profile_preserves_an_explicit_supplier_standard_outside_options():
    case = load_case("S01.json")
    offer = {"unit_price": 20.0, "payment_days": 21}
    standard = {"payment_days": 21}
    plan = plan_packages(case, offer, supplier_standard_terms=standard)
    result = generate_packages(case, offer, plan["candidate_unit_prices"], standard,
                               term_constraints_by_price=plan["term_constraints_by_price"])
    assert {item["terms"]["payment_days"] for item in result["packages"]} == {21}


def test_unknown_profile_repairs_buyer_coverage_without_claiming_supplier_motivation():
    case = load_case("S03.json")
    offer = {"unit_price": 239.55, "payment_days": 30, "contract_months": 12, "incoterm": "DAP"}

    plan = plan_packages(case, offer)

    assert all(terms["contract_months"] == 24 for terms in plan["term_constraints_by_price"].values())
    assert not any(plan["profile_used"].values())
    assert plan["trade_hypotheses"] == []
    assert "contract months covers more of the buyer's stated need" in plan["buyer_term_reasons"]


def test_unknown_profile_does_not_extend_coverage_when_it_would_raise_buyer_cost():
    case = load_case("S03.json")
    case["buyer"]["fallback_unit_price"] = 100.0
    offer = {"unit_price": 239.55, "payment_days": 30, "contract_months": 12, "incoterm": "DAP"}

    plan = plan_packages(case, offer)

    assert all(terms["contract_months"] == 12 for terms in plan["term_constraints_by_price"].values())
    assert plan["buyer_term_reasons"] == []


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
    assert plan["term_constraints_by_price"][19.0] == {"payment_days": 14}
    assert plan["term_constraints_by_price"][19.4] == {"payment_days": 30}
    assert plan["term_constraints_by_price"][19.8] == {"payment_days": 30}
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
    assert plan["term_constraints_by_price"][plan["candidate_unit_prices"][0]]["payment_days"] == 14


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

    for price in plan["candidate_unit_prices"][:1]:
        assert plan["term_constraints_by_price"][price] == {
            "payment_days": 14, "contract_months": 24, "incoterm": "EXW"
        }
        assert "earlier payment in return for the lower package price" in plan["rationales_by_price"][price]
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


def test_quality_trade_uses_a_stated_guarantee_without_inventing_a_better_one():
    case = load_case("S01.json")
    case["negotiable"].append("ppm_commitment")
    case["term_options"]["ppm_commitment"] = [100, 600, 1200]
    profile = build_supplier_context(load_evidence([{
        "Information": {"supplier_id": "sup:1", "notes": "We guarantee a defect rate below 500 ppm."},
        "Source": "supplier email",
    }]), "sup:1")["supplier_profile"]
    offer = {"unit_price": 20.0, "payment_days": 30, "ppm_commitment": 1200}
    plan = plan_packages(case, offer, profile)
    assert plan["term_constraints_by_price"][19.0]["ppm_commitment"] == 1200
    assert plan["term_constraints_by_price"][19.4]["ppm_commitment"] == 600
    assert plan["trade_hypotheses"][0]["supplier_gives"] == {"ppm_commitment": 600}
    assert plan["unmapped_profile_dimensions"] == []
    del profile["quality_sensitive"]["supported_terms"]
    unknown_value = plan_packages(case, offer, profile)
    assert unknown_value["trade_hypotheses"] == []
    assert all(t["ppm_commitment"] == 1200 for t in unknown_value["term_constraints_by_price"].values())


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


def test_coverage_is_costed_at_each_actual_candidate_price_and_rechecked_after_concession():
    from copy import deepcopy

    from test_kit import CASE

    case = deepcopy(CASE)
    case["negotiable"].append("contract_months")
    del case["fixed_terms"]["contract_months"]
    case["term_options"]["contract_months"] = [12, 24, 36]
    case["buyer"].update(fallback_unit_price=96, reference_payment_days=30)
    offer = {"unit_price": 100, "payment_days": 30, "contract_months": 12}
    plan = plan_packages(case, offer)
    assert plan["term_constraints_by_price"][95]["contract_months"] == 24
    assert plan["term_constraints_by_price"][97]["contract_months"] == 12
    plan["term_constraints_by_price"] = {98: plan["term_constraints_by_price"][95]}
    recheck_buyer_terms(case, plan, offer, {})
    assert plan["term_constraints_by_price"][98]["contract_months"] == 12


def test_earlier_payment_buys_a_lower_price_than_the_baseline_option():
    case = load_case("S01.json")
    profile = {"cash_sensitive": {"state": "likely", "confidence": 0.8,
                                  "evidence": [{"id": "doc:x", "source": "email"}]}}
    plan = plan_packages(case, {"unit_price": 20, "payment_days": 30}, profile)
    early = [p for p, terms in plan["term_constraints_by_price"].items() if terms["payment_days"] == 14]
    ordinary = [p for p, terms in plan["term_constraints_by_price"].items() if terms["payment_days"] == 30]
    assert early and ordinary and max(early) < min(ordinary)
