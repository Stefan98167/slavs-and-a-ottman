"""Cost explicit supplier-invited exchanges without inferring hidden motives.

Used after the ordinary price ladder stalls. A higher price shares at most
half the modeled buyer benefit of one changed term. Index variants retain the
supplier's offered series/share/base and only negotiate an allowed deadband.
One message per thread; no promise that a proposal will be accepted.
"""

import math
import re
from copy import deepcopy

from .evaluator import evaluate_deal
from .response_signal import response_signal

RESPONSE_TRADE_MARKER = "For this alternative package, we offer a higher price"


def response_trade_packages(case, offer, events, invited_fields, supplier_economics=None):
    if not any(event.get("from") == "buyer" and event.get("term_sheets") for event in events):
        return []
    if any(event.get("from") == "buyer" and RESPONSE_TRADE_MARKER in str(event.get("body", ""))
           for event in events):
        return []
    current = {field: deepcopy(offer["closed_terms"][field]) for field in case["negotiable"]
               if field in offer["closed_terms"]}
    if set(current) != set(case["negotiable"]):
        return []
    message = next((event for event in reversed(events) if event.get("from") not in {"buyer", "arena"}), {})
    price_linked = re.search(
        r"(?:higher|increas\w*).{0,45}\bprice\b|\bprice\b.{0,45}(?:higher|increas\w*)",
        str(message.get("body") or ""), re.I,
    )
    signal = response_signal(case, events, supplier_economics)
    candidates = []
    for field in case["negotiable"]:
        if field == "unit_price":
            continue
        if field == "index_clause":
            quoted = current[field]
            if not isinstance(quoted, dict):
                continue
            options = [value for value in case.get("term_options", {}).get(field, [])
                       if isinstance(value, dict)
                       and all(value.get(key) == quoted.get(key)
                               for key in ("series", "material_share", "base_month"))
                       and isinstance(value.get("deadband_pct"), (int, float))
                       and isinstance(quoted.get("deadband_pct"), (int, float))
                       and value["deadband_pct"] > quoted["deadband_pct"]]
        elif field in invited_fields and (price_linked or signal):
            options = case.get("term_options", {}).get(field, [])
        elif signal and field == "payment_days":
            # A one-shot commercial experiment after observed stalling, not a
            # cash profile: request later payment in return for a higher price.
            options = case.get("term_options", {}).get(field, [])
        else:
            continue
        for value in options:
            if value == current[field]:
                continue
            # Never buy unwanted extra volume/duration even if a cost model
            # clips commitments beyond the buyer's horizon.
            if field == "volume_per_year" and value > case["buyer"]["need_per_year"]:
                continue
            if field == "contract_months" and value > 12 * case["buyer"]["horizon_years"]:
                continue
            terms = {**deepcopy(current), field: deepcopy(value)}
            evaluation = evaluate_deal(case, terms, offer["standard"], supplier_economics)
            if not evaluation["valid_for_negotiation"]:
                continue
            cost = evaluation["buyer"]["total_cost"]
            benefit = offer["standing_cost"] - cost
            if benefit <= 0:
                continue
            higher = evaluate_deal(
                case, {**terms, "unit_price": current["unit_price"] + 1}, offer["standard"], supplier_economics
            )
            slope = higher["buyer"]["total_cost"] - cost
            if slope <= 0:
                continue
            terms["unit_price"] = math.floor((current["unit_price"] + benefit / (2 * slope) + 1e-9) * 100) / 100
            if terms["unit_price"] <= current["unit_price"]:
                continue
            final = evaluate_deal(case, terms, offer["standard"], supplier_economics)
            if (not final["valid_for_negotiation"] or final["buyer"]["total_cost"] > offer["reservation_cost"]
                    or final["buyer"]["total_cost"] > offer["standing_cost"] - benefit / 2 + 0.01):
                continue
            candidates.append({"terms": terms, "evaluation": final, "changed_field": field,
                               "source_offer_id": offer["offer_id"],
                               "response_signal": signal,
                               "rationale": "supplier-invited or quoted-index trade; buyer retains half the benefit"})
    return sorted(candidates, key=lambda item: item["evaluation"]["buyer"]["total_cost"])[:3]
