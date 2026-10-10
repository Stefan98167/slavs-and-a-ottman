"""Arena-compatible agent driven by supplier offers and parsed supplier context only."""

from decimal import Decimal, InvalidOperation
import re

from arena_kit.docs import standard_terms
from arena_kit.play import latest, live_threads, standing

from .policy import SupplierOnlyPolicy


_PRICE = re.compile(r"^\+?\d+(?:[.,]\d+)?$")


def _price(value):
    """Parse an unambiguous positive decimal from a supplier term sheet."""
    if isinstance(value, bool) or not _PRICE.fullmatch(str(value).strip()):
        return None
    try:
        price = Decimal(str(value).strip().replace(",", "."))
    except InvalidOperation:
        return None
    return price if price.is_finite() and price > 0 else None


def _opening_price(events):
    for event in events:
        if event.get("from") == "buyer":
            continue
        for sheet in (event.get("term_sheets") or [])[:1]:
            if (price := _price((sheet.get("terms") or {}).get("unit_price"))) is not None:
                return price
    return None


def _previous_supplier_price(events):
    supplier_prices = []
    for event in events:
        if event.get("from") == "buyer":
            continue
        for sheet in (event.get("term_sheets") or [])[:1]:
            price = _price((sheet.get("terms") or {}).get("unit_price"))
            if price is not None:
                supplier_prices.append(price)
    return supplier_prices[-2] if len(supplier_prices) > 1 else None


def _previous_buyer_price(events):
    for event in reversed(events):
        if event.get("from") != "buyer":
            continue
        for sheet in (event.get("term_sheets") or [])[:1]:
            if (price := _price((sheet.get("terms") or {}).get("unit_price"))) is not None:
                return price
    return None


def _csv_context(events, part_id=None):
    """Find unambiguous, supplier-scoped CSV context from this thread."""
    contexts = []
    for event in events:
        if event.get("from") == "buyer":
            continue
        for attachment in event.get("attachments") or []:
            if attachment.get("csv_parse_error"):
                continue
            bundle = attachment.get("supplier_context") or {}
            contexts.extend(bundle.get("contexts") or [])
    if part_id is not None:
        matching = [context for context in contexts if context.get("part_id") == part_id]
        return matching[0] if len(matching) == 1 else None
    if len(contexts) == 1:
        return contexts[0]
    unscoped = [context for context in contexts if context.get("part_id") is None]
    return unscoped[0] if len(unscoped) == 1 else None


def _lead_source(context):
    if not context:
        return None
    evidence = [item for item in context.get("evidence", []) if isinstance(item, dict) and item.get("source")]
    evidence.sort(key=lambda item: item.get("priority") if type(item.get("priority")) is int else 99)
    source = evidence[0].get("source") if evidence else None
    return re.sub(r"[\r\n\x00-\x1f]+", " ", str(source))[:180] if source else None


def _top_argument(context):
    """Return the supplier's highest-ranked explicit evidence row, without inference."""
    if not context:
        return None
    evidence = [item for item in context.get("evidence", []) if isinstance(item, dict)]
    evidence.sort(key=lambda item: item.get("priority") if type(item.get("priority")) is int else 99)
    return evidence[0] if evidence else None


def _evidence_terms(context):
    """Read explicit standard term values from supplier rows; never infer missing values."""
    if not context:
        return {}
    evidence = sorted(
        (item for item in context.get("evidence", []) if isinstance(item, dict)),
        key=lambda item: item.get("priority") if type(item.get("priority")) is int else 99,
    )
    allowed = {"payment_days", "lead_time_days", "incoterm", "currency", "unit_price",
               "volume_per_year", "contract_months", "tooling_eur", "index_clause"}
    integer_fields = {"payment_days", "lead_time_days", "volume_per_year", "contract_months"}
    numeric_fields = {"unit_price", "tooling_eur"}
    terms = {}
    for item in evidence:
        data = item.get("data") or {}
        for field in allowed:
            value = data.get(field)
            if value in (None, ""):
                continue
            if field in integer_fields:
                numeric = _price(value)
                if numeric is None or numeric != numeric.to_integral_value():
                    continue
                value = int(numeric)
            elif field in numeric_fields:
                numeric = _price(value)
                if numeric is None:
                    continue
                value = float(numeric)
            elif not isinstance(value, str):
                continue
            terms.setdefault(field, value)
    return terms


def _history_floor(context, current_terms):
    """Use a supplier's lowest comparable, same-context quote as an auditable anchor."""
    if not context:
        return None, None
    current_currency = str(current_terms.get("currency") or "").strip().upper()
    quotes = []
    for item in context.get("evidence", []):
        if not isinstance(item, dict) or item.get("kind") != "quote":
            continue
        data = item.get("data") or {}
        price = _price(data.get("unit_price"))
        currency = str(data.get("currency") or "").strip().upper()
        if price is None:
            continue
        if current_currency and currency != current_currency:
            continue
        quotes.append((price, item.get("source")))
    if not quotes:
        return None, None
    low, source = min(quotes, key=lambda pair: pair[0])
    return low, source


def _argument_text(context):
    item = _top_argument(context)
    if not item:
        return None
    data = item.get("data") or {}
    # Keep the exact supplier-provided fields and values visible in the negotiation.
    details = "; ".join(f"{key}: {value}" for key, value in list(data.items())[:4])
    if not details:
        return None
    return re.sub(r"[\r\n\x00-\x1f]+", " ", details)[:240]


class SupplierContextAgent:
    """Negotiate using only supplier messages, attachments, and explicit policy settings.

    ``case`` is accepted to satisfy the Arena agent interface and deliberately never read.
    Parsed CSV context supplies explicit terms, ranked supplier arguments, and comparable
    same-part quote history. Price targets adapt to supplier concessions and supplier-stated
    quote history. The agent does not load buyer targets or Arena case data.
    """

    def __init__(self, policy=None):
        self.policy = policy or SupplierOnlyPolicy()
        self.decision_history = []

    def decide(self, case, threads):
        return self._decide(threads)

    def close(self, case, threads):
        """At the deadline, prefer a target offer, then any complete offer over walking away."""
        return self._decide(threads, closing=True)

    def _decide(self, threads, closing=False):
        active = live_threads(threads)
        if not active:
            raise ValueError("No live supplier thread")

        candidates = []
        last_resort_offers = []
        for supplier_id in active:
            events = threads[supplier_id]
            offer_id, terms = standing(events)
            current_price = _price(terms.get("unit_price"))
            opening_price = _opening_price(events)
            rounds = sum(event.get("from") == "buyer" for event in events)
            is_final = latest(events).get("status") == "final_offer"
            std = standard_terms(events)
            context = _csv_context(events, terms.get("part_id"))
            evidence_terms = _evidence_terms(context)
            required = set(terms) | set(evidence_terms)
            for event in events:
                if event.get("from") != "buyer":
                    required.update(event.get("missing_fields") or [])
            # Live term sheets take precedence; CSV rows fill only what the supplier
            # omitted from the active offer and standard terms.
            supplied = {**evidence_terms, **std, **terms}
            missing = sorted(field for field in required if field not in supplied)
            target = None
            history_floor, history_source = _history_floor(context, terms)
            previous_price = _previous_supplier_price(events)
            previous_target = _previous_buyer_price(events)
            if opening_price is not None:
                try:
                    target = self.policy.target_price(
                        opening_price, current_price=current_price,
                        previous_supplier_price=previous_price,
                        previous_buyer_price=previous_target,
                        historical_low=history_floor, rounds=rounds,
                    )
                except ValueError:
                    pass

            complete = bool(offer_id and current_price and target and not missing)
            source = _lead_source(context)
            argument = _argument_text(context)

            if complete and current_price <= target:
                message = {"action": {"type": "accept", "term_sheet_id": offer_id}}
                self._record(supplier_id, offer_id, opening_price, target, current_price,
                             "accept", context, message)
                return {"supplier_id": supplier_id, "message": message}

            if closing or is_final or rounds >= self.policy.max_messages_per_supplier:
                # A valid standing offer is preferable to ending the session with
                # zero. Prefer the offer whose price is closest to its own target;
                # do not rank suppliers by raw prices across different contexts.
                if offer_id and current_price is not None and not missing:
                    gap = ((current_price - target) / opening_price
                           if target is not None and opening_price else Decimal("Infinity"))
                    last_resort_offers.append((gap, supplier_id, offer_id, opening_price,
                                               target, current_price, context))
                continue

            if current_price is None or target is None:
                body = "Please send a clear unit price, currency, price unit, and applicable terms."
                action = "request_quote"
                message = {"body": body, "term_sheets": []}
            elif missing:
                body = f"Please clarify the missing supplier terms: {', '.join(missing)}."
                action = "request_terms"
                message = {"body": body, "term_sheets": []}
            else:
                proposed = {field: supplied[field] for field in required}
                proposed["unit_price"] = float(target)
                rationale = []
                if argument:
                    rationale.append(f"We reviewed your priority information ({argument}).")
                if history_floor is not None:
                    rationale.append(
                        f"Your comparable quote history includes {history_floor}"
                        f"{f' ({history_source})' if history_source else ''}."
                    )
                elif source:
                    rationale.append(f"We reviewed the supplier evidence at {source}.")
                rationale.append(f"Please consider our counter at {target} per unit.")
                body = " ".join(rationale)
                action = "counter_offer"
                message = {
                    "subject": latest(events).get("subject", "Supplier quote"),
                    "body": body[:8000],
                    "term_sheets": [{"terms": proposed}],
                }
            candidates.append((current_price is None, supplier_id, offer_id, opening_price,
                               target, current_price, action, context, message,
                               history_floor, history_source, previous_price, previous_target,
                               argument))

        if candidates:
            # Work a priced quote before a thread that has not yet supplied a price;
            # never compare prices across different suppliers or parts.
            candidate = min(candidates, key=lambda item: item[0])
            (_, supplier_id, offer_id, opening, target, current, action, context, message,
             history_floor, history_source, previous_price, previous_target, argument) = candidate
            self._record(supplier_id, offer_id, opening, target, current, action, context, message)
            self.decision_history[-1].update({
                "previous_supplier_price": float(previous_price) if previous_price is not None else None,
                "previous_buyer_target": float(previous_target) if previous_target is not None else None,
                "supplier_history_low": float(history_floor) if history_floor is not None else None,
                "supplier_history_source": history_source,
                "top_priority_argument": argument,
                "supplier_evidence_terms": _evidence_terms(context),
            })
            return {"supplier_id": supplier_id, "message": message}

        if last_resort_offers:
            _, supplier_id, offer_id, opening, target, current, context = min(
                last_resort_offers, key=lambda item: item[0]
            )
            message = {"action": {"type": "accept", "term_sheet_id": offer_id}}
            self._record(supplier_id, offer_id, opening, target, current,
                         "accept_last_resort", context, message)
            return {"supplier_id": supplier_id, "message": message}

        supplier_id = active[0]
        message = {"action": {"type": "walk_away"}}
        self._record(supplier_id, standing(threads[supplier_id])[0], None, None, None,
                     "walk_away", None, message)
        return {"supplier_id": supplier_id, "message": message}

    def _record(self, supplier_id, offer_id, opening, target, current, action, context, message):
        self.decision_history.append({
            "supplier_id": supplier_id,
            "offer_id": offer_id,
            "action": action,
            "opening_price": float(opening) if opening is not None else None,
            "target_price": float(target) if target is not None else None,
            "current_price": float(current) if current is not None else None,
            "context_part_id": context.get("part_id") if context else None,
            "lead_source": _lead_source(context),
            "input_policy": "supplier_only",
            "message": message,
        })
