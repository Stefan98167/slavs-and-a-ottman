"""Conservative supplier cost estimates from explicitly scoped cost facts."""

import math
from collections.abc import Mapping


def estimate_supplier_economics(case, supplier_id, facts):
    """Return evaluator inputs for a stabilise/secure-supply case, or None if unsupported.

    Supplier-specific `cost:<part>-<supplier>` facts take precedence over the
    generic `cost:<part>` fact. Fact costs are converted to the case unit by
    dividing `unit_cost` by the fact's `price_unit`.
    """
    buyer = case.get("buyer") or {}
    if buyer.get("category_goal") not in {"stabilise", "secure_supply"}:
        return None
    parts = case.get("parts") or []
    if len(parts) != 1 or not isinstance(parts[0], str) or ":" not in parts[0]:
        return None
    interest_rate = buyer.get("interest_rate")
    if not _positive_or_zero(interest_rate):
        return None
    if not isinstance(facts, Mapping):
        return None
    fact = supplier_cost_fact(case, supplier_id, facts)
    if fact is not None:
        _, record = fact
        full_cost = float(record["unit_cost"]) / float(record["price_unit"])
        if math.isfinite(full_cost) and full_cost > 0:
            return {"interest_rate": float(interest_rate), "full_cost": full_cost}
    return None


def supplier_cost_fact(case, supplier_id, facts):
    """Return the preferred scoped (fact ID, fact) pair, or None if unusable."""
    parts = case.get("parts") or []
    if len(parts) != 1 or not isinstance(parts[0], str) or ":" not in parts[0]:
        return None
    if not isinstance(facts, Mapping):
        return None
    part_suffix = parts[0].split(":", 1)[1]
    supplier_suffix = str(supplier_id).split(":", 1)[-1]
    for ref in (f"cost:{part_suffix}-{supplier_suffix}", f"cost:{part_suffix}"):
        fact = facts.get(ref)
        if (isinstance(fact, Mapping) and fact.get("part") == parts[0]
                and _positive(fact.get("unit_cost")) and _positive(fact.get("price_unit"))):
            return ref, fact
    return None


def _positive(value):
    return _positive_or_zero(value) and float(value) > 0


def _positive_or_zero(value):
    return (isinstance(value, (int, float)) and not isinstance(value, bool)
            and math.isfinite(float(value)) and float(value) >= 0)
