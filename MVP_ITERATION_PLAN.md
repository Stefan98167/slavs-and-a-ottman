# Three-cycle improvement plan

Continue the completed MVP plan, preserving existing work and comparison agents.
Run exactly three fresh random hosted practice sessions per cycle (nine total).
Record selection before opening sessions; never replace poor results. Freeze
code before each hosted batch and retain local/hosted source fingerprints.

1. Repair whole-package stopping: when the supplier beats our price but changes
   a previously requested term, try at most one costed restoration trade. Share
   at most half the modeled buyer benefit through a higher price, capped at the
   previous ask. Never invent supplier motives or bypass must-haves/reservation.
   Test generic payment and risk changes and unchanged-price success locally.
   Then run three random Arena cases and read every transcript.
2. Re-read the rules and cycle-one evidence. Choose a general improvement based
   on observed behavior, not case IDs or hidden best prices. Test the changed
   behavior and all local cases before three further random Arena cases.
3. Repeat the reflection using cycle-two evidence. Address the next justified
   gap, run regressions/local cases, then the final three random Arena cases.

After each cycle record failures as well as successes. Final report includes
all nine scores, replay links, safety checks, local baseline comparisons and
remaining limitations. Random batches have different case mixes: changes in
their averages are not a controlled measurement of strategy improvement.
Do not change the default agent or push without a separate request.

## Reflection after cycle one

185 tests passed; 1 skipped; 15 subtests passed. S01–S03 scores unchanged.
Seed 90500493 selected P11, P07, P10. Scores: 61.96, 62.74, 65.51 /100.
All deals valid, audit errors zero; source fingerprint matches local validation.
No selected case needed term restoration, so hosted benefit is unproven.
P10 explicitly requested price evidence; the agent ignored the question. P11
partially disclosed material share and refused more, yet got another request.
Cycle two therefore adds a separate, scope-checked buyer argument renderer and
recognizes that partial refusal. Historical quotes are qualified context only,
not supplier economics, motive evidence, or a guaranteed current benchmark.

## Reflection after cycle two

198 tests passed; 1 skipped; 15 subtests passed. S01–S03 unchanged.
Seed 491255777 selected P08, P01, P07: 7.07, 22.58, 62.74 /100. All valid.
The changed case mix prevents attributing the lower mean to the code changes.
P08 stopped with a small gain; coverage was considered using the opening price
rather than each proposed price. P01 selected the option combining earlier
payment AND the higher price, exposing a one-sided trade. Its request to share
the cited document was also not covered by the price-question handler.
Cycle three fixes the package economics, rechecks coverage after concessions,
and sends requested copies only of already cited verified supplier documents.
Unknown profiles, must-haves, reservation limits and baselines remain intact.

## Completion and final reflection

- [x] Cycle one: changes, focused/full tests, local comparison, random three,
  transcript review and reflection.
- [x] Cycle two: response improvements, focused/full tests, local comparison,
  random three, transcript review and reflection.
- [x] Cycle three: reciprocal pricing/coverage/source replies, focused/full
  tests, local comparison, random three, transcript review and reflection.
- [x] Compare all source fingerprints and acceptance costs; preserve all nine
  session records; write `MVP_ITERATION_REPORT.md` including remaining gaps.

Final suite: 202 passed, 1 skipped, 15 subtests passed. Seed 535048855 selected
P07/P01/P18: 62.74/26.79/27.03. All nine sessions had valid deals and zero
contract audit errors. A historical citation was marked irrelevant; indirect
document-request wording was missed; the index-restoration offer was rejected.
Those limits are reported rather than silently tuning a fourth version.
No commit, push or default-agent promotion was performed.
