from copy import deepcopy

import pytest
from test_kit import CASE
from test_unified import supplier

from arena_kit.agents.unified import UnifiedAgent
from negotiator.intelligence import build_supplier_context, load_evidence
from scripts.validate_mvp import audit_decisions, select_cases


@pytest.mark.parametrize('price', [1.25, 37.8, 425.0])
@pytest.mark.parametrize('quantity', [25, 7300])
@pytest.mark.parametrize('statement', ['', 'We require earlier payment.', 'Our price is fixed.'])
def test_cost_and_contract_invariants_hold_across_price_quantity_and_profile(price, quantity, statement):
    case = deepcopy(CASE)
    case['buyer'].update(need_per_year=quantity, current_unit_price=price, fallback_unit_price=price * 1.1)
    case['buyer']['must_haves'] = [{'field': 'payment_days', 'op': '>=', 'value': 30}]
    case['fixed_terms']['volume_per_year'] = quantity
    opening = supplier('open', price, body=statement, payment_days=45)
    agent = UnifiedAgent()
    agent.decide(case, {'sup:A': [opening]})
    assert audit_decisions(case, agent.decision_history) == []


@pytest.mark.parametrize('text', ['We guarantee 1,200 ppm.', 'We guarantee 12.5 ppm.'])
def test_ambiguous_quality_number_never_becomes_a_stricter_guarantee(text):
    evidence = load_evidence([{'Information': {'supplier_id': 'sup:A', 'notes': text}, 'Source': 'msg:1'}])
    profile = build_supplier_context(evidence, 'sup:A')['supplier_profile']['quality_sensitive']
    assert 'supported_terms' not in profile


def test_random_hosted_selection_is_reproducible_unique_and_has_no_case_filter():
    cases = [{'case_id': f'case:X{index}', 'hosted': index < 10} for index in range(19)]
    eligible, selected = select_cases(cases, 9243)
    assert len(eligible) == 10
    assert len({case['case_id'] for case in selected}) == 3
    assert all(case['hosted'] for case in selected)
    assert select_cases(cases, 9243)[1] == selected
    assert select_cases(cases, 4329)[1] != selected


def test_last_available_move_can_still_improve_an_offer():
    case = {**CASE, 'round_limit': 1}
    agent = UnifiedAgent()
    opening = supplier('open', 42)
    out = agent.decide(case, {'sup:A': [opening]})
    assert out['message']['term_sheets']
    events = [opening, {**out['message'], 'from': 'buyer'}, supplier('open', 41)]
    closed = agent.decide(case, {'sup:A': events})
    assert closed['message']['action']['type'] == 'accept'
    assert audit_decisions(case, agent.decision_history) == []
