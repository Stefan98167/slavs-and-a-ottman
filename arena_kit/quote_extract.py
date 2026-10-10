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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csvs", nargs="+", type=Path)
    parser.add_argument("--delimiter")
    parser.add_argument("--encoding", default="utf-8-sig")
    parser.add_argument("--priority", choices=["heuristic", "llm"], default="heuristic")
    parser.add_argument("--priority-context", help="Negotiation context used by the LLM ranker")
    args = parser.parse_args()
    if args.priority == "llm":
        from .cli import load_env

        load_env()
    try:
        records = extract(args.csvs, delimiter=args.delimiter, encoding=args.encoding,
                          priority=args.priority, priority_context=args.priority_context,
                          progress=lambda message: print(message, file=sys.stderr, flush=True))
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    json.dump(records, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    print(f"Done: {len(records)} records written as JSON to stdout.", file=sys.stderr, flush=True)


if __name__ == "__main__":
    main()
