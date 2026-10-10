"""Tentative dialogue signals, never supplier-profile or hidden-floor estimates."""

import re

from arena_kit.cost import closing_terms
from arena_kit.docs import standard_terms

from .evaluator import evaluate_deal


def supplier_sentences(message):
    """Narrow first-hand text only; unfamiliar/quoted language stays unused."""
    if message.get("from") in {"buyer", "arena"} or not message.get("message_id"):
        return []
    return [sentence.strip() for sentence in re.split(r"(?<=[.!?])\s+|[\r\n]+", str(message.get("body") or ""))
            if not re.search(r'["“”>]|\b(?:you said|you wrote|hypothetically|suppose|if we|might)\b', sentence, re.I)]


def response_signal(case, events):
    """One explicit freeze or three comparable response observations.

    The 0.25% threshold is an uncalibrated exploration trigger, not a floor.
    Changed non-price terms or renewed movement break the comparison window.
    """
    freeze = None
    observations, seen = [], set()
    buyer_since = True
    for index, event in enumerate(events):
        if event.get("from") == "buyer":
            buyer_since = True
            continue
        if event.get("from") == "arena":
            continue
        for sentence in supplier_sentences(event):
            if re.search(r"\bwe (?:can|are now able to) (?:reduce|lower) (?:our |the )?price", sentence, re.I):
                freeze = None
            elif re.search(r"\b(?:we (?:cannot|will not|are unable to) (?:accommodate further price reductions|"
                           r"(?:reduce|lower) (?:our |the )?price)|head office has frozen all price reductions|"
                           r"our price is fixed)\b",
                           sentence, re.I):
                freeze = {"kind": "explicit_price_constraint", "sources": [event["message_id"]]}
        sheets = event.get("term_sheets") or []
        if not sheets or not buyer_since:
            continue
        sheet = sheets[0]
        identity = (event.get("message_id"), sheet.get("term_sheet_id"))
        if not all(identity) or identity in seen:
            continue
        seen.add(identity)
        buyer_since = False
        try:
            standard = standard_terms([m for m in events[:index + 1] if m.get("from") not in {"buyer", "arena"}])
            terms = {**{k: v for k, v in standard.items() if k in case["negotiable"]}, **sheet["terms"]}
            if any(k not in terms for k in case["negotiable"]):
                observations = []
                continue
            evaluation = evaluate_deal(case, terms, standard)
            if not evaluation["valid_for_negotiation"]:
                observations = []
                continue
            closed = closing_terms(case, evaluation["final_terms"], standard)
            basis = {k: v for k, v in closed.items() if k != "unit_price"}
            if observations and observations[-1]["basis"] != basis:
                observations = []
            observations.append({"basis": basis, "price": closed["unit_price"], "source": event["message_id"]})
        except (KeyError, TypeError, ValueError):
            observations = []
    if freeze:
        return freeze
    if len(observations) >= 3:
        recent = observations[-3:]
        changes = [(a["price"] - b["price"]) / a["price"] * 100
                   for a, b in zip(recent, recent[1:], strict=False)]
        if all(0 <= change <= 0.25 for change in changes):
            return {"kind": "diminishing_progress", "sources": [x["source"] for x in recent],
                    "concessions_pct": changes, "threshold_pct": 0.25}
    return None
