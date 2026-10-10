import json
from pathlib import Path

from test_kit import CASE

from arena_kit.agents import AdvancedAgent, PackageAgent, UnifiedAgent
from arena_kit.cli import agent_factory
from negotiator import SupplierContextAgent


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
    assert {sheet["terms"]["payment_days"] for sheet in out["message"]["term_sheets"]} == {30}
    assert "S1 rose 5.0" in out["message"]["body"]


def test_unified_agent_applies_and_cites_bounded_supplier_cost_claim_on_opening_ask():
    threads = {
        "sup:claim": [supplier(
            "open", 42.0,
            body="LCI-C rose 50 % in twelve months and is 80 % of our cost.",
        )]
    }
    agent = UnifiedAgent()

    out = agent.decide(CASE, threads)

    prices = [sheet["terms"]["unit_price"] for sheet in out["message"]["term_sheets"]]
    assert prices[0] == 40.74  # 5% ask softened by the 2-point cap
    assert agent.decision_history[-1]["supplier_claimed_cost_impact_pct"] == 2.0
    assert "Your email states: LCI-C rose 50 % in twelve months and is 80 % of our cost." in out["message"]["body"]
    assert "capped at 2 percentage points" in out["message"]["body"]


def test_unified_consumes_jonas_profile_from_live_supplier_email():
    case = {**CASE, "refs": ["msg:42.0"]}
    agent = UnifiedAgent()

    out = agent.decide(
        case,
        {"sup:cash": [supplier("open", 42.0, body="We require earlier payment.")]},
    )

    terms = [sheet["terms"] for sheet in out["message"]["term_sheets"]]
    assert out["message"]["refs"] == ["msg:42.0"]
    assert any(term["payment_days"] == 14 for term in terms)
    assert agent.decision_history[-1]["profile_used"]["cash_sensitive"]
    assert agent.decision_history[-1]["trade_hypotheses"][0]["evidence"] == [
        {"id": "msg:42.0", "source": "msg:42.0"}
    ]


def test_unified_agent_ties_profile_trade_to_evidence_and_cites_case_ref(monkeypatch):
    case = {**CASE, "refs": ["doc:cash-priority"]}
    agent = UnifiedAgent()
    monkeypatch.setattr(
        UnifiedAgent,
        "_context",
        staticmethod(lambda events, supplier_id, part_id: {
            "part_id": part_id,
            "evidence": [],
            "supplier_claims": [],
            "supplier_profile": {
                "cash_sensitive": {
                    "state": "likely",
                    "confidence": 0.9,
                    "evidence": [{"id": "doc:cash-priority", "source": "supplier email"}],
                },
                "capacity_sensitive": {"state": "unknown", "confidence": 0.0, "evidence": []},
                "quality_sensitive": {"state": "unknown", "confidence": 0.0, "evidence": []},
                "price_rigid": {"state": "unknown", "confidence": 0.0, "evidence": []},
            },
        }),
    )

    out = agent.decide(case, {"sup:cash": [supplier("open", 42.0, payment_days=30)]})

    sheets = out["message"]["term_sheets"]
    assert sheets[0]["terms"]["payment_days"] == 30
    assert any(sheet["terms"]["payment_days"] == 14 for sheet in sheets)
    assert out["message"]["refs"] == ["doc:cash-priority"]
    assert "cash sensitive package trade" in out["message"]["body"]
    assert "supplier email" in out["message"]["body"]
    assert agent.decision_history[-1]["trade_hypotheses"][0]["profile_dimension"] == "cash_sensitive"


def test_unified_agent_filters_profile_trade_through_must_haves(monkeypatch):
    case = {**CASE, "buyer": {
        **CASE["buyer"],
        "must_haves": [{"field": "payment_days", "op": ">=", "value": 30}],
    }}
    monkeypatch.setattr(
        UnifiedAgent,
        "_context",
        staticmethod(lambda events, supplier_id, part_id: {
            "part_id": part_id,
            "evidence": [],
            "supplier_claims": [],
            "supplier_profile": {
                "cash_sensitive": {
                    "state": "likely", "confidence": 0.9,
                    "evidence": [{"id": "doc:cash", "source": "mail"}]
                }
            },
        }),
    )

    out = UnifiedAgent().decide(case, {"sup:cash": [supplier("open", 42.0, payment_days=30)]})

    assert out["message"].get("term_sheets")
    assert all(sheet["terms"]["payment_days"] >= 30 for sheet in out["message"]["term_sheets"])
    assert "cash sensitive package trade" not in out["message"]["body"]
    assert "earlier payment" not in out["message"]["body"]
    assert "payment in 30 days" in out["message"]["body"]
    assert "Option 1: unit price" in out["message"]["body"]


def test_unified_agent_does_not_send_packages_above_the_fallback_reservation():
    case = {**CASE, "buyer": {**CASE["buyer"], "fallback_unit_price": 39.0}}
    agent = UnifiedAgent()

    out = agent.decide(case, {"sup:A": [supplier("open", 42.0)]})

    assert out["message"]["action"] == {"type": "walk_away"}
    assert agent.decision_history[-1]["reason"] == "no available package beats the reservation cost"
    assert agent.decision_history[-1]["reservation_cost"] < agent.decision_history[-1]["standing_total_cost"]


def test_unified_agent_holds_once_after_supplier_repeats_its_standing_offer():
    agent = UnifiedAgent()
    events = [supplier("open", 42.0)]
    first = agent.decide(CASE, {"sup:A": events})
    events.extend([{**first["message"], "from": "buyer"}, supplier("open", 42.0)])

    hold = agent.decide(CASE, {"sup:A": events})

    assert "term_sheets" not in hold["message"]
    assert "cost breakdown" in hold["message"]["body"]
    assert agent.decision_history[-1]["action"] == "hold"
    assert agent.decision_history[-1]["supplier_status"] == "open"


def test_unified_agent_does_not_repeat_a_refused_cost_breakdown_request():
    agent = UnifiedAgent()
    events = [supplier("open", 42.0)]
    first = agent.decide(CASE, {"sup:A": events})
    events.extend([
        {**first["message"], "from": "buyer"},
        supplier("open", 42.0, body="We do not disclose internal cost breakdowns."),
    ])

    hold = agent.decide(CASE, {"sup:A": events})

    assert agent.decision_history[-1]["action"] == "hold"
    assert "term preventing approval" in hold["message"]["body"]
    assert "cost breakdown" not in hold["message"]["body"]


def test_unified_agent_clarifies_a_standing_sheet_that_supplier_says_is_infeasible():
    case_path = Path(__file__).parents[1] / "arena_kit" / "sim_cases" / "S02.json"
    case = json.loads(case_path.read_text())
    agent = UnifiedAgent()
    opening = supplier(
        "open", 16.0,
        body="A lead time of 35 days is not feasible; 54 days is required.",
    )
    opening["term_sheets"][0]["terms"]["lead_time_days"] = 35
    events = [opening]

    clarification = agent.decide(case, {"sup:A": events})

    assert agent.decision_history[-1]["action"] == "clarify_terms"
    assert "35 days" in clarification["message"]["body"]
    assert "Please reconcile the lead time" in clarification["message"]["body"]
    assert "term_sheets" not in clarification["message"]

    events.extend([{**clarification["message"], "from": "buyer"},
                   supplier("final_offer", 15.8,
                            body="15.80 is our final price.")])
    events[-1]["term_sheets"][0]["terms"]["lead_time_days"] = 35

    result = agent.decide(case, {"sup:A": events})

    assert result["message"]["action"] == {"type": "walk_away"}

    confirmed = supplier("final_offer", 15.8, body="We confirm a lead time of 35 days is feasible.")
    confirmed["term_sheets"][0]["terms"]["lead_time_days"] = 35
    resolved = UnifiedAgent().decide(case, {"sup:A": [*events[:-1], confirmed]})

    assert resolved["message"]["action"] == {"type": "accept", "term_sheet_id": "offer:15.8"}


def test_unified_agent_accepts_an_acceptable_offer_after_no_progress_on_hold():
    agent = UnifiedAgent()
    events = [supplier("open", 42.0)]
    first = agent.decide(CASE, {"sup:A": events})
    events.extend([{**first["message"], "from": "buyer"}, supplier("open", 42.0)])
    hold = agent.decide(CASE, {"sup:A": events})
    events.extend([{**hold["message"], "from": "buyer"}, supplier("open", 42.0)])

    out = agent.decide(CASE, {"sup:A": events})

    assert out["message"]["action"] == {"type": "accept", "term_sheet_id": "offer:42.0"}
    assert agent.decision_history[-1]["action"] == "accept"


def test_unified_agent_repackages_only_after_supplier_improves_and_claim_is_opening_only():
    agent = UnifiedAgent()
    events = [supplier("open", 42.0, body="LCI-C rose 50 % in twelve months and is 80 % of our cost.")]
    first = agent.decide(CASE, {"sup:A": events})
    assert first["message"]["term_sheets"][0]["terms"]["unit_price"] == 40.74
    events.extend([{**first["message"], "from": "buyer"}, supplier("open", 41.0)])

    second = agent.decide(CASE, {"sup:A": events})

    assert second["message"]["term_sheets"][0]["terms"]["unit_price"] == 38.95
    assert agent.decision_history[-1]["action"] == "counter_packages"
    assert agent.decision_history[-1]["supplier_claimed_cost_impact_pct"] == 0.0
    assert agent.decision_history[-1]["remaining_moves"] == CASE["round_limit"] - 1


def test_unified_agent_uses_its_last_buyer_message_then_accepts_a_valid_supplier_final():
    case = {**CASE, "round_limit": 1, "buyer": {**CASE["buyer"], "fallback_unit_price": 42.0}}
    agent = UnifiedAgent()
    events = [supplier("open", 42.0)]

    counter = agent.decide(case, {"sup:A": events})
    assert counter["message"].get("term_sheets")
    assert agent.decision_history[-1]["remaining_moves"] == 1
    events.extend([
        {**counter["message"], "from": "buyer"},
        supplier("final_offer", 41.4),
    ])

    out = agent.decide(case, {"sup:A": events})

    assert out["message"]["action"] == {"type": "accept", "term_sheet_id": "offer:41.4"}
    assert agent.decision_history[-1]["remaining_moves"] == 0


def test_unified_agent_prices_omitted_supplier_terms_at_pdf_standard_before_reservation_check():
    case_path = Path(__file__).parents[1] / "arena_kit" / "sim_cases" / "S03.json"
    case = json.loads(case_path.read_text())
    opening = supplier("open", 239.55)
    opening["term_sheets"][0]["terms"] = {"unit_price": 239.55}
    opening["missing_fields"] = ["payment_days", "contract_months", "incoterm"]
    opening["attachments"] = [{
        "name": "quote.pdf",
        "text": (
            "Our standard terms\n"
            "Payment terms (days net): 14\n"
            "Contract term (months): 12\n"
            "Incoterm: EXW\n"
            "Lead time (days): 35\n"
            "Volume per year (pcs): 8490\n"
            "Tooling (EUR): 0\n"
        ),
    }]
    agent = UnifiedAgent()

    out = agent.decide(case, {"sup:70520": [opening]})

    assert out["message"]["action"] == {"type": "walk_away"}
    assert agent.decision_history[-1]["standing_total_cost"] > agent.decision_history[-1]["reservation_cost"]


def test_cli_factory_keeps_comparison_agents_and_unified_selectable():
    expected = {
        "supplier": SupplierContextAgent,
        "packages": PackageAgent,
        "advanced": AdvancedAgent,
        "unified": UnifiedAgent,
    }

    for name, agent_type in expected.items():
        assert isinstance(agent_factory(name, None)(), agent_type)


def test_unified_agent_accepts_a_final_offer_only_when_it_beats_the_alternative():
    case = {**CASE, "buyer": {**CASE["buyer"], "alternative": {"kind": "quote", "terms": {"unit_price": 46}}}}

    out = UnifiedAgent().decide(case, {"sup:A": [supplier("final_offer", 42.0)]})

    assert out["message"]["action"] == {"type": "accept", "term_sheet_id": "offer:42.0"}


def test_unified_agent_chooses_cheapest_standing_supplier_when_another_goes_final():
    out = UnifiedAgent().decide(CASE, {
        "sup:expensive": [supplier("final_offer", 42.0)],
        "sup:cheap": [supplier("open", 41.0)],
    })

    assert out["supplier_id"] == "sup:cheap"
    assert out["message"]["action"] == {"type": "accept", "term_sheet_id": "offer:41.0"}


def test_unified_agent_rejects_a_cheaper_final_offer_that_breaks_a_delivery_must_have():
    case_path = Path(__file__).parents[1] / "arena_kit" / "sim_cases" / "S02.json"
    case = json.loads(case_path.read_text())
    case["buyer"]["must_haves"] = [{"field": "lead_time_days", "op": "<=", "value": 35}]
    final = supplier("final_offer", 15.0)
    final["term_sheets"][0]["terms"]["lead_time_days"] = 49

    out = UnifiedAgent().decide(case, {"sup:A": [final]})

    assert out["message"]["action"] == {"type": "walk_away"}


def test_unified_agent_walks_away_from_a_final_offer_worse_than_the_alternative():
    case = {**CASE, "buyer": {**CASE["buyer"], "alternative": {"kind": "quote", "terms": {"unit_price": 40}}}}

    out = UnifiedAgent().decide(case, {"sup:A": [supplier("final_offer", 42.0)]})

    assert out["message"]["action"]["type"] == "walk_away"


def test_unified_agent_uses_fallback_cost_when_no_alternative_quote_exists():
    case = {**CASE, "buyer": {**CASE["buyer"], "fallback_unit_price": 40.0}}

    out = UnifiedAgent().decide(case, {"sup:A": [supplier("final_offer", 42.0)]})

    assert out["message"]["action"]["type"] == "walk_away"
