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

Quote history is descriptive. It does not establish cash pressure, capacity pressure,
price rigidity, quality sensitivity, or buyer targets. Profile dimensions therefore
remain `unknown`. The `SupplierContextAgent` uses the available evidence directly:
it carries explicit supplier-stated commercial terms into counters, considers a
historical quote only when currency, price unit, and all available volume and commercial
terms match, responds to the supplier's latest concession, and cites the highest-priority
supplier evidence in its message. Supplier-stated index movement times cost share can
adjust the initial discount by up to the policy's configured `max_claim_adjustment_pct`
(2 percentage points by default). This is a bounded use of an unverified supplier claim,
not an independent cost estimate.
Those steps use observed supplier facts; they do not claim to infer the supplier's
motives or the buyer's willingness to pay.

## Relationship to the deal evaluator

`negotiator.evaluator.evaluate_deal()` remains a separate prototype. It requires an
Arena case and uses buyer costs, must-haves, and alternatives. The supplier CSV
parser does not call it, because those inputs are outside the supplier-only evidence
pipeline.
