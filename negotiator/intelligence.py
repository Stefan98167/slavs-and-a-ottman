"""Deterministic normalization and sourced context from supplier evidence.

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

from .supplier_profile import build_supplier_profile


class EvidenceInputError(ValueError):
    """Raised when an evidence document cannot be read as the expected JSON array."""


_NUMBER = re.compile(r"^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?$")
_WRAPPER_KEYS = {"Information", "Source", "Priority (Argument wise)"}
_CANONICAL_FIELD_ALIASES = {
    "supplier_id": {"supplier_id", "supplier id", "supplier", "supplier number"},
    "part_id": {"part_id", "part id", "part", "part number", "item", "item number"},
    "unit_price": {
        "unit_price", "unit price", "historical unit price", "purchase price", "quoted price",
        "quote price", "offered price", "net price", "price", "preis",
    },
    "quote_date": {"quote_date", "quote date", "date", "offer date"},
    "currency": {"currency", "currency code", "währung", "waehrung"},
    "price_unit": {"price unit", "unit of measure", "uom", "pricing unit"},
    "payment_days": {
        "payment_days", "payment days", "payment terms", "payment terms days net",
        "days net", "net payment days", "zahlungsziel",
    },
    "lead_time_days": {"lead_time_days", "lead time", "lead time days", "delivery days"},
    "incoterm": {"incoterm", "incoterms"},
    "contract_months": {
        "contract_months", "contract months", "contract term", "contract duration",
        "contract length",
    },
    "volume_per_year": {
        "volume_per_year", "volume per year", "annual volume", "yearly volume",
        "annual quantity", "yearly quantity",
    },
    "tooling_eur": {"tooling_eur", "tooling", "tooling eur", "tooling cost"},
    "index_clause": {"index_clause", "index clause", "price index", "indexation"},
    "ppm_commitment": {"ppm_commitment", "quality commitment", "quality ppm", "ppm"},
    "chargeback_eur_per_complaint": {
        "chargeback_eur_per_complaint", "chargeback per complaint", "complaint chargeback"
    },
    "index_change_pct": {
        "index_change_pct", "index change pct", "index change percent", "change percent", "change pct",
    },
    "cost_share_pct": {
        "cost_share_pct", "cost share pct", "material share pct", "material cost share",
        "cost share percent", "cost share",
    },
}


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


def bind_evidence_scope(
    evidence: list[Mapping[str, Any]], supplier_id: str, part_id: str | None = None
) -> list[dict[str, Any]]:
    """Bind unscopeable supplier-upload records to the live negotiation identity.

    A supplier attachment often has commercial rows but no arena supplier or part ID.  The
    caller already knows that identity from the live supplier thread, so this function attaches
    it explicitly rather than trying to infer it from CSV content.  Existing non-empty IDs must
    agree with the supplied scope; disagreement raises :class:`EvidenceInputError` to prevent
    evidence from one supplier being silently used for another.
    """
    if not isinstance(supplier_id, str) or not supplier_id:
        raise EvidenceInputError("supplier_id must be a non-empty string when binding evidence scope")
    if part_id is not None and (not isinstance(part_id, str) or not part_id):
        raise EvidenceInputError("part_id must be a non-empty string or None when binding evidence scope")

    bound: list[dict[str, Any]] = []
    for index, record in enumerate(evidence):
        if not isinstance(record, Mapping):
            raise EvidenceInputError(f"evidence record at index {index} must be an object")
        existing_supplier = record.get("supplier_id")
        existing_part = record.get("part_id")
        if existing_supplier not in (None, supplier_id):
            raise EvidenceInputError(
                f"evidence record at index {index} belongs to {existing_supplier!r}, not {supplier_id!r}"
            )
        if part_id is not None and existing_part not in (None, part_id):
            raise EvidenceInputError(
                f"evidence record at index {index} belongs to part {existing_part!r}, not {part_id!r}"
            )
        copy = dict(record)
        copy["supplier_id"] = supplier_id
        if part_id is not None:
            copy["part_id"] = part_id
        bound.append(copy)
    return bound


def build_supplier_context(
    evidence: list[Mapping[str, Any]], supplier_id: str, part_id: str | None = None
) -> dict[str, Any]:
    """Build a JSON-serializable, traceable context for one supplier and optional part.

    Only records whose normalized ``kind`` is ``quote`` contribute to ``quote_history``.  The
    profile uses narrowly scoped explicit supplier statements with source references.
    """
    matches = filter_evidence(evidence, supplier_id, part_id)
    quotes = [record for record in matches if record.get("kind") == "quote"]
    claims = [record for record in matches if record.get("kind") == "claim"]

    return {
        "supplier_id": supplier_id,
        "part_id": part_id,
        "evidence": [_context_evidence(record) for record in matches],
        "quote_history": _quote_history(quotes),
        "supplier_claims": [_context_evidence(record) for record in claims],
        "supplier_profile": build_supplier_profile(matches),
        "evidence_gaps": _evidence_gaps(matches),
    }


def contexts_from_records(
    records: list[object], supplier_id: str, part_id: str | None = None
) -> list[dict[str, Any]]:
    """Normalize supplier CSV/PDF/message records into contexts for the live identity.

    A live supplier thread establishes the Arena identity. Conflicting IDs in an uploaded
    file remain visible as supplier-reported fields and do not change that thread scope.
    """
    if not isinstance(supplier_id, str) or not supplier_id.strip():
        raise EvidenceInputError("supplier_id from the live negotiation thread is required for context output")
    evidence = load_evidence(records)
    for record in evidence:
        information = record["data"]
        csv_supplier_id = record.get("supplier_id")
        if csv_supplier_id not in (None, supplier_id):
            information["supplier_reported_supplier_id"] = csv_supplier_id
            information.pop("supplier_id", None)
            record["supplier_id"] = None
        csv_part_id = record.get("part_id")
        if part_id is not None and csv_part_id not in (None, part_id):
            information["supplier_reported_part_id"] = csv_part_id
            information.pop("part_id", None)
            record["part_id"] = None

    evidence = bind_evidence_scope(evidence, supplier_id, part_id)
    parts = {record.get("part_id") for record in evidence if record.get("part_id")}
    has_unscoped_part = any(not record.get("part_id") for record in evidence)
    if part_id is not None:
        return [build_supplier_context(evidence, supplier_id, part_id)]
    if len(parts) > 1:
        if has_unscoped_part:
            raise EvidenceInputError(
                "supplier records identify multiple parts and some records have no part ID; pass part_id to scope them"
            )
        return [build_supplier_context(evidence, supplier_id, part)
                for part in sorted(parts, key=str)]
    inferred_part = next(iter(parts), None)
    if inferred_part is not None:
        evidence = [
            {**record, "part_id": record.get("part_id") or inferred_part}
            for record in evidence
        ]
    return [build_supplier_context(evidence, supplier_id, inferred_part)]


def _normalize_record(record: Mapping[str, Any]) -> dict[str, Any]:
    information_value = record.get("Information", {})
    information = _normalize_value(information_value) if isinstance(information_value, Mapping) else {}
    if isinstance(information, Mapping):
        information = _canonicalize_information(information)
    wrapper_fields = {key: _normalize_value(value) for key, value in record.items() if key not in _WRAPPER_KEYS}
    if "Information" in record and not isinstance(information_value, Mapping):
        # A malformed or future non-object payload is retained rather than preventing unrelated
        # evidence from being ingested. It simply cannot supply the standard identity fields.
        wrapper_fields["Information"] = _normalize_value(information_value)
    # CSV extracts retain an exact line-range source but normally have no separate ID.  The
    # source is therefore the stable evidence ID for those records, preserving traceability.
    record_id = (information.get("id") or information.get("offer_id") or information.get("claim_id")
                 or wrapper_fields.get("id") or record.get("Source"))
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
        prefix = record_id.split(":", 1)[0]
        if prefix in {"quote", "document", "payment", "financial", "capacity", "quality"}:
            return prefix
    # An extracted supplier row with a recognizable price field is commercial quote evidence,
    # not a basis for inferring supplier pressure or preferences.
    if "unit_price" in information:
        return "quote"
    return "unknown"


def _canonicalize_information(information: Mapping[str, Any]) -> dict[str, Any]:
    """Retain supplied CSV headers and expose a small set of deterministic aliases."""
    result = dict(information)
    normalized_keys = {
        _header_key(str(key)): key
        for key in information
    }
    for canonical, aliases in _CANONICAL_FIELD_ALIASES.items():
        if canonical in result:
            continue
        for alias in aliases:
            original_key = normalized_keys.get(_header_key(alias))
            if original_key is not None:
                result[canonical] = _canonical_value(canonical, information[original_key])
                break
    if "unit_price" in result and "price_unit" not in result:
        # Arena offer sheets define unit_price per ordered item. Explicit CSV UOMs win.
        unit_price_header = next(
            (str(key) for key in information if _header_key(str(key)) in {
                _header_key(alias) for alias in _CANONICAL_FIELD_ALIASES["unit_price"]
            }),
            "",
        )
        result["price_unit"] = _unit_from_price_header(unit_price_header)
    return result


def _canonical_value(field: str, value: Any) -> Any:
    """Parse unambiguous European decimal-comma values for recognized numeric fields."""
    if field == "price_unit" and isinstance(value, str):
        unit = value.strip().casefold()
        if unit in {"pc", "pcs", "piece", "pieces", "unit", "units", "each"}:
            return "each"
    numeric_fields = {
        "unit_price", "payment_days", "lead_time_days", "contract_months", "volume_per_year",
        "tooling_eur", "ppm_commitment", "chargeback_eur_per_complaint", "index_change_pct",
        "cost_share_pct",
    }
    if field in numeric_fields and isinstance(value, str) and "," in value and "." not in value:
        candidate = value.strip()
        if re.fullmatch(r"[+-]?\d+,\d+", candidate):
            return float(candidate.replace(",", "."))
    return value


def _unit_from_price_header(header: str) -> str | None:
    parenthetical = re.search(r"\(([^)]*)\)", header)
    unit_text = parenthetical.group(1).lower() if parenthetical else ""
    match = re.search(r"(?:/|per\s+)(\d+\s*)?(pcs?|pieces?|units?|kg|g|tonnes?|tons?|m|lit(?:er|re)s?)\b", unit_text)
    if match:
        quantity, unit = match.groups()
        unit = unit.rstrip("s")
        if unit in {"pc", "piece", "unit"}:
            unit = "each"
        return f"{quantity.strip()} {unit}" if quantity else unit
    return "each" if "unit price" in _header_key(header) else None


def _header_key(value: str) -> str:
    # Parentheses often carry units, e.g. ``Unit price (EUR)`` or ``Volume (pcs)``.
    # Preserve the original header in ``data`` while matching a unit-free alias here.
    value = re.sub(r"\([^)]*\)", " ", value)
    value = re.sub(r"[^\w]+", " ", value.lower(), flags=re.UNICODE)
    return " ".join(value.split())


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
    # Record order is not quote chronology: attachments can contain older history.
    latest_dated = _latest_by_date(quotes)
    prices = [
        (float(quote["data"]["unit_price"]), quote)
        for quote in quotes
        if _finite_number(quote.get("data", {}).get("unit_price"))
    ]
    priced_quotes = [quote for _, quote in prices]
    latest_price_quote = _latest_by_date(priced_quotes)
    bases = {
        (str(quote["data"].get("currency") or "").strip().upper(),
         str(quote["data"].get("price_unit") or "").strip().casefold())
        for quote in priced_quotes
    }
    one_known_basis = (
        len(bases) == 1 and all(currency and unit for currency, unit in bases)
    )
    # A common currency/unit alone does not make different commercial offers comparable.
    commercial_fields = ("volume_per_year", "contract_months", "payment_days", "lead_time_days",
                         "incoterm", "index_clause", "tooling_eur", "effective_date",
                         "ppm_commitment", "chargeback_eur_per_complaint")
    commercial_bases = {
        json.dumps({field: _quote_terms(quote["data"]).get(field) for field in commercial_fields},
                   sort_keys=True, default=str)
        for quote in priced_quotes
    }
    comparable_prices = prices if one_known_basis and len(commercial_bases) == 1 else []
    min_price = min(comparable_prices, key=lambda item: item[0], default=None)
    max_price = max(comparable_prices, key=lambda item: item[0], default=None)
    awarded = [quote for quote in quotes if quote.get("data", {}).get("awarded") is True]

    return {
        "count": len(quotes),
        "latest_quote_date": _data_value(latest_dated, "quote_date"),
        "latest_unit_price": _data_value(latest_price_quote, "unit_price"),
        "latest_price_basis": (
            {"currency": _data_value(latest_price_quote, "currency"),
             "price_unit": _data_value(latest_price_quote, "price_unit")}
            if latest_price_quote else None
        ),
        "latest_price_is_dated": latest_price_quote is not None,
        "comparable_price_basis": (
            {"currency": next(iter(bases))[0], "price_unit": next(iter(bases))[1]}
            if one_known_basis else None
        ),
        "min_unit_price": min_price[0] if min_price else None,
        "max_unit_price": max_price[0] if max_price else None,
        "awarded_quote_count": len(awarded),
        "quotes": [
            {
                "evidence_id": quote.get("id"),
                "source": quote.get("source"),
                "quote_date": quote.get("data", {}).get("quote_date"),
                "unit_price": quote.get("data", {}).get("unit_price"),
                "currency": quote.get("data", {}).get("currency"),
                "price_unit": quote.get("data", {}).get("price_unit"),
                "terms": _quote_terms(quote.get("data", {})),
            }
            for quote in quotes
        ],
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


def _quote_terms(data: Mapping[str, Any]) -> dict[str, Any]:
    nested = data.get("terms")
    if isinstance(nested, Mapping) and nested:
        return dict(nested)
    term_fields = {
        "unit_price", "currency", "price_unit", "payment_days", "lead_time_days", "volume_per_year",
        "contract_months", "effective_date", "index_clause", "incoterm", "tooling_eur",
        "ppm_commitment", "chargeback_eur_per_complaint",
    }
    return {field: data[field] for field in term_fields if field in data}


def _reference(record: Mapping[str, Any]) -> dict[str, Any]:
    return {"evidence_id": record.get("id"), "source": record.get("source")}


def _finite_number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))


def _evidence_gaps(matches: list[Mapping[str, Any]]) -> list[str]:
    gaps = []
    kinds = {record.get("kind") for record in matches}
    if not matches:
        return ["No supplier evidence was available in this input."]
    if "claim" not in kinds:
        gaps.append("No explicit supplier index or cost-share claims were found in the supplied records.")
    if not any(record.get("kind") == "quote" for record in matches):
        gaps.append("No supplier quote or offer with a unit price was found in the supplied records.")
    if kinds - {"quote", "claim"}:
        gaps.append(
            "Other supplier evidence is retained; only recognized explicit statements support supplier profiles."
        )
    return gaps
