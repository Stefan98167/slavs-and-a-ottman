"""Run a deterministic evaluator example against the starter-kit S01 case."""

from __future__ import annotations

import json
from pathlib import Path

from negotiator.evaluator import evaluate_deal


def main() -> None:
    case_path = Path(__file__).resolve().parents[1] / "arena_kit" / "sim_cases" / "S01.json"
    case = json.loads(case_path.read_text())
    supplier_standard_terms = {"payment_days": 30}
    supplier_economics = {
        "interest_rate": 0.12,
        "full_cost": 14.10,
        "extra": 0.0,
    }
    proposed_terms = {"unit_price": 16.20, "payment_days": 60}
    print(json.dumps(evaluate_deal(case, proposed_terms, supplier_standard_terms, supplier_economics), indent=2))


if __name__ == "__main__":
    main()
