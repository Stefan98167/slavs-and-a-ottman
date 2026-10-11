import json
from pathlib import Path

import pytest
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
    agent = UnifiedAgent(claim_adjustment_cap_pct=2)

    out = agent.decide(CASE, threads)

    prices = [sheet["terms"]["unit_price"] for sheet in out["message"]["term_sheets"]]
    assert prices[0] == 36.54  # 15% standard ask softened by the 2-point cap
    assert agent.decision_history[-1]["supplier_claimed_cost_impact_pct"] == 2.0
    assert "Your email states: LCI-C rose 50 % in twelve months and is 80 % of our cost." in out["message"]["body"]
    assert agent.decision_history[-1]["claim_adjustment_cap_pct"] == 2.0
    assert "percentage points" not in out["message"]["body"]


def test_bolder_opening_flag_asks_for_larger_but_reservation_safe_discount(monkeypatch):
    monkeypatch.setenv("UNIFIED_BOLDER_OPENING", "1")
    monkeypatch.delenv("UNIFIED_OPENING_DISCOUNT_PCT", raising=False)
    agent = UnifiedAgent()

    out = agent.decide(CASE, {"sup:test": [supplier("open", 42.0)]})

    terms = out["message"]["term_sheets"][0]["terms"]
    assert terms["unit_price"] == 33.6  # The optional 20% ask vs. the standard 15% ask.
    assert set(terms) == set(CASE["negotiable"])
    assert agent.decision_history[-1]["bolder_opening_enabled"] is True
    assert agent.decision_history[-1]["effective_max_discount_pct"] == 20.0
    assert agent.decision_history[-1]["best_package_total_cost"] <= agent.decision_history[-1]["reservation_cost"]


def test_bolder_opening_flag_is_off_by_default(monkeypatch):
    monkeypatch.delenv("UNIFIED_BOLDER_OPENING", raising=False)
    monkeypatch.delenv("UNIFIED_OPENING_DISCOUNT_PCT", raising=False)
    monkeypatch.delenv("UNIFIED_ADAPTIVE_OPENING", raising=False)
    monkeypatch.delenv("UNIFIED_ADAPTIVE_OPENING_V2", raising=False)

    agent = UnifiedAgent()
    out = agent.decide(CASE, {"sup:test": [supplier("open", 42.0)]})

    assert out["message"]["term_sheets"][0]["terms"]["unit_price"] == 35.7
    assert agent.decision_history[-1]["bolder_opening_enabled"] is False
    assert agent.adaptive_opening_enabled is False
    assert agent.decision_history[-1]["effective_max_discount_pct"] == 15.0


def test_opening_discount_override_sets_exact_fifteen_percent(monkeypatch):
    for name in ("UNIFIED_BOLDER_OPENING", "UNIFIED_ADAPTIVE_OPENING", "UNIFIED_ADAPTIVE_OPENING_V2"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("UNIFIED_OPENING_DISCOUNT_PCT", "15")

    agent = UnifiedAgent()
    out = agent.decide(CASE, {"sup:test": [supplier("open", 42.0)]})

    assert out["message"]["term_sheets"][0]["terms"]["unit_price"] == 35.7
    assert agent.decision_history[-1]["effective_max_discount_pct"] == 15.0
    assert agent.opening_discount_override_enabled


def test_adaptive_opening_classifies_observed_supplier_behavior(monkeypatch):
    monkeypatch.delenv("UNIFIED_BOLDER_OPENING", raising=False)
    monkeypatch.delenv("UNIFIED_OPENING_DISCOUNT_PCT", raising=False)
    monkeypatch.delenv("UNIFIED_ADAPTIVE_OPENING_V2", raising=False)
    monkeypatch.setenv("UNIFIED_ADAPTIVE_OPENING", "1")
    agent = UnifiedAgent()

    opening = {**supplier("open", 60.0), "from": "sup:test"}
    buyer_move = {"from": "buyer", "term_sheets": [{"terms": {"unit_price": 51.0}}]}
    conceded = {**supplier("open", 59.0), "from": "sup:test"}
    held = {**supplier("open", 60.0), "from": "sup:test"}

    assert agent._opening_discount_for_events([opening]) == (
        15.0,
        {"response": "initial_or_unobserved", "supplier_price_move_pct": None,
         "reciprocal_concession_share": 0.5},
    )
    discount, response = agent._opening_discount_for_events([opening, buyer_move, conceded])
    assert discount == 8.0
    assert response["response"] == "supplier_conceded_price"
    assert response["supplier_price_move_pct"] == pytest.approx(-1.67)
    assert response["reciprocal_concession_share"] == 0.8

    discount, response = agent._opening_discount_for_events([opening, buyer_move, held])
    assert discount == 20.0
    assert response["response"] == "supplier_held_or_raised_price"
    assert response["reciprocal_concession_share"] == 0.0


def test_adaptive_opening_applies_reciprocal_share_to_counter(monkeypatch):
    monkeypatch.delenv("UNIFIED_BOLDER_OPENING", raising=False)
    monkeypatch.delenv("UNIFIED_OPENING_DISCOUNT_PCT", raising=False)
    monkeypatch.delenv("UNIFIED_ADAPTIVE_OPENING_V2", raising=False)
    monkeypatch.setenv("UNIFIED_ADAPTIVE_OPENING", "1")
    agent = UnifiedAgent()
    first = {"sup:test": [supplier("open", 42.0)]}

    initial = agent.decide(CASE, first)
    first["sup:test"].extend([
        {"from": "buyer", "status": "open", "term_sheets": initial["message"]["term_sheets"]},
        supplier("open", 41.0),
    ])
    counter = agent.decide(CASE, first)

    assert counter["message"]["term_sheets"]
    assert agent.decision_history[-1]["adaptive_supplier_response"]["response"] == "supplier_conceded_price"
    assert agent.decision_history[-1]["effective_max_discount_pct"] == 8.0
    previous_ask = initial["message"]["term_sheets"][0]["terms"]["unit_price"]
    adaptive_ask = counter["message"]["term_sheets"][0]["terms"]["unit_price"]
    assert previous_ask < adaptive_ask < 41.0


def test_bolder_and_adaptive_openings_cannot_be_enabled_together(monkeypatch):
    monkeypatch.setenv("UNIFIED_BOLDER_OPENING", "1")
    monkeypatch.setenv("UNIFIED_ADAPTIVE_OPENING", "1")
    monkeypatch.delenv("UNIFIED_ADAPTIVE_OPENING_V2", raising=False)
    monkeypatch.delenv("UNIFIED_OPENING_DISCOUNT_PCT", raising=False)

    with pytest.raises(ValueError, match="mutually exclusive"):
        UnifiedAgent()


def test_second_adaptive_strategy_scales_giveback_to_supplier_concession(monkeypatch):
    for name in ("UNIFIED_BOLDER_OPENING", "UNIFIED_ADAPTIVE_OPENING", "UNIFIED_OPENING_DISCOUNT_PCT"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("UNIFIED_ADAPTIVE_OPENING_V2", "1")
    agent = UnifiedAgent()
    opening = {**supplier("open", 42.0), "from": "sup:test"}
    buyer_move = {"from": "buyer", "term_sheets": [{"terms": {"unit_price": 35.7}}]}

    discount, response = agent._opening_discount_for_events(
        [opening, buyer_move, {**supplier("open", 41.5), "from": "sup:test"}]
    )
    assert discount == 15.0
    assert response["response"] == "supplier_conceded_modestly"
    assert response["reciprocal_concession_share"] == 0.5

    discount, response = agent._opening_discount_for_events(
        [opening, buyer_move, {**supplier("open", 41.0), "from": "sup:test"}]
    )
    assert discount == 15.0
    assert response["response"] == "supplier_conceded_strongly"
    assert response["reciprocal_concession_share"] == 0.25

    discount, response = agent._opening_discount_for_events(
        [opening, buyer_move, {**supplier("open", 42.0), "from": "sup:test"}]
    )
    assert discount == 20.0
    assert response["response"] == "supplier_held_or_raised_price"
    assert response["reciprocal_concession_share"] == 0.0


def test_second_adaptive_strategy_propagates_to_live_counteroffer(monkeypatch):
    for name in ("UNIFIED_BOLDER_OPENING", "UNIFIED_ADAPTIVE_OPENING", "UNIFIED_OPENING_DISCOUNT_PCT"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("UNIFIED_ADAPTIVE_OPENING_V2", "1")
    agent = UnifiedAgent()
    threads = {"sup:test": [supplier("open", 42.0)]}

    first = agent.decide(CASE, threads)
    threads["sup:test"].extend([
        {"from": "buyer", "status": "open", "term_sheets": first["message"]["term_sheets"]},
        supplier("open", 41.0),
    ])
    counter = agent.decide(CASE, threads)

    assert counter["message"]["term_sheets"]
    assert agent.decision_history[-1]["adaptive_opening_v2_enabled"] is True
    assert agent.decision_history[-1]["adaptive_supplier_response"]["response"] == "supplier_conceded_strongly"
    previous_ask = first["message"]["term_sheets"][0]["terms"]["unit_price"]
    next_ask = counter["message"]["term_sheets"][0]["terms"]["unit_price"]
    assert previous_ask < next_ask < 41.0


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
    assert len(sheets) == 1  # Other evaluated choices remain private, not a menu.
    assert any(sheet["terms"]["payment_days"] == 14 for sheet in sheets)
    assert out["message"]["refs"] == ["doc:cash-priority"]
    assert "earlier payment in exchange for the listed price" in out["message"]["body"]
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
    case = {**CASE, "buyer": {**CASE["buyer"], "fallback_unit_price": 33.0}}
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
    assert "cost breakdown" in first["message"]["body"]
    assert "cost breakdown" not in hold["message"]["body"]  # Already requested; do not nag.
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
    agent = UnifiedAgent(max_discount_pct=5.0, claim_adjustment_cap_pct=2)
    events = [supplier("open", 42.0, body="LCI-C rose 50 % in twelve months and is 80 % of our cost.")]
    first = agent.decide(CASE, {"sup:A": events})
    assert first["message"]["term_sheets"][0]["terms"]["unit_price"] == 40.74
    events.extend([{**first["message"], "from": "buyer"}, supplier("open", 41.5)])

    second = agent.decide(CASE, {"sup:A": events})

    assert second["message"]["term_sheets"][0]["terms"]["unit_price"] == 40.99
    assert all(
        current["terms"]["unit_price"] >= prior["terms"]["unit_price"]
        for prior, current in zip(
            first["message"]["term_sheets"], second["message"]["term_sheets"], strict=False
        )
    )
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

    assert out["message"]["term_sheets"]
    assert all(sheet["terms"]["contract_months"] == 24 for sheet in out["message"]["term_sheets"])
    assert agent.decision_history[-1]["standing_total_cost"] > agent.decision_history[-1]["reservation_cost"]
    assert agent.decision_history[-1]["best_package_total_cost"] <= agent.decision_history[-1]["reservation_cost"]


def test_unified_repairs_buyer_must_have_before_generating_p10_style_packages():
    case = {
        **CASE,
        "negotiable": ["unit_price", "volume_per_year", "contract_months", "lead_time_days"],
        "fixed_terms": {"incoterm": "DAP", "payment_days": 30},
        "term_options": {
            "volume_per_year": [3000, 4000],
            "contract_months": [12, 24],
            "lead_time_days": [35, 42, 56],
        },
        "buyer": {
            **CASE["buyer"],
            "need_lead_time_days": 42,
            "must_haves": [{"field": "volume_per_year", "op": ">=", "value": 3800}],
        },
    }
    opening = supplier("open", 42.0)
    opening["term_sheets"][0]["terms"] = {
        "unit_price": 42.0, "volume_per_year": 3000,
        "contract_months": 12, "lead_time_days": 54,
    }
    agent = UnifiedAgent()

    out = agent.decide(case, {"sup:A": [opening]})

    sheets = out["message"]["term_sheets"]
    assert len(sheets) == 1  # Identical terms at a higher price are redundant options.
    assert all(sheet["terms"]["volume_per_year"] == 4000 for sheet in sheets)
    assert all(sheet["terms"]["contract_months"] == 24 for sheet in sheets)
    assert all(sheet["terms"]["lead_time_days"] == 56 for sheet in sheets)
    assert not any(agent.decision_history[-1]["profile_used"].values())


def test_unified_uses_explicit_duration_invitation_after_a_rejected_price_only_ask():
    case = json.loads((Path(__file__).parents[1] / "arena_kit" / "sim_cases" / "S03.json").read_text())
    opening = supplier("open", 239.55)
    terms = {"unit_price": 239.55, "payment_days": 30, "contract_months": 12, "incoterm": "DAP"}
    opening["term_sheets"][0]["terms"] = terms
    previous = {"from": "buyer", "term_sheets": [{"terms": {**terms, "unit_price": 230.0}}]}
    response = supplier(
        "open", 239.55,
        body="If you can adjust the contract duration, we can evaluate a revised package.",
    )
    response["term_sheets"][0]["terms"] = terms
    agent = UnifiedAgent()

    out = agent.decide(case, {"sup:70520": [opening, previous, response]})

    assert agent.decision_history[-1]["action"] == "counter_packages"
    assert all(sheet["terms"]["contract_months"] == 24 for sheet in out["message"]["term_sheets"])
    assert all(sheet["terms"]["unit_price"] >= 230.0 for sheet in out["message"]["term_sheets"])


def test_unified_asks_for_a_concrete_trade_once_before_rejecting_an_unchanged_offer():
    case = json.loads((Path(__file__).parents[1] / "arena_kit" / "sim_cases" / "S03.json").read_text())
    terms = {"unit_price": 239.55, "payment_days": 30, "contract_months": 12, "incoterm": "DAP"}
    opening = supplier("open", 239.55)
    opening["term_sheets"][0]["terms"] = terms
    prior = {"from": "buyer", "term_sheets": [{"terms": {**terms, "unit_price": 230.0,
                                                     "contract_months": 24}}]}
    response = supplier(
        "open", 239.55,
        body="We could consider changing the contract duration if that helps.",
    )
    response["term_sheets"][0]["terms"] = terms
    events = [opening, prior, response]
    agent = UnifiedAgent()

    clarification = agent.decide(case, {"sup:70520": events})

    assert agent.decision_history[-1]["action"] == "clarify_trade"
    assert "contract months" in clarification["message"]["body"]
    assert "term_sheets" not in clarification["message"]
    events.extend([{**clarification["message"], "from": "buyer"}, response])
    followup = agent.decide(case, {"sup:70520": events})
    assert agent.decision_history[-1]["action"] != "clarify_trade"
    assert followup["message"]["action"]["type"] == "walk_away"


def test_unified_does_not_lower_its_previous_asks_after_a_tiny_supplier_concession():
    agent = UnifiedAgent()
    events = [supplier("open", 42.0)]
    first = agent.decide(CASE, {"sup:A": events})
    events.extend([{**first["message"], "from": "buyer"}, supplier("open", 41.98)])

    second = agent.decide(CASE, {"sup:A": events})

    first_prices = [sheet["terms"]["unit_price"] for sheet in first["message"]["term_sheets"]]
    second_prices = [sheet["terms"]["unit_price"] for sheet in second["message"]["term_sheets"]]
    assert len(first_prices) == len(second_prices)
    assert all(old <= new < 41.98 for old, new in zip(first_prices, second_prices, strict=True))
    assert second_prices[0] == first_prices[0] + 0.01


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
    assert out["message"]["term_sheets"]  # This supplier still has room to negotiate.


def test_unified_accepts_global_best_when_remaining_proposals_cannot_improve_it():
    out = UnifiedAgent().decide(CASE, {
        "sup:expensive": [supplier("open", 60.0)],
        "sup:cheap": [supplier("final_offer", 40.0)],
    })
    assert out["supplier_id"] == "sup:cheap"
    assert out["message"]["action"]["type"] == "accept"


def test_unified_stops_when_even_the_proposal_would_save_less_than_threshold():
    agent = UnifiedAgent(max_discount_pct=5.0, claim_adjustment_cap_pct=2, minimum_rounds=0)
    events = [supplier("open", 42.0, body="LCI-C rose 50 % in twelve months and is 80 % of our cost.")]
    first = agent.decide(CASE, {"sup:A": events})
    events.extend([{**first["message"], "from": "buyer"}, supplier("open", 40.8)])
    out = agent.decide(CASE, {"sup:A": events})
    assert out["message"]["action"]["type"] == "accept"
    assert "negligible" in agent.decision_history[-1]["reason"]


def test_unified_does_not_accept_missing_terms_without_a_supplier_standard():
    opening = supplier("final_offer", 40.0)
    del opening["term_sheets"][0]["terms"]["payment_days"]
    out = UnifiedAgent().decide(CASE, {"sup:A": [opening]})
    assert out["message"]["action"]["type"] == "walk_away"


def test_unified_keeps_only_distinct_term_choices_and_batches_supplier_messages():
    agent = UnifiedAgent()
    decisions = agent.decide_batch(CASE, {
        "sup:A": [supplier("open", 42.0)], "sup:B": [supplier("open", 41.5)],
    })
    assert {decision["supplier_id"] for decision in decisions} == {"sup:A", "sup:B"}
    for decision in decisions:
        assert len(decision["message"]["term_sheets"]) == 1


def test_supported_quality_guarantee_is_explained_as_a_concrete_trade():
    case = {**CASE, "negotiable": [*CASE["negotiable"], "ppm_commitment"],
            "buyer": {**CASE["buyer"], "cost_per_defect": 2000},
            "term_options": {**CASE["term_options"], "ppm_commitment": [100, 500, 1200]}}
    opening = supplier("open", 42, body="We guarantee a defect rate below 500 ppm.")
    opening["term_sheets"][0]["terms"]["ppm_commitment"] = 1200
    out = UnifiedAgent(max_discount_pct=5.0).decide(case, {"sup:A": [opening]})
    assert "pairs your stated quality guarantee" in out["message"]["body"]
    assert {s["terms"]["ppm_commitment"] for s in out["message"]["term_sheets"]} == {500}
    assert len(out["message"]["term_sheets"]) == 1


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
