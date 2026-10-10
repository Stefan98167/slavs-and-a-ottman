"""Deterministic generation and selection of buyer-efficient term packages.

Price levels are an input from negotiation policy: this module does not pretend
to know the supplier's floor.  It combines each supplied price with every
allowed non-price term, evaluates the resulting package with the published
buyer-cost model, and returns at most three valid, distinct proposals.
"""

from __future__ import annotations

import itertools
import json
import math
from collections.abc import Iterable, Mapping
from typing import Any

from arena_kit.cost import complete_offer

from .evaluator import evaluate_deal


class PackageInputError(ValueError):
    """Raised when package-generation inputs cannot define valid candidates."""


def generate_packages(
    case: Mapping[str, Any],
    supplier_offer_terms: Mapping[str, Any],
    candidate_unit_prices: Iterable[float],
    supplier_standard_terms: Mapping[str, Any] | None = None,
    *,
    supplier_economics: Mapping[str, Any] | None = None,
    max_packages: int = 3,
    require_beats_alternative: bool = True,
    term_constraints_by_price: Mapping[float, Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Return up to ``max_packages`` valid buyer packages for one supplier.

    ``candidate_unit_prices`` must be supplied by the calling negotiation
    policy.  The generator enumerates each price against the case's permitted
    options for every other negotiable field.  ``term_constraints_by_price``
    can pin allowed fields for a given price, making a reciprocal package such
    as an earlier-payment-for-lower-price offer explicit. Fields without an option list
    retain the supplier's offer/standard term, or the buyer's case default.

    Packages are valid only if they satisfy the published case constraints and
    buyer must-haves.  By default, a package that costs more than the buyer's
    stated alternative is excluded.  Selection keeps the lowest-C package for
    each price level first, then fills any remaining slots by lowest total C.
    This produces a concise price/term ladder rather than near-duplicate offers.
    """
    _validate_inputs(
        case,
        supplier_offer_terms,
        candidate_unit_prices,
        supplier_standard_terms,
        supplier_economics,
        max_packages,
        require_beats_alternative,
    )
    prices = _unique_prices(candidate_unit_prices)
    constraints = _normalize_constraints(case, prices, term_constraints_by_price)
    standard = dict(supplier_standard_terms or {})
    base_terms = {**standard, **supplier_offer_terms}
    candidates = _candidate_terms(case, base_terms, prices, constraints)

    valid: list[dict[str, Any]] = []
    excluded_worse_than_alternative = 0
    for terms in candidates:
        evaluation = evaluate_deal(
            dict(case), terms, standard, dict(supplier_economics) if supplier_economics is not None else None
        )
        if not evaluation["valid_for_negotiation"]:
            continue
        if require_beats_alternative and not evaluation["buyer"]["beats_alternative"]:
            excluded_worse_than_alternative += 1
            continue
        valid.append({"terms": evaluation["final_terms"], "evaluation": evaluation})

    valid.sort(key=_buyer_rank)
    selected = _select_price_distinct(valid, max_packages)
    best_cost_by_price = {}
    for candidate in valid:
        best_cost_by_price.setdefault(
            candidate["terms"]["unit_price"], candidate["evaluation"]["buyer"]["total_cost"]
        )
    for rank, package in enumerate(selected, start=1):
        price = package["terms"]["unit_price"]
        package["rank"] = rank
        if package["evaluation"]["buyer"]["total_cost"] == best_cost_by_price[price]:
            package["rationale"] = f"Lowest buyer total cost among valid generated packages at unit price {price}."
        else:
            package["rationale"] = "Next-lowest buyer total cost after covering each available price level."

    return {
        "packages": selected,
        "generated_candidates": len(candidates),
        "valid_candidates": len(valid),
        "excluded_worse_than_alternative": excluded_worse_than_alternative,
        "selection_policy": "lowest buyer cost per unit-price level, then lowest buyer cost overall",
    }


def _validate_inputs(
    case: object,
    offered: object,
    prices: object,
    standard: object,
    economics: object,
    max_packages: object,
    require_beats_alternative: object,
) -> None:
    if not isinstance(case, Mapping):
        raise PackageInputError("case must be a mapping")
    negotiable = case.get("negotiable")
    if not isinstance(negotiable, list) or "unit_price" not in negotiable:
        raise PackageInputError("case must have unit_price in its negotiable fields")
    if not isinstance(offered, Mapping):
        raise PackageInputError("supplier_offer_terms must be a mapping")
    if standard is not None and not isinstance(standard, Mapping):
        raise PackageInputError("supplier_standard_terms must be a mapping or None")
    if economics is not None and not isinstance(economics, Mapping):
        raise PackageInputError("supplier_economics must be a mapping or None")
    if type(max_packages) is not int or not 1 <= max_packages <= 3:
        raise PackageInputError("max_packages must be an integer from 1 to 3")
    if not isinstance(require_beats_alternative, bool):
        raise PackageInputError("require_beats_alternative must be a boolean")
    if isinstance(prices, (str, bytes)) or not isinstance(prices, Iterable):
        raise PackageInputError("candidate_unit_prices must be an iterable of finite positive numbers")


def _unique_prices(prices: Iterable[float]) -> list[float]:
    result: list[float] = []
    for index, value in enumerate(prices):
        invalid = (
            not isinstance(value, (int, float))
            or isinstance(value, bool)
            or not math.isfinite(float(value))
            or value <= 0
        )
        if invalid:
            raise PackageInputError(f"candidate_unit_prices[{index}] must be a finite positive number")
        price = round(float(value), 2)
        if price not in result:
            result.append(price)
    if not result:
        raise PackageInputError("candidate_unit_prices must not be empty")
    return result


def _candidate_terms(
    case: Mapping[str, Any],
    base_terms: Mapping[str, Any],
    prices: list[float],
    constraints: Mapping[float, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    try:
        baseline = complete_offer(dict(case), dict(base_terms))
    except (KeyError, TypeError, ValueError) as exc:
        raise PackageInputError(f"case or supplier terms cannot form a package baseline: {exc}") from exc

    fields = list(case["negotiable"])

    seen: set[str] = set()
    result: list[dict[str, Any]] = []
    for price in prices:
        choices: list[list[Any]] = []
        for field in fields:
            if field == "unit_price":
                choices.append([price])
                continue
            if field in constraints.get(price, {}):
                choices.append([constraints[price][field]])
                continue
            options = case.get("term_options", {}).get(field)
            choices.append(list(options) if options else [baseline.get(field)])
        for values in itertools.product(*choices):
            raw_terms = dict(zip(fields, values, strict=True))
            try:
                terms = complete_offer(dict(case), raw_terms)
            except (KeyError, TypeError, ValueError) as exc:
                raise PackageInputError(f"could not complete generated package: {exc}") from exc
            signature = json.dumps(terms, sort_keys=True, default=str, separators=(",", ":"))
            if signature not in seen:
                seen.add(signature)
                result.append(terms)
    return result


def _normalize_constraints(
    case: Mapping[str, Any], prices: list[float], constraints: Mapping[float, Mapping[str, Any]] | None
) -> dict[float, dict[str, Any]]:
    if constraints is None:
        return {}
    if not isinstance(constraints, Mapping):
        raise PackageInputError("term_constraints_by_price must be a mapping or None")
    normalized: dict[float, dict[str, Any]] = {}
    negotiable = set(case["negotiable"])
    for raw_price, terms in constraints.items():
        if not isinstance(raw_price, (int, float)) or isinstance(raw_price, bool):
            raise PackageInputError("term_constraints_by_price keys must be numeric prices")
        price = round(float(raw_price), 2)
        if price not in prices:
            raise PackageInputError(f"term constraint price {price} is not in candidate_unit_prices")
        if not isinstance(terms, Mapping):
            raise PackageInputError(f"term constraints for price {price} must be a mapping")
        fields = set(terms)
        unknown = fields - negotiable
        if unknown or "unit_price" in fields:
            names = ", ".join(sorted(unknown | ({"unit_price"} if "unit_price" in fields else set())))
            raise PackageInputError(f"term constraints contain unsupported fields: {names}")
        for field, value in terms.items():
            options = case.get("term_options", {}).get(field)
            if options and value not in options:
                raise PackageInputError(f"term constraint {field}={value!r} is not an allowed case option")
        normalized[price] = dict(terms)
    return normalized


def _buyer_rank(package: Mapping[str, Any]) -> tuple[float, str]:
    return (
        float(package["evaluation"]["buyer"]["total_cost"]),
        json.dumps(package["terms"], sort_keys=True, default=str, separators=(",", ":")),
    )


def _select_price_distinct(candidates: list[dict[str, Any]], max_packages: int) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    seen_prices: set[float] = set()
    for candidate in candidates:
        price = candidate["terms"]["unit_price"]
        if price not in seen_prices:
            selected.append(candidate)
            seen_prices.add(price)
        if len(selected) == max_packages:
            return selected
    for candidate in candidates:
        if candidate not in selected:
            selected.append(candidate)
        if len(selected) == max_packages:
            break
    return selected
