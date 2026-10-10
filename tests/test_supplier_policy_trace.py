import json
from pathlib import Path

from negotiator.agent import SupplierContextAgent, _history_floor
from negotiator.policy import SupplierOnlyPolicy


TRACE = Path(__file__).parent / "fixtures" / "supplier_only_trace.json"


def test_supplier_trace_uses_claim_with_a_bound_and_accepts_concession():
    trace = json.loads(TRACE.read_text())
    supplier_id = trace["supplier_id"]
    events = [trace["opening"]]
    agent = SupplierContextAgent()

    counter = agent.decide({}, {supplier_id: events})["message"]
    counter_price = counter["term_sheets"][0]["terms"]["unit_price"]
    assert counter_price == 97.0  # claimed 2.655% impact is capped at a 2-point softening
    assert "2.66% claimed cost impact" in counter["body"]
    assert agent.decision_history[-1]["supplier_claimed_cost_impact_pct"] == 2.655

    events.extend([
        {"from": "buyer", "term_sheets": [{"terms": {"unit_price": counter_price}}]},
        trace["counter_response"],
    ])
    decision = agent.decide({}, {supplier_id: events})
    assert decision["message"]["action"] == {"type": "accept", "term_sheet_id": "offer:trace-01-1"}
    assert agent.decision_history[-1]["target_price"] == 98.0


def test_historical_floor_requires_matching_currency_unit_and_terms():
    current_terms = {
        "unit_price": 10.0, "currency": "EUR", "price_unit": "each",
        "volume_per_year": 100, "contract_months": 12,
    }
    rows = [
        {"Information": {"kind": "quote", "offer_id": "offer:current", **current_terms,
                         "part_id": "part:1"}, "Source": "current.pdf", "Priority (Argument wise)": 1},
        {"Information": {"kind": "quote", "offer_id": "offer:matching", "unit_price": 8.0,
                         "currency": "EUR", "price_unit": "each", "volume_per_year": 100,
                         "contract_months": 12, "part_id": "part:1"},
         "Source": "history_matching.csv:2", "Priority (Argument wise)": 1},
        {"Information": {"kind": "quote", "offer_id": "offer:wrong-volume", "unit_price": 2.0,
                         "currency": "EUR", "price_unit": "each", "volume_per_year": 500,
                         "contract_months": 12, "part_id": "part:1"},
         "Source": "history_wrong_volume.csv:2", "Priority (Argument wise)": 1},
        {"Information": {"kind": "quote", "offer_id": "offer:wrong-currency", "unit_price": 1.0,
                         "currency": "USD", "price_unit": "each", "volume_per_year": 100,
                         "contract_months": 12, "part_id": "part:1"},
         "Source": "history_wrong_currency.csv:2", "Priority (Argument wise)": 1},
        {"Information": {"kind": "quote", "offer_id": "offer:wrong-terms", "unit_price": 3.0,
                         "currency": "EUR", "price_unit": "each", "volume_per_year": 100,
                         "contract_months": 24, "part_id": "part:1"},
         "Source": "history_wrong_terms.csv:2", "Priority (Argument wise)": 1},
    ]
    # Bind the saved supplier rows to this live thread scope through CSV normalization.
    from negotiator.intelligence import contexts_from_records

    context = contexts_from_records(rows, "sup:1", "part:1")[0]
    assert _history_floor(context, current_terms, "offer:current") == (8.0, "history_matching.csv:2")
    unmatched = contexts_from_records([rows[0], rows[2], rows[3], rows[4]], "sup:1", "part:1")[0]
    assert _history_floor(unmatched, current_terms, "offer:current") == (None, None)


def test_policy_claim_adjustment_is_bounded_and_only_changes_initial_target():
    policy = SupplierOnlyPolicy(max_claim_adjustment_pct=2)

    assert policy.target_price(100, claimed_cost_impact_pct=2.655) == 97
    assert policy.target_price(100, claimed_cost_impact_pct=50) == 97
    assert policy.target_price(100, claimed_cost_impact_pct=-50) == 93
    assert policy.target_price(100, current_price=98, previous_supplier_price=100,
                               previous_buyer_price=97, rounds=1,
                               claimed_cost_impact_pct=50) == 98
