"""Parse supplier CSV uploads into JSON-ready negotiation records.

extract(csvs) accepts one path/file object or an iterable of them. Values remain
strings, preserving identifiers, currencies, decimal formats and missing cells.
Priority is a header-based heuristic: 1 price/contract, 2 operations, 3 context.
Unknown columns receive priority 3. No supplier-specific schema is required.
"""

import argparse
import csv
import io
import json
import re
import sys
from os import PathLike
from pathlib import Path

from .supplier_input import ensure_supplier_source


COLUMNS = ("Information", "Source", "Priority (Argument wise)")
PRIORITY_WORDS = {
    1: {"price", "cost", "amount", "currency", "discount", "payment", "contract",
        "preis", "kosten", "rabatt", "zahlung", "vertrag"},
    2: {"delivery", "lead", "quantity", "qty", "volume", "quality", "capacity",
        "lieferzeit", "menge", "qualität"},
}


def _priority(information):
    words = {
        word for key, value in information.items() if value.strip()
        for word in re.findall(r"[^\W_]+", key.lower())
    }
    return next((rank for rank, keywords in PRIORITY_WORDS.items() if words & keywords), 3)


def extract(csvs, *, delimiter=None, encoding="utf-8-sig", priority="heuristic",
            complete=None, priority_context=None, progress=None):
    """Return a list of {Information, Source, Priority (Argument wise)} dicts.

    Inputs: filesystem paths, text streams, or binary upload streams. For raw
    content use io.StringIO(text) or io.BytesIO(bytes). Stream cursors are read
    from their current position and remain open. Source includes the filename
    (or upload_N.csv for unnamed streams) and physical line range.

    Comma, semicolon, tab and pipe delimiters are detected automatically; pass
    delimiter explicitly for ambiguous files. A header is required. Duplicate
    or blank headers and inconsistent row widths raise ValueError instead of
    silently losing data. Empty files produce no records. Input order is kept.
    Use json.dumps(extract(csvs)) when a serialized JSON string is needed.
    Set priority="llm" to rank records with the configured LLM (or inject
    complete(system, user)); priority_context describes your negotiation.
    Optional progress(message) receives LLM batch status messages.
    """
    if priority not in ("heuristic", "llm"):
        raise ValueError("priority must be 'heuristic' or 'llm'")
    if isinstance(csvs, (str, PathLike)) or hasattr(csvs, "read"):
        csvs = [csvs]
    if delimiter is not None and (not isinstance(delimiter, str) or len(delimiter) != 1):
        raise ValueError("delimiter must be a single character")
    result = []
    for index, source in enumerate(csvs, 1):
        if isinstance(source, (str, PathLike)):
            name = str(source)
            ensure_supplier_source(source)
            ensure_supplier_source(Path(source).resolve())
            text = Path(source).read_text(encoding=encoding)
        elif hasattr(source, "read"):
            name = str(getattr(source, "name", None) or f"upload_{index}.csv")
            ensure_supplier_source(name)
            text = source.read()
            if isinstance(text, bytes):
                text = text.decode(encoding)
        else:
            raise TypeError("Each CSV must be a path or readable file object")
        text = text.lstrip("\ufeff")
        if not text.strip():
            continue
        separator = delimiter
        if separator is None:
            try:
                separator = csv.Sniffer().sniff(text[:65536], delimiters=",;\t|").delimiter
            except csv.Error:
                # Retry the header alone for malformed rows; width validation
                # below then reports the source and offending line.
                try:
                    separator = csv.Sniffer().sniff(text.splitlines()[0], delimiters=",;\t|").delimiter
                except csv.Error:
                    separator = ","  # valid one-column CSVs
        reader = csv.reader(io.StringIO(text, newline=""), delimiter=separator, strict=True)
        try:
            headers = next(reader)
            if any(not h.strip() for h in headers) or len(set(headers)) != len(headers):
                raise ValueError(f"{name}: headers must be nonempty and unique")
            while True:
                start = reader.line_num + 1
                values = next(reader, None)
                if values is None:
                    break
                if not values:  # ignore physically blank lines
                    continue
                if len(values) != len(headers):
                    raise ValueError(f"{name}:{start}: expected {len(headers)} cells, got {len(values)}")
                information = dict(zip(headers, values))
                end = reader.line_num
                location = str(start) if start == end else f"{start}-{end}"
                result.append({
                    "Information": information,
                    "Source": f"{name}:{location}",
                    "Priority (Argument wise)": _priority(information),
                })
        except csv.Error as exc:
            raise ValueError(f"{name}:{reader.line_num}: invalid CSV: {exc}") from exc
    if priority == "llm":
        from .priority import DEFAULT_CONTEXT, prioritize

        return prioritize(result, complete=complete,
                          context=DEFAULT_CONTEXT if priority_context is None else priority_context,
                          progress=progress)
    return result


def extract_supplier_context(csvs, *, supplier_id=None, part_id=None, delimiter=None,
                            encoding="utf-8-sig", priority="heuristic", complete=None,
                            priority_context=None, progress=None):
    """Extract supplier CSVs and pass their records through the intelligence engine.

    ``supplier_id`` and ``part_id`` are negotiation identities supplied by the caller,
    not guessed from names or vendor-specific IDs in a supplier file. Multiple parts
    produce separate contexts. For ambiguous part data, pass an explicit part scope.
    The returned object contains the original extracted rows and auditable contexts.
    """
    from negotiator.intelligence import (
        EvidenceInputError,
        bind_evidence_scope,
        build_supplier_context,
        load_evidence,
    )

    records = extract(csvs, delimiter=delimiter, encoding=encoding, priority=priority,
                      complete=complete, priority_context=priority_context, progress=progress)
    evidence = load_evidence(records)
    if supplier_id is None:
        raise EvidenceInputError("supplier_id from the live negotiation thread is required for context output")
    if not isinstance(supplier_id, str) or not supplier_id.strip():
        raise EvidenceInputError("supplier_id must be a non-empty string")

    # A supplier's own identifiers are not necessarily Arena identities. The
    # uploaded attachment is scoped by its live thread; preserve conflicting CSV
    # identifiers as evidence, then bind the live identity for context grouping.
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

    try:
        evidence = bind_evidence_scope(evidence, supplier_id, part_id)
    except EvidenceInputError as exc:
        raise ValueError(str(exc)) from exc

    parts = {record.get("part_id") for record in evidence if record.get("part_id")}
    has_unscoped_part = any(not record.get("part_id") for record in evidence)
    if part_id is not None:
        contexts = [build_supplier_context(evidence, supplier_id, part_id)]
    elif len(parts) > 1:
        if has_unscoped_part:
            raise EvidenceInputError(
                "CSV rows identify multiple parts and some rows have no part ID; pass part_id to scope this upload"
            )
        contexts = [build_supplier_context(evidence, supplier_id, part)
                    for part in sorted(parts, key=str)]
    else:
        inferred_part = next(iter(parts), None)
        contexts = [build_supplier_context(evidence, supplier_id, inferred_part)]

    return {
        "schema": "supplier_context_v1",
        "supplier_id": supplier_id,
        "records": records,
        "contexts": contexts,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csvs", nargs="+", type=Path)
    parser.add_argument("--delimiter")
    parser.add_argument("--encoding", default="utf-8-sig")
    parser.add_argument("--priority", choices=["heuristic", "llm"], default="heuristic")
    parser.add_argument("--priority-context", help="Negotiation context used by the LLM ranker")
    parser.add_argument("--context", action="store_true",
                        help="also run the extracted supplier rows through negotiator.intelligence")
    parser.add_argument("--supplier-id", help="supplier identity from the live negotiation thread (required with --context)")
    parser.add_argument("--part-id", help="optional part identity from the live negotiation thread")
    args = parser.parse_args()
    if args.priority == "llm":
        from .cli import load_env

        load_env()
    try:
        options = dict(delimiter=args.delimiter, encoding=args.encoding, priority=args.priority,
                       priority_context=args.priority_context,
                       progress=lambda message: print(message, file=sys.stderr, flush=True))
        if args.context:
            records = extract_supplier_context(args.csvs, supplier_id=args.supplier_id,
                                               part_id=args.part_id, **options)
        else:
            if args.supplier_id or args.part_id:
                parser.error("--supplier-id and --part-id require --context")
            records = extract(args.csvs, **options)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    json.dump(records, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    count = len(records["records"]) if isinstance(records, dict) else len(records)
    output_kind = "supplier context" if isinstance(records, dict) else "records"
    print(f"Done: {count} {output_kind} written as JSON to stdout.", file=sys.stderr, flush=True)


if __name__ == "__main__":
    main()
