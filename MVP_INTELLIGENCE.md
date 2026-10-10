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
profiles can add a bounded reciprocal term. A quality profile may additionally carry
`supported_terms: {"ppm_commitment": 500}` when the supplier explicitly guarantees
that numeric defect ceiling. The policy may propose an allowed ceiling at least as
high as that value in exchange for a less aggressive price ask; it never invents a
stricter guarantee. Generic quality statements remain unmapped. Unknown profile
values keep the conservative price-only ladder, except for explicit buyer must-have
repairs or cost-saving coverage up to the buyer's need and horizon. Supplier-stated
index movement times cost share can adjust the opening discount by up to 2
percentage points when explicitly enabled using `claim_adjustment_cap_pct` on
`UnifiedAgent`. Unified defaults to zero numerical adjustment: sourced claims
remain in its message, but are not independently verified supplier economics.
Conflicting series claims or combined shares over 100% cannot soften the ask.

With `--data data`, unified also loads relevant supplier-authored letters using
`negotiator.case_evidence.CaseSupplierEvidence`. Authorship, supplier, part and date
are checked before these records enter the context; buyer notes and generic market
records cannot establish a supplier motive. Document IDs are preserved in citations.
The adapter sees a downloaded Sunday release through `DataPackage`; missing or
unattributable documents provide no inferred motivation. Text rendered from supplier
XLSX attachments also enters the profile, without guessing numbers from formulas.

Common explicit requests such as paying invoices within a specified number of days
or requiring binding commitments are recognized. The rules remain narrow and mostly
English. Conflicting evidence stays unknown even if one statement is newer.

### Three-cycle package and response improvements

Supported earlier-payment/commitment options now request the lower package
price; higher price options retain the ordinary terms. This avoids giving away
both a higher price and earlier payment together. Buyer coverage is evaluated
at each actual candidate price and checked again after counterprice changes.

`negotiator.term_repair` makes at most one bounded restoration proposal when a
supplier beats the price target but changes a previously requested non-price
term. A price increase can share at most half the modeled saving, capped at the
previous ask. The package still has to pass must-haves and reservation checks.

`negotiator.buyer_arguments` answers explicit price-evidence requests with
eligible case-referenced quotes or two scope-checked, dated same-part/supplier
purchase orders with known currency and unit basis. Arbitrary historical quote
IDs are not treated as eligible rival-quote evidence. If no eligible evidence
exists, it gives an honest commercial explanation.
This is separate from supplier profiling: historical buyer data cannot establish
a supplier motive or hidden cost floor. Direct or indirect requests for missing
source excerpts are answered only from already cited, verified supplier-authored
archive documents. P01's purchase-order argument verified in hosted practice;
that did not improve its score.

`negotiator.response_trades` can propose a higher price after an explicit
price-linked invitation to change a term, or in return for reducing a quoted
index clause's exposure through an allowed deadband. The clause's series,
share and base month remain unchanged. At most half the modeled benefit is
shared with the supplier; proposals must obey must-haves and reservation cost.
Only one such message is attempted per thread, after the price ladder stalls.
It can also attempt later payment after a direct price constraint or three
comparable small-concession observations. `negotiator.response_signal` records
the sources and tentative trigger without changing the supplier profile or
claiming to know its floor. Opening unknown-profile behavior stays conservative.
Payment pivots explicitly replace the earlier payment/price arrangement.

`negotiator.supplier_alternatives` evaluates additional complete structured
sheets in the latest open supplier reply. A cheaper valid option is sent back
exactly to request a matching standing quote before acceptance. Stale,
incomplete, invalid and already-requested options are excluded; terms are never
reconstructed from prose. A concrete small saving is not discarded by the
speculative stopping threshold.

`negotiator.proposal_safety` chooses one complete proposal; internal alternatives
and exclusions remain in the decision log. Reservation and available safe-offer
cost ceilings prevent givebacks. Exact prior packages are filtered across the
whole thread. Price movement uses whole-package cost improvement (or a repaired
must-have), capped at half the price gap, not an inferred supplier utility.

The opening cost aspiration is reconstructed from the original supplier prefix
and its standards, not later concessions. Threshold-based early acceptance
normally waits for two buyer messages. Final/deadline closing remains safe, and
concrete cheaper alternatives still receive standing-confirmation requests.
Incomplete index invitations prompt a targeted question, not invented clauses.

See [MVP_ROUND3_REPORT.md](MVP_ROUND3_REPORT.md) for the latest three batches,
[MVP_ROUND2_REPORT.md](MVP_ROUND2_REPORT.md) for the preceding round,
and [MVP_ITERATION_REPORT.md](MVP_ITERATION_REPORT.md) for the earlier round.
The response-trade branch improved P03's observed actual total cost in round
three, but neither its threshold nor general superiority is established.
The alternative-confirmation branch still has mainly local regression evidence.
Hosted relationship costs can differ from our model when supplier economics
are unavailable; post-run reconciliation records the discrepancy, never guesses
those private economics or feeds the observed hidden optimum into the policy.

## Relationship to the deal evaluator

`negotiator.evaluator.evaluate_deal()` remains a separate prototype. It requires an
Arena case and uses buyer costs, must-haves, and alternatives. The supplier CSV
parser does not call it, because those inputs are outside the supplier-only evidence
pipeline.
