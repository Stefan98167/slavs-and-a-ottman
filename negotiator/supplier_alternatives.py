"""Promote a supplier's current structured alternative into a standing offer.

The API documents acceptance of the standing ID, not arbitrary alternative IDs.
Do not directly accept an alternate or reconstruct terms from prose. Send its
exact, complete, valid package once and request a matching standing quote.
"""

from copy import deepcopy

from .evaluator import evaluate_deal

ALTERNATIVE_MARKER = "Please make your listed alternative our standing offer"


def supplier_alternative_package(case, offer, events, supplier_economics=None):
    message = next((event for event in reversed(events) if event.get("from") not in {"buyer", "arena"}), {})
    if message.get("status") != "open":
        return None
    already_requested = [sheet.get("terms") for event in events
                         if event.get("from") == "buyer" and ALTERNATIVE_MARKER in str(event.get("body", ""))
                         for sheet in event.get("term_sheets", [])]
    candidates = []
    for sheet in (message.get("term_sheets") or [])[1:]:
        terms = sheet.get("terms") or {}
        if set(terms) != set(case["negotiable"]) or terms in already_requested:
            continue
        evaluated = evaluate_deal(case, terms, offer["standard"], supplier_economics)
        if not evaluated["valid_for_negotiation"]:
            continue
        cost = evaluated["buyer"]["total_cost"]
        if cost > offer["reservation_cost"] or cost >= offer["standing_cost"] - 0.01:
            continue
        candidates.append({"terms": deepcopy(terms), "evaluation": evaluated,
                           "source_offer_id": sheet.get("term_sheet_id"),
                           "rationale": "supplier supplied a complete cheaper alternative; seek standing confirmation"})
    return min(candidates, key=lambda item: item["evaluation"]["buyer"]["total_cost"], default=None)
