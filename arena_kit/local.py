"""Offline CSV/JSON-to-decision runner. No credentials, server or network needed.

python3 -m arena_kit.local supplier_quote.csv --out decisions.json
python3 -m arena_kit.local --json output.json --out decisions.json
"""

import argparse
import json
import sys
from pathlib import Path

from .decision_engine import decide
from .quote_extract import extract


def run_local(csvs=None, *, json_file=None, delimiter=None, encoding="utf-8-sig",
              counter_discount_pct=5):
    """Extract supplied CSVs (or load extractor JSON) and return dummy decisions.

    An explicit supplier CSV or extracted JSON input is required. Network
    clients and environment credentials are never loaded. Each decision retains
    its extracted Information, Source and Priority (Argument wise).
    """
    if csvs is not None and json_file is not None:
        raise ValueError("Supply CSVs or a JSON file, not both")
    if csvs is None and json_file is None:
        raise ValueError("Supply the supplier's CSV files or --json supplier extraction; no bundled data is loaded")
    if json_file is not None:
        records = json.loads(Path(json_file).read_text(encoding="utf-8-sig"))
    else:
        records = extract(csvs, delimiter=delimiter, encoding=encoding)
    return {"mode": "local", "input_policy": "supplier_only",
            **decide(records, counter_discount_pct=counter_discount_pct)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csvs", nargs="*", type=Path, help="Supplier CSV files; explicit input is required")
    parser.add_argument("--json", dest="json_file", type=Path, help="Existing extractor JSON instead of CSVs")
    parser.add_argument("--out", type=Path, help="Save decisions to a file; defaults to stdout")
    parser.add_argument("--delimiter")
    parser.add_argument("--encoding", default="utf-8-sig")
    parser.add_argument("--counter-discount-pct", default="5")
    args = parser.parse_args(argv)
    inputs = args.csvs + ([args.json_file] if args.json_file else [])
    if args.out and any(args.out.resolve() == path.resolve() for path in inputs):
        parser.error("Output file must differ from input files")
    try:
        result = run_local(args.csvs or None, json_file=args.json_file,
                           delimiter=args.delimiter, encoding=args.encoding,
                           counter_discount_pct=args.counter_discount_pct)
        output = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
        if args.out:
            args.out.write_text(output, encoding="utf-8")
        else:
            sys.stdout.write(output)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
