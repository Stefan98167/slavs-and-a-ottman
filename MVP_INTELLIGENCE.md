# Supplier evidence intelligence

`negotiator/intelligence.py` converts supplier CSV extraction records into normalized,
source-traceable context. `arena_kit.quote_extract.extract_supplier_context()` connects
the CSV parser to this module and returns both the original rows and the generated
context as JSON-ready data.

During Arena sessions, `arena_kit.play.fetch_documents()` parses incoming supplier CSV
attachments into `csv_records` and reads PDFs into text. The supplier agent combines
those inputs with supplier email claims and live term sheets through
`negotiator.supplier_evidence.build_thread_supplier_context()`. The resulting context
unifies PDF quote sections, CSV rows, offer history, and index/cost-share claims while
preserving the attachment, row, or message that supplied each fact. Malformed CSVs
stay on the message as `csv_parse_error`.

The supplier identity and optional part identity come from the live negotiation
thread or the caller. The parser does not guess Arena IDs from a supplier name or
vendor-specific ID. Conflicting supplier-provided IDs are retained as reported
evidence while the live thread ID scopes the context. Files with multiple identified
parts produce one context per part; ambiguous rows require an explicit `part_id`.
Known bundled `data/data/` inputs are rejected by the CSV extractor.

## Use from Python

```python
from arena_kit.quote_extract import extract_supplier_context

result = extract_supplier_context(
    ["supplier_quote.csv"],
    supplier_id="sup:from-live-thread",
)
```

The result shape is:

```json
{
  "schema": "supplier_context_v1",
  "supplier_id": "sup:from-live-thread",
  "records": [],
  "contexts": []
}
```

Each context contains matching evidence, quote history with `fact_sources`, explicit
supplier claims, supplier profile dimensions, and evidence gaps. Original headers and
source line references remain available in `records` and the context evidence. Quote
history only identifies a latest quote when its supplier-provided `quote_date` exists;
it leaves that value unknown when dates are absent. Aggregate min/max prices are only
reported when every quote has one explicitly shared currency and price unit.

## Use from the command line

```bash
python -m arena_kit.quote_extract supplier_quote.csv \
  --context --supplier-id sup:from-live-thread > supplier_context.json
```

Pass `--part-id part:from-live-thread` when the uploaded rows do not identify a part
and the live thread provides one. Without `--context`, the command retains its
original behavior and writes the extracted JSON array.

`load_evidence()` also accepts a JSON array or a list of records directly. It
canonicalizes common supplier CSV headers such as `Unit Price`, `Price`, and
`Payment Terms` while retaining original keys and unfamiliar fields. If an extracted
row has no ID, its `Source` line becomes its stable evidence ID.

Quote history is descriptive; price patterns alone do not establish cash pressure,
capacity pressure, price rigidity, quality sensitivity, or buyer targets. The separate
`build_supplier_profile()` rules mark a dimension `likely` only from narrowly matched,
explicit supplier statements and retain the source evidence ID, source, excerpt, and
rule. These deterministic confidence values are rule support, not calibrated
probabilities. Unsupported, ambiguous, or conflicting statements remain `unknown`.

`SupplierContextAgent` remains a supplier-only baseline: it carries explicit
supplier-stated commercial terms into counters, considers historical prices only when
currency, price unit, volume, and material commercial terms match, responds to the
supplier's latest concession, and cites supplier evidence in its rationale. It does
not apply buyer-side profile trades. The selectable unified package policy consumes
the structured profile without reinterpreting its evidence; supported cash or capacity
profiles can add a bounded reciprocal term, while `quality_sensitive` currently has no
safe policy mapping and is exposed as unmapped. Unknown profile values keep the
conservative price-only ladder. Supplier-stated index movement times cost share can
adjust the opening discount by up to 2 percentage points; this is a bounded use of an
unverified supplier claim, not an independent cost estimate.

## Relationship to the deal evaluator

`negotiator.evaluator.evaluate_deal()` remains a separate prototype. It requires an
Arena case and uses buyer costs, must-haves, and alternatives. The supplier CSV
parser does not call it, because those inputs are outside the supplier-only evidence
pipeline.
