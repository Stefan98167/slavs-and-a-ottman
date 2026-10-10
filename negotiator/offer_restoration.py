"""Ask once to restore a better prior primary quote after a failed experiment.

A historical quote is not an actionable offer. Only its complete negotiable
terms can be proposed again, under current standards, with fresh confirmation.
"""

from copy import deepcopy

from arena_kit.docs import standard_terms

from .evaluator import evaluate_deal
from .response_trades import RESPONSE_TRADE_MARKER

RESTORE_OFFER_MARKER = "Could you renew your earlier quoted package"


def restore_prior_offer(case, offer, events):
    if offer["status"] != "open" or not offer["acceptable"]:
        return None
    if not any(event.get("from") == "buyer" and RESPONSE_TRADE_MARKER in str(event.get("body", ""))
               for event in events):
        return None
    if any(event.get("from") == "buyer" and RESTORE_OFFER_MARKER in str(event.get("body", ""))
           for event in events):
        return None
    candidates = []
    for index, event in enumerate(events[:-1]):
        if event.get("from") in {"buyer", "arena"} or not event.get("term_sheets"):
            continue
        sheet = event["term_sheets"][0]
        if not sheet.get("term_sheet_id") or not event.get("message_id"):
            continue
        try:
            std = standard_terms([m for m in events[:index + 1] if m.get("from") not in {"buyer", "arena"}])
            old = {**std, **sheet.get("terms", {})}
            if any(field not in old for field in case["negotiable"]):
                continue
            terms = {field: deepcopy(old[field]) for field in case["negotiable"]}
            evaluation = evaluate_deal(case, terms, offer["standard"])
            if not evaluation["valid_for_negotiation"]:
                continue
            cost = evaluation["buyer"]["total_cost"]
            if cost >= offer["standing_cost"] - 0.01 or cost > offer["reservation_cost"]:
                continue
            candidates.append({"terms": terms, "evaluation": evaluation,
                               "source_offer_id": sheet["term_sheet_id"], "source_message_id": event["message_id"],
                               "rationale": "request renewal of better previously quoted negotiable terms"})
        except (KeyError, TypeError, ValueError):
            continue
    return min(candidates, key=lambda p: p["evaluation"]["buyer"]["total_cost"], default=None)
