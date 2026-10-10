"""Bounded clarification, never a substitute for a binding complete offer.

At most two recovery questions per thread, and at most one question per issue.
The budget is reconstructed from sent messages, so resume/replay is consistent.
No supplier motive, missing commercial value or hidden economics is inferred.
"""

import re

from .response_signal import supplier_sentences

RECOVERY_MARKER = "Please clarify the following quotation issue"
TRADE_MARKER = "Which concrete values and matching price"
MAX_QUESTIONS = 2


def can_clarify(events, issue):
    questions = [event for event in events if event.get("from") == "buyer"
                 and (RECOVERY_MARKER.lower() in str(event.get("body", "")).lower()
                      or TRADE_MARKER.lower() in str(event.get("body", "")).lower())]
    return len(questions) < MAX_QUESTIONS and not any(
        f"[clarification:{issue}]" in str(event.get("body", "")) for event in questions
    )


def unasked_trade_terms(events, fields):
    # Old saved messages have no tags. Recognize their exact introductory term
    # list without treating incidental mentions of another term as a question.
    unasked = []
    for field in fields:
        asked = any(event.get("from") == "buyer"
                    and TRADE_MARKER.lower() in str(event.get("body", "")).lower()
                    and field.replace("_", " ") in str(event.get("body", "")).lower().split(
                        TRADE_MARKER.lower())[0]
                    for event in events)
        if not asked and can_clarify(events, field):
            unasked.append(field)
    return unasked


def capacity_refused(message):
    for sentence in supplier_sentences(message):
        if re.search(r"\b(?:cannot|can't|unable to|not able to)\s+(?:\w+\s+){0,3}"
                     r"(?:supply|deliver|commit|meet|support)\b.{0,65}"
                     r"\b(?:volume|quantity|capacity|units|schedule)\b", sentence, re.I):
            return True
        if re.search(r"\b(?:volume|quantity|capacity)\b.{0,55}\b"
                     r"(?:not feasible|not available|cannot be met)\b", sentence, re.I):
            return True
    return False


def indicative_alternative(message, negotiable):
    # Only the current supplier reply. Never reconstruct historic prices or fill
    # a secondary sheet from the primary offer's different commercial basis.
    for sheet in (message.get("term_sheets") or [])[1:]:
        terms = sheet.get("terms") or {}
        if terms and set(terms) < set(negotiable):
            return True
    return any(re.search(r"\b(?:we (?:can|could) offer|we propose|our alternative)\b"
                         r".{0,100}\b(?:alternative|package|option)\b", sentence, re.I)
               for sentence in supplier_sentences(message))


def recovery_message(issue, details=""):
    requests = {
        "incomplete_offer": "Please provide your complete current standing term sheet, including "
                            "every negotiable field, and a readable quote confirming EUR per item. "
                            "We cannot confirm terms that are missing or ambiguous.",
        "capacity": "You said the requested capacity is not feasible. Please state the volume "
                    "and delivery schedule you can actually commit to, with a matching price "
                    "in one complete standing term sheet. No changed requirement is agreed.",
        "alternative": "Please put your current indicative alternative into one complete "
                       "standing term sheet with all terms and its matching price. "
                       "This is a request for confirmation, not acceptance of unstated terms.",
        "feasibility": "The current quotation does not meet the required contract conditions. "
                       "Please send a complete feasible proposal or identify which condition "
                       "you cannot satisfy. No requirement is waived.",
    }
    return {"subject": "Re: quotation clarification",
            "body": f"{RECOVERY_MARKER} [clarification:{issue}]. {requests[issue]}{details}"}
