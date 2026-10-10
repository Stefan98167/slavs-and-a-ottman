"""Conservative price-ladder and reciprocal-term policy for package generation."""

from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Any

from arena_kit.cost import closing_terms, snap

from .packages import PackageInputError

CLAIM_ADJUSTMENT_CAP_PCT = 2.0


def plan_packages(
    case: Mapping[str, Any],
    supplier_offer_terms: Mapping[str, Any],
    supplier_profile: Mapping[str, Any] | None = None,
    *,
    supplier_standard_terms: Mapping[str, Any] | None = None,
    claimed_cost_impact_pct: float = 0.0,
    max_discount_pct: float = 5.0,
) -> dict[str, Any]:
    """Create a transparent, bounded package plan from the standing offer.

    The default ladder asks for 5%, 3%, and 1% below the opening price. A
    supplier explicitly profiled as price-rigid receives a softer 2%, 1%, and
    0% ladder. A likely cash- or capacity-sensitive supplier gets a real
    give-get: the less aggressive prices are paired with earlier payment or a
    longer available commitment.

    ``supplier_profile`` is Jonas's structured contract, not raw evidence.
    The policy reads only a dimension's ``state`` and treats every missing,
    malformed, or non-``likely`` value as unknown. An unknown profile keeps a
    conservative price-only ladder by pinning every non-price negotiable term
    to the supplier's current quote, standard terms, or conservative case
    completion. It never interprets profile evidence itself.

    ``claimed_cost_impact_pct`` is a supplier-stated index movement multiplied
    by its stated cost share. It adjusts only the opening discount, within a
    documented cap of +/- 2 percentage points. The caller must pass zero after
    the opening buyer message; later prices respond to supplier movement.
    """
    if not isinstance(case, Mapping) or not isinstance(supplier_offer_terms, Mapping):
        raise PackageInputError("case and supplier_offer_terms must be mappings")
    if supplier_standard_terms is not None and not isinstance(supplier_standard_terms, Mapping):
        raise PackageInputError("supplier_standard_terms must be a mapping or None")
    if supplier_profile is not None and not isinstance(supplier_profile, Mapping):
        raise PackageInputError("supplier_profile must be a mapping or None")
    opening = supplier_offer_terms.get("unit_price")
    if not _positive_number(opening):
        raise PackageInputError("supplier_offer_terms must contain a finite positive unit_price")
    if not _nonnegative_number(max_discount_pct) or max_discount_pct >= 100:
        raise PackageInputError("max_discount_pct must be a finite non-negative number below 100")
    if not _finite_number(claimed_cost_impact_pct):
        raise PackageInputError("claimed_cost_impact_pct must be a finite number")

    profile = supplier_profile or {}
    claim_adjustment = max(
        -CLAIM_ADJUSTMENT_CAP_PCT,
        min(CLAIM_ADJUSTMENT_CAP_PCT, float(claimed_cost_impact_pct)),
    )
    adjusted_discount = max(0.0, float(max_discount_pct) - claim_adjustment)
    discounts = _discounts(adjusted_discount, _profile_present(profile, "price_rigid"))
    price_discounts = [
        (round(float(opening) * (1 - discount / 100), 2), discount)
        for discount in discounts
    ]
    prices = _unique_round_money([price for price, _ in price_discounts])
    # Start from the supplied commercial terms. This is deliberately separate
    # from the supplier profile: an absent/unknown profile is not permission to
    # optimise payment, volume, or duration in the buyer's favour.
    try:
        baseline_terms = closing_terms(
            dict(case), dict(supplier_offer_terms), dict(supplier_standard_terms or {})
        )
        conservative_terms = {
            field: snap(dict(case), field, baseline_terms.get(field))
            for field in case.get("negotiable", [])
            if field != "unit_price"
        }
    except (KeyError, TypeError, ValueError) as exc:
        raise PackageInputError(f"could not establish conservative package terms: {exc}") from exc
    constraints: dict[float, dict[str, Any]] = {
        price: dict(conservative_terms) for price in prices
    }
    rationales: dict[float, list[str]] = {price: [] for price in prices}

    supplier_friendly: dict[str, Any] = {}
    negotiable_fields = set(case.get("negotiable", []))
    if _profile_present(profile, "cash_sensitive") and "payment_days" in negotiable_fields:
        if (payment_days := _extreme_option(case, "payment_days", smallest=True)) is not None:
            if payment_days >= conservative_terms.get("payment_days", payment_days):
                payment_days = None
        if payment_days is not None:
            supplier_friendly["payment_days"] = payment_days
    if _profile_present(profile, "capacity_sensitive"):
        for field in ("contract_months", "volume_per_year"):
            if field not in negotiable_fields:
                continue
            value = _capacity_commitment_option(case, field)
            if value is not None and value > conservative_terms.get(field, value):
                supplier_friendly[field] = value

    if supplier_friendly:
        for price in prices[1:]:
            constraints[price].update(supplier_friendly)
            if "payment_days" in supplier_friendly:
                rationales[price].append("earlier payment in return for a less aggressive price")
            if any(field in supplier_friendly for field in ("contract_months", "volume_per_year")):
                rationales[price].append("greater commitment in return for a less aggressive price")

    discounts_by_price = dict(price_discounts)
    for price in prices:
        discount = discounts_by_price[price]
        rationales[price].insert(0, f"{discount:g}% below the standing unit price")
    profile_used = {
        field: _profile_present(profile, field)
        for field in ("cash_sensitive", "capacity_sensitive", "quality_sensitive", "price_rigid")
    }
    profile_evidence = {
        field: _profile_evidence(profile, field)
        for field in profile_used
        if profile_used[field]
    }
    trade_hypotheses = _trade_hypotheses(profile, supplier_friendly)
    applied_dimensions = {item["profile_dimension"] for item in trade_hypotheses}
    if profile_used["price_rigid"]:
        applied_dimensions.add("price_rigid")
    return {
        "candidate_unit_prices": prices,
        "term_constraints_by_price": constraints,
        "rationales_by_price": rationales,
        "profile_used": profile_used,
        "profile_evidence": profile_evidence,
        "unmapped_profile_dimensions": [
            field for field, present in profile_used.items() if present and field not in applied_dimensions
        ],
        "claim_adjustment_pct": claim_adjustment,
        "trade_hypotheses": trade_hypotheses,
    }


def _discounts(max_discount_pct: float, price_rigid: bool) -> list[float]:
    if price_rigid:
        return [round(max_discount_pct * 0.4, 2), round(max_discount_pct * 0.2, 2), 0.0]
    return [round(max_discount_pct, 2), round(max_discount_pct * 0.6, 2), round(max_discount_pct * 0.2, 2)]


def _profile_present(profile: Mapping[str, Any], field: str) -> bool:
    """Trust Jonas's state when its provenance links are structurally present."""
    value = profile.get(field)
    confidence = value.get("confidence") if isinstance(value, Mapping) else None
    return (
        isinstance(value, Mapping)
        and value.get("state") == "likely"
        and _finite_number(confidence)
        and 0 <= confidence <= 1
        and bool(_profile_evidence(profile, field))
    )


def _profile_evidence(profile: Mapping[str, Any], field: str) -> list[dict[str, str]]:
    value = profile.get(field)
    entries = value.get("evidence") if isinstance(value, Mapping) else None
    if not isinstance(entries, list):
        return []
    normalized = []
    for item in entries:
        if not isinstance(item, Mapping):
            continue
        # Jonas's profile contract names this ``evidence_id``; ``id`` remains
        # accepted for older callers and existing agent fixtures.
        evidence_id = item.get("evidence_id") or item.get("id")
        source = item.get("source")
        if (
            isinstance(evidence_id, str)
            and evidence_id.strip()
            and isinstance(source, str)
            and source.strip()
        ):
            normalized.append({"id": evidence_id, "source": source})
    return normalized


def _trade_hypotheses(profile: Mapping[str, Any], supplier_friendly: Mapping[str, Any]) -> list[dict[str, Any]]:
    hypotheses = []
    mappings = {
        "cash_sensitive": ("payment_days", "earlier payment", "less aggressive price"),
        "capacity_sensitive": ("contract_months/volume_per_year", "greater commitment", "less aggressive price"),
    }
    for dimension, (give, get, price_side) in mappings.items():
        relevant = [field for field in give.split("/") if field in supplier_friendly]
        if not relevant or not _profile_present(profile, dimension):
            continue
        hypotheses.append({
            "profile_dimension": dimension,
            "buyer_gives": {field: supplier_friendly[field] for field in relevant},
            "supplier_gets": price_side,
            "rationale": f"{get} in return for a less aggressive price",
            "evidence": _profile_evidence(profile, dimension),
        })
    return hypotheses


def _extreme_option(case: Mapping[str, Any], field: str, *, smallest: bool) -> Any | None:
    options = case.get("term_options", {}).get(field)
    if not options or not all(isinstance(value, (int, float)) and not isinstance(value, bool) for value in options):
        return None
    return min(options) if smallest else max(options)


def _capacity_commitment_option(case: Mapping[str, Any], field: str) -> Any | None:
    """Choose a larger available commitment without exceeding buyer need/horizon."""
    options = case.get("term_options", {}).get(field)
    buyer = case.get("buyer", {})
    if field == "contract_months":
        horizon = buyer.get("horizon_years") if isinstance(buyer, Mapping) else None
        ceiling = 12 * horizon if isinstance(horizon, (int, float)) and not isinstance(horizon, bool) else None
    elif field == "volume_per_year":
        ceiling = buyer.get("need_per_year") if isinstance(buyer, Mapping) else None
    else:
        return None
    if not options or not isinstance(ceiling, (int, float)):
        return None
    numeric = [
        value for value in options
        if isinstance(value, (int, float)) and not isinstance(value, bool) and value <= ceiling
    ]
    return max(numeric) if numeric else None


def _positive_number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value)) and value > 0


def _nonnegative_number(value: object) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
        and value >= 0
    )


def _finite_number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))


def _unique_round_money(values: list[float]) -> list[float]:
    result: list[float] = []
    for value in values:
        money = round(value, 2)
        if money not in result:
            result.append(money)
    return result
