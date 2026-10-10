#!/usr/bin/env python3
"""Compare fact-based relationship estimates with saved P02/P03 Arena costs.

This is an offline calibration helper. It reads existing local validation results only;
it does not contact the Arena or alter those results.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from arena_kit.cost import relationship_cost
from arena_kit.data import DataPackage
from negotiator.supplier_economics import estimate_supplier_economics, supplier_cost_fact

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "output/validation/full-suite-10-hosted"


def _contract_terms(case):
    ref = next((item for item in case.get("refs", []) if item.startswith("ctr:")), None)
    if not ref:
        return {}
    path = ROOT / "data/contracts" / f"{ref.split(':', 1)[1]}.md"
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return {}
    terms = {}
    if match := re.search(r"Payment:\s*(\d+)\s+days", text, re.I):
        terms["payment_days"] = int(match.group(1))
    if match := re.search(r"Delivery\s+(EXW|FCA|DAP)\b", text, re.I):
        terms["incoterm"] = match.group(1).upper()
    return terms


def main():
    package = DataPackage(ROOT / "data")
    for case_id in ("P02", "P03"):
        path = RESULTS / f"unified-{case_id}.json"
        saved = json.loads(path.read_text(encoding="utf-8"))
        case, result = saved["case"], saved["result"]
        supplier_id = result["supplier_id"]
        fact = supplier_cost_fact(case, supplier_id, package.facts)
        economics = estimate_supplier_economics(case, supplier_id, package.facts)
        if fact is None or economics is None:
            print(f"{case_id}: no usable scoped supplier cost fact; estimate unavailable")
            continue
        standard = {**_contract_terms(case), **saved["decisions"][-1].get("supplier_standard_terms", {})}
        estimate = relationship_cost(
            case, result["terms"], supplier={**economics, "standard": standard}
        )
        actual = result["cost_breakdown"]["relationship"]
        fact_id, record = fact
        print(
            f"{case_id} {supplier_id}: fact={fact_id} unit_cost={record['unit_cost']} "
            f"price_unit={record['price_unit']} full_cost={economics['full_cost']:.2f}; "
            f"estimated relationship=EUR {estimate:.2f}; Arena actual=EUR {actual:.2f}; "
            f"difference=EUR {estimate - actual:+.2f}"
        )


if __name__ == "__main__":
    main()
