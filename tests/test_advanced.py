from arena_kit.agents import AdvancedAgent

from test_kit import CASE


def supplier(status, price, standard=None):
    return {
        "from": "sales@example.test",
        "status": status,
        "term_sheets": [{"term_sheet_id": "offer:1", "terms": {"unit_price": price}}],
        "attachments": [] if standard is None else [{"name": "quote.pdf", "text": standard}],
    }


def test_advanced_agent_asks_for_a_package_before_accepting():
    agent = AdvancedAgent()
    out = agent.decide(CASE, {"sup:A": [supplier("open", 44.0)]})
    assert out["supplier_id"] == "sup:A"
    assert out["message"]["term_sheets"][0]["terms"]["unit_price"] == 39.6
    assert "breakdown" in out["message"]["body"]


def test_advanced_agent_accepts_a_final_offer_that_beats_the_alternative():
    case = {**CASE, "buyer": {**CASE["buyer"], "alternative": {"kind": "quote", "terms": {"unit_price": 46}}}}
    out = AdvancedAgent().decide(case, {"sup:A": [supplier("final_offer", 42.0)]})
    assert out["message"]["action"]["type"] == "accept"
