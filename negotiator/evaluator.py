"""Deterministic evaluation of one proposed supplier deal.

This module deliberately only evaluates terms.  It does not select suppliers, write messages,
or infer supplier economics.  Cost arithmetic remains in :mod:`arena_kit.cost`.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Any

from arena_kit.cost import (
    closing_terms,
    complete_offer,
    cost_breakdown,
    must_haves_ok,
    supplier_value,
    total_cost,
)


class EvaluationInputError(ValueError):
    """Raised when the case or one of the top-level inputs is not usable.

    Invalid *term-sheet* values are reported in the returned evaluation's ``warnings`` and make
    ``valid_for_negotiation`` false.  This exception is reserved for malformed API inputs such as
    a case without the fields required by the starter-kit cost functions.
    """


def evaluate_deal(
    case: dict[str, Any],
    proposed_terms: dict[str, Any],
    supplier_standard_terms: dict[str, Any],
    supplier_economics: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Evaluate a candidate term sheet using the starter-kit cost functions.

    ``supplier_standard_terms`` are the supplier's quoted fallback terms for fields omitted by
    the proposed sheet.  ``supplier_economics`` may contain ``interest_rate``, ``full_cost`` and
    optional ``usual_rate``, ``ppm`` and ``extra``.  No economic assessment is made unless both
    required estimates are present and finite.
    """
    _validate_top_level_inputs(case, proposed_terms, supplier_standard_terms, supplier_economics)

    try:
        warnings = _term_sheet_errors(case, proposed_terms)
        final_terms = complete_offer(case, proposed_terms)
    except (KeyError, TypeError, ValueError) as exc:
        raise EvaluationInputError(f"case or proposed_terms cannot be completed: {exc}") from exc
    standard = dict(supplier_standard_terms)
    # This is the actual closure: candidate terms, then supplier fallbacks, then case-fixed
    # terms. The starter-kit cost helpers apply the same order internally.
    try:
        closed_terms = closing_terms(case, final_terms, standard)
    except (KeyError, TypeError, ValueError) as exc:
        raise EvaluationInputError(f"case cannot be closed with the supplied standard terms: {exc}") from exc

    supplier, supplier_result, supplier_warning = _supplier_assessment(
        case, final_terms, standard, supplier_economics
    )
    if supplier_warning:
        warnings.append(supplier_warning)

    buyer_cost: float
    breakdown: dict[str, float]
    must_haves = False
    try:
        # Passing standard here matters for terms omitted before completion and for relationship
        # cost; it is the same closing-term behaviour used by the starter kit.
        buyer_cost = float(total_cost(case, final_terms, standard, supplier))
        breakdown = {key: float(value) for key, value in cost_breakdown(case, final_terms, standard, supplier).items()}
        must_haves = bool(must_haves_ok(case, closed_terms, standard))
    except (KeyError, TypeError, ValueError, ZeroDivisionError) as exc:
        buyer_cost = math.inf
        breakdown = {}
        warnings.append(f"could not calculate buyer cost: {exc}")

    if not must_haves:
        warnings.append("buyer must-haves are not satisfied")
    if not math.isfinite(buyer_cost):
        warnings.append("buyer total cost is not finite")

    alternative_cost, alternative_warning = _alternative_cost(case)
    if alternative_warning:
        warnings.append(alternative_warning)
    beats_alternative = alternative_cost is None or buyer_cost <= alternative_cost
    if alternative_cost is not None and not beats_alternative:
        warnings.append("buyer total cost is worse than the available alternative")

    return {
        "final_terms": final_terms,
        "buyer": {
            "total_cost": _json_number_or_none(buyer_cost),
            "cost_breakdown": breakdown,
            "must_haves_ok": must_haves,
            "alternative_cost": alternative_cost,
            "beats_alternative": beats_alternative,
        },
        "supplier": supplier_result,
        "valid_for_negotiation": not warnings_for_invalid_deal(warnings, must_haves, buyer_cost),
        "warnings": warnings,
    }


def warnings_for_invalid_deal(warnings: list[str], must_haves: bool, buyer_cost: float) -> bool:
    """Return whether a result fails the explicitly required negotiation validity gates."""
    return (not must_haves) or (not math.isfinite(buyer_cost)) or any(
        warning.startswith("invalid term sheet:") for warning in warnings
    )


def _validate_top_level_inputs(
    case: object, proposed_terms: object, standard: object, economics: object) -> None:
    if not isinstance(case, Mapping):
        raise EvaluationInputError("case must be a mapping")
    missing = {"buyer", "negotiable"} - set(case)
    if missing:
        raise EvaluationInputError(f"case is missing required fields: {', '.join(sorted(missing))}")
    if not isinstance(proposed_terms, Mapping):
        raise EvaluationInputError("proposed_terms must be a mapping")
    if not isinstance(standard, Mapping):
        raise EvaluationInputError("supplier_standard_terms must be a mapping")
    if economics is not None and not isinstance(economics, Mapping):
        raise EvaluationInputError("supplier_economics must be a mapping or None")


def _term_sheet_errors(case: Mapping[str, Any], proposed_terms: Mapping[str, Any]) -> list[str]:
    negotiable = set(case["negotiable"])
    errors: list[str] = []
    unknown = sorted(set(proposed_terms) - negotiable)
    if unknown:
        errors.append(f"unknown fields: {', '.join(unknown)}")

    for field, value in proposed_terms.items():
        options = case.get("term_options", {}).get(field)
        if options and value not in options:
            errors.append(f"{field}={value!r} is not one of {options!r}")
    price = proposed_terms.get("unit_price")
    if price is not None and (not _finite_number(price) or float(price) <= 0):
        errors.append("unit_price must be a finite number greater than zero")
    return [f"invalid term sheet: {error}" for error in errors]


def _supplier_assessment(
    case: Mapping[str, Any],
    terms: Mapping[str, Any],
    standard: Mapping[str, Any],
    economics: Mapping[str, Any] | None,
) -> tuple[dict[str, Any] | None, dict[str, Any], str | None]:
    unavailable = {
        "value_per_unit": None,
        "estimated_margin_pct": None,
        "assessment_available": False,
        "reason_unavailable": None,
    }
    if economics is None:
        unavailable["reason_unavailable"] = "supplier_economics was not supplied"
        return None, unavailable, None

    missing = [name for name in ("interest_rate", "full_cost") if name not in economics]
    non_finite = [
        name
        for name in ("interest_rate", "full_cost")
        if name in economics and not _finite_number(economics[name])
    ]
    if missing or non_finite:
        details = []
        if missing:
            details.append("missing " + ", ".join(missing))
        if non_finite:
            details.append("non-finite " + ", ".join(non_finite))
        unavailable["reason_unavailable"] = "supplier economic assumptions incomplete: " + "; ".join(details)
        return None, unavailable, None

    # supplier_value requires `standard`, but its standard contractual terms are supplied through
    # the separate public argument to avoid duplicating or fabricating them.
    supplier = {**economics, "standard": dict(standard)}
    try:
        value = float(supplier_value(case, dict(terms), supplier))
        if not math.isfinite(value) or value == 0:
            raise ValueError("supplier value is not finite and non-zero")
        margin = (value - float(economics["full_cost"])) / value * 100
        if not math.isfinite(margin):
            raise ValueError("estimated supplier margin is not finite")
    except (KeyError, TypeError, ValueError, ZeroDivisionError) as exc:
        unavailable["reason_unavailable"] = f"supplier assessment could not be calculated: {exc}"
        return None, unavailable, None

    return supplier, {
        "value_per_unit": value,
        "estimated_margin_pct": margin,
        "assessment_available": True,
        "reason_unavailable": None,
    }, None


def _alternative_cost(case: Mapping[str, Any]) -> tuple[float | None, str | None]:
    alternative = case.get("buyer", {}).get("alternative")
    if not isinstance(alternative, Mapping) or alternative.get("kind") in (None, "none"):
        return None, None
    terms = alternative.get("terms")
    if not isinstance(terms, Mapping) or not _finite_number(terms.get("unit_price")) or terms["unit_price"] <= 0:
        return None, "case alternative is not usable (it needs a finite positive unit_price)"
    try:
        value = float(total_cost(case, dict(terms)))
    except (KeyError, TypeError, ValueError, ZeroDivisionError) as exc:
        return None, f"case alternative is not usable: {exc}"
    if math.isfinite(value):
        return _json_number_or_none(value), None
    return None, "case alternative cost is not finite"


def _finite_number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))


def _json_number_or_none(value: float) -> float | None:
    return float(value) if math.isfinite(value) else None
