from test_kit import CASE

from arena_kit.agents import UnifiedAgent


def supplier(status, price, *, body="", payment_days=30):
    return {
        "message_id": f"msg:{price}",
        "from": "sales@example.test",
        "status": status,
        "body": body,
        "term_sheets": [
            {"term_sheet_id": f"offer:{price}", "terms": {"unit_price": price, "payment_days": payment_days}}
        ],
    }


def test_unified_agent_selects_lowest_cost_supplier_and_sends_valid_packages_with_evidence():
    threads = {
        "sup:high": [supplier("open", 44.0)],
        "sup:low": [supplier("open", 42.0, body="S1 rose 5.0 % in twelve months and is 40 % of our cost.")],
    }

    out = UnifiedAgent().decide(CASE, threads)

    assert out["supplier_id"] == "sup:low"
    assert 1 <= len(out["message"]["term_sheets"]) <= 3
    assert all(sheet["terms"]["unit_price"] < 42 for sheet in out["message"]["term_sheets"])
    assert "S1 rose 5.0" in out["message"]["body"]


def test_unified_agent_accepts_a_final_offer_only_when_it_beats_the_alternative():
    case = {**CASE, "buyer": {**CASE["buyer"], "alternative": {"kind": "quote", "terms": {"unit_price": 46}}}}

    out = UnifiedAgent().decide(case, {"sup:A": [supplier("final_offer", 42.0)]})

    assert out["message"]["action"] == {"type": "accept", "term_sheet_id": "offer:42.0"}


def test_unified_agent_walks_away_from_a_final_offer_worse_than_the_alternative():
    case = {**CASE, "buyer": {**CASE["buyer"], "alternative": {"kind": "quote", "terms": {"unit_price": 40}}}}

    out = UnifiedAgent().decide(case, {"sup:A": [supplier("final_offer", 42.0)]})

    assert out["message"]["action"]["type"] == "walk_away"


def test_unified_agent_uses_fallback_cost_when_no_alternative_quote_exists():
    case = {**CASE, "buyer": {**CASE["buyer"], "fallback_unit_price": 40.0}}

    out = UnifiedAgent().decide(case, {"sup:A": [supplier("final_offer", 42.0)]})

    assert out["message"]["action"]["type"] == "walk_away"
