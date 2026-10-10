# Three-cycle MVP validation report

Date: 10 October 2026. Scope: the selectable `unified` agent, not a claim that
every legacy agent or the final-event deployment is ready. Work is on
`task/stefan-mvp-completion`; existing uncommitted work was preserved.

## Bottom line

Completed **three improvement cycles and nine new random Arena sessions**.
All nine closed valid deals. Final regression suite: **202 passed, 1 skipped,
15 subtests passed**. The agent is better connected and its trades are more
coherent, but these results do **not** establish competitive MVP performance.
Raw-material and price-increase negotiations still need work.

| Cycle | Random cases and scores /100 | Mean /100 |
| --- | --- | ---: |
| 1 | P11 61.96 · P07 62.74 · P10 65.51 | 63.40 |
| 2 | P08 7.07 · P01 22.58 · P07 62.74 | 30.80 |
| 3 | P07 62.74 · P01 26.79 · P18 27.03 | 38.85 |

The nine-session average is **44.35/100**, with six unique cases. Do not read
the different batch averages as a controlled improvement/regression curve.
Nothing was committed or pushed. `unified` remains explicitly selectable;
the default and comparison agents were not changed.

## Method

Each cycle reviews the rules and prior transcripts, implements a general fix,
runs regression tests and all three local cases with four agents, freezes the
code, and samples three hosted practice cases uniformly without replacement.
The seed and selection are saved before sessions open. Repeats across cycles
are allowed; weak scores are never replaced. No hidden best price is used by
the agent. Local and hosted source hashes must match within each cycle.

Random batches have different case mixes. Their averages are descriptive,
not proof that a change improves negotiation performance.

## Cycle one — compare whole packages before stopping

Previous P18 evidence showed that a supplier could beat our requested price
while adding index risk, and the agent would stop. A separate restoration
module now considers a previously requested term at a higher price. It offers
at most half the modeled benefit back to the supplier, never above the prior
ask, and preserves buyer constraints and reservation cost. It tries this only
once per supplier and explicitly asks for approval. It does not infer motives.

Tests: **185 passed, 1 skipped, 15 subtests passed**. Added tests cover payment,
index risk, buyer constraints, repeat avoidance, and immediate acceptance when
the target is achieved with unchanged terms. Changed-file Ruff and diff checks
passed. Local scores stayed unchanged, with no contract audit errors.

Seed: `90500493`. Source SHA-256:
`70085df8ee0a39e60547b0b7c60cbae2f21450026af89726dd7064a64b174f87`.

| Case | Score /100 | Replay |
| --- | ---: | --- |
| P11 | 61.96 | [Quality negotiation](https://arena.tacto.ai/replay/474a8aec6d025a89) |
| P07 | 62.74 | [Bundling negotiation](https://arena.tacto.ai/replay/607b387ea2b3b814) |
| P10 | 65.51 | [Capacity negotiation](https://arena.tacto.ai/replay/1b0e001bbcf2f40a) |

All three were valid deals, with zero automated contract audit errors and no
runner errors. None needed restoration: the hosted benefit of that branch
was not tested by this random selection. P11 repaired the 1500-ppm must-have
and reduced price, but did not explore stronger quality/chargeback trades.
P07 secured full-horizon coverage. P10 secured the required volume but ignored
a direct request for evidence supporting our target price. P11 also received
a repeated breakdown request after sharing material percentage and refusing
further detail. Those two observed response-handling gaps informed cycle two.

## Cycle two — answer the supplier's evidence question

Added a separate buyer-argument module, outside the supplier-profile pipeline.
On a price-evidence request, it may cite a dated same-part/same-supplier quote
with known EUR/per-one-unit basis. It states explicitly that historical terms
may differ and the record is not a current comparable offer or a supplier cost
floor. Without usable evidence it honestly calls the target a commercial
proposal. No private reservation value is disclosed, no motive inferred, and
the price ladder is unchanged. Partial refusal of further cost details is now
recognized too.

Tests: **198 passed, 1 skipped, 15 subtests passed**. Invalid scope, unknown
currency, other currencies, price units, future/missing dates, non-finite prices,
duplicate citations and partial disclosure are covered. Local scores unchanged.

Seed: `491255777`. Source SHA-256:
`3072a235414ead3e6f6bb6afe79c5580f89ae6ae853c191faa28c0dd14bf0f0d`.

| Case | Score /100 | Replay |
| --- | ---: | --- |
| P08 | 7.07 | [Raw-material negotiation](https://arena.tacto.ai/replay/ef9b9822c5659efc) |
| P01 | 22.58 | [Price-increase negotiation](https://arena.tacto.ai/replay/7eeb3f813ce80c4c) |
| P07 | 62.74 | [Bundling negotiation](https://arena.tacto.ai/replay/a4e1c02958f7b0d5) |

All three deals met must-haves, zero contract audit/runner errors. P07's messages
were identical to cycle one. P08 stopped when its next one-cent proposal fell
under the stopping threshold; it retained half-horizon coverage. Inspection
showed coverage had been costed at the opening price, not candidate prices.
P01 chose our earlier-payment/higher-price option and held at EUR 136.50 with
14-day payment. That exposed a one-sided package trade. The supplier asked for
the cited document, which the price-question detector did not recognize.
No cycle-two run exercised the new qualified historical quote renderer, so
that branch remains unit-tested rather than hosted-proven.

## Cycle three — economically coherent packages and source replies

Earlier payment/larger supported commitments now accompany the lowest price
option; higher price options retain ordinary terms. Stronger supported quality
can still cost the buyer a higher price: that is a different, legitimate trade.
Buyer-coverage changes are costed at each actual candidate price and rechecked
after price concessions and other term changes, not at the old quote price.
Unknown motives still produce the conservative ladder, except for explicit
buyer constraints and economically justified demand coverage.

A request for a previously cited document can now receive up to two text
attachments: only verified supplier-authored archive records already cited in
that thread. The text is labeled as source excerpts, not independent cost
verification. No arbitrary file is sent; no repeat attachment is made.
The agent also recognizes the supplier saying its cost figures remain private.

Added regression checks cover the direction of the payment/price trade,
coverage switching at a generic break-even point, rechecking after repricing,
source scope, duplicate attachment prevention and actual agent integration.

Final tests: **202 passed, 1 skipped, 15 subtests passed**, including a full
suite rerun on the exact hosted source version. Changed-file Ruff and
`git diff --check` passed. This is not a claim of clean repository-wide lint:
three previously known import-order findings in untouched files remain.

Seed: `535048855`. Final source SHA-256:
`099c205e94163e3959c4e0f8626c2c29ccef477eab35fd3cdac746745a3f96a3`.

| Case | Score /100 | Replay |
| --- | ---: | --- |
| P07 | 62.74 | [Bundling negotiation](https://arena.tacto.ai/replay/2c9bf8989354f7f5) |
| P01 | 26.79 | [Price-increase negotiation](https://arena.tacto.ai/replay/5864d94fd561c88c) |
| P18 | 27.03 | [Raw-material negotiation](https://arena.tacto.ai/replay/b35b2561054ef8d6) |

All three deals met must-haves, zero contract audit/runner errors. Across all
nine runs the predicted accepted total cost matched Arena's actual closing
cost, and local/hosted fingerprints matched within each cycle. The final code
still matches cycle three's frozen fingerprint. No code was tuned after the
last hosted batch; the following findings remain explicit follow-up work.

- **P07:** same messages, terms and score across all three cycles. No regression
  there, but no demonstrated gain either.
- **P01:** EUR 136.69 with 30-day payment cost EUR 1,138,519.68, versus cycle
  two's EUR 136.50 with 14-day payment costing EUR 1,140,916.33. The higher
  unit price was the cheaper overall deal: EUR 2,396.65 saved and +4.21 score
  points. This is one repeat with several changes, not causal proof.
- **P01 evidence:** the new renderer answered the price question using the
  same-supplier/same-part historical `quote:7300001`, with explicit caveats.
  Arena marked that citation **irrelevant**; the supplier treated it partly
  as a rival-quote claim while acknowledging it was its own older quote. It
  was not marked contradicted, but it was also not verified useful leverage.
  The wording “the referenced document was not included” did not trigger the
  narrow document-request handler. Attachment delivery remains local-tested,
  not demonstrated in these hosted runs.
- **P18:** the supplier offered EUR 5.60 with index risk for 24 months. The
  restoration branch offered EUR 5.68 without index risk, modeled to save
  EUR 4,544.08 versus the standing package. The supplier refused: indexation
  was mandatory for that duration. The agent did not repeat the package, but
  spent one generic clarification message before accepting the same indexed
  offer at final status. Thus the restoration proposal itself produced **no
  additional saving**. The 27.03 score exceeds the earlier pre-cycle run's
  20.24, but the difference came from the supplier's initial counterprice,
  not successful removal of index risk. The cheaper initial counter cannot
  be attributed to one code change from this uncontrolled comparison.

## Local comparisons and safety

All cycles reproduced these local simulator scores (out of 100):

| Agent | S01 | S02 | S03 |
| --- | ---: | ---: | ---: |
| unified | 34.78 | 34.37 | 40.63 |
| supplier | 34.28 | 34.37 | 11.64 |
| packages | 8.45 | 8.59 | 23.19 |
| advanced | 60.91 | 60.32 | 73.79 |

These are scripted cases, not realistic supplier performance. `advanced`
still scores higher locally. We did not tune to beat those fixtures or claim
that unified beats the baselines in hosted negotiations; that needs matched
comparisons. Every unified local run passed the automated contract audit.

No case-ID-specific policy was added. Tests use generic payment, quantity,
quality, price and index conditions. Unknown profiles remain conservative.
The nine hosted sessions created here are recorded by distinct session IDs;
shared team quota counters also moved between batches, so their total change
is not presented as this run's consumption. No extra replacement sessions or
final-event result feeds were used.

## What remains — in simple terms

1. **Find better trades when price bargaining stalls.** After a supplier rejects
   removing indexation, consider permitted risk limits/deadbands or shorter
   duration and a matching price. Ask for concrete quality options rather than
   inventing guarantees. The current restoration mechanism changes one earlier
   requested term once; it is not a full negotiation search.
2. **Use evidence the Arena recognizes as relevant.** A true old quote is not
   automatically a useful rival quote. Validate the intended claim type and
   its exact scope; compare against buyer records without guessing costs.
   Supplier claim adjustments are still capped, not independently verified.
3. **Understand more supplier responses.** Narrow text rules can miss indirect
   document requests and ask a generic question after the supplier already
   explained a refusal. Broader response handling needs generic regression
   examples, not phrases hardcoded for these case IDs.
4. **Test comparable strategies and multi-supplier cases.** All nine randomly
   selected sessions had one supplier. Parallel RFQ behavior is locally tested
   but not covered by this batch. Keep the default unchanged until controlled
   hosted baseline comparisons support a decision.
5. **Verify final-event operations.** Actual release data, deployment, deadlines
   and submission still need an operational check. Unknown supplier margins
   mean relationship charges cannot be predicted in every future case, even
   though all nine observed closing costs matched.

The next useful experiment is a matched comparison on weak case types with
claim-relevance checks and a bounded index-risk trade. It was not added as a
fourth cycle or an unrequested extra Arena batch.

## Evidence locations

Full manifests, per-case decisions and actual transcripts are stored locally
under ignored `output/validation/iteration-{1,2,3}-{local,hosted}/` folders.
The final cycle-three local manifest is in `iteration-3-final-local/`; the
earlier `iteration-3-local/` run is retained from before a source-excerpt wording
clarification. The final local and hosted hashes match.
The plan is [MVP_ITERATION_PLAN.md](MVP_ITERATION_PLAN.md). This report preserves
the earlier [MVP_VALIDATION_REPORT.md](MVP_VALIDATION_REPORT.md) as historical
evidence rather than replacing its results.
