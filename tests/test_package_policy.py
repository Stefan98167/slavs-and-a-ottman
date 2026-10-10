import json
from pathlib import Path

from arena_kit.agents import PackageAgent
from arena_kit.play import play
from arena_kit.sim import SimTable
from negotiator.package_policy import plan_packages

CASES = Path(__file__).parents[1] / "arena_kit" / "sim_cases"


def load_case(name: str) -> dict:
    return json.loads((CASES / name).read_text())


def test_default_policy_uses_a_bounded_price_ladder_without_inventing_trade_terms():
    plan = plan_packages(load_case("S01.json"), {"unit_price": 20.0})

    assert plan["candidate_unit_prices"] == [19.0, 19.4, 19.8]
    assert plan["term_constraints_by_price"] == {}
    assert plan["profile_used"] == {"cash_sensitive": False, "capacity_sensitive": False, "price_rigid": False}


def test_cash_and_capacity_profile_adds_explicit_reciprocal_terms():
    plan = plan_packages(
        load_case("S03.json"),
        {"unit_price": 300.0},
        {"cash_sensitive": {"state": "likely"}, "capacity_sensitive": {"state": "likely"}},
    )

    for price in plan["candidate_unit_prices"][1:]:
        assert plan["term_constraints_by_price"][price] == {"payment_days": 14, "contract_months": 24}
        assert "earlier payment in return for a less aggressive price" in plan["rationales_by_price"][price]


def test_price_rigid_profile_softens_the_ladder():
    plan = plan_packages(load_case("S01.json"), {"unit_price": 20.0}, {"price_rigid": {"state": "likely"}})

    assert plan["candidate_unit_prices"] == [19.6, 19.8, 20.0]


def test_package_agent_sends_up_to_three_costed_term_sheets_and_can_finish_a_simulated_case():
    agent = PackageAgent()
    result = play(SimTable(), "case:S01", agent)

    assert result["ended"] and result["deal"]
    first = agent.decision_history[0]
    sheets = first["message"]["term_sheets"]
    assert 1 <= len(sheets) <= 3
    assert all(set(sheet["terms"]) == {"unit_price", "payment_days"} for sheet in sheets)
