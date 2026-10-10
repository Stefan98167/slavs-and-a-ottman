# MVP completion plan

Scope: finish the documented negotiation loop, preserve the existing comparison
agents, validate locally, and then run exactly three randomly selected hosted
practice cases. Starting point: `cb01512` plus the existing local coverage and
multi-round fixes. Existing user changes are part of this starting point.

Follow-up: the requested three improvement cycles are complete in
[MVP_ITERATION_PLAN.md](MVP_ITERATION_PLAN.md), with all nine new hosted outcomes
and final reflection in [MVP_ITERATION_REPORT.md](MVP_ITERATION_REPORT.md).

## Execution order

1. [x] Record the local baseline and review the rules and current integration.
2. [x] Connect relevant supplier-authored archive/trigger documents to unified
   with supplier/part/source checks; support release data. Keep buyer notes and
   unverified market interpretations out of supplier profiling. Test scope,
   missing data, conflicting evidence and current explicit supplier statements.
3. [x] Complete evidence-backed trades and clear give/get messages. Map supported
   quality evidence only to permitted terms; preserve buyer constraints and cost
   limits. Keep unknown motives conservative. Test all affected decisions.
4. [x] Improve stopping and multi-supplier orchestration: use attainable package
   improvement, remaining moves and supplier responses; do not end an RFQ just
   because one supplier is final. Validate concurrent supplier service, closing,
   and provenance under synthetic scenarios as well as the local cases.
5. [x] Run all local cases against the comparison agents and a general scenario
   matrix. Reflect on failures and make only general, tested fixes. Run the full
   suite and lint. Freeze the tested implementation before hosted evaluation.
6. [x] Select three hosted practice cases uniformly without replacement, record
   the selection before opening any session, run unified, and save scores,
   decisions and replay links. Do not select replacements for poor scores.
7. [x] Write `MVP_VALIDATION_REPORT.md` with implementation details, local and
   hosted results, reviewed failures, and an explicit remaining-work decision.

## Acceptance and interpretation

- Every sent sheet obeys the Arena contract and buyer must-haves. Accepted
  standing terms must fit the buyer reservation cost.
- Motives come from explicit, sourced supplier statements. Ambiguous, conflicting
  or unsupported statements stay unknown. No invented supplier economics.
- Local simulator scores check execution and regressions, not hosted strength.
- No case-ID branches, hidden-supplier parameters, or tuning to the random hosted
  sample. Any future fixes prompted by that sample need fresh validation.
- Keep `unified` selectable. Three random cases alone do not prove it is better
  than a baseline or justify automatically changing the default.
- Final-event operational readiness and slide submission are reported separately
  from code completion; the actual timed final cannot be certified in advance.
