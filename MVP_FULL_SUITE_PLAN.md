# Full-suite benchmark and reflection

## Scope and protected strategy

Implement the remaining targeted dialogue/protocol recommendations from
`MVP_ROUND3_REPORT.md`, then exactly **13 new hosted sessions**: all ten hosted
practice cases on one frozen version, followed by three randomly selected cases
on a second tested version. No replacement attempts, merging, pushing, baseline
changes, default promotion, case-ID tactics, score lookup or inferred hidden costs.

Unknown supplier motives remain unknown. Every proposal and acceptance retains
must-have, complete-term, provenance, current-standing-ID and reservation gates.
Clarification does not concede a term or imply agreement. Final offers are not
pushed merely to explore an indicative alternative: the API warns that this can
lose an available deal.

## Before the ten-case benchmark

1. Add bounded per-term clarification memory, so a new invitation is not blocked
   by an unrelated old question and ignored questions cannot loop indefinitely.
2. Recover incomplete/unreadable standing offers with a single explicit request,
   without inventing missing supplier terms. Ask a targeted capacity question on
   an explicit refusal and record why an infeasible deal cannot be repaired.
3. Ask for complete confirmation of current incomplete/indicative alternatives;
   never parse a binding deal from prose or accept a secondary offer ID.
4. Extend the validation harness to all ten eligible cases with unique IDs,
   pre-saved selection, sufficient quota and source fingerprints. Preserve the
   existing three-random default and baseline/local comparisons.
5. Run focused tests, full suite and all local cases. Freeze and execute all ten.

## Reflection and three follow-ups

Read every buyer/supplier message, actual terms, argument result, stopping reason,
cost reconciliation, audit and error. Record general failure mechanisms before
editing. Apply only changes justified by these mechanisms; add varied synthetic
regressions and repeat local gates. Freeze again; preselect three uniformly at
random without replacement from the full hosted population and run them once.

Report the ten-case mean as the broad benchmark. Compare follow-up scores with
the same cases from that benchmark, but do not present three practice observations
as an unseen holdout or a statistically established improvement.

## Deliverable

A visually checked PDF explaining the hackathon, score, original architecture,
every major component, safety boundaries, all 13 results, conversation findings,
what works, what is weak, and prioritized next decisions. Include an original-
layout system map, negotiation loop and results chart. Preserve raw evidence.

Broad OCR/locale rewrites, a new logging framework and shared guards that change
comparison baselines remain separate infrastructure projects, as explicitly
deferred in the previous plan. Monitor unknown relationship cost rather than
fabricating supplier economics from post-run results.

## Ten-case reflection, before follow-up edits

Frozen source `7e618c0819fff26779815ce74e75759cd3034208cf6a89b4c6be5bb92de44400`.
288 tests passed, one skipped; local comparisons unchanged. All ten completed:
P01 61.61, P02 17.69, P03 89.98, P04 76.61, P05 33.46, P07 64.72,
P08 19.58, P10 65.51, P11 53.60, P18 20.24. Mean **50.2996837/100**.
Every buyer/supplier message and returned timeout was read. All deals satisfied
must-haves and actual reservation; contract audits and runner errors were empty.

Observed mechanisms, not case-specific tactics:

- P05: the later-payment experiment changed 32.50/45 days into 33.00/90 days,
  increasing total cost by EUR 1,442.00. The policy had no request to restore a
  previous actually quoted package. Add one conditional restoration request,
  restricted to an open thread, full valid terms, and fresh standing confirmation.
- P05: a sentence describing the current extended payment period was misread as
  a new invitation. Restrict invitation matching to first-hand sentences and
  require prospective change language; exclude negative/historical descriptions.
- P02: its explicit evidence request was dropped when the agent chose a
  clarification instead of a numeric counter. Add the same bounded, sourced
  evidence response to clarification/hold messages. Reject quoted/negated
  document requests as well as quoted/negated price requests.
- P05: two inactive rivals had five timeouts in total; one withdrew. Our local
  thread snapshots could become stale. Refresh remote state before closing,
  including timeout-generated standing IDs, and let unified re-evaluate safety.
  Add explicit timeout summaries. This fixes stale closing, not all independent
  per-thread scheduling or the inability to park a supplier in the API.
- P02/P03: Arena relationship costs add EUR 115,648.66 / EUR 259.63 respectively.
  Do not fit private costs from these observations. Disclose model uncertainty.
- P11: 53.60 versus an earlier 61.96 is a regression worth controlled study;
  feasibility-credit settings and reply variation cannot be isolated here.
  Do not tune a discount to the exposed hidden best cost.
- P18: the supplier rejected the improved index band. A valid proposal is not
  proof of supplier acceptance. Do not force a clause or push a final offer.

After these general fixes: varied regression tests, full suite, all local cases,
then exactly three uniformly random sessions. Do not select P05 just to validate
the new branch; use saved-input tests if it is absent from the random sample.

## Completion

- [x] Remaining targeted changes and first local gate (288 passed).
- [x] All ten hosted cases, frozen code, full transcript review and reflection.
- [x] Follow-up general changes and second local gate (305 passed).
- [x] Exactly three uniform random follow-ups, selected with seed 2742409430:
  P05, P18, P01. All valid; no runner/audit errors or recorded timeouts.
- [x] All thirteen conversations analyzed; no policy edits after final runs.
- [x] Markdown audit report and graphical PDF generated and visually reviewed.

Follow-up mean 39.02, versus 38.44 for the same three earlier cases. P05 restored
the earlier safe package and recovered EUR 1,442; P01/P18 were unchanged. Faster
responses confound the absence of timeouts. Remaining priorities and explicit
limitations are in `MVP_FULL_SUITE_REPORT.md` and the PDF.
