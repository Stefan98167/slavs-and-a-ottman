# MVP core characteristics: mechanisms, purpose and validation

**Snapshot:** 10 October 2026, after the three-iteration Arena review.

**Scope:** the supplier-evidence pipeline and the integrated `unified` negotiation agent. This reference covers the capabilities we added or integrated into the MVP, including supporting safety, diagnostics and validation. The published cost functions and HTTP/session infrastructure include starter-kit functionality; where relevant, the addition is their disciplined integration into the evidence-driven policy, not a claim that we invented the underlying Arena protocol or scoring formula.

The most useful demonstrated qualities are source integrity, deterministic cost and constraint checks, explicit package selection, conditional commercial trades, and bounded adaptation to supplier responses. “Proved useful” has different meanings for different mechanisms. A live negotiated improvement, a regression that prevents a known bug, and a plausible but untested strategy are not equivalent evidence.

## How to read the evidence labels

| Label | What it supports | What it does not support |
|---|---|---|
| **Live observed** | The mechanism operated in a real Arena session, with the stated outcome. | Causality, optimal settings, or success against other suppliers. |
| **Regression validated** | Automated tests reproduce the relevant inputs and verify intended behavior. | Supplier acceptance or higher live scores. |
| **Saved-history validated** | The current policy produces a valid decision on recorded live inputs. | How the supplier would have answered that new decision. |
| **Synthetic validated** | A local simulator exercises the policy and its safety properties. | Real-world market accuracy or Arena supplier psychology. |
| **Optional / unproven strategy** | The capability exists, but evidence for its strategic benefit is limited. | A recommendation to enable it automatically. |

The latest complete suite recorded **201 passed, 2 skipped, 15 subtests passed**. Final replay covered **22 saved-history decisions with zero common-guard replacements**. The final focused synthetic benchmark covered **15 runs with no errors, constraint violations or reservation violations**. These counts describe the recorded validation run, not a guarantee about future changes.

Primary evidence: [three-iteration report](ARENA_ITERATION_REPORT.md), [hardening history](MVP_HARDENING.md), [test suite](tests), and the linked local run artifacts. Generated `runs/` files are ignored by Git, so those evidence links require the local artifacts to be retained or shared separately.

## 1. Overall architecture and data boundaries

### 1. One integrated agent behind the existing Arena interface

**Mechanism.** `UnifiedAgent` implements `decide(case, threads)` and `close(case, threads)`. It consumes the current explicit case brief and supplier threads, and returns a supplier ID plus one message or a closing action. The existing play runner handles attachments, state progression, transport and results. The current integrated path is selected with `--agent unified`; other agents remain available as baselines. The CLI default has not automatically been promoted to unified.

**What it is good for.** Parser, context builder, package generator, evaluator and negotiation policy operate together rather than requiring manually copied JSON between every live move. The same interface supports saved-input replay and local simulation.

**Evidence.** Live observed in the recorded P01/P02/P03 batches and all six review sessions; integration regressions in [test_unified.py](tests/test_unified.py) and [test_mvp_hardening.py](tests/test_mvp_hardening.py).

**Implementation:** [unified.py](arena_kit/agents/unified.py), [play.py](arena_kit/play.py), [cli.py](arena_kit/cli.py).

### 2. Supplier evidence is separated from buyer requirements and demo data

**Mechanism.** Supplier commercial assertions come from the live supplier messages and their supplied documents. The explicit buyer brief supplies authorized decision inputs such as need, horizon, must-haves, negotiable fields, option lists and fallback terms. Unified does not load the bundled procurement data as supplier evidence. The standalone upload pipeline rejects known `data/data/` source paths, including resolved filesystem paths.

**What it is good for.** Prevents a convincing-looking negotiation based on demo quotes, unrelated suppliers or privileged simulator information. It also avoids confusing buyer requirements with supplier statements.

**Boundary.** “Supplier-only evidence” does not mean discarding the buyer's explicit requirement or cost model. A filename guard catches known bundled sources; it cannot authenticate who originally created an arbitrary upload. Caller provenance still matters.

**Evidence.** Regression validated in extraction/intelligence tests and visible in every decision audit's `input_policy`. [supplier_input.py](arena_kit/supplier_input.py) contains the source guard.

### 3. Live thread identity establishes supplier scope

**Mechanism.** The context builder takes the supplier ID from the live thread. Standalone context extraction requires an explicit `supplier_id`. Arena-style IDs in a file that disagree with the live identity become visible scope conflicts. Vendor-specific identifiers can be retained as supplier-reported identifiers without replacing the live supplier identity. Part scope is explicit when needed; multiple parts can produce separate contexts, while ambiguous mixed scoped/unscoped records require clarification.

**What it is good for.** Stops a quote from one supplier or part becoming leverage or profile evidence for another. Handles supplier CSVs that omit Arena identifiers without guessing identities from company names.

**Evidence.** Regression validated for explicit identity conflicts, multiple-part scope and profile isolation. [intelligence.py](negotiator/intelligence.py), [test_intelligence.py](tests/test_intelligence.py), [test_supplier_profile.py](tests/test_supplier_profile.py).

### 4. Numeric decisions are deterministic and reproducible

**Mechanism.** The integrated agent uses rule-based extraction, cost evaluation, package generation and message templates. Its live decisions do not call an LLM. Optional LLM ranking is a separate explicit preprocessing mode. Candidate costs and constraints are evaluated in Python, not estimated in prose.

**What it is good for.** Makes a bad decision reproducible and inspectable. It avoids hidden model variability in arithmetic and reduces runtime dependency on a model API. This distinction was essential in P11: its loop was a policy branch failure, not a model being confused by copied wording.

**Boundary.** Deterministic does not mean commercially optimal. The current agent has no learned supplier utility or acceptance-probability model.

**Evidence.** Live logs, repeatable tests, and the architecture in [unified.py](arena_kit/agents/unified.py) and [evaluator.py](negotiator/evaluator.py).

## 2. Runtime extraction and source preservation

### 5. A reusable runtime CSV extraction function

**Mechanism.** `extract(csvs)` accepts one path, one readable stream, or an iterable of paths/streams. Text streams and binary upload streams are supported. Raw content can be wrapped in `io.StringIO` or `io.BytesIO`. It returns JSON-ready Python dictionaries; callers serialize them with `json.dumps` when required. Streams stay open and are consumed from their current cursor position.

The row contract remains:

```json
{
  "Information": {"Unit price (EUR)": "17.47"},
  "Source": "supplier_quote.csv:2",
  "Priority (Argument wise)": 1
}
```

**What it is good for.** Supports arbitrary runtime uploads without generating a bespoke parser or predefined output files for every supplier. It works from a CLI, application upload handler or live attachment parser.

**Evidence.** Regression validated in [test_quote_extract.py](tests/test_quote_extract.py). [quote_extract.py](arena_kit/quote_extract.py) exposes both `extract` and `extract_supplier_context`.

### 6. Raw CSV cell values are preserved before semantic normalization

**Mechanism.** Extraction retains cell values as strings, preserving leading-zero identifiers, decimal spelling, currencies and empty cells. Original headers are retained. Semantic normalization occurs later, where recognized aliases can be added without discarding unfamiliar fields.

**What it is good for.** Avoids corrupting supplier part IDs or silently treating an ambiguous number as a known price. Preserved originals also let a teammate add a new alias without requesting the same document again.

**Boundary.** Retaining an unknown column is not understanding its commercial meaning.

**Evidence.** Regression validated for identifiers, unknown fields and alias preservation in extraction/intelligence tests.

### 7. Delimiter and common supplier-export encoding support

**Mechanism.** CSV parsing detects comma, semicolon, tab or pipe separators. An explicit delimiter can override detection. UTF-8 BOMs are handled, UTF-16 BOMs are detected under the default encoding, and an explicit encoding remains available. Excel `sep=` declarations are recognized; conflicting explicit separators raise an error.

**What it is good for.** Handles common European and spreadsheet-generated supplier exports without manual conversion. Physical source offsets remain correct when a separator declaration precedes the header.

**Evidence.** Regression validated, including UTF-16 Excel exports and separator declarations, in [test_mvp_hardening.py](tests/test_mvp_hardening.py).

### 8. Strict structural CSV validation

**Mechanism.** Headers must be present, nonblank and unique after trimming/case normalization. Inconsistent row widths and malformed quoting raise source-specific errors. Blank physical lines are skipped; empty files return no records. Multiline quoted cells are supported by the CSV reader rather than splitting records by line manually.

**What it is good for.** Prevents duplicate columns or malformed rows silently overwriting data. A failed supplier upload produces an actionable error rather than a seemingly valid but incomplete negotiation context.

**Evidence.** Regression validated for duplicate headers, malformed input and row widths in extraction/hardening tests.

### 9. Physical row-level provenance

**Mechanism.** Every extracted row receives a filename and physical line or line range. Unnamed streams receive stable upload labels within the extraction call. Live attachments retain their original names plus an attachment-linked source label. Multiline records identify the full physical range.

**What it is good for.** A reviewer can locate the original supplier statement behind a JSON value. This supports correcting parsing errors, explaining decisions and distinguishing repeated statements from independent evidence.

**Boundary.** CSV provenance is row-level. PDF records retain document text and attachment/offer references; the current normalized contract does not promise page-coordinate provenance for every PDF field.

**Evidence.** Regression validated; source references are present in live parsed context and decision logs.

### 10. Live attachment extraction on every supplier turn

**Mechanism.** The runner downloads attachments within the active session. Supplier CSVs receive `csv_records` and supplier-scoped context; PDFs receive extracted text and parse diagnostics. Attachments already represented as text are handled through the existing message structure. Later supplier replies can therefore update context without manually rerunning the extractor.

**What it is good for.** Ensures the agent can reason from current supplier documents during a negotiation, not only a preprocessed opening quote.

**Evidence.** Live observed through attachment-download and parsed-context events; regression validated in supplier-evidence and simulator tests. [play.py](arena_kit/play.py), [supplier_evidence.py](negotiator/supplier_evidence.py).

### 11. Structured PDF term sections

**Mechanism.** Recognized quote labels are parsed into stated, standard, fixed and agreed sections. Supported terms include unit price, payment, lead time, annual volume, duration, effective date, index clause, Incoterm, tooling, quality commitment and complaint chargeback. Matching tolerates case, spacing, optional colons and recognized unit annotations. Effective terms are exposed while the original sections and full extracted text remain available.

**What it is good for.** Distinguishes a supplier's actual offered terms from defaults and enquiry-fixed terms. This matters when a term sheet omits payment or quality but the attached quote supplies the applicable standard.

**Evidence.** Regression validated with supplier P01-style PDFs, decimal commas and label variants; live PDF ingestion observed. [docs.py](arena_kit/docs.py), [test_supplier_evidence.py](tests/test_supplier_evidence.py).

### 12. Partial PDF readability is preserved; OCR is bounded and optional

**Mechanism.** Text extraction first uses `pypdf`. Only unreadable pages are sent to optional local OCR using Tesseract/Poppler-related tools. OCR has a shared approximately ten-second document budget. Readable pages are preserved if another page remains unreadable. Corrupt files, missing OCR dependencies and unreadable pages produce explicit errors or warnings.

**What it is good for.** Avoids fabricating content from scans or losing an entire mixed document because one page is an image. The runtime budget also prevents an OCR attempt from consuming the whole negotiation turn.

**Boundary.** OCR accuracy depends on local dependencies and scan quality. Unified conservatively refuses to rely on PDFs carrying unreadability diagnostics. These checks do not prove arbitrary scanned supplier documents will parse successfully.

**Evidence.** Regression validated with mocked OCR, mixed pages, missing tools and invalid documents. The fallback machinery is supported; broad real-scan accuracy remains unproven.

### 13. Localized field failures remain visible

**Mechanism.** A recognized PDF field with an invalid value records a `parse_warnings` entry rather than inventing a replacement. Other readable terms remain preserved. CSV/PDF/document parse failures are attached to the source attachment and represented in context.

**What it is good for.** Separates “we read the document but could not interpret this term” from “the supplier never provided it.” Preserved diagnostics make review and targeted correction possible.

**Evidence.** Regression validated for bad numeric PDF fields and missing OCR. Current offer safety excludes unsuitable/conflicted quote evidence rather than treating a warning as verified data.

### 14. Conservative locale-aware number and date normalization

**Mechanism.** Recognized fields support unambiguous decimal commas, common thousands-grouping patterns and finite numeric values. Boolean values are not prices. Ambiguous comma-grouped values remain uninterpreted. Dates support ISO and selected unambiguous formats; slash dates that could mean both day/month and month/day are not guessed. Leading-zero identity values remain intact.

**What it is good for.** Prevents a locale or date-order error from changing a price target or quote chronology. Uncertainty is represented instead of hidden by a plausible conversion.

**Evidence.** Regression validated in intelligence/evidence hardening tests. [evidence_values.py](negotiator/evidence_values.py).

### 15. Header aliases expose canonical fields without erasing originals

**Mechanism.** A narrow alias map recognizes common English/German price, payment, currency, quantity and contract headers, including unit annotations. Normalized canonical fields coexist with the supplied headers. If two aliases disagree, an extraction conflict is recorded instead of choosing whichever happened to be processed last.

**What it is good for.** Lets differently formatted supplier files feed the same downstream policy while keeping the evidence auditable.

**Boundary.** This is deterministic alias recognition, not universal interpretation of arbitrary column names.

**Evidence.** Regression validated for unit-bearing headers, unknown columns and conflicting aliases. [intelligence.py](negotiator/intelligence.py).

## 3. Unified context, history and supplier profile

### 16. PDF, CSV and email facts share one context contract

**Mechanism.** Contexts expose `supplier_id`, `part_id`, `evidence`, `quote_history`, `supplier_claims`, `supplier_profile` and `evidence_gaps`. Evidence records carry IDs, kind, source, priority and data. The live bundle also retains original extracted records and separate part contexts.

**What it is good for.** The agent and evaluator do not need a separate commercial reasoning path for every file format. Sources survive the transformation from document to decision.

**Evidence.** Regression validated for mixed PDF/CSV/email threads; live parsed-context logs use this integrated path. [supplier_evidence.py](negotiator/supplier_evidence.py), [intelligence.py](negotiator/intelligence.py).

### 17. Duplicate evidence is consolidated without discarding provenance

**Mechanism.** Repeated versions of the same recognized assertion/offer are merged with source references where compatible. Conflicting versions remain visible and receive conflict metadata. Numeric comparisons and profile rules exclude conflicted evidence instead of resolving it by input order.

**What it is good for.** An email that repeats its attached PDF cannot count as independent corroboration or double a cost claim. A disagreement between two sources remains reviewable.

**Evidence.** Regression validated for duplicate provenance and conflicting quote versions.

### 18. Quote chronology requires actual dates

**Mechanism.** Undated quotes remain listed with their prices but do not become “latest” because they were processed last. Recognized dates drive latest-date selection. Conflicting quote terms on the newest date do not receive an arbitrary winner. Calculated history fields retain fact-source references.

**What it is good for.** Prevents an older CSV processed after a current PDF from being treated as the current offer. This addresses the observed P08 chronology problem.

**Boundary.** “Latest dated quote” means latest among usable dated records, not necessarily the current actionable Arena offer. Actionability is determined separately from live thread state.

**Evidence.** Regression validated for input-order independence, undated records and same-date conflicts.

### 19. Historical price comparisons require a comparable commercial basis

**Mechanism.** Min/max history summaries require one known currency/unit basis and matching relevant commercial terms. Fields considered include annual volume, duration, payment, lead time, Incoterm, index clause, tooling, effective date, quality commitment and chargeback. Multiple-price comparisons require the core commercial fields to be complete. Incomparable prices remain visible as individual records rather than being pooled into a misleading target.

**What it is good for.** Prevents using a cheaper price per hundred pieces, another currency, a different volume commitment or worse payment terms as a supposedly equivalent benchmark.

**Boundary.** The integrated numerical target is anchored in the live opening package; historical prices are not automatically promoted to supplier floors. Correct history is useful context even when no policy rule consumes it.

**Evidence.** Regression validated across changed currencies, units and commercial terms in profile/intelligence/hardening tests.

### 20. Evidence gaps are explicit

**Mechanism.** Context reports when no supplier evidence, no recognizable quote, or no explicit index/cost-share claims were supplied. Unrecognized evidence remains available with a clear explanation of limited interpretation.

**What it is good for.** Makes “unknown” actionable for the team and prevents a missing document from being interpreted as proof of supplier flexibility or pressure.

**Evidence.** Regression validated for future/unknown evidence types and empty contexts.

### 21. A stable four-dimensional supplier-profile contract

**Mechanism.** The profile has `cash_sensitive`, `capacity_sensitive`, `quality_sensitive` and `price_rigid`. Each dimension is `unknown` or `likely`, with confidence and an evidence list. Unknown states have zero confidence and no invented support.

**What it is good for.** Gives the rest of the system a predictable interface for explicit supplier positions, including honest absence of evidence.

**Evidence.** Positive and unknown/negative cases are covered for every dimension in [test_supplier_profile.py](tests/test_supplier_profile.py).

### 22. Supplier-profile states require narrow, sourced statements

**Mechanism.** Rules look for explicit requests for earlier/advance payment, explicit capacity constraints or capacity-linked commitments, explicit quality commitments/quality risks, and fixed-price language or repeated distinct price refusals. A quoted quality commitment can support the quality dimension; observed ppm alone cannot. Confidence is fixed rule support—typically 0.8 or 0.85—not a calibrated probability.

Every likely state includes source, evidence ID, excerpt and rule. Repeated refusal support requires distinct message evidence. Price history, buyer wishes and missing files cannot establish a profile trait.

**What it is good for.** Supports explainable, restrained tailoring without speculative psychological labels. A teammate can inspect precisely why a flag exists.

**Boundary.** A quality-sensitive flag does not imply willingness to trade quality away. Current unified tactics directly reduce the discount for sourced `price_rigid`; other dimensions are retained/audited and are not a full supplier utility model. Availability of earlier-payment trades alone is not proof of cash pressure.

**Evidence.** Regression validated for each rule and unsupported/unprovenanced data. [supplier_profile.py](negotiator/supplier_profile.py).

### 23. Negation, quotations, conflicts and revisions are treated conservatively

**Mechanism.** Rules reject supported categories of quoted, reported, hypothetical and negated statements. Narrow German patterns supplement English rules. Conflicting explicit positions keep the result unknown. A clearly dated explicit revision can supersede an older position; an ambiguous/undated revision cannot silently clear a conflict.

**What it is good for.** Stops a supplier quoting our request—or saying “we do not need earlier payment”—from becoming evidence of that supplier's preference.

**Boundary.** This is tested pattern handling, not complete language understanding. Unfamiliar phrasing and languages may remain unknown. Copied text cannot be assumed harmless in every format, but P11's observed failure was not caused by copying.

**Evidence.** Regression validated with English/German statements, quotations, hypothetical language and dated revisions.

## 4. Argument priority and evidence use

### 24. A deterministic priority baseline

**Mechanism.** The extractor assigns priority 1 to recognized price/cost/payment/contract headers, 2 to recognized operational headers and 3 to context/unknown fields. Matching uses headers associated with nonempty values. The priority stays with the row through normalization.

**What it is good for.** Supplies a predictable relevance ordering without a model dependency. It keeps the pipeline usable locally when no LLM is configured.

**Boundary.** This is a coarse header heuristic, not a guarantee of argument strength or factual reliability.

**Evidence.** Regression validated by extractor tests.

### 25. Optional LLM priority ranking with a strict output contract

**Mechanism.** Explicit `priority="llm"` sends batches of supplied rows and negotiation context to a configured/injected completion function. Default batch size is 25. Results are matched by row ID, not response order. Every row must receive exactly one integer priority 1–3. Unknown/duplicate/missing IDs, invalid values and malformed JSON raise errors. Information and source values are not rewritten; empty input makes no model calls.

**What it is good for.** Allows contextual relevance ranking beyond header keywords without giving the model authority to alter source facts.

**Boundary.** The prompt treats CSV instructions as untrusted data and forbids external facts. Prompt restrictions are not a proof against all adversarial content. Provider failure is visible rather than disguised as successful heuristic ranking. This capability is optional; its effect on negotiation scores has not been established.

**Evidence.** Regression validated with injected completions in [test_priority.py](tests/test_priority.py); no ranking-model calls were needed for the latest deterministic live tests. [priority.py](arena_kit/priority.py).

### 26. Stronger relevant claims are presented first

**Mechanism.** Usable index/cost-share claims are ordered by priority 1 first, then descending absolute weighted impact, then stable evidence ID. File order does not decide the argument order. A duplicate claim with stronger priority updates the selected provenance/priority without double-counting the numerical impact.

**What it is good for.** Leads with the most relevant supported facts and makes output stable when attachment order changes.

**Boundary.** Priority measures relevance. It does not establish truth, supplier acceptance, or support for a discount.

**Evidence.** Regression validated in [test_tactics.py](tests/test_tactics.py); ordered claim metadata appears in decision audits.

### 27. Index claims and cost shares are calculated explicitly

**Mechanism.** A claim's weighted impact is `index_change_pct × cost_share_pct / 100`, expressed in percentage points. Decimal parsing is used for the components. Claims require sources and finite bounded values. For example, 6.5% movement on a 24% cost share contributes 1.56 percentage points.

**What it is good for.** Converts supplier prose into inspectable arithmetic instead of repeating index names without understanding their scale.

**Boundary.** This measures the supplier's stated impact. It does not verify the index, baseline, applicability, complete cost structure or resulting price.

**Evidence.** Regression validated and visible in live P01/P02/P03/P08 messages. [evidence_use.py](negotiator/evidence_use.py).

### 28. Claims cannot silently inflate a combined impact

**Mechanism.** Exact duplicate series/period claims are consolidated. Repeated/conflicting series or multiple periods for the same series prevent a safe combined sum. Shares above 100% also prevent aggregation. Scoped/conflicted or unsupported records cannot enter the calculation.

**What it is good for.** Prevents counting the same material inflation twice or adding incompatible time windows into a misleading total.

**Boundary.** The checks detect recognized structural overlap, not every possible economic overlap between different index names. Different claims can still rest on unverified supplier assumptions.

**Evidence.** Regression validated for duplicates, conflicts, repeated series and overlapping share totals.

### 29. Supplier claims do not automatically soften the numerical ask

**Mechanism.** `claim_adjustment_cap_pct` defaults to zero. If explicitly enabled, only usable claims produce an adjustment bounded by that cap. The agent records the claim report and applied adjustment. Unsupported/conflicting claims cannot silently move a numeric target.

**What it is good for.** Preserves the distinction between understanding a supplier's explanation and accepting it as established economics.

**Boundary.** Nonzero softening is an optional, unproven strategy setting. The existence of this control is useful; no optimal cap has been demonstrated.

**Evidence.** Regression validated for opt-in, bounds and component provenance in hardening tests.

### 30. Used and unused evidence is audited

**Mechanism.** Decision logs include claim sources, argument order, profile references, current-offer comparisons and an evidence-use audit. Evidence not matched by an active rule remains visible with a reason such as no supported rule changing this decision.

**What it is good for.** Lets the team distinguish extraction success from decision use. It directly addresses the concern that the context arrives intact but some of it never affects action.

**Boundary.** A logged use category does not prove that every fact changed the chosen number. The current policy still uses some evidence mainly in rationale rather than numerical selection.

**Evidence.** Regression validated and inspectable in live JSON decision records.

## 5. Cost evaluation and safety

### 31. Whole-package buyer cost replaces price-only ranking

**Mechanism.** The evaluator integrates the Arena's fixed-need/fixed-horizon cost model. It evaluates purchase spend, uncovered need, fallback risk, payment financing, freight, lateness, defects/chargebacks, tooling and index exposure/risk. A relationship-cost component exists only when authorized supplier-economic estimates are supplied; unified does not invent those estimates.

**What it is good for.** Allows a higher unit price to be a better agreement when payment, delivery, duration or other terms compensate. It also catches cheap short contracts that leave expensive uncovered demand.

**Live evidence.** P02 at EUR 373.75 with 90-day payment produced lower total cost than the prior EUR 368.45/14-day result, improving the observed score from 0.156989 to 0.280605. This supports evaluating financing; it does not isolate the causal effect of every policy change.

**Implementation/tests:** [cost.py](arena_kit/cost.py), [evaluator.py](negotiator/evaluator.py), [test_evaluator.py](tests/test_evaluator.py), [test_kit.py](tests/test_kit.py).

### 32. The cost model accounts for coverage, commitment and timing

**Mechanism.** Committed units cost money even if they exceed the buyer's need. Need not covered by volume or contract duration is bought at fallback cost, with the configured risk uplift. Contract coverage is limited to the buying horizon. Delayed price effectiveness uses the current price for applicable pre-change units. Payment uses the model's buyer interest rate and 360-day convention. Late delivery and defect costs use explicit case rates.

**What it is good for.** Prevents choosing a low headline price on the wrong quantity, an insufficient contract horizon, or a payment concession whose financing cost exceeds the discount.

**Boundary.** These are the published simulation/evaluation economics, not independently measured supplier or buyer financials. Longer commitment beyond the modeled horizon does not earn extra modeled coverage.

**Evidence.** Cost regressions and the diagnosed P07 short-horizon failure.

### 33. Actual closure is evaluated rather than favorable proposal defaults

**Mechanism.** Evaluation uses the actual proposed terms and supplier standard terms with the case's fixed terms and explicit plan defaults. In the helper's concrete merge order, buyer plan defaults are overlaid by supplier standards, case-fixed terms and finally proposed terms. Unsupported changes to fixed fields are rejected separately by validation. Negotiable fields are evaluated as they would close; omitted fields are not snapped to the buyer's preferred prior proposal.

**What it is good for.** Stops accepting a price-only supplier sheet under an imagined 90-day payment agreement when the actual quote's standard is 14 or 30 days.

**Evidence.** Regression validated for supplier-default closure and no favorable buyer snapping. Supplier standard extraction excludes buyer/Arena messages.

### 34. Must-haves and allowed term options are hard gates

**Mechanism.** Comparisons such as `ppm_commitment <= 1500` and `volume_per_year >= 22230` are evaluated on the actual closed package. Negotiable fields and allowed options constrain outgoing packages. Invalid numbers, unsupported terms and nonfinite costs cannot be accepted as valid deals.

**What it is good for.** Keeps an attractive price or fear of a zero score from overriding a real buyer requirement.

**Live evidence.** P10's final allocation of 19,890 remained below the 22,230 minimum, so the agent did not accept it. P11's earlier 6,400-ppm quote was also correctly identified as unacceptable, although its earlier follow-up behavior was defective.

**Regression evidence.** Numeric invalidity, allowed options and must-haves are covered across evaluator, package and safety tests.

### 35. A known reservation bound is required

**Mechanism.** A valid explicit buyer alternative defines the reservation cost. If no explicit alternative is supplied, a finite positive fallback cost is derived from need × horizon × fallback price with the configured risk uplift. A malformed explicit alternative does not become permission to spend without a bound. Unknown, NaN, infinite, negative or boolean inputs cannot authorize acceptance.

**What it is good for.** Prevents “any agreement is better than walking” from producing a deal worse than the authorized fallback.

**Evidence.** Regression validated for unusable alternatives and invalid fallback inputs. [_reservation_cost in unified.py](arena_kit/agents/unified.py).

### 36. Currency and pricing-unit compatibility fail closed

**Mechanism.** The live buyer cost model operates in EUR per ordered item. Explicit unsupported currencies or units, quote-basis conflicts and relevant parsing warnings exclude the quote from usable standing offers. The agent does not silently apply an exchange rate or convert a bulk unit with unknown semantics.

**What it is good for.** Prevents an apparently cheap USD or per-100-piece quote from being treated as an equivalent EUR unit price.

**Boundary.** Some Arena sheets rely on the protocol's EUR/item conventions when metadata is omitted. This is not universal authentication or conversion of arbitrary supplier pricing bases.

**Evidence.** Regression validated for non-EUR and incompatible unit metadata.

### 37. Supplier economics remain unavailable unless supplied

**Mechanism.** Evaluation supports supplier value/margin assessment only with usable explicit economic inputs such as full cost and financing rates. Otherwise it marks the assessment unavailable. The integrated agent does not back-solve hidden costs or a reservation price from a few concessions.

**What it is good for.** Prevents false precision in arguments about supplier margins, financing savings or sustainable pricing.

**Evidence.** Regression validated in evaluator/packages tests; no hidden supplier economics are loaded in unified.

### 38. A shared runner guard protects every selectable agent

**Mechanism.** The runner checks live supplier identity, action type, primary standing ID, validity, must-haves and reservation cost. Outgoing numeric sheets must cover the complete negotiable-field set. It also enforces message limits: at most three term sheets and a body no longer than 8,000 characters. Unsafe actions/counters are replaced using the integrated safety policy and the override is logged.

**What it is good for.** Keeps a baseline or future policy from bypassing core buyer constraints. Safety is enforced at execution as well as candidate selection.

**Boundary.** A guard checks available facts, not supplier truthfulness or global negotiation quality. Unified itself sends one sheet, while the shared protocol limit remains three.

**Evidence.** Regression validated for unsafe baseline acceptance, invalid counters and premature walking. The final 22 saved-history checks required zero replacements.

## 6. Package construction and selection

### 39. One selected package is sent, with alternatives kept internally

**Mechanism.** Unified evaluates internal candidates, selects one eligible package and sends exactly one term sheet. Considered candidates, exclusions, buyer costs and selected terms are retained in the private audit.

**What it is good for.** The buyer makes a decision and sells that proposal instead of sending a menu and letting the supplier choose the easiest concession.

**Boundary.** Lowest buyer cost among generated eligible candidates does not mean highest acceptance probability or global bargaining optimum. Repair selection is a separate path that favors a smaller necessary change among retained safe candidates.

**Evidence.** Regression validated for one-sheet output and selection auditing; live observed in later batches.

### 40. Price reductions are connected to explicit commercial consideration

**Mechanism.** The standard counter retains quoted non-price terms with a moderate price request. A stronger reduction can be conditional on earlier payment. Where appropriate and allowed, another concession can involve longer duration, larger volume or more delivery time. The outbound message names the give-get and makes the whole package conditional.

**What it is good for.** Gives the supplier a concrete reason to consider the price rather than asking only for money. It also prevents presenting a buyer concession as unconditional.

**Live evidence.** P01, P02 and P08 suppliers explicitly acknowledged earlier payment when reducing price. P03 accepted a longer commitment for later payment at the retained quoted price.

**Boundary.** The discount scale is a policy hypothesis. We do not know the supplier's actual value for each concession.

### 41. Distinct trades survive; redundant price ladders collapse

**Mechanism.** Candidate deduplication uses non-price commercial terms. With identical non-price terms, the lower buyer price survives. Distinct payment/duration/volume combinations are not declared supplier-dominated without a supplier utility model. The conventional trade shortlist retains deliberate diversity, up to three internal packages.

**What it is good for.** Preserves genuine negotiation options while avoiding several near-identical prices disguised as meaningful packages.

**Evidence.** Regression validated for distinct trades and identical-term ladder removal in tactics/packages tests.

### 42. Later-payment and supplier-alternative counters share a buyer-cost budget

**Mechanism.** Later payment can support a higher proposed price within the retained-terms counter's buyer-cost budget. The implementation calculates a price cap using the cost model's affine response to unit price, flooring to cents. Counters retaining an actual supplier alternative's terms also remain within that budget.

**What it is good for.** Prevents giving the supplier an easier total-cost ask merely because it appears as another package option. Makes commercial tradeoffs comparable in buyer economics.

**Boundary.** A buyer-cost-equivalent premium is not an estimate of supplier financing cost.

**Evidence.** Regression validated, including a later-payment option budgeted against the counter rather than the undiscounted opening.

### 43. No-giveback protection against current safe offers

**Mechanism.** Ordinary proposal selection caps total buyer cost at the best current safe supplier option. Identical non-price terms also cap unit price at the available quote. A package already available as the actionable standing offer is not resent as a new counter.

**What it is good for.** Stops the agent offering a worse deal than the supplier just offered. It directly addresses the older P01 sequence in which a EUR 136.06 counter followed an available EUR 135.50 offer on the same terms.

**Boundary.** The comparison can include supplier-authored indicative alternatives as information; only an actionable standing offer can be accepted.

**Evidence.** Saved live failure plus targeted regression in [test_tactics.py](tests/test_tactics.py). [proposal.py](negotiator/proposal.py).

### 44. Opening acceptance goals stay anchored

**Mechanism.** The acceptance target is derived from the original safe opening package search and stored per case/supplier. Moving the counter price later does not automatically raise that goal. Original supplier standard terms are reconstructed from the opening events, not overwritten by a later PDF.

**What it is good for.** Prevents accepting a weak supplier quote merely because our own concession schedule eventually crosses it. Keeps counter progression and success criteria separate.

**Boundary.** The original target may still be unrealistic. Final/deadline decisions are allowed to accept the best safe available deal even if that target was not achieved.

**Evidence.** Regression validated against the saved P01 moving-target failure and changed standard terms.

### 45. Broader search when conventional trades find no viable package

**Mechanism.** If the normal trade generator produces no safe opening/current package, the agent searches permitted commercial combinations at the quoted and scheduled counter prices. The opening-target shortcut no longer prevents that search. General package enumeration honors option lists, constraints and fallback bounds; candidate-space size is bounded before enumeration at 25,000 term combinations per candidate price.

**What it is good for.** Handles cases where a duration, volume or other commercial change matters more than another discount. P07's 12-month package against a two-year need exposed this gap.

**Evidence.** Regression and saved-opening validated: the corrected P07 path proposes a longer contract rather than asking for quote data already supplied. No corrected live P07 outcome is claimed.

**Boundary.** Search output is shortlisted. It is not an exhaustive search for supplier acceptability or a proof of an attainable deal.

### 46. Invalid packages trigger a specific revision request

**Mechanism.** Known must-have violations and recognized invalid option values are identified explicitly. The agent attempts a compliant package at the supplier's quoted price, retaining other known terms. Among its retained safe repair candidates, it prefers the smallest change to the invalid fields, then buyer cost. If no safe numeric repair is available, it asks for the specific revision/feasibility instead of pretending the quote is missing.

**What it is good for.** Converts “we cannot accept this quality/delivery/volume” into a useful next move. Avoids P11's repeated generic request for price/currency when the actual obstacle was 6,400 ppm versus a 1,500-ppm limit.

**Evidence.** Saved P11 opening replay now yields a compliant quality revision at EUR 47 and passes the guard. Regression tests verify quality repair, nearest retained quality choice and impossible revisions. P10 live observed a volume/delivery revision request.

**Boundary.** The agent cannot force the supplier to meet the requirement. Final unsafe offers remain unacceptable.

### 47. Repairable competitors are considered even when another offer is acceptable

**Mechanism.** An unacceptable supplier package is not discarded solely because another supplier already offers a safe deal. A costed revision can compete if it meets buyer constraints and costs no more than the best available safe offer. The decision evaluates the repaired package, not merely the cost of the invalid original. An uncosted revision does not displace an available safe deal.

**What it is good for.** Keeps a potentially cheaper supplier with a fixable delivery/quality issue in contention. P05 exposed the earlier tendency to negotiate only the initially acceptable supplier.

**Evidence.** Regression validated, including a case where the invalid quote's lateness cost exceeds the incumbent but a compliant repair is cheaper. Saved P05 opening now selects a delivery revision for supplier 70240. No corrected live P05 result is claimed.

### 48. Exact previously proposed packages are filtered in ordinary negotiation too

**Mechanism.** Previously sent identical term dictionaries are excluded regardless of price-freeze wording. If cent rounding/caps collapse scheduled counters into repeated packages, a broader permitted commercial search at the current quote is attempted. If no useful safe new proposal exists, an available safe standing deal can be accepted.

**What it is good for.** Prevents spending turns on identical numeric proposals while the supplier waits for meaningful movement. The repeated EUR 5.77 P08 package exposed the gap.

**Evidence.** Regression validated and final saved-history checked. This final change has not had an additional live test.

**Boundary.** This filter handles identical numeric packages; it is not a complete detector of semantically repetitive prose or every partial-term equivalent.

## 7. Adaptation, memory and argumentation

### 49. Explicit price freezes change the search dimension

**Mechanism.** A direct supplier statement that price reductions are frozen changes candidate generation to allowed non-price terms at the current quoted price. Quoted, hypothetical, negated or reported freeze statements are excluded by narrow rules. A recognized explicit statement that reductions are now possible clears the freeze state.

**What it is good for.** Avoids repeatedly demanding a lower price when the supplier identifies an organizational constraint. It asks whether a different trade can work rather than assuming non-price flexibility was promised.

**Live evidence.** P03 moved to EUR 436.44, 90-day payment and a 24-month commitment, yielding a 0.809957 score. Earlier menu tactics on P03 had produced 0.000000, but several changes separate those runs, so the score difference is not a controlled causal estimate.

**Boundary.** The quoted price may have been conditional on earlier payment. Changing payment is a new complete proposal, not an entitlement to keep a conditionally discounted price.

### 50. Supplier behavior provides a tentative progress signal

**Mechanism.** The agent observes primary supplier quotes following buyer responses. It needs three comparable observations, producing two consecutive concessions between 0% and 0.25% each. Changed modeled non-price terms, invalid prices or missing source IDs reset the comparison. A larger recent concession clears the signal. Repeated supplier snapshots without a buyer response do not create additional observations.

**What it is good for.** Recognizes diminishing price progress without waiting for exact “price freeze” wording. It adapts to actions while keeping uncertainty explicit.

**Boundary.** The threshold is a policy hypothesis, not a learned supplier floor. This does not infer motivation, credit stress or true capacity. Comparison uses evaluated negotiable commercial terms within the live EUR/item scope; it is not a universal equivalence detector for unmodeled supplier conditions.

**Evidence.** Regression validated for sparse inputs, changed bases, invalid values, renewed movement and missing provenance. Live observed in P02, with sources and measured concession percentages in the audit. [response_sensitivity.py](negotiator/response_sensitivity.py).

### 51. Behavioral exploration is deliberately bounded

**Mechanism.** A tentative signal allows one exploratory selection per case/supplier in an agent instance. Candidate exploration changes one allowed non-price dimension at the scheduled counter price and avoids commercial combinations already proposed. Selection still applies buyer cost, no-giveback, must-have and reservation checks. It does not permanently freeze price or force indexation; ordinary selection resumes afterward.

**What it is good for.** Adds sensitivity without fully committing to a personality label or endlessly jumping between tactics.

**Live evidence.** P02 switched from 14-day to 90-day payment; the supplier offered a financing-adjusted price that improved total cost. The mechanism worked in these runs, but the threshold and one-attempt policy are not calibrated across suppliers.

### 52. Explicit capacity refusal receives a feasibility response

**Mechanism.** After numeric volume repairs are exhausted, a latest reply with recognized capacity/allocation limitation and refusal language produces an acknowledgement, restates the buyer's required minimum and asks whether another permitted package can comply. The source message/offer is recorded.

**What it is good for.** Avoids responding to a clear capacity explanation as if the supplier had forgotten to quote. It keeps the must-have intact while allowing one meaningful question about alternatives.

**Evidence.** Derived from P10's live refusal and regression validated. No post-fix live P10 outcome is claimed.

**Boundary.** This is a narrow English-pattern branch, not a general refusal-understanding engine. It cannot invent capacity expansion, authorize a lower minimum, or guarantee every feasibility question will be nonrepetitive.

### 53. Explicit supplier answers and confidentiality refusals are remembered

**Mechanism.** Conversation state stores recognized baseline and inclusion answers with source references. It records whether a baseline/inclusion/breakdown question has already been asked and whether the supplier has refused to disclose its calculation. Buyer/Arena text and quoted/hypothetical answers cannot become confirmed supplier answers.

**What it is good for.** Prevents repeatedly demanding a confidential breakdown or re-asking a narrow question the supplier has already answered. Keeps the negotiation focused on the actionable disagreement.

**Boundary.** Memory is rule-specific. It does not yet summarize every possible supplier objection or prevent every generic clarification loop.

**Evidence.** Regression validated in conversation-state/tactical tests; acknowledgements are visible in P02/P08 messages.

### 54. Outbound argumentation is tied to the selected package

**Mechanism.** The message leads with the selected price and human-readable terms, explains concrete conditional consideration, and asks for confirmation or the blocking term. It avoids sending internal offer/message IDs, priority metadata or buyer reservation budgets. Those details remain in the private log.

**What it is good for.** Gives the supplier a coherent commercial proposal and avoids confusing implementation identifiers with external benchmark evidence.

**Evidence.** Regression validated for one proposal, concrete give-get wording and internal-ID exclusion; live observed in selected-package runs.

**Boundary.** Cleaner argumentation is observable. Superior persuasion independent of package economics has not been established.

### 55. Evidence is repeated when relevant, not indiscriminately

**Mechanism.** Numeric index claims are normally introduced with the initial rationale or when the supplier asks for supporting data. The message states that figures are supplier-supplied and unverified. Commercial price requests are described as negotiating proposals, not discounts proved by index arithmetic. Baseline questions are not automatically repeated after being asked/answered.

**What it is good for.** Avoids claiming that a supplier's own inflation evidence proves a lower price, and reduces repetitive boilerplate.

**Boundary.** Recognized supplier requests for data can still cause the same figures to be restated. No independent market benchmark is invented to satisfy such a request.

**Evidence.** Regression validated; live transcripts show the distinction between supplied figures and commercial requests.

### 56. Payment pivots explicitly replace the prior arrangement

**Mechanism.** When payment is extended relative to the current quote, the message names both periods, states that it replaces the earlier arrangement, asks the supplier to assess price and terms together, and invites a complete price-adjusted package.

**What it is good for.** Prevents the buyer appearing to retain an earlier-payment discount while withdrawing the earlier payment without acknowledgement. It creates a clearer path for a supplier financing premium.

**Evidence.** Implemented after iteration 1 and regression validated. P02's supplier had already demonstrated such repricing in the prior live outcome; the revised wording itself is not isolated as the cause of an improved score.

## 8. Acceptance, protocol and walking away

### 57. Informative alternatives are separated from actionable standing offers

**Mechanism.** All sheets in the latest supplier reply can inform cost comparison and counters. Only the first primary standing sheet is actionable for direct acceptance. Superseded historical offers are not accepted by ID merely because their terms look attractive.

**What it is good for.** Prevents a valid-looking but protocol-invalid accept. Earlier live P03 returned HTTP 422 when the agent tried to accept an additional alternative ID.

**Evidence.** Live protocol failure identified the rule; regression tests now cover indicative and superseded offers. The earlier failure was recovered within the same session using the actual standing ID.

### 58. Better indicative packages can be promoted by confirmation

**Mechanism.** When a cheaper acceptable supplier-authored alternative exists and the negotiation is sufficiently mature or final with enough moves remaining, the agent can request that exact package as the standing offer. It sends terms rather than accepting the indicative ID. Confirmation attempts are bounded for the same package; deadline closing falls back to a safe actionable offer.

**What it is good for.** Retains value from supplier alternatives while respecting the Arena's acceptance contract.

**Evidence.** Regression validated for confirmation, refusal, move budget and final primary acceptance.

**Boundary.** A proposed promotion is not guaranteed to succeed. No live score gain from this mechanism alone has been established.

### 59. Safe closing considers actual alternatives and budgets

**Mechanism.** At final offers, agreement status, move limits, configured message budget or explicit close, the agent chooses the cheapest acceptable actionable offer. An expensive final quote from one supplier does not by itself force accepting it or abandon another viable thread. Goal-based acceptance requires the anchored goal and minimum round condition. If no improving valid package remains, an available safe offer can be accepted.

**What it is good for.** Avoids losing a valid agreement through endless countering while retaining meaningful competition between visible suppliers.

**Boundary.** This is not optimal scheduling of all supplier conversations. It does not predict which unnegotiated supplier would make the best future concession.

**Evidence.** Regression validated for expensive final suppliers, competing offers, move budgets and deadline closing; live sessions completed with valid primary acceptance actions.

### 60. Walking away is a constrained last option, not a universal score rule

**Mechanism.** The agent seeks clarification or a compliant revision while moves and useful threads remain. The shared guard blocks premature walking when safe actionable offers or further eligible dialogue exist. Final unsafe offers are not accepted just to avoid a no-deal result.

**What it is good for.** Prevents unnecessary zero-score exits while preserving quality, volume and reservation limits.

**Important correction.** The Arena returned score **0.121058 with no deal in P07**, so walking away is not universally 0.00. P10 did return 0.00. Results are preserved exactly rather than forcing one interpretation across cases.

**Evidence.** Regression validated for premature walks; live observed at P07/P10 boundaries.

### 61. Existing session reliability mechanisms are integrated with the policy

**Mechanism.** The HTTP client uses the same move ID when retrying a POST, supporting server-side idempotency. Transient errors and short rate-limit delays can be retried; exhausted quota is not treated as a transient move failure. The runner supports current-session state recovery, missed-turn handling and deadline-aware closing. It does not need to open a replacement session to recover a standing-offer mistake.

**What it is good for.** Reduces duplicated moves, accidental quota use and lost negotiations after network or protocol issues.

**Boundary.** These are partly inherited infrastructure capabilities. They do not guarantee recovery from every error. The completed three-iteration task opened exactly six distinct sessions, without replacement sessions.

**Evidence.** Simulator/transport tests in [test_sim.py](tests/test_sim.py), live session logs and the earlier same-session P03 recovery. [client.py](arena_kit/client.py), [play.py](arena_kit/play.py).

## 9. Observability, local operation and validation

### 62. Incremental atomic logs survive failures

**Mechanism.** `play --out PATH` writes pending/running/ended or failed status incrementally. Logs include session/case/agent identity, opened input, parsed context, decisions and their reasons, supplier replies, safety overrides, results and errors. Atomic replacement prevents a partially written JSON file from replacing the last intact record. A failure retains the moves already recorded.

**What it is good for.** Makes errors diagnosable without spending another live session to reproduce the whole conversation. It enabled the P11/P07/P05/P08 investigations.

**Evidence.** Regression validated for failure persistence and live observed across sessions. [run_log.py](arena_kit/run_log.py).

### 63. Decision settings and source-code fingerprints are retained

**Mechanism.** Logs record settings such as opening discount, message budget, minimum rounds and claim cap. A SHA-256 fingerprint is calculated over Python files in `arena_kit` and `negotiator`. Final replay/benchmark artifacts also carry code identity.

**What it is good for.** Prevents comparing two scores as if they used the same policy when a code change occurred between runs. Distinguishes a final offline check from earlier live outcomes.

**Boundary.** A code hash is not a full environment lock: it does not capture every dependency, external service behavior or hidden server change.

**Evidence.** Inspectable in live JSON logs and final offline artifacts.

### 64. Known secrets are redacted and generated artifacts are kept out of normal pushes

**Mechanism.** Logs redact recognized sensitive keys and sufficiently long secret values discovered in the current environment. Nonfinite numbers are made JSON-safe. `.gitignore` excludes `.env`, environment copies, virtual environments, caches and generated `runs/`, while allowing `.env.example`.

**What it is good for.** Reduces accidental credential disclosure and keeps generated negotiation material out of ordinary source commits.

**Boundary.** Redaction only covers recognized keys/known values; it is not an exhaustive data-loss-prevention system. Supplier documents and case briefs can still be commercially sensitive. Ignoring a file does not remove it from Git history if it was already committed.

**Evidence.** Regression validated for known-secret redaction. [.gitignore](.gitignore), [run_log.py](arena_kit/run_log.py).

### 65. JSON execution records and readable conversations serve different review needs

**Mechanism.** JSON holds full machine-readable context and decisions. Generated Markdown conversations expose supplier/buyer message bodies, exact term sheets, closing actions, replay URLs and final result. The three-iteration report links both types of evidence and records what changed after each pair.

**What it is good for.** Lets a commercial teammate read the conversation while an engineer traces the exact selected candidate, source and execution branch.

**Boundary.** Markdown is a rendered view; JSON remains the more complete audit. Generated local artifacts are not automatically published or committed.

**Evidence.** Live-review artifacts in [the iteration report](ARENA_ITERATION_REPORT.md).

### 66. Local simulation exercises the existing architecture without Tacto calls

**Mechanism.** Local simulation and offline evaluation use the same agent contract and cost machinery. Offline tests explicitly unset hosted Arena test credentials when running the complete suite; simulator HTTP tests bind localhost. Supplier-provided evidence can be supplied through the extraction/context path. Simulator fixtures are evaluation inputs, not live supplier evidence.

**What it is good for.** Makes regression checking possible without live-session quota or model API charges.

**Boundary.** The simulator's supplier behavior is simplified. It cannot certify live supplier response or prove that a policy is persuasive.

**Evidence.** Local end-to-end tests and [evaluate.py](arena_kit/evaluate.py).

### 67. Saved traces are used as decision regressions, not invented outcomes

**Mechanism.** Replays feed recorded case briefs and supplier histories into the current policy and check decisions/guards. Later recorded supplier replies remain recognized as responses to the original buyer actions. The replay does not attach a new hypothetical negotiation score to those changed decisions.

**What it is good for.** Turns a costly live failure into a reusable offline regression. Preserves honest separation between “the policy now asks the right thing” and “the supplier would have agreed.”

**Evidence.** Tactical fixture tests and the final **22 checks / zero guard replacements** in [final replay](runs/three-iteration-review-20261010/final-offline-replay.json).

### 68. Synthetic stress scenarios check safety beyond the standard script

**Mechanism.** The benchmark covers standard supplier behavior, rigid suppliers, buyer must-have variants, short budgets and strict reservation bounds. Missing-document behavior is covered separately by extraction and runtime regressions. Agent/configuration sweeps allow comparison against baselines. Baselines can be evaluated without the production guard to reveal their own failures. Only standard-script scores are summarized where the theoretical optimum remains meaningful.

**What it is good for.** Detects unsafe acceptance, reservation violations and error-prone control flow before spending live quota. Shows when an apparent score gain comes from ignoring constraints.

**Evidence.** Latest focused benchmark: **15/15 completed, zero constraint or reservation violations**, standard-script mean **0.276773**. Earlier broad sweeps covered 75 runs/configurations. [final benchmark](runs/three-iteration-review-20261010/final-offline-benchmark.json).

**Boundary.** The unified mean was lower than an earlier aggressive buyer-only package baseline on the simple simulator. Safety and responsiveness improvements must not be relabeled as a universal score improvement.

### 69. Live development uses explicit budgets and preselected cases

**Mechanism.** The latest review sampled six distinct hosted practice cases without replacement before starting sessions. It saved the eligible list and seed, ran two sessions per iteration, recorded the results, implemented supported takeaways and validated offline before the next pair. Final changes were checked offline because the six-session budget was exhausted.

**What it is good for.** Limits quota consumption, reduces cherry-picking and creates a traceable change history.

**Boundary.** This remains a development sample. Different cases ran under different code versions; their score average does not measure the causal effect of changes. Cases were not held out from all earlier development.

**Evidence.** [selection manifest](runs/three-iteration-review-20261010/selection.json) and [complete review](ARENA_ITERATION_REPORT.md).

## 10. What has actually proved useful in live results

The following examples are the strongest concrete outcome evidence. They support keeping these mechanisms while preserving uncertainty about general performance.

| Mechanism | Observed example | Practical conclusion | Limit |
|---|---|---|---|
| Conditional earlier payment | P01/P02/P08 suppliers explicitly acknowledged payment concessions when reducing price. | Give the supplier concrete consideration rather than only asking for a discount. | The optimal discount/payment exchange is unknown. |
| Total-cost comparison | P02: EUR 373.75/90 days scored 0.280605 versus the earlier EUR 368.45/14-day result at 0.156989. | A higher price can be preferable after financing effects. | This is an observed run comparison, not a controlled experiment. |
| Response-sensitive exploration | P02's shrinking concessions triggered one alternative-term attempt. | Supplier actions can reveal when another trade is worth testing. | The 0.25% threshold is uncalibrated. |
| Commercial search under explicit price freeze | P03 agreed to EUR 436.44/90 days/24 months; score 0.809957. | An organizational price constraint need not close every bargaining dimension. | Acceptance of this package does not imply all frozen-price suppliers have the same flexibility. |
| Hard-constraint enforcement | P10 declined allocation below the required minimum. | A score incentive must not erase buyer requirements. | No-deal may be unavoidable; persuasion cannot create capacity. |
| Specific invalid-package revision | P10 received a numeric compliant revision request instead of missing-quote boilerplate. | Correctly identify the obstacle before negotiating. | Supplier refused; successful repair is not guaranteed. |
| Auditable source/decision logs | P11/P07 loops and P05 missed competition were traced to concrete branches. | Logging produces actionable learning without another live run. | Logs alone do not fix policy gaps. |
| Protocol-aware standing acceptance | Earlier P03 alternative-ID rejection was diagnosed and recovered in-session. | Separate economic attractiveness from executable acceptance. | Indicative alternatives still require confirmation. |

The six random-review scores were P02 **0.280605**, P03 **0.809957**, P05 **0.172908**, P07 **0.121058 without a deal**, P10 **0.000000**, and P08 **0.092021**. Four deals were reached. This is evidence of a runnable MVP with identifiable strengths and remaining weaknesses, not evidence of consistently strong negotiation performance.

## 11. Settings and capabilities we should not call proven

For completeness, these elements are present but their strategic benefit is not established:

- Default maximum opening discount **5%**; the standard retained-term request uses a fraction of that discount and stronger trades use the full scale.
- Default maximum buyer messages **6**, default minimum goal-based acceptance rounds **2**, and a concession scale that decreases with available rounds but has a floor.
- Profile-based price-rigidity softening and optional nonzero claim adjustment.
- The exact **0.25%** behavioral threshold and exactly one exploratory attempt per case/supplier.
- LLM-generated priority as a better ranking than the deterministic baseline.
- Selecting the lowest buyer-cost generated proposal as the best acceptance-adjusted offer.
- Automatically favorable supplier response to index sharing, longer contracts, quality commitments or higher volume.
- Broad arbitrary-document/OCR understanding or general multilingual supplier reasoning.
- Live score benefit of the last P05/P07 broader-search and P08/P10 follow-up fixes. They have offline evidence only in the latest task.

These are not reasons to remove the architecture. They are reasons to keep the distinction between a tested mechanism, a supported commercial hypothesis and a demonstrated negotiation outcome.

## 12. Implementation and verification map

| Layer | Main implementation | Main checks |
|---|---|---|
| Runtime CSV rows and context entry point | [quote_extract.py](arena_kit/quote_extract.py) | [test_quote_extract.py](tests/test_quote_extract.py), hardening CSV checks |
| Optional priority model | [priority.py](arena_kit/priority.py) | [test_priority.py](tests/test_priority.py) |
| Bundled-source exclusion | [supplier_input.py](arena_kit/supplier_input.py) | Extraction/context boundary checks |
| PDF reading and standard terms | [docs.py](arena_kit/docs.py) | [test_supplier_evidence.py](tests/test_supplier_evidence.py), OCR/closure hardening checks |
| Mixed supplier evidence | [supplier_evidence.py](negotiator/supplier_evidence.py) | Supplier-evidence and conflict tests |
| Scalar normalization and source-scoped context | [evidence_values.py](negotiator/evidence_values.py), [intelligence.py](negotiator/intelligence.py) | [test_intelligence.py](tests/test_intelligence.py), chronology/comparability checks |
| Supplier-profile contract | [supplier_profile.py](negotiator/supplier_profile.py) | [test_supplier_profile.py](tests/test_supplier_profile.py) |
| Buyer cost and validity | [cost.py](arena_kit/cost.py), [evaluator.py](negotiator/evaluator.py) | [test_evaluator.py](tests/test_evaluator.py), [test_kit.py](tests/test_kit.py) |
| Allowed package enumeration | [packages.py](negotiator/packages.py) | [test_packages.py](tests/test_packages.py) |
| Conditional trade construction | [tactics.py](negotiator/tactics.py) | [test_tactics.py](tests/test_tactics.py) |
| One-package selection and no-giveback | [proposal.py](negotiator/proposal.py) | Tactical and response-sensitivity checks |
| Claim calculations, memory and messages | [evidence_use.py](negotiator/evidence_use.py) | Tactical and claim-hardening checks |
| Behavioral signal and exploration | [response_sensitivity.py](negotiator/response_sensitivity.py) | [test_response_sensitivity.py](tests/test_response_sensitivity.py) |
| Integrated policy and repair | [unified.py](arena_kit/agents/unified.py) | [test_unified.py](tests/test_unified.py), [test_package_revision.py](tests/test_package_revision.py) |
| Runtime execution and common guard | [play.py](arena_kit/play.py), [client.py](arena_kit/client.py) | [test_sim.py](tests/test_sim.py), guard-hardening checks |
| Atomic audit and secret handling | [run_log.py](arena_kit/run_log.py) | Log persistence/redaction checks |
| Offline comparison | [evaluate.py](arena_kit/evaluate.py) | Saved replay and synthetic benchmark artifacts |

## 13. Practical reading and running guide

Select the integrated agent explicitly when running a live session; the command below is an example only and was not executed to create this reference:

```sh
python -m arena_kit.cli play case:P01 --agent unified --out runs/example-P01.json -v
```

Extract actual supplier files as rows or as a scoped context:

```python
from arena_kit.quote_extract import extract, extract_supplier_context

rows = extract(["supplier_quote.csv", "supplier_history.csv"])
context = extract_supplier_context("supplier_quote.csv", supplier_id="sup:FROM_LIVE_THREAD")
```

For local verification, keep hosted test credentials unset:

```sh
env -u ARENA_TEST_URL -u ARENA_TEST_KEY python -m pytest -q
python -m arena_kit.evaluate --agents unified --discounts 5 --out runs/offline-check.json
```

Local HTTP simulator tests may require permission to bind localhost. The benchmark is synthetic and does not start a live Arena session. Optional LLM ranking has separate model configuration and provider usage; the integrated deterministic agent does not automatically use it.

To diagnose a negotiation, inspect the full JSON in this order: actual input/attached sources, selected action and its reason, evaluated closed terms, constraint/reservation result, internal candidate exclusions, supplier reply, then final server cost and score. The Markdown conversation is useful for commercial reading; the decision audit explains why the program took that action.

## Appendix A. Exact policy settings and arithmetic worth preserving

This appendix documents concrete implementation details behind the characteristics. The presence of a precise formula is not proof that its strategic parameters are optimal.

### A1. Opening and concession schedule

- `max_discount_pct=5.0`, `max_messages=6`, `minimum_rounds=2`, `claim_adjustment_cap_pct=0.0` are constructor defaults.
- Discount/cap inputs must be finite numeric values in `[0,100)`; boolean values are rejected. The maximum opening discount must be positive. Message count must be a positive integer; minimum rounds must be a nonnegative integer.
- When explicitly enabled and supported by usable claims, the adjustment is the weighted claim impact clipped to `[-claim_adjustment_cap_pct, +claim_adjustment_cap_pct]`.
- The working discount is `max(0.01, max_discount_pct - adjustment)`.
- The round budget is the smaller of the configured message budget and the case round limit. The scheduled discount multiplier is `max(0.2, 1 - buyer_rounds / max(1, budget - 1))`.
- Conventional retained-term counters use `0.6 × discount`; earlier-payment or another explicit concession can use the full discount. Prices are rounded to cents.
- A supported `price_rigid` profile reduces the conventional discount by multiplying it by `0.4`. This is a rule-based hypothesis, not an estimated supplier floor.
- Target storage is keyed by `(case_id, supplier_id)` so movement in one negotiation does not redefine another's acceptance target.
- Behavioral exploration history also checks case identity and supplier identity. One exploratory selection per such scope is allowed within the agent instance.

### A2. Budget conversion for a different commercial package

For a fixed non-price package, the current cost model is affine in unit price. The policy evaluates the package at unit prices 1 and 2 to obtain `C1` and `C2`. When `C2 > C1`, a target buyer cost `B` implies:

```text
unit_price_cap = floor_to_cents(1 + (B - C1) / (C2 - C1))
```

This appears both in conditional-trade budgeting and in no-giveback caps. The result is reevaluated as an actual package and still must pass validity, must-have and reservation checks. It is not a supplier profitability calculation. The formula must be reconsidered if the cost model stops being affine in price.

### A3. Repair search and selection details

1. Identify recognized invalid-option fields and individual failing buyer must-haves.
2. Use the supplier's current quoted unit price only when it is finite, positive and not itself the invalid field.
3. Pin known nonviolating negotiable terms to their quoted values; let the allowed option lists supply revisions for invalid fields.
4. Keep only valid packages within the reservation and, when another actionable safe offer exists, within that offer's cost ceiling.
5. Exclude exact repair packages already sent in the recorded buyer thread.
6. Prefer the smallest normalized change across the invalid fields among retained candidates; use buyer cost as the secondary ordering.
7. Send one complete proposed sheet with an explanation of the required correction.
8. If no costed repair can compete with an existing safe offer, keep that safe offer rather than displacing it with an uncosted request.
9. Without an available safe offer, keep the exact unresolved requirement visible in a textual revision request. Recognized exhausted-volume/capacity cases receive the feasibility acknowledgement described above.

The numeric distance is `abs(new-old)/max(1, abs(old))` for numeric fields, summed across the invalid fields. Nonnumeric changes contribute a changed/unchanged indicator. General enumeration returns at most three retained packages, so this is the nearest retained safe repair, not a mathematical guarantee of the nearest point in a large full option grid.

### A4. Acceptance and action precedence

The current high-level path is:

1. Build usable current offers and identify acceptable actionable primary sheets.
2. When appropriate, request standing confirmation of a better indicative alternative.
3. While dialogue remains open, consider costed repairs of invalid packages, including competitors.
4. At close/final/budget conditions, accept the cheapest safe actionable offer if available.
5. Otherwise construct candidates, apply fixed-target acceptance where eligible, and send the chosen counter.
6. If no candidate remains, accept an available safe actionable offer.
7. If information is missing and useful dialogue remains, ask for clarification.
8. If no permissible safe agreement remains at closure, walk away.

The order matters. An invalid offer is neither an automatically missing quote nor an acceptable deal. A supplier-authored alternative is neither automatically irrelevant nor automatically actionable. Finality and move budgets constrain how much exploration can still occur.

### A5. Finite costs and score interpretation

The cost sum is rounded to cents. Evaluation returns a JSON-safe `null` total when computation is nonfinite, with warnings; such a result cannot authorize a deal. Logs separately replace nonfinite float values with JSON-safe nulls rather than emitting invalid JSON numeric literals.

The Arena's server result is authoritative for the completed session's score and cost. The agent does not receive or use a hidden best achievable deal as its reservation target. Comparing `c_open`, `c_deal` and server `c_best` after a session is an evaluation activity. A historical low price, supplier claim impact, or chosen counter is not a substitute for the server's actual result.

### A6. Source handling details that should survive future refactors

- Supplier message bodies are retained as document evidence even when no narrow claim/profile rule matches them.
- Recognized structured supplier claims and free-text index/cost-share claims can both enter the claim context.
- Attachment records are processed before the email's term-sheet representation so the attached quote can supply primary details and the sheet can fill omissions.
- Compatible duplicate records retain additional source references rather than multiplying their evidentiary weight.
- Source scope/extraction conflicts prevent numerical/profile use but remain available for inspection.
- Supplier standard terms come from supplier quote PDFs, excluding buyer/Arena messages; the opening standard is reconstructed from the opening prefix when anchoring the goal.
- Original attachment names remain attached to the message. The CSV extraction label uses a safe basename rather than treating a supplier-provided path as a local file to open.
- CSV raw byte parsing uses the downloaded content when available, preserving BOM/encoding behavior even though a readable text representation is also exposed.
- CLI extraction writes JSON to stdout and progress/completion status to stderr, so redirecting stdout to a JSON file does not mix status messages into the document.
- LLM priority ranking does not show the existing heuristic priority to the ranking model, preventing trivial copying of that score. It changes priority values only, preserves input ordering and validates complete row coverage.

## Appendix B. Team handoff checklist for preserving these strengths

When changing a mechanism, preserve the relevant invariant rather than its incidental wording:

| Invariant | A regression to avoid |
|---|---|
| Supplier facts retain sources and scope. | A useful-looking fact from another supplier or part affects this negotiation. |
| Unknown/conflicted input stays explicit. | A parser guesses a locale, currency, date or document meaning to make the pipeline look complete. |
| The policy evaluates actual closure. | Acceptance assumes payment/quality from our prior proposal rather than the standing quote. |
| Numeric sheets satisfy hard constraints and known bounds. | A no-deal score concern authorizes an unsafe package. |
| One proposal is selected and audited. | The supplier is asked to choose our strategy from a menu. |
| A concession is conditional on its package. | A later message withdraws the buyer's consideration without acknowledging it. |
| Current supplier concessions are not given back. | Scheduled counter movement offers a higher cost than available safe terms. |
| Progress signals remain tentative and sourced. | Small price movement becomes a fabricated hard floor or psychological diagnosis. |
| Unacceptable known terms receive revision requests. | A quality/capacity/economic problem becomes repeated “please send your quote.” |
| Repaired alternatives compete on repaired cost. | A potential competitor is discarded using the cost of its invalid original terms. |
| Only executable standing IDs are accepted. | A cheaper indicative or superseded quote ID causes a protocol error. |
| Logged tests remain honest about their scope. | A saved-history replay or simulator score is presented as a new live outcome. |
| Live quota is explicit. | A transport failure or disappointing score silently causes a replacement session. |

No new live session or model API call was made to write this reference. It documents the implementation and previously recorded evidence; it does not add new validation of bargaining outcomes.
