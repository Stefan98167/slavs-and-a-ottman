"""Answer price-evidence requests without turning buyer data into supplier motives.

Follow the Arena's evidence contract: case-referenced quotes or 2--8 same-part
purchase orders, not arbitrary historical quote IDs. A historical price is
descriptive context, never a supplier cost floor. Missing context produces an
honest commercial explanation. Buyer records never establish supplier motives.
"""

import base64
import math
import re
from datetime import date


def source_document_reply(events, records):
    """Share only previously cited, verified supplier-authored archive documents."""
    message = next((event for event in reversed(events) if event.get("from") not in {"buyer", "arena"}), {})
    body = str(message.get("body") or "")
    direct = r"\b(?:share|send|provide|attach)\b.{0,160}\b(?:document|letter|email|source)\b"
    missing = r"\b(?:document|letter|email|source)\b.{0,40}\b(?:not (?:included|attached|provided)|missing)\b"
    requests = [sentence for sentence in re.split(r"(?<=[.!?])\s+|[\r\n]+", body)
                if not re.search(r'["“”>]|\b(?:do not|don.t|not asking|no need|you wrote|you said)\b', sentence, re.I)
                and (re.search(missing, sentence, re.I) or (
                    re.search(r"\b(?:please|could you|can you|would you|we (?:ask|need|request))\b", sentence, re.I)
                    and re.search(direct, sentence, re.I)))]
    if not requests:
        return None
    cited = {ref for event in events if event.get("from") == "buyer" for ref in event.get("refs", [])}
    already_shared = {att.get("name") for event in events if event.get("from") == "buyer"
                      for att in event.get("attachments", [])}
    attachments, refs = [], []
    for record in records:
        info = record.get("Information") or {}
        ref, content = info.get("id"), info.get("document_text")
        if ref not in cited or not info.get("archive_source") or not isinstance(content, str):
            continue
        name = re.sub(r"[^\w.-]", "_", ref) + ".md"
        if name in already_shared:
            continue
        attachments.append({"name": name, "type": "md", "content_b64": base64.b64encode(content.encode()).decode()})
        refs.append(ref)
        if len(attachments) == 2:
            break
    if not attachments:
        return None
    return {"refs": refs, "attachments": attachments, "text": (
        "As requested, we attach the supplier-authored source excerpt(s) we cited: " + ", ".join(refs)
        + ". These are the statements behind our earlier reference, not independent cost verification."
    )}


def price_evidence_reply(case, supplier_id, events, package=None, *, proactive=False):
    """Cite safe price history on request, or proactively on the opening counter.

    Proactive use prefers a lower case-referenced quote. Otherwise it requires two
    recent, distinct same-supplier POs that are each at least 1% below the current
    quote. Historical prices are transactions, not supplier cost floors or proof
    of identical terms.
    """
    supplier_message = next((event for event in reversed(events) if event.get("from") not in {"buyer", "arena"}), {})
    body = str(supplier_message.get("body") or "")
    evidence = r"(?:data|evidence|basis|justif\w*|support\w*|benchmark\w*)"
    price = r"(?:price|target)"
    direct = r"\bwhich figures\b.{0,35}\bbased on\b|\bplease (?:send|provide|share) (?:us )?the data\b"
    requests = []
    for sentence in re.split(r"(?<=[.!?])\s+|[\r\n]+", body):
        if re.search(r'["“”>]|\b(?:do not|don.t|not asking|no need|you wrote|you said)\b', sentence, re.I):
            continue
        asks = re.search(r"\b(?:please (?:send|provide|share)|(?:can|could|would) you (?:please )?"
                         r"(?:send|provide|share)|we (?:ask|request|need|require)|what|which)\b", sentence, re.I)
        if asks and re.search(rf"{evidence}.{{0,80}}{price}|{price}.{{0,80}}{evidence}|{direct}", sentence, re.I):
            requests.append(sentence)
    if not requests and not proactive:
        return None
    parts = case.get("parts") or []
    # Ambiguous multi-part scope is not comparable enough for a numeric citation.
    quotes, orders = [], []
    try:
        cutoff = date.fromisoformat(case.get("as_of") or date.today().isoformat())
    except (TypeError, ValueError):
        cutoff = date.today()
    facts = case.get("facts") or {}
    alternative = case.get("buyer", {}).get("alternative") or {}
    quote_refs = set(case.get("refs") or []) | {alternative.get("ref")}
    refs = set(facts) | quote_refs | (set(package.ids("po:")) if package else set())
    used = {ref for event in events if event.get("from") == "buyer" for ref in event.get("refs", [])}
    for ref in sorted(ref for ref in refs - used if isinstance(ref, str)):
        is_quote = ref.startswith("quote:") and ref in quote_refs
        if not (is_quote or ref.startswith("po:")) or len(parts) != 1:
            continue
        fact = facts.get(ref) or (package.lookup(ref) if package else None) or {}
        metadata = package.record(ref) if package else {}
        if not fact.get("supplier") or fact.get("part") != parts[0]:
            continue
        if not is_quote and (fact.get("supplier") != supplier_id or metadata.get("price_note") == "stale_condition"):
            continue
        currency = fact.get("currency") or metadata.get("currency")
        unit = fact.get("price_unit", metadata.get("price_unit"))
        value = fact.get("unit_price")
        if currency != "EUR" or isinstance(unit, bool) or unit not in (1, "1"):
            continue
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
            continue
        try:
            dated = date.fromisoformat(fact.get("date") or "")
        except (TypeError, ValueError):
            continue
        if dated <= cutoff:
            (quotes if is_quote else orders).append((dated, ref, value, metadata))
    current = (supplier_message.get("term_sheets") or [{}])[0].get("terms", {}).get("unit_price", 0)
    quotes = [row for row in quotes if row[2] < current]
    if quotes:
        dated, ref, value, _metadata = min(quotes, key=lambda row: row[2])
        return {"refs": [ref], "kind": "case_quote", "text": (
            f"The case's reference quote {ref} lists EUR {value:g} per one unit for this part. "
            "Its other commercial terms may differ; this is price context, not your cost floor. "
            "Please review our complete proposal against this reference and let us know the best "
            "package you can approve."
        )}
    if proactive:
        # A single old transaction is weak leverage. Require two distinct recent
        # purchase orders, each materially below the quote, and never substitute
        # another supplier's order history.
        if not isinstance(current, (int, float)) or isinstance(current, bool) or not math.isfinite(current):
            return None
        eligible = [row for row in orders if row[2] <= current * 0.99]
        chosen, seen_orders = [], set()
        for row in sorted(eligible, key=lambda item: item[0], reverse=True):
            po_number = row[3].get("po_number") or row[1]
            if po_number in seen_orders:
                continue
            seen_orders.add(po_number)
            chosen.append(row)
            if len(chosen) == 2:
                break
        if len(chosen) < 2:
            return None
    elif len(orders) >= 2:
        chosen = sorted(orders, key=lambda item: item[0], reverse=True)[:2]
    else:
        chosen = []
    if chosen:
        refs = [row[1] for row in chosen]
        facts_text = " and ".join(
            f"EUR {row[2]:g} per unit on {row[0].isoformat()} ({row[1]})" for row in chosen
        )
        return {"refs": refs, "kind": "purchase_order_history", "text": (
            f"Our recent purchase orders for this same part record {facts_text}. These are prior "
            "transaction prices; their volumes or other terms may differ, and they are not a claim "
            "about your costs. Please review our complete proposal against this history and tell us "
            "the best package you can approve."
        )}
    if proactive:
        return None
    return {"refs": [], "kind": "commercial_proposal", "text": (
        "Regarding the basis for our target: this is a commercial proposal, not a claim about your costs. "
        "We have no verified comparable price benchmark to cite here. Please indicate the package you can approve."
    )}
