"""Supplier profile v1: narrow English statement rules, never inferred from prices.

Confidence is fixed rule support, not a calibrated probability. Conflicting explicit
statements keep a dimension unknown. Unsupported languages/phrasing remain unknown.
"""
import re

DIMENSIONS = ('cash_sensitive', 'capacity_sensitive', 'quality_sensitive', 'price_rigid')
# Each pattern must express a supplier request, commitment, constraint or refusal.
RULES = {
    'cash_sensitive': (
        'explicit_payment_request', 0.8,
        r'\b(?:we (?:need|require|request)|please (?:pay|provide))\b.{0,65}\b(?:earlier payment|advance payment|payment in advance|prepayment)\b|\b(?:earlier payment|advance payment|prepayment)\b.{0,60}\b(?:would allow us|will allow us|in exchange|discount)\b',
        r'\b(?:we do not (?:need|require)|no need for)\b.{0,40}\b(?:earlier payment|advance payment|prepayment)\b'),
    'capacity_sensitive': (
        'explicit_capacity_constraint', 0.85,
        r'\b(?:our|we have)\b.{0,30}\b(?:limited capacity|capacity (?:is limited|is constrained|is fully booked)|production (?:is fully booked|capacity is limited))\b|\bwe (?:need|require)\b.{0,45}\b(?:forecast|commitment)\b.{0,45}\b(?:reserve|secure) capacity\b',
        r'\b(?:our capacity is not (?:limited|constrained)|we have no capacity (?:constraints|limits))\b'),
    'quality_sensitive': (
        'explicit_quality_commitment', 0.8,
        r'\bwe (?:commit to|guarantee)\b.{0,60}\b(?:quality|ppm|defect rate|defects)\b|\bwe (?:are concerned about|cannot accept)\b.{0,50}\b(?:quality risk|quality deterioration|defect risk)\b',
        r'\bwe (?:cannot|do not) (?:commit to|guarantee)\b.{0,60}\b(?:quality|ppm|defect rate|defects)\b'),
    'price_rigid': (
        'explicit_fixed_price', 0.85,
        r'\b(?:our|this) price is (?:fixed|non-negotiable)\b|\bwe (?:cannot|will not) (?:reduce|lower) (?:our |the )?price (?:any )?further\b',
        r'\b(?:our|this) price is (?:not fixed|negotiable)\b|\bwe (?:can|are willing to) (?:reduce|lower) (?:our |the )?price further\b'),
}
TEXT_FIELDS = {'claim text', 'document text', 'message text', 'statement', 'text', 'notes', 'note', 'comment', 'comments', 'description'}


def build_supplier_profile(evidence):
    """Consume supplier-scoped normalized evidence and return the stable v1 contract."""
    result = {key: {'state': 'unknown', 'confidence': 0.0, 'evidence': []} for key in DIMENSIONS}
    for dimension, (rule, confidence, positive, negative) in RULES.items():
        support, refusals, seen, conflict = [], [], set(), False
        for item in evidence:
            if not item.get('id') or not item.get('source'):
                continue
            data = item.get('data') or {}
            for key, value in data.items():
                header = re.sub(r'[_\W]+', ' ', str(key).casefold()).strip()
                if header not in TEXT_FIELDS or not isinstance(value, str):
                    continue
                for statement in re.split(r'(?<=[.!?])\s+|[\r\n]+', value):
                    if re.search(negative, statement, re.I):
                        conflict = True
                        continue
                    # Reject hypotheticals, reported buyer wishes, and ambiguous negation.
                    if re.search(r'\b(?:if|might|could|buyer|customer|never)\b', statement, re.I):
                        continue
                    if dimension != 'price_rigid' and re.search(r'\bnot\b', statement, re.I):
                        continue
                    if dimension == 'price_rigid' and re.search(
                        r'\bwe (?:cannot|will not) (?:reduce|lower) (?:our |the )?price\b', statement, re.I
                    ):
                        refusals.append({'evidence_id': item['id'], 'source': item['source'],
                                         'excerpt': statement.strip(), 'rule': 'repeated_price_refusal'})
                    if re.search(positive, statement, re.I):
                        identity = (str(item['id']), statement.strip().casefold())
                        if identity not in seen:
                            seen.add(identity)
                            support.append({'evidence_id': item['id'], 'source': item['source'],
                                            'excerpt': statement.strip(), 'rule': rule})
        if not support and len({str(item['evidence_id']) for item in refusals}) >= 2:
            support = list({str(item['evidence_id']): item for item in refusals}.values())
            confidence = 0.8
        if support and not conflict:
            result[dimension] = {'state': 'likely', 'confidence': confidence, 'evidence': support}
    return result
