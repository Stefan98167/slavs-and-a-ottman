"""Deterministic ingestion and supplier context from analysis-team evidence JSON.

The reader intentionally knows very little about evidence semantics.  It standardizes the
current analysis export, preserves unfamiliar fields, and limits quote-derived conclusions to
quote history.  In particular, a historical quote is not evidence of supplier pressure or
preferences.
"""

from __future__ import annotations

import json
import math
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any


class EvidenceInputError(ValueError):
    """Raised when an evidence document cannot be read as the expected JSON array."""


_NUMBER = re.compile(r"^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?$")
_WRAPPER_KEYS = {"Information", "Source", "Priority (Argument wise)"}
_PROFILE_DIMENSIONS = (
    "cash_sensitive",
    "capacity_sensitive",
    "price_rigid",
    "quality_sensitive",
)


def load_evidence(source: str | Path | list[object]) -> list[dict[str, Any]]:
    """Load, validate, and normalize an analysis-team evidence array.

    ``source`` can be a path to JSON or an already-loaded list.  Records need only be objects:
    missing or unfamiliar ``Information`` fields remain usable so future evidence types can be
    passed through without changes to this reader.
    """
    if isinstance(source, (str, Path)):
        path = Path(source)
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except OSError as exc:
            raise EvidenceInputError(f"could not read evidence JSON at {path}: {exc}") from exc
        except json.JSONDecodeError as exc:
            raise EvidenceInputError(f"invalid evidence JSON at {path}: {exc.msg}") from exc
    elif isinstance(source, list):
        raw = source
    else:
        raise EvidenceInputError("evidence input must be a JSON path or an already-loaded list")

    if not isinstance(raw, list):
        raise EvidenceInputError("evidence JSON must contain a top-level array")

    normalized: list[dict[str, Any]] = []
    for index, record in enumerate(raw):
        if not isinstance(record, Mapping):
            raise EvidenceInputError(f"evidence record at index {index} must be an object")
        normalized.append(_normalize_record(record))
    return normalized


def filter_evidence(
    evidence: list[Mapping[str, Any]], supplier_id: str, part_id: str | None = None
) -> list[dict[str, Any]]:
    """Return normalized records for ``supplier_id`` and, optionally, ``part_id``.

    The return value is a copy of matching records, so callers may safely add presentation data
    without changing the loaded evidence.
    """
    return [
        dict(record)
        for record in evidence
        if record.get("supplier_id") == supplier_id and (part_id is None or record.get("part_id") == part_id)
    ]


def build_supplier_context(
    evidence: list[Mapping[str, Any]], supplier_id: str, part_id: str | None = None
) -> dict[str, Any]:
    """Build a JSON-serializable, traceable context for one supplier and optional part.

    Only records whose normalized ``kind`` is ``quote`` contribute to ``quote_history``.  The
    profile deliberately remains unknown until a future evidence-specific rule is added.
    """
    matches = filter_evidence(evidence, supplier_id, part_id)
    quotes = [record for record in matches if record.get("kind") == "quote"]

    return {
        "supplier_id": supplier_id,
        "part_id": part_id,
        "evidence": [_context_evidence(record) for record in matches],
        "quote_history": _quote_history(quotes),
        "supplier_profile": {dimension: {"state": "unknown", "confidence": 0.0} for dimension in _PROFILE_DIMENSIONS},
        "evidence_gaps": _evidence_gaps(matches),
    }


def _normalize_record(record: Mapping[str, Any]) -> dict[str, Any]:
    information_value = record.get("Information", {})
    information = _normalize_value(information_value) if isinstance(information_value, Mapping) else {}
    wrapper_fields = {key: _normalize_value(value) for key, value in record.items() if key not in _WRAPPER_KEYS}
    if "Information" in record and not isinstance(information_value, Mapping):
        # A malformed or future non-object payload is retained rather than preventing unrelated
        # evidence from being ingested. It simply cannot supply the standard identity fields.
        wrapper_fields["Information"] = _normalize_value(information_value)
    record_id = information.get("id") or wrapper_fields.get("id")
    return {
        "id": record_id,
        "kind": _evidence_kind(information, wrapper_fields, record_id),
        "supplier_id": information.get("supplier_id") or wrapper_fields.get("supplier_id"),
        "part_id": information.get("part_id") or wrapper_fields.get("part_id"),
        "source": _normalize_value(record.get("Source")),
        "priority": _normalize_value(record.get("Priority (Argument wise)")),
        "data": information,
        "record_fields": wrapper_fields,
    }


def _normalize_value(value: Any) -> Any:
    """Recursively convert safe scalar encodings while retaining all values and keys."""
    if isinstance(value, Mapping):
        return {str(key): _normalize_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_normalize_value(item) for item in value]
    if isinstance(value, str):
        stripped = value.strip()
        lower = stripped.lower()
        if lower == "true":
            return True
        if lower == "false":
            return False
        if _NUMBER.fullmatch(stripped):
            number = float(stripped) if any(marker in stripped.lower() for marker in (".", "e")) else int(stripped)
            if math.isfinite(float(number)):
                return number
    return value


def _evidence_kind(information: Mapping[str, Any], wrapper_fields: Mapping[str, Any], record_id: Any) -> str:
    for field in ("kind", "evidence_kind", "type"):
        value = information.get(field, wrapper_fields.get(field))
        if isinstance(value, str) and value:
            return value
    if isinstance(record_id, str) and ":" in record_id:
        return record_id.split(":", 1)[0]
    return "unknown"


def _context_evidence(record: Mapping[str, Any]) -> dict[str, Any]:
    """Present one normalized record without dropping unfamiliar analysis output."""
    result = {
        "id": record.get("id"),
        "kind": record.get("kind", "unknown"),
        "source": record.get("source"),
        "priority": record.get("priority"),
        "data": dict(record.get("data", {})),
    }
    if record.get("record_fields"):
        result["record_fields"] = dict(record["record_fields"])
    return result


def _quote_history(quotes: list[Mapping[str, Any]]) -> dict[str, Any]:
    quote_refs = [_reference(quote) for quote in quotes]
    latest_dated = _latest_by_date(quotes)
    prices = [
        (float(quote["data"]["unit_price"]), quote)
        for quote in quotes
        if _finite_number(quote.get("data", {}).get("unit_price"))
    ]
    latest_price_quote = _latest_by_date([quote for _, quote in prices])
    min_price = min(prices, key=lambda item: item[0], default=None)
    max_price = max(prices, key=lambda item: item[0], default=None)
    awarded = [quote for quote in quotes if quote.get("data", {}).get("awarded") is True]

    return {
        "count": len(quotes),
        "latest_quote_date": _data_value(latest_dated, "quote_date"),
        "latest_unit_price": _data_value(latest_price_quote, "unit_price"),
        "min_unit_price": min_price[0] if min_price else None,
        "max_unit_price": max_price[0] if max_price else None,
        "awarded_quote_count": len(awarded),
        # References make every calculated field inspectable without inferring new supplier traits.
        "fact_sources": {
            "count": quote_refs,
            "latest_quote_date": [_reference(latest_dated)] if latest_dated else [],
            "latest_unit_price": [_reference(latest_price_quote)] if latest_price_quote else [],
            "min_unit_price": [_reference(min_price[1])] if min_price else [],
            "max_unit_price": [_reference(max_price[1])] if max_price else [],
            "awarded_quote_count": [_reference(quote) for quote in awarded],
        },
    }


def _latest_by_date(quotes: list[Mapping[str, Any]]) -> Mapping[str, Any] | None:
    dated = [quote for quote in quotes if isinstance(quote.get("data", {}).get("quote_date"), str)]
    # ISO dates sort chronologically; using input order as the tiebreaker keeps ties deterministic.
    return max(enumerate(dated), key=lambda item: (item[1]["data"]["quote_date"], item[0]))[1] if dated else None


def _data_value(record: Mapping[str, Any] | None, key: str) -> Any:
    return record.get("data", {}).get(key) if record else None


def _reference(record: Mapping[str, Any]) -> dict[str, Any]:
    return {"evidence_id": record.get("id"), "source": record.get("source")}


def _finite_number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))


def _evidence_gaps(matches: list[Mapping[str, Any]]) -> list[str]:
    if not matches or all(record.get("kind") == "quote" for record in matches):
        return ["No payment, financial, document, capacity, or quality evidence is available in this input."]
    return [
        "Supplier-profile evidence is retained but not yet interpreted; profile states remain unknown until "
        "evidence-specific rules are added."
    ]
