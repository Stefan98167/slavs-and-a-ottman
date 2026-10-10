# MVP intelligence: evidence ingestion and supplier context

`negotiator/intelligence.py` turns the data-analysis team's JSON export into deterministic,
JSON-serializable supplier context. It complements `negotiator/evaluator.py`: intelligence
organizes evidence; the evaluator assesses proposed deal terms.

## Current input

The input is a JSON array. Current records use an `Information` object plus `Source` and
`Priority (Argument wise)` wrapper fields. Historical quote records include IDs such as
`quote:7100001`, a supplier ID, a part ID, quote date, unit price, and other commercial terms.

`load_evidence(path_or_list)` validates that the top level is an array and raises
`EvidenceInputError` with a clear message otherwise. It converts safe numeric and boolean string
encodings (for example, `"142.5"` and `"true"`) while preserving `Information`, source, priority,
and unfamiliar wrapper fields. Records merely need to be JSON objects, which lets future evidence
types pass through even when their `Information` fields differ from quotes.

## Output

`build_supplier_context(evidence, supplier_id, part_id=None)` returns matching evidence, quote
history, a supplier profile, and evidence gaps. Each evidence item retains its original ID and
source. Quote-history values include `fact_sources`, which maps every derived field to the ID and
source record(s) used to calculate it. This makes count, latest date/price, min/max price, and
awarded count auditable.

## Quote-only limitation

Historical quotes describe quote history only. They must **not** be used to infer cash pressure,
capacity pressure, or quality sensitivity. Consequently all four current profile dimensions
(`cash_sensitive`, `capacity_sensitive`, `price_rigid`, and `quality_sensitive`) remain
`unknown` with confidence `0.0`, including when many historical quotes are present. Quote-only
input reports the missing payment, financial, document, capacity, and quality evidence.

## Extending with future evidence

Future records can expose a `kind`, `evidence_kind`, or `type` field; otherwise the ID prefix is
used (for example, `document:12` becomes `document`). Unknown fields are retained in `data`, and
unknown wrapper fields in `record_fields`. Add narrowly scoped, deterministic rules for each new
kind before changing a profile dimension, and include the contributing evidence ID/source in the
corresponding provenance. Do not make an LLM call or infer traits from unrelated evidence.

## Demo

Run the default local export, or provide a different file and filters:

```bash
uv run python -m negotiator.demo_intelligence
uv run python -m negotiator.demo_intelligence path/to/output.json --supplier-id sup:70110 --part-id part:310010
```
