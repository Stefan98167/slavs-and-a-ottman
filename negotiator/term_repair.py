"""One bounded restoration trade after a price target changes other terms.

This does not infer a supplier preference. It offers a price concession for a
term we already requested, only when the buyer retains at least half the
modeled benefit. The supplier still has to agree to the complete package.
"""

import math
from copy import deepcopy

from .evaluator import evaluate_deal

REPAIR_MARKER = "In exchange for restoring the earlier requested term"


def restoration_packages(case, offer, previous_sheets, events):
    if any(event.get("from") == "buyer" and REPAIR_MARKER in str(event.get("body", ""))
           for event in events):
        return []
    current = {field: offer["closed_terms"][field] for field in case["negotiable"]
               if field in offer["closed_terms"]}
    if set(current) != set(case["negotiable"]):
        return []
    standard = offer["standard"]
    candidates = []
    for sheet in previous_sheets:
        prior = sheet.get("terms", {})
        if prior.get("unit_price", 0) < current["unit_price"]:
            continue
        for field in case["negotiable"]:
            if field == "unit_price" or field not in prior or prior[field] == current[field]:
                continue
            terms = {**deepcopy(current), field: deepcopy(prior[field])}
            evaluation = evaluate_deal(case, terms, standard)
            if not evaluation["valid_for_negotiation"]:
                continue
            cost = evaluation["buyer"]["total_cost"]
            benefit = offer["standing_cost"] - cost
            if benefit <= 0:
                continue
            slope = evaluate_deal(case, {**terms, "unit_price": terms["unit_price"] + 1}, standard)
            per_euro = slope["buyer"]["total_cost"] - cost
            if per_euro <= 0:
                continue
            ceiling = min(prior["unit_price"], current["unit_price"] + benefit / (2 * per_euro))
            terms["unit_price"] = math.floor((ceiling + 1e-9) * 100) / 100
            if terms["unit_price"] <= current["unit_price"]:
                continue  # A reciprocal trade must actually give something back.
            evaluation = evaluate_deal(case, terms, standard)
            final_cost = evaluation["buyer"]["total_cost"]
            if (not evaluation["valid_for_negotiation"] or final_cost > offer["reservation_cost"]
                    or final_cost > offer["standing_cost"] - benefit / 2 + 0.01):
                continue
            candidate = {"terms": terms, "evaluation": evaluation,
                         "restored_field": field, "rationale": "bounded restoration of a previously requested term"}
            if not any(item["terms"] == terms for item in candidates):
                candidates.append(candidate)
    return sorted(candidates, key=lambda item: item["evaluation"]["buyer"]["total_cost"])[:3]
