"""Conservative price-ladder and reciprocal-term policy for package generation."""

from __future__ import annotations

import math
import operator
from collections.abc import Mapping
from typing import Any

from arena_kit.cost import closing_terms, snap, total_cost, with_supplier_options

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
    give-get: the lowest price is paired with earlier payment or a longer
    commitment; higher prices retain the baseline terms. Never give the
    supplier both a higher price and an extra concession for nothing in return.

    ``supplier_profile`` is Jonas's structured contract, not raw evidence.
    The policy reads only a dimension's ``state`` and treats every missing,
    malformed, or non-``likely`` value as unknown. An unknown profile keeps a
    conservative price-only ladder by pinning non-price negotiable terms to
    the supplier's quote, except where a buyer must-have requires repair or a
    buyer-approved volume/duration closes a cheaper coverage gap. These buyer
    requirements do not imply anything about the supplier's motivation.

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
    case = with_supplier_options(case, supplier_standard_terms or {})
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
    # Start from supplied commercial terms. A missing supplier profile is not
    # permission to invent payment or delivery preferences. Buyer must-haves
    # and uncovered demand are separate, explicit reasons to amend terms.
    try:
        baseline_terms = closing_terms(
            dict(case), dict(supplier_offer_terms), dict(supplier_standard_terms or {})
        )
        conservative_terms = {
            field: snap(dict(case), field, baseline_terms.get(field))
            for field in case.get("negotiable", [])
            if field != "unit_price"
        }
        quoted_terms = dict(conservative_terms)
    except (KeyError, TypeError, ValueError) as exc:
        raise PackageInputError(f"could not establish conservative package terms: {exc}") from exc
    constraints: dict[float, dict[str, Any]] = {
        price: dict(conservative_terms) for price in prices
    }
    rationales: dict[float, list[str]] = {
        price: _buyer_required_terms(case, constraints[price], price, supplier_standard_terms or {})
        for price in prices
    }
    buyer_term_reasons = list(dict.fromkeys(reason for reasons in rationales.values() for reason in reasons))

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
            if value is not None and value > quoted_terms.get(field, value):
                supplier_friendly[field] = value

    if supplier_friendly and len(prices) > 1:
        for price in prices[:1]:
            constraints[price].update(supplier_friendly)
            if "payment_days" in supplier_friendly:
                rationales[price].append("earlier payment in return for the lower package price")
            if any(field in supplier_friendly for field in ("contract_months", "volume_per_year")):
                rationales[price].append("greater commitment in return for the lower package price")
    elif len(prices) == 1:
        supplier_friendly = {}  # Keep the baseline when rounding leaves no reciprocal price choice.

    quality_terms = {}
    if _profile_present(profile, "quality_sensitive") and "ppm_commitment" in negotiable_fields:
        supported = profile["quality_sensitive"].get("supported_terms") or {}
        ceiling = supported.get("ppm_commitment") if isinstance(supported, Mapping) else None
        current = quoted_terms.get("ppm_commitment")
        if _nonnegative_number(ceiling) and _nonnegative_number(current):
            options = [value for value in case.get("term_options", {}).get("ppm_commitment", [])
                       if _nonnegative_number(value) and ceiling <= value < current]
            if options:
                quality_terms["ppm_commitment"] = min(options)
                for price in prices[1:]:
                    constraints[price].update(quality_terms)
                    rationales[price].append("a supported quality guarantee for a less aggressive price ask")

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
    if quality_terms:
        trade_hypotheses.append({
            "profile_dimension": "quality_sensitive",
            "buyer_gives": {},
            "supplier_gives": quality_terms,
            "supplier_gets": "a less aggressive price ask",
            "rationale": "the supplier's explicit quality guarantee in return for a higher package price",
            "evidence": _profile_evidence(profile, "quality_sensitive"),
        })
    applied_dimensions = {item["profile_dimension"] for item in trade_hypotheses}
    if profile_used["price_rigid"]:
        applied_dimensions.add("price_rigid")
    plan = {
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
        "buyer_term_reasons": buyer_term_reasons,
    }
    recheck_buyer_terms(case, plan, supplier_offer_terms, supplier_standard_terms or {})
    return plan


def recheck_buyer_terms(case, plan, offered, standard):
    """Re-evaluate coverage after repricing or changing payment/quality terms.

    Explicit supplier-profile commitments remain proposals backed by that
    profile. Pure buyer-coverage changes must save money at the actual price,
    not the earlier price from which a ladder happened to be constructed.
    """
    case = with_supplier_options(case, standard)
    quoted = closing_terms(case, dict(offered), standard)
    supported = {field for trade in plan["trade_hypotheses"]
                 if trade["profile_dimension"] == "capacity_sensitive" for field in trade["buyer_gives"]}
    reasons = []
    for price, terms in plan["term_constraints_by_price"].items():
        for field in ("contract_months", "volume_per_year"):
            if field in terms and field not in supported:
                terms[field] = snap(case, field, quoted.get(field))
        reasons.extend(_buyer_required_terms(case, terms, price, standard))
    plan["buyer_term_reasons"] = list(dict.fromkeys(reasons))


_MUST_HAVE_OPS = {
    "<=": operator.le, "<": operator.lt, ">=": operator.ge,
    ">": operator.gt, "==": operator.eq, "!=": operator.ne,
}


def _buyer_required_terms(case, terms, opening_price, standard):
    """Repair explicit buyer constraints, then close cost-saving coverage gaps.

    This does not assert a supplier preference or that a proposed commitment
    has already been accepted by the supplier.
    """
    buyer = case.get("buyer", {})
    reasons = []
    negotiable = set(case.get("negotiable", []))
    must_haves = buyer.get("must_haves", [])
    for field in dict.fromkeys(
        requirement.get("field") for requirement in must_haves
        if isinstance(requirement, Mapping)
    ):
        if field not in negotiable or field == "unit_price":
            continue
        requirements = [item for item in must_haves if item.get("field") == field]
        current = terms.get(field)
        if _meets_requirements(current, requirements):
            continue
        options = case.get("term_options", {}).get(field) or []
        valid = [value for value in options if _meets_requirements(value, requirements)]
        if not valid:
            continue  # The generator will correctly reject an unrepairable sheet.
        terms[field] = min(valid, key=lambda value: _distance(value, current))
        reasons.append(f"{field.replace('_', ' ')} adjusted to meet the buyer must-have")

    for field, ceiling in (
        ("volume_per_year", buyer.get("need_per_year")),
        ("contract_months", 12 * buyer["horizon_years"] if _positive_number(buyer.get("horizon_years")) else None),
    ):
        current = terms.get(field)
        options = case.get("term_options", {}).get(field) or []
        if field not in negotiable or not _positive_number(ceiling) or not _positive_number(current):
            continue
        available = [value for value in options if _positive_number(value) and current < value <= ceiling]
        if not available:
            continue
        candidate = max(available)
        before = total_cost(case, {**terms, "unit_price": opening_price}, standard)
        proposed = {**terms, field: candidate, "unit_price": opening_price}
        after = total_cost(case, proposed, standard)
        if math.isfinite(before) and math.isfinite(after) and after < before - 0.01:
            terms[field] = candidate
            reasons.append(f"{field.replace('_', ' ')} covers more of the buyer's stated need")
    return reasons


def _meets_requirements(value, requirements):
    for item in requirements:
        compare = _MUST_HAVE_OPS.get(item.get("op"))
        if compare is None or (value is None and item.get("op") not in ("==", "!=")):
            return False
        try:
            if not compare(value, item.get("value")):
                return False
        except TypeError:
            return False
    return True


def _distance(value, current):
    if isinstance(value, (int, float)) and isinstance(current, (int, float)):
        return (abs(value - current), value)
    return (value != current, str(value))


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
        "cash_sensitive": ("payment_days", "earlier payment"),
        "capacity_sensitive": ("contract_months/volume_per_year", "greater commitment"),
    }
    for dimension, (give, get) in mappings.items():
        relevant = [field for field in give.split("/") if field in supplier_friendly]
        if not relevant or not _profile_present(profile, dimension):
            continue
        hypotheses.append({
            "profile_dimension": dimension,
            "buyer_gives": {field: supplier_friendly[field] for field in relevant},
            "supplier_gets": get,
            "buyer_gets": "the lower package price",
            "rationale": f"{get} in return for the lower package price",
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
