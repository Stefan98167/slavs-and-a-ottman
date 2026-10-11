"""Buyer-side proposal limits, independent of supplier motive interpretation."""

import json
import math

from .evaluator import evaluate_deal


def finite_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def reservation_cost(case, evaluation):
    """Unknown or malformed authorization never becomes an unlimited budget."""
    buyer = case.get("buyer", {})
    alternative = buyer.get("alternative")
    if alternative is not None and not isinstance(alternative, dict):
        return 0.0
    if alternative and alternative.get("kind") != "none":
        cost = evaluation["buyer"].get("alternative_cost")
        return cost if finite_number(cost) and cost > 0 else 0.0
    factors = [buyer.get(key) for key in ("need_per_year", "horizon_years", "fallback_unit_price")]
    risk = buyer.get("fallback_risk_pct", 0)
    if not all(finite_number(x) and x > 0 for x in factors) or not finite_number(risk) or risk < 0:
        return 0.0
    bound = math.prod(factors) * (1 + risk / 100)
    return round(bound, 2) if math.isfinite(bound) else 0.0


def select_proposal(case, offer, packages, events, ceiling=None, supplier_economics=None,
                    max_packages=1):
    """Select safe new packages; never give back an available safe deal's value.

    The default remains a single proposal. A caller may explicitly request a
    small menu of up to three alternatives for controlled experiments.
    """
    if type(max_packages) is not int or not 1 <= max_packages <= 3:
        raise ValueError("max_packages must be an integer from 1 to 3")
    seen = {json.dumps(sheet.get("terms"), sort_keys=True) for event in events
            if event.get("from") == "buyer" for sheet in event.get("term_sheets", [])}
    limit = offer["reservation_cost"]
    if ceiling is not None:
        limit = min(limit, ceiling)
    if offer["acceptable"]:
        limit = min(limit, offer["standing_cost"])
    retained, excluded = [], []
    for package in packages:
        terms = package["terms"]
        check = evaluate_deal(case, terms, offer["standard"], supplier_economics)
        reason = None
        if set(terms) != set(case["negotiable"]) or not check["valid_for_negotiation"]:
            reason = "invalid or incomplete package"
        elif check["buyer"]["total_cost"] > limit + 0.001:
            reason = "reservation or current safe offer cost ceiling"
        elif json.dumps(terms, sort_keys=True) in seen:
            reason = "already sent in this thread"
        elif offer["acceptable"] and all(terms.get(k) == offer["closed_terms"].get(k) for k in terms):
            reason = "already available as standing offer"
        if reason:
            excluded.append({"terms": terms, "reason": reason})
        else:
            retained.append({**package, "evaluation": check})
    retained.sort(key=lambda item: item["evaluation"]["buyer"]["total_cost"])
    return retained[:max_packages], excluded
