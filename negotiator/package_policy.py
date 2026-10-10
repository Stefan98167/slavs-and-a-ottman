"""Conservative price-ladder and reciprocal-term policy for package generation."""

from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Any

from .packages import PackageInputError


def plan_packages(
    case: Mapping[str, Any],
    supplier_offer_terms: Mapping[str, Any],
    supplier_profile: Mapping[str, Any] | None = None,
    *,
    max_discount_pct: float = 5.0,
) -> dict[str, Any]:
    """Create a transparent, bounded package plan from the standing offer.

    The default ladder asks for 5%, 3%, and 1% below the opening price. A
    supplier explicitly profiled as price-rigid receives a softer 2%, 1%, and
    0% ladder.  A likely cash- or capacity-sensitive supplier gets a real
    give-get: the less aggressive prices are paired with earlier payment or a
    longer available commitment. Unknown profile dimensions never trigger an
    invented reciprocal trade.
    """
    if not isinstance(case, Mapping) or not isinstance(supplier_offer_terms, Mapping):
        raise PackageInputError("case and supplier_offer_terms must be mappings")
    opening = supplier_offer_terms.get("unit_price")
    if not _positive_number(opening):
        raise PackageInputError("supplier_offer_terms must contain a finite positive unit_price")
    if not _positive_number(max_discount_pct) or max_discount_pct >= 100:
        raise PackageInputError("max_discount_pct must be a finite positive number below 100")

    profile = supplier_profile or {}
    discounts = _discounts(float(max_discount_pct), _profile_present(profile, "price_rigid"))
    price_discounts = [
        (round(float(opening) * (1 - discount / 100), 2), discount)
        for discount in discounts
    ]
    prices = _unique_round_money([price for price, _ in price_discounts])
    constraints: dict[float, dict[str, Any]] = {}
    rationales: dict[float, list[str]] = {price: [] for price in prices}

    supplier_friendly: dict[str, Any] = {}
    if _profile_present(profile, "cash_sensitive"):
        if payment_days := _extreme_option(case, "payment_days", smallest=True):
            supplier_friendly["payment_days"] = payment_days
    if _profile_present(profile, "capacity_sensitive"):
        for field in ("contract_months", "volume_per_year"):
            if value := _extreme_option(case, field, smallest=False):
                supplier_friendly[field] = value

    if supplier_friendly:
        for price in prices[1:]:
            constraints[price] = dict(supplier_friendly)
            if "payment_days" in supplier_friendly:
                rationales[price].append("earlier payment in return for a less aggressive price")
            if any(field in supplier_friendly for field in ("contract_months", "volume_per_year")):
                rationales[price].append("greater commitment in return for a less aggressive price")

    discounts_by_price = dict(price_discounts)
    for price in prices:
        discount = discounts_by_price[price]
        rationales[price].insert(0, f"{discount:g}% below the standing unit price")
    return {
        "candidate_unit_prices": prices,
        "term_constraints_by_price": constraints,
        "rationales_by_price": rationales,
        "profile_used": {
            field: _profile_present(profile, field)
            for field in ("cash_sensitive", "capacity_sensitive", "price_rigid")
        },
    }


def _discounts(max_discount_pct: float, price_rigid: bool) -> list[float]:
    if price_rigid:
        return [round(max_discount_pct * 0.4, 2), round(max_discount_pct * 0.2, 2), 0.0]
    return [round(max_discount_pct, 2), round(max_discount_pct * 0.6, 2), round(max_discount_pct * 0.2, 2)]


def _profile_present(profile: Mapping[str, Any], field: str) -> bool:
    value = profile.get(field)
    if isinstance(value, Mapping):
        value = value.get("state")
    return value is True or (isinstance(value, str) and value.lower() in {"likely", "yes", "true", "high"})


def _extreme_option(case: Mapping[str, Any], field: str, *, smallest: bool) -> Any | None:
    options = case.get("term_options", {}).get(field)
    if not options or not all(isinstance(value, (int, float)) and not isinstance(value, bool) for value in options):
        return None
    return min(options) if smallest else max(options)


def _positive_number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value)) and value > 0


def _unique_round_money(values: list[float]) -> list[float]:
    result: list[float] = []
    for value in values:
        money = round(value, 2)
        if money not in result:
            result.append(money)
    return result
