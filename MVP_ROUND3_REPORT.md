# Third three-cycle improvement report

## Results

Completed **three change/test/reflection cycles and nine new random hosted
sessions** (iterations 7–9). No merge, replacement runs, commit, push or default
agent promotion. All nine deals met must-haves and remained below their actual
reservation bounds. There were no runner errors, contract-audit errors,
evidence-loader warnings or recorded timeouts.

| Cycle | Random case scores /100 | Mean /100 |
| --- | --- | ---: |
| 7 | P02 **4.68**, P11 **61.96**, P03 **82.39** | 49.67 |
| 8 | P10 **65.51**, P03 **89.98**, P04 **76.61** | 77.37 |
| 9 | P04 **76.61**, P07 **64.72**, P01 **61.61** | 67.64 |

Overall **64.90/100** across nine sessions and seven distinct cases. This is
higher than the preceding round's 34.48, but **not a controlled overall uplift**:
the samples differ and this round did not include weak P05/P08. Multiple changes
and supplier response variability prevent isolating each mechanism's effect.

Specific observed progress is more informative:

| Case | Earlier result /100 | Latest result /100 | What happened |
| --- | ---: | ---: | --- |
| P03 | 82.39 | 89.98 | A higher price bought 90-day payment and lower actual total cost. |
| P04 | 0.00 | 76.61 | The cheaper 24-month package became the primary standing offer. |
| P07 | 62.74 | 64.72 | EUR 5.49 instead of 5.52 with the same 24-month/30-day terms. |
| P01 | 26.79 | 61.61 | One sourced earlier-payment proposal led to several reciprocal price reductions. |
| P02 | 9.22 | 4.68 | Stronger opening did not help; later cycle-eight fixes were not rerun on it. |

Final local verification: **276 passed, 1 skipped, 15 subtests passed**. This
includes a small disclosure fix made after the final transcript review; that
fix has **local/saved-input validation only**, not a new Arena result. The
last hosted version passed 271 tests before its three sessions. The distinction
and both fingerprints are retained below.

## Review of Jonas's recommendations and strategy safeguards

Reviewed all 876 lines of `MVP_CORE_CHARACTERISTICS.md`. Its referenced source
modules and live artifacts are not all present here, so its score claims are
treated as reported evidence, not independently reproduced results. No branch
was fetched or merged. The starting working-tree source was
`8047ab679d7d55006808b487bcf663e3432a3d534ec15006c1efa6aefe1ec154`.

| Recommendation | Decision and reason |
| --- | --- |
| One selected package, private alternatives | Adopt. Makes the conditional proposal explicit; do not assume a menu is always better. |
| No giveback, full-history duplicate checks | Adopt as economic/interaction safeguards, not supplier psychology. |
| Finite reservation, actual closure, compatible quote basis | Harden. Malformed alternatives must not authorize unlimited spend. |
| Supplier claims default to zero numerical adjustment | Adopt. Still cite them; a supplied explanation is not verified cost. Preserve opt-in two-point cap. |
| Diminishing-progress and price-freeze adaptation | Adapt in the next cycle, with sourced observations and bounded term exploration. Never label a hidden floor. |
| Useful repair and competitor selection | Preserve existing costed must-have repairs; review general gaps against new transcripts. |
| Automatically offering earlier payment | Do not adopt. Our opening trades require a sourced profile; unknown motives stay unknown. |
| Exact round/discount/0.25% settings | Do not copy as proven settings. They lack controlled evidence. |
| Broader OCR/CSV, alternative logger, guard changing all baselines | Defer as separate infrastructure work; preserve baseline comparability. |

The published grade is based on **accepted total cost**, normalized against a
hidden fixed best cost, not on citations or proposal quality. Buyer constraints
remain hard limits. Hidden economics and post-run `c_best` never enter policy.
No case IDs, memorized winning prices or practice-score lookup are used.
Budgets, internal cost calculations and our exploratory signals stay out of
supplier messages. The implementation remains deterministic and uses no LLM.

## Iteration seven

Implemented the first four adopted items in a separate proposal-safety module
and the unified policy. Only one complete package is sent, while considered
packages and exclusions are retained in the decision audit. Exact prior sheets
are excluded across the thread. Proposals cannot cost more than an available
safe offer/reservation, including when a price rise is justified by another term.

Explicit invalid alternative/fallback inputs now fail closed; fallback risk is
included when deriving a fallback bound. Buyer attachments cannot set supplier
standards, and explicit non-EUR/bulk-unit quote bases cannot authorize a deal.
Claims remain cited as unverified supplier statements; conflicting/overlapping
claim totals do not move prices, and numerical softening defaults to zero with
an explicit opt-in cap of two percentage points.

Local gate: **243 passed, 1 skipped, 15 subtests passed**; all four agents'
three local-case scores unchanged, with no unified contract-audit errors.
Changed-file Ruff and diff checks passed. Seed **490206095** selected:

Source: `96ced2c609740744eb366f0c039b7a85761ded31ed45e6f42ece1d63237c1d16`;
the final local gate and hosted fingerprints match.

| Case | Score /100 | Replay |
| --- | ---: | --- |
| P02 | 4.68 | [Motor](https://arena.tacto.ai/replay/5e23a4e68ee47bb2) |
| P11 | 61.96 | [Quality](https://arena.tacto.ai/replay/cfcaf17071848d66) |
| P03 | 82.39 | [Renewal](https://arena.tacto.ai/replay/9ffebbca85965686) |

All three deals met must-haves; no runner or contract-audit errors. P11 and P03
matched previous outcomes. P02 declined from the previous 9.22 to 4.68. Several
message/selection changes occurred, so this is not an isolated estimate of the
claim-cap effect. It certainly does not support claiming a stronger opening
automatically produces a stronger result.

Reflection: P02 repeatedly identified indexation as a possible exchange, but the
agent failed to ask for its full clause. P03 said price cuts were blocked and
invited volume/payment proposals, but clarification did not become a concrete
economic experiment. P11 correctly repaired quality and reached the same final
price; its fixed payment term must not become an invented bargaining lever.

## Iteration eight

Implemented whole-package progress: price movement now accounts for modeled
cost improvements, with a half-gap cap. Turning a must-have failure into a valid
package can also earn bounded movement; a lower price with worse total cost
does not. Supplier standards are reconstructed at the earlier observation.

A separate response signal uses a sourced direct price constraint or three
comparable supplier observations after buyer replies with two concessions in
the 0–0.25% band. This is an explicitly uncalibrated trigger, not a hidden floor
or supplier motive. Changed non-price terms, duplicated observations, missing
IDs and renewed movement break the comparison; a stated reopening clears a
freeze. Quotes and conditional statements are excluded by narrow rules.

Once ordinary price negotiation stalls, one higher-price/later-payment
experiment is allowed, retaining at least half the modeled benefit and every
buyer constraint. It leaves the profile unchanged, clearly replaces the old
payment arrangement and never leaks the internal signal. Index invitations
without complete terms instead receive one targeted request for series, share,
base month, deadband and matching price; no missing value is guessed.

Local gate: **258 passed, 1 skipped, 15 subtests passed**. Added tests cover
price-scale changes, repeated/missing observations, changed payment bases,
explicit reopening, quoted/negated/hypothetical refusals, one-shot exploration,
incomplete-clause clarification and feasible delivery repairs at varied prices.
The previous stopping test was adjusted to a genuinely negligible residual gap
under the new half-gap cap; the stopping rule itself was not removed.
All local comparison scores stayed unchanged; audits and changed-file checks
passed. Seed **3081553500** selected P10, P03, P04 before sessions opened.
Local/hosted source: `2e20bda776b5a5289a0334112b08627511f72af82971ae8936a143a684c3c6e5`.

| Case | Score /100 | Replay |
| --- | ---: | --- |
| P10 | 65.51 | [Capacity](https://arena.tacto.ai/replay/f42c01a2e3cfaa5f) |
| P03 | 89.98 | [Renewal/payment trade](https://arena.tacto.ai/replay/dc7aac384ebe43c1) |
| P04 | 76.61 | [Bearing renewal](https://arena.tacto.ai/replay/45600ca5252cf4cb) |

Mean **77.37/100**; all valid deals and no runner/contract-audit errors. P10
matched its prior 65.51 result. The costed feasibility credit was exercised, and
its purchase-order citation verified. P04 improved from the earlier zero: the
supplier put EUR 4.88/24 months directly into the primary standing offer. It
did not require the secondary-offer confirmation branch in this run, so we do
not attribute the gain specifically to that branch.

P03 gives useful live mechanism evidence: after three flat comparable quotes,
the agent proposed EUR 433.03 for 90-day payment and retained its 24-month,
4,580-unit commitment. The supplier countered at **EUR 433.08/90 days**, which
was accepted. This lowered actual cost from the previous EUR 3,968,442.37 to
**EUR 3,942,826.22**, a **EUR 25,616.15** improvement, and raised the observed
score from 82.39 to **89.98**. The more expensive/oversized supplier alternative
was not chosen. No hidden supplier financing rate was guessed.

Important model limit: predicted accepted cost was EUR 3,942,566.59, **EUR 259.63
below Arena's result**. Arena's relationship-cost component accounts for the
gap; our policy lacks the supplier economics needed to calculate it. P10/P04
matched exactly. All actual accepted costs remained below their reservation.
Do not describe this as a universally exact evaluator or back-solve the hidden
cost from this result. The final cycle adds explicit post-run reconciliation.

Reflection: keep the bounded trade because it operated usefully, but do not
claim the 0.25% trigger is optimal. P04 again asked “Which figures is that based
on? Please send us the data,” which our phrase matcher missed. Earlier P08 also
showed stopping after one small supplier move; use an anchored opening goal and
a minimum observation period for threshold-based early stopping, without
blocking deadline/final acceptance or concrete cheaper alternatives.

## Iteration nine

Implemented an opening buyer-cost aspiration reconstructed from the original
supplier prefix, including its original standard terms and scoped evidence.
It is cached separately by case, supplier and opening input; later concessions
cannot make the goal easier. It remains an internal policy aspiration, not an
estimate of the hidden optimum. Threshold-based early acceptance now waits for
two buyer messages by default; an exhausted search, final status or deadline
can still close safely. Cheaper current structured alternatives are not dropped
just because the aspiration is met.

Direct requests for supporting figures now receive eligible evidence or an
honest commercial-proposal explanation. Breakdown requests are not repeated
when ignored. Parallel secondary counters are also checked against the global
safe-offer cost ceiling, without closing an RFQ per supplier. Completed hosted
runs record predicted/actual cost and component differences; this is post-run
reporting, never a feedback channel for hidden supplier economics.

Local gate: **271 passed, 1 skipped, 15 subtests passed**. All four agents'
local scores remain unchanged. Focused tests cover scoped/fixed goals, original
standards, threshold timing, final/deadline precedence, concrete alternatives,
secondary RFQ budget checks, evidence questions and honest cost reconciliation.
Changed-file Ruff and diff checks passed.

Seed **298294475**; local/hosted source:
`c80de2f0985204f6e836000c42d623b73928b59b7c29863160b495e88984f6e7`.

| Case | Score /100 | Replay |
| --- | ---: | --- |
| P04 | 76.61 | [Bearing renewal](https://arena.tacto.ai/replay/b326f6572b72cd69) |
| P07 | 64.72 | [Fastener commitment](https://arena.tacto.ai/replay/2b1d082c1f74835e) |
| P01 | 61.61 | [Foundry/earlier payment](https://arena.tacto.ai/replay/4f37ca812050311c) |

Mean **67.64/100**. All three valid deals; no runner/audit errors or timeouts.
Predicted and actual accepted cost matched to the cent in this batch.

P04's newly recognized evidence request received two qualifying purchase orders
and the argument verified. Its price stayed at EUR 4.88: verified evidence did
not earn extra points. P07 accepted EUR 5.49/30 days/24 months, saving EUR 1,812
more than the previous EUR 5.52 deal. Its coverage improvement informed bounded
counter movement, rather than producing another fresh percentage discount.

P01's selected opening was EUR 131.62/14 days, backed by the supplier's archived
earlier-payment request. The supplier explicitly acknowledged that consideration
and moved to 135.60, 134.50, 133.90 and finally **EUR 133.80/14 days**. The
accepted cost was **EUR 1,118,686.39**, EUR 19,833.29 below the preceding
EUR 136.69/30-day outcome, even after pricing the buyer's earlier-payment cost.
The agent stopped on negligible remaining proposed benefit, not by pretending
it had reached its anchored aspiration.

### Final reflection fix — local only

Review exposed an argumentation bug: the price/evidence keyword matcher treated
P01's acknowledgement of verified price history as a fresh request, then sent
more purchase-order IDs. These were valid and nonduplicate, but unnecessarily
disclosed more history; the supplier said it had received a lot of material.
Do not treat the higher score as proof that this repetition was desirable.

The matcher now requires a real request/question and rejects recognized quoted,
negated and acknowledgement-only text. New tests cover all four cases plus a
genuine request following an acknowledgement. On the saved P01 messages it
still answers the first actual request and emits nothing for the later
acknowledgements. This verifies the trigger, **not the supplier's hypothetical
reply or a new score**. No tenth session was opened.

Final local-only source:
`7ec1597179b26948aa08f150622f4dc84d1914fc2995ca32220066b7934c548e`.
**276 passed, 1 skipped, 15 subtests passed**; local comparisons unchanged and
contract audits clean. This final fingerprint differs from the last hosted
fingerprint only because of the disclosed post-review code/test fix.

## Local comparison and reproducibility

Scores /100 remained identical in every local gate, including post-review:

| Agent | S01 | S02 | S03 |
| --- | ---: | ---: | ---: |
| unified | 34.78 | 34.37 | 40.63 |
| supplier | 34.28 | 34.37 | 11.64 |
| packages | 8.45 | 8.59 | 23.19 |
| advanced | 60.91 | 60.32 | 73.79 |

These scripted cases establish no observed local regression, not superiority:
`advanced` still scores better here. All comparison agents and the `supplier`
CLI default remain intact. Changed-file Ruff and `git diff --check` pass.

Each random sample/seed was persisted before opening any of its sessions; each
hosted source matched its preceding completed local gate. No code was edited
while a hosted batch ran. Full manifests, decisions and transcripts are under
`output/validation/iteration-{7,8,9}-hosted/`. Final matching local manifests are
`iteration-7-local-final`, `iteration-8-local`, `iteration-9-local-final`, plus
`iteration-9-post-review-local` for the final disclosure safeguard. Earlier
local attempts were retained rather than overwritten. These output directories
are ignored by Git; replay links above are the shareable hosted evidence.
Git base remains `cb01512947a07d98ae020af3014d968d21ef06cd`, with pre-existing
user work preserved. These source identities describe working-tree versions,
not committed releases.

## Final reflection and remaining work

**Keep:** one explicitly selected conditional proposal; original-evidence
aspirations; no-giveback and constraint gates; observed whole-package progress;
one bounded response trade; exact standing-offer acceptance; and auditable
source/cost checks. The strongest new live mechanism evidence is P03's
higher-price/later-payment exchange. P01 also supports retaining a concrete
sourced early-payment proposal rather than offering the supplier an easier
menu choice. Neither example establishes universally optimal settings.

**Do not claim:** that every Jonas feature was merged, that nine development
runs prove general superiority, that history proves supplier costs, that the
evaluator knows hidden relationship economics, or that the final local-only
disclosure fix already has the same hosted scores.

Remaining priorities:

1. **Matched validation on weaker cases.** P02 remains weak; P05/P08 were not
   sampled in this round. Test the new index clarification, feasibility-value
   counters and stopping rules on predeclared matched cases/configurations,
   with enough repeats to distinguish behavior from response variability.
   Keep all failures; no best-run cherry-picking or hidden C_best tuning.
2. **Control repetition and clarification scope.** The final disclosure fix
   needs hosted confirmation. Our English phrase rules still miss some wording;
   a generic trade-detail question is currently bounded once per thread, not
   separately per genuinely new term. Extend with targeted regressions rather
   than broad guessing or unlimited clarification loops.
3. **Understand model uncertainty without inventing economics.** Eight of nine
   accepted costs matched exactly; P03 differed by the hidden relationship
   component. Monitor discrepancies and retain reservation headroom. Explicit
   disclosed supplier inputs can support richer evaluation; post-run score
   numbers must not become fictitious supplier facts.
4. **Finish targeted repair/protocol coverage.** Existing numeric must-have
   repair and parallel competition are retained. Explicit capacity-refusal
   follow-up, more detailed no-feasible-repair explanations, incomplete-offer
   recovery and broader indicative-offer confirmation still merit focused work.
   The new global RFQ ceiling is locally tested, not exercised in this final
   all-single-supplier batch.
5. **Keep infrastructure work separate.** Jonas's broader OCR/locale/conflict
   hardening, shared baseline execution guard and alternative logging system
   were not copied wholesale. They need separate scoped reviews; this round
   should not destabilize all baselines to imitate another checkout.

Protection against overfitting: no case/supplier-ID branches or score lookup in
new policy modules; tests vary prices, quantities, constraints and scope;
random selections remain unfiltered; supplier profiles are not inferred from
concessions; no hidden supplier floor is estimated; and no default promotion.
These safeguards reduce overfitting risk but **do not make practice cases an
unseen holdout**. The next useful experiment is a controlled comparison, not
another unexplained accumulation of heuristics.

The docs skill guided the durable report workflow. Its connector was unavailable,
so the plan and report are repository Markdown. No merge, commit or push was
performed, and no additional hosted session was used for final cleanup.
