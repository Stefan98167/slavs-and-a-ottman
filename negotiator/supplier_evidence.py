"""Normalize supplier quote PDFs, CSV rows, and offer messages into sourced context."""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

from .intelligence import EvidenceInputError, contexts_from_records


_OFFER_ID = re.compile(r"\boffer:[\w.-]+\b", re.IGNORECASE)
_PART_ID = re.compile(r"\bpart:[\w.-]+\b", re.IGNORECASE)
_INDEX_COST_CLAIM = re.compile(
    r"\b(?P<series>[A-Z][A-Z0-9-]*)\s+rose\s+(?P<change>\d+(?:[.,]\d+)?)\s*%"
    r"\s+(?:in|over)\s+(?P<period>[^.]{1,60}?)\s+and\s+is\s+"
    r"(?P<share>\d+(?:[.,]\d+)?)\s*%\s+of\s+(?:our|the)\s+cost\b",
    re.IGNORECASE,
)


def quote_pdf_record(text: str, source: str, supplier_id: str | None = None) -> dict[str, Any]:
    """Convert a supplier quote PDF's structured sections to one provenance record."""
    from arena_kit.docs import quote_terms

    sections = quote_terms(text)
    offer_match = _OFFER_ID.search(text)
    part_match = _PART_ID.search(text)
    offer_id = offer_match.group(0) if offer_match else None
    part_id = part_match.group(0) if part_match else None

    # Retain each source section, while exposing one effective term map for negotiation.
    effective_terms: dict[str, Any] = {}
    for section in ("standard", "fixed", "stated", "agreed"):
        effective_terms.update(sections.get(section) or {})
    information: dict[str, Any] = {
        "kind": "quote" if effective_terms else "document",
        "supplier_id": supplier_id,
        "part_id": part_id,
        "offer_id": offer_id,
        "currency": "EUR" if "unit_price" in effective_terms else None,
        "term_sections": sections,
        "terms": effective_terms,
        "document_text": text[:20000],
        **effective_terms,
    }
    if "unit_price" in effective_terms:
        information.setdefault("price_unit", "each")
    if not effective_terms:
        information["document_text"] = text[:20000]
    return _record(information, source, priority=1 if effective_terms else 3)


def supplier_message_records(message: Mapping[str, Any], supplier_id: str) -> list[dict[str, Any]]:
    """Extract quote-sheet terms and explicit index/cost claims from one supplier email."""
    source = _message_source(message)
    records: list[dict[str, Any]] = []
    body = str(message.get("body") or "")
    if body.strip() and message.get("from") not in {"buyer", "arena"}:
        records.append(_record({"kind": "document", "id": source,
                                "supplier_id": supplier_id, "message_text": body}, source, 3))
    claims: dict[tuple[str, str], dict[str, Any]] = {}

    for match in _INDEX_COST_CLAIM.finditer(body):
        series = match.group("series").upper()
        claims[(series, match.group("change"))] = {
            "kind": "claim",
            "claim_type": "index_change_and_cost_share",
            "series": series,
            "index_change_pct": _number(match.group("change")),
            "time_window": match.group("period").strip(),
            "cost_share_pct": _number(match.group("share")),
            "claim_text": match.group(0),
        }

    for claim in message.get("claims") or []:
        if not isinstance(claim, Mapping):
            continue
        claim_type = str(claim.get("type") or "supplier_claim")
        asserted = claim.get("asserted") if isinstance(claim.get("asserted"), Mapping) else {}
        refs = claim.get("refs") if isinstance(claim.get("refs"), list) else []
        series = next((_series_from_ref(ref) for ref in refs if _series_from_ref(ref)), None)
        change = asserted.get("change_pct")
        key = (series or claim_type, str(change) if change is not None else "")
        normalized = claims.setdefault(key, {
            "kind": "claim",
            "claim_type": claim_type,
            "series": series,
        })
        normalized["structured_claim"] = dict(claim)
        if refs:
            normalized["refs"] = refs
        if change is not None:
            normalized.setdefault("index_change_pct", _number(change))
        for field, value in asserted.items():
            normalized.setdefault(field, value)

    for index, information in enumerate(claims.values()):
        information = {key: value for key, value in information.items() if value is not None}
        information.update({"supplier_id": supplier_id, "claim_id": f"{source}:claim:{index}"})
        records.append(_record(information, source, priority=1))

    for sheet in message.get("term_sheets") or []:
        if not isinstance(sheet, Mapping):
            continue
        terms = sheet.get("terms") if isinstance(sheet.get("terms"), Mapping) else {}
        offer_id = sheet.get("term_sheet_id")
        if not offer_id and not terms:
            continue
        information = {
            "kind": "quote",
            "supplier_id": supplier_id,
            "offer_id": offer_id,
            "terms": dict(terms),
            **dict(terms),
        }
        if "unit_price" in terms:
            information.setdefault("price_unit", "each")
        if str(terms.get("currency") or "").strip():
            information["currency"] = terms["currency"]
        records.append(_record(information, source, priority=1))
    return records


def build_thread_supplier_context(
    events: list[Mapping[str, Any]], supplier_id: str, part_id: str | None = None
) -> dict[str, Any]:
    """Combine all supplier evidence in a thread, preserving the source of every fact."""
    records: list[dict[str, Any]] = []
    for event in events:
        if event.get("from") in {"buyer", "arena"}:
            continue
        # Attachments come first so an attached quote PDF is the primary source for
        # that offer; the email term sheet fills any fields the PDF omitted.
        for attachment in event.get("attachments") or []:
            records.extend(_attachment_records(attachment, supplier_id))
        records.extend(supplier_message_records(event, supplier_id))

    records = _deduplicate(records)
    try:
        contexts = contexts_from_records(records, supplier_id, part_id)
    except EvidenceInputError as exc:
        return {
            "schema": "supplier_context_v1",
            "supplier_id": supplier_id,
            "contexts": [],
            "context_error": str(exc),
        }
    return {"schema": "supplier_context_v1", "supplier_id": supplier_id,
            "records": records, "contexts": contexts}


def context_for_part(bundle: Mapping[str, Any], part_id: str | None = None) -> dict[str, Any] | None:
    contexts = [item for item in bundle.get("contexts", []) if isinstance(item, dict)]
    if part_id is not None:
        matches = [item for item in contexts if item.get("part_id") == part_id]
        return matches[0] if len(matches) == 1 else None
    return contexts[0] if len(contexts) == 1 else None


def _attachment_records(attachment: Mapping[str, Any], supplier_id: str) -> list[dict[str, Any]]:
    records = attachment.get("csv_records")
    if isinstance(records, list):
        output = list(records)
    else:
        output = []
    name = str(attachment.get("name") or "supplier_document")
    source = f"{attachment.get('attachment_id') or name} ({name})"
    text = attachment.get("text")
    if name.lower().endswith(".pdf") and isinstance(text, str):
        output.append(quote_pdf_record(text, source, supplier_id))
    # Preserve a precomputed context from external callers when no raw rows are attached.
    if not output:
        bundle = attachment.get("supplier_context") or {}
        for context in bundle.get("contexts") or []:
            for item in context.get("evidence") or []:
                if not isinstance(item, Mapping):
                    continue
                information = dict(item.get("data") or {})
                information.update({"id": item.get("id"), "kind": item.get("kind", "unknown")})
                output.append(_record(information, str(item.get("source") or source), item.get("priority", 3)))
    return output


def _record(information: Mapping[str, Any], source: str, priority: int) -> dict[str, Any]:
    return {
        "Information": dict(information),
        "Source": source,
        "Priority (Argument wise)": priority,
    }


def _deduplicate(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    output = []
    positions: dict[tuple[str, str], int] = {}
    for record in records:
        information = record.get("Information") or {}
        kind = str(information.get("kind") or ("quote" if "unit_price" in information else "unknown"))
        identity = information.get("id") or information.get("offer_id") or information.get("claim_id")
        if identity is None:
            identity = record.get("Source")
        key = (kind, str(identity))
        if key not in positions:
            positions[key] = len(output)
            copy = dict(record)
            copy["Information"] = dict(information)
            copy["Information"]["source_refs"] = [record.get("Source")]
            output.append(copy)
            continue
        existing = output[positions[key]]
        existing_info = existing["Information"]
        for field, value in information.items():
            if field not in existing_info or existing_info[field] in (None, ""):
                existing_info[field] = value
        source_refs = existing_info.setdefault("source_refs", [])
        if record.get("Source") not in source_refs:
            source_refs.append(record.get("Source"))
    return output


def _message_source(message: Mapping[str, Any]) -> str:
    return str(message.get("message_id") or message.get("offer_id") or "supplier_message")


def _series_from_ref(ref: Any) -> str | None:
    if not isinstance(ref, str) or not ref.startswith("idx:"):
        return None
    return ref[4:].split("@", 1)[0]


def _number(value: Any) -> float | Any:
    try:
        return float(str(value).replace(",", "."))
    except (TypeError, ValueError):
        return value
