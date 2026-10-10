"""Print supplier context from explicitly supplied extracted supplier records."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from negotiator.intelligence import build_supplier_context, load_evidence

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="JSON array from the supplier CSV extractor")
    parser.add_argument("--supplier-id", help="Supplier identity from the live negotiation thread")
    parser.add_argument("--part-id", help="Optional part identity from the live negotiation thread")
    args = parser.parse_args()

    evidence = load_evidence(args.input)
    if not evidence:
        parser.error("the evidence array is empty")
    first = next((record for record in evidence if record.get("supplier_id")), None)
    if first is None and args.supplier_id is None:
        parser.error("no record has a supplier_id; pass --supplier-id to inspect an empty context")

    supplier_id = args.supplier_id or first["supplier_id"]
    part_id = args.part_id if args.part_id is not None else first.get("part_id")
    print(json.dumps(build_supplier_context(evidence, supplier_id, part_id), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
