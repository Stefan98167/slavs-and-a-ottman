# Second three-cycle improvement round

Starting source: `099c205e94163e3959c4e0f8626c2c29ccef477eab35fd3cdac746745a3f96a3`.
Preserve previous work and reports. Exactly nine new hosted sessions: three
random cases after each cycle's local tests. No replacements or case-ID policy.

## Scoring interpretation

`score = clip((C_open - C_deal) / (C_open - C_best), 0, 1)`; broken must-haves
score zero, walking away scores the alternative if one exists. C_best is hidden
and fixed per case. We cannot target a live score from private supplier data.
Reduce expected accepted total cost, not just unit price; retain safe closing.
Payment, coverage, risk, quality and timing can outweigh a price concession.
Evidence is not bonus points: it must be relevant, correct and persuasive.

The API's citation rules accept case-referenced quotes/live rival offers,
2–8 same-part purchase orders, valid index windows and other specified facts.
An arbitrary historical quote is not an accepted substitute for a rival quote.

## Execution

1. Correct evidence selection to the grading contract and handle indirect source
   requests. Keep commercial proposals distinct from supplier-cost assertions.
   Validate scope, dates, units, duplicate IDs, the local cases and all tests;
   freeze code, run three random cases and review every supplier response.
2. Re-read those outcomes. Prior candidate: negotiate bounded index-risk options
   within the supplier's offered clause instead of only demanding no indexation.
   Preserve buyer limits and unknown-profile discipline. Decide from evidence,
   implement general rules, test, run three fresh random cases and reflect.
3. Choose the next substantive gap from the preceding results and scoring
   rules. Validate locally before the last three random sessions. No hidden
   optimal-price inputs, no opportunistic changes while a batch runs.

Record seeds, code fingerprints, actual scores, cost components, citation
outcomes and failed hypotheses. Compare repeats cautiously; batch means are
not controlled comparisons. Keep baselines/default intact and do not push.

## Cycle four reflection

207 tests passed, 1 skipped, 15 subtests passed. Local scores unchanged.
Seed 764067330 selected P03, P05, P11: 82.39 / 30.08 / 61.96. All valid deals.
P05 exercised the real multi-supplier path with no runner errors. One higher-cost
supplier was not countered because its packages did not beat the reservation.
No new citation was needed in this batch, so the evidence correction remains
locally validated, not yet a demonstrated hosted improvement.

P03 explicitly stated that longer payment terms require a higher price. We
asked for details and then accepted without costing a reciprocal proposal.
Cycle five adds one bounded, economically costed response to explicit
price-linked term invitations, plus same-series index-deadband options when
the supplier has offered indexation. Vague invitations still get clarification.
Each proposed higher price shares at most half the modeled buyer benefit.

## Cycle five reflection

213 tests passed, 1 skipped, 15 subtests passed. Local scores unchanged.
Seed 1968169352 selected P05, P08, P04: 30.08 / 7.07 / 0.00. All deals met
must-haves, but P04 matched its opening cost and therefore earned zero. No
selected case triggered the new response trade, so its live effect is unknown.

P04's supplier sent TWO structured sheets: its primary 12-month offer at 4.96
and a complete 24-month alternative at 4.88. The agent inspected only the first,
then asked a generic question; the alternative disappeared in the next reply.
Cycle six prioritizes valid, cheaper, current structured alternatives. It
requests exact-term standing confirmation rather than assuming an alternative
ID can be accepted. Invalid, incomplete, stale, prose-only and repeated options
are excluded. Concrete savings are not discarded by the speculative stopping
threshold. This is a general multi-option handling fix, not a P04-specific rule.

## Cycle six reflection and completion

223 tests passed, 1 skipped, 15 subtests passed. Local and baseline results
unchanged. Seed 1169296111 selected P02, P07, P01: 9.22 / 62.74 / 26.79.
All deals met must-haves and predicted accepted costs matched Arena exactly.
P01's purchase-order argument verified and the missing source excerpt was
attached, but its score did not improve. Neither new trade branch was triggered
in this sample, so their hosted value remains unproven. P02 stalled on price;
its prose-only index invitation was correctly not turned into invented terms.

- [x] Scoring rules reread and evidence contract corrected.
- [x] Cycle four: changes, local gate, three random sessions, reflection.
- [x] Cycle five: changes, local gate, three random sessions, reflection.
- [x] Cycle six: changes, local gate, three random sessions, reflection.
- [x] Nine unique sessions audited; local/hosted fingerprints matched.
- [x] Baselines/default preserved; no commit, push or extra hosted attempts.
- [x] Results and remaining strategy work documented in
  [MVP_ROUND2_REPORT.md](MVP_ROUND2_REPORT.md).

Next priority is whole-package countervalue and targeted clarification, then
matched comparison of opening/stopping rules. Overall 34.48/100 is not evidence
of improvement over the prior different sample. Do not promote on test count
alone or label locally validated branches as live wins.
