# MVP deterministic deal evaluator

This is a separate evaluation prototype. It evaluates one possible deal using Arena case and buyer data; it is not part of the supplier-only CSV extraction path and does not write e-mails, mine supplier data, optimise a package, select a supplier, or run an arena.

## API

```python
from negotiator.evaluator import evaluate_deal

evaluation = evaluate_deal(
    case,
    proposed_terms={"unit_price": 16.20, "payment_days": 60},
    supplier_standard_terms={"payment_days": 30},
    supplier_economics={"interest_rate": 0.12, "full_cost": 14.10},  # optional
)
```

`case` is an Arena case dictionary. `proposed_terms` may omit negotiable fields; the evaluator completes them using `arena_kit.cost.complete_offer`. Explicit unknown fields, invalid option values, or a non-positive/non-finite unit price leave a result available for inspection but mark it invalid for negotiation. `supplier_standard_terms` are the supplier's quoted fallbacks for omitted terms. `supplier_economics`, when supplied, requires finite `interest_rate` and `full_cost`; optional keys are `usual_rate`, `ppm`, and `extra`.

Omitted negotiable fields take the supplied supplier standard before buyer defaults.
The Arena permits the supplier's explicit standard value as well as the case's listed
options. The evaluator and package policy preserve such values instead of snapping
them to a different term. An explicitly allowed `null` index clause also stays `null`.
Unified refuses acceptance when a negotiable field is missing from both the standing
sheet and the supplier standard; buyer defaults alone cannot establish a supplier's promise.

The JSON-serializable result is shaped as follows:

```json
{
  "final_terms": {},
  "buyer": {
    "total_cost": 0.0,
    "cost_breakdown": {},
    "must_haves_ok": true,
    "alternative_cost": null,
    "beats_alternative": true
  },
  "supplier": {
    "value_per_unit": null,
    "estimated_margin_pct": null,
    "assessment_available": false,
    "reason_unavailable": "supplier_economics was not supplied"
  },
  "valid_for_negotiation": true,
  "warnings": []
}
```

Buyer total cost is the starter kit's full-horizon cost `arena_kit.cost.total_cost`: committed purchases, uncovered fallback need and risk, payment terms, freight, delivery, quality, tooling, index, and applicable relationship effects.  Its detailed parts are returned unchanged in `cost_breakdown`. Candidate cost calculations use the supplied standard terms when closing terms; a rival alternative is costed from its own stated terms.

Supplier value and margin are estimates, not facts.  They are computed with `arena_kit.cost.supplier_value` only from manually supplied economic assumptions. Missing, non-finite, or incompatible assumptions result in no supplier assessment—never an invented cost, interest rate, or margin.

`valid_for_negotiation` is false only for an invalid term sheet, failed buyer must-haves, or a non-finite buyer cost. A deal that loses to an available alternative stays valid but carries a warning for later policy to decide.

Malformed top-level inputs raise `negotiator.evaluator.EvaluationInputError`; malformed term sheets return an invalid evaluation with clear warnings.

## Run

```bash
python -m negotiator.demo_evaluator
pytest -q tests/test_evaluator.py
```
