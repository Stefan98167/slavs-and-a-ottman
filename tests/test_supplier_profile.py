import json

import pytest

from negotiator.intelligence import build_supplier_context, load_evidence
from negotiator.supplier_evidence import build_thread_supplier_context, context_for_part


POSITIVE = {
    'cash_sensitive': 'We require earlier payment.',
    'capacity_sensitive': 'Our capacity is limited.',
    'quality_sensitive': 'We guarantee a defect rate below 500 ppm.',
    'price_rigid': 'Our price is fixed.',
}
NEGATIVE = {
    'cash_sensitive': 'We do not require earlier payment.',
    'capacity_sensitive': 'Our capacity is not limited.',
    'quality_sensitive': 'We cannot guarantee a defect rate below 500 ppm.',
    'price_rigid': 'Our price is negotiable.',
}


def context(text, source='supplier.csv:2', supplier='sup:1', **extra):
    rows = load_evidence([{'Information': {'supplier_id': supplier, 'notes': text, **extra},
                          'Source': source}])
    return build_supplier_context(rows, 'sup:1')


@pytest.mark.parametrize('dimension', POSITIVE)
def test_explicit_statement_has_sourced_profile(dimension):
    result = context(POSITIVE[dimension])['supplier_profile']
    assert set(result) == set(POSITIVE)
    assert result[dimension]['state'] == 'likely'
    assert 0 < result[dimension]['confidence'] <= 1
    assert result[dimension]['evidence'][0]['evidence_id'] == 'supplier.csv:2'
    assert result[dimension]['evidence'][0]['source'] == 'supplier.csv:2'
    assert result[dimension]['evidence'][0]['excerpt'] == POSITIVE[dimension]
    assert json.loads(json.dumps(result)) == result


@pytest.mark.parametrize('dimension', POSITIVE)
def test_unknown_negated_hypothetical_and_conflicting_statements(dimension):
    for text in ('Standard payment terms: 30 days. High quality products.',
                 NEGATIVE[dimension], 'If demand rises, ' + POSITIVE[dimension],
                 POSITIVE[dimension] + ' ' + NEGATIVE[dimension]):
        assert context(text)['supplier_profile'][dimension] == {
            'state': 'unknown', 'confidence': 0.0, 'evidence': []}


def test_prices_and_unprovenanced_or_other_supplier_statements_are_not_traits():
    for result in (context('', unit_price=100, payment_days=14, lead_time_days=90),
                   context(POSITIVE['cash_sensitive'], source=None),
                   context(POSITIVE['cash_sensitive'], supplier='sup:other')):
        assert all(item['state'] == 'unknown' for item in result['supplier_profile'].values())


def test_live_email_and_pdf_context_and_duplicate_provenance():
    events = [
        {'from': 'sales', 'message_id': 'msg:1', 'body': POSITIVE['cash_sensitive'],
         'attachments': [{'attachment_id': 'att:1', 'name': 'offer.pdf', 'text':
             'Offered terms\nUnit price (EUR) 100\n' + POSITIVE['capacity_sensitive']}]},
        {'from': 'buyer', 'message_id': 'msg:buyer', 'body': POSITIVE['price_rigid']},
        {'from': 'arena', 'message_id': 'msg:arena', 'body': POSITIVE['price_rigid']},
    ]
    result = context_for_part(build_thread_supplier_context(events + [events[0]], 'sup:1'))
    profile = result['supplier_profile']
    assert profile['cash_sensitive']['state'] == 'likely'
    assert len(profile['cash_sensitive']['evidence']) == 1
    assert profile['capacity_sensitive']['evidence'][0]['source'] == 'att:1 (offer.pdf)'
    assert profile['price_rigid']['state'] == 'unknown'


@pytest.mark.parametrize('field,value', [('volume_per_year', 500), ('payment_days', 60),
                                        ('incoterm', 'DAP'), ('contract_months', 24)])
def test_quote_history_does_not_aggregate_different_commercial_terms(field, value):
    common = {'supplier_id': 'sup:1', 'unit_price': 100, 'currency': 'EUR', 'price_unit': 'each',
              'volume_per_year': 100, 'payment_days': 30, 'incoterm': 'FCA', 'contract_months': 12}
    rows = load_evidence([
        {'Information': common, 'Source': 'supplier.csv:2'},
        {'Information': {**common, field: value, 'unit_price': 80}, 'Source': 'supplier.csv:3'},
    ])
    history = build_supplier_context(rows, 'sup:1')['quote_history']
    assert history['min_unit_price'] is None
    assert history['max_unit_price'] is None
    assert len(history['quotes']) == 2


def test_price_refusals_require_distinct_records_and_fixed_language_does_not():
    def profile(sources):
        records = load_evidence([
            {'Information': {'supplier_id': 'sup:1', 'notes': 'We will not lower our price.'},
             'Source': source} for source in sources
        ])
        return build_supplier_context(records, 'sup:1')['supplier_profile']['price_rigid']
    assert profile(['msg:1'])['state'] == 'unknown'
    assert profile(['msg:1', 'msg:1'])['state'] == 'unknown'
    assert profile(['msg:1', 'msg:2'])['state'] == 'likely'
    assert len(profile(['msg:1', 'msg:2'])['evidence']) == 2
    assert context('We will not lower our price further.')['supplier_profile']['price_rigid']['state'] == 'likely'


def test_profile_is_scoped_to_the_requested_part():
    rows = load_evidence([{'Information': {'supplier_id': 'sup:1', 'part_id': 'part:other',
                                         'notes': POSITIVE['cash_sensitive']}, 'Source': 'supplier.csv:2'}])
    assert build_supplier_context(rows, 'sup:1', 'part:wanted')['supplier_profile']['cash_sensitive']['state'] == 'unknown'
