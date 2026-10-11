# Laptop changes compared with `origin/main`

Date of comparison: 2026-10-11 (Europe/Berlin)

This is a handoff inventory for Jonas. It describes what is present in this
laptop checkout, what is already committed on `integration/final`, and what is
still only in the working tree. It is not a request to merge or adopt every
item.

## Comparison point and size

- Refreshed `origin/main` from GitHub before comparing. It is still
  `cb01512947a07d98ae020af3014d968d21ef06cd` (`cb01512`).
- Current branch: `integration/final`, HEAD
  `713820fb332e346e5eb050c52d9d2039dcff3b7b` (`713820f`). It tracks
  `origin/integration/final` at the same commit.
- `origin/main` is the merge base; this branch has **16 commits ahead and 0
  commits behind** it.
- The committed tree differs in **76 tracked files**, about **10,170 additions
  and 177 deletions**. This includes code, tests, project notes, two PDFs, and
  an architecture visualization.
- There are also **six modified but uncommitted files**, about **95 additions
  and 9 deletions**, for an opt-in package-menu experiment. These are not in
  the branch's current commit or on GitHub.
- This handoff file is new and is not included in those counts. No `.env`, key,
  or validation transcript is copied into it.

In one sentence: relative to `origin/main`, this laptop has the fuller
benchmarked unified negotiation agent and reports, plus a set of Live Final
reliability tools and opt-in experiments; the latest package-menu trial did
not improve P18 and remains local/default-off.

## High-level system changes

### 1. Unified negotiation policy and safeguards

The imported implementation connects supplier evidence and the published buyer
cost model to a deterministic negotiation loop. It prepares scoped context,
generates complete term-sheet proposals, checks them against buyer requirements
and reservation cost, handles supplier responses, and accepts or walks away.
The comparison agents remain available; the CLI still defaults to `supplier`,
so the Live Final invocation must explicitly use `--agent unified`.

Notable policy safeguards and behavior:

- An unknown supplier profile stays unknown; quote history alone is not treated
  as proof of cash, capacity, quality, or price sensitivity.
- Every proposed package is checked for exactly the case's negotiable fields,
  Arena validity, buyer must-haves, reservation cost, and whether it gives back
  an already available safe offer. Duplicate proposals already sent in the
  thread are excluded.
- Supplier claims can be cited without being treated as verified cost.
  Numerical adjustment from index/cost-share claims has a documented cap and
  defaults to zero unless explicitly configured.
- The policy handles term repair, clarification, evidence/source requests,
  supplier alternatives, bounded reciprocal trades, prior-offer restoration,
  price anchoring, stopping decisions, and final/deadline closure.
- Accepted deals use the supplier's actual standing sheet/offer ID. The agent
  does not accept a historical offer merely because it was once quoted.

Main files:

- `arena_kit/agents/unified.py` — orchestrates preparation, offers, decisions,
  response choices, and safe closing.
- `negotiator/package_policy.py`, `negotiator/packages.py`,
  `negotiator/evaluator.py`, `negotiator/proposal_safety.py` — candidate package
  planning, evaluation, and buyer-side safety limits.
- New focused policy modules listed under [New negotiation modules](#new-negotiation-modules).
- `arena_kit/cost.py` — relationships between evaluator costs and the Arena
  buyer-cost model, including optional supplier relationship economics.

### 2. Evidence intake and provenance

New evidence adapters allow unified to use eligible supplier-authored documents
and release data while preserving their IDs and source information. Evidence is
scoped by supplier, part, and date. Buyer-authored notes, unrelated suppliers,
future documents, and unattributable claims do not become supplier motives. The
agent can also consume case-inline `facts` and the Sunday release package when
available. Missing or malformed optional archives should degrade to no inferred
evidence, not a crash.

Main files: `negotiator/case_evidence.py`, `negotiator/supplier_evidence.py`,
`negotiator/supplier_profile.py`, `arena_kit/data.py`, and the evidence path in
`arena_kit/agents/unified.py`.

### 3. Runner resilience for the unattended Live Final

Changes to `arena_kit/play.py`, `arena_kit/client.py`, `arena_kit/cli.py`, and
their tests add:

- Continued wave polling after transient errors rather than terminating the
  whole runner.
- Per-case recovery after agent or HTTP failures: fetch fresh server state,
  rebuild thread messages (including timeout-created offer IDs), and attempt a
  contract-safe accept or walk-away close. Stale accepts are refreshed and
  retried within a bound; recovery failures are logged loudly.
- Resume of already-open final sessions after a runner restart, using the
  Arena's existing-session conflict response rather than opening duplicates.
- Deadline-aware HTTP timeouts/retries and early closing so one slow request
  does not consume the remaining wave time.
- Reconciliation of authoritative session/thread state before closing, to
  avoid acting on a superseded offer.
- Optional RFQ keepalive behavior described below.

`scripts/run_final.sh` runs the final command, logs under ignored `logs/`, and
restarts after a crash until the five-wave run completes. The README documents
use and environment variable *names* only.

### 4. Optional experiments (not all should be enabled)

| Feature | Switch | Default | What it does | Evidence / caution |
|---|---|---|---|---|
| RFQ keepalive | `--rfq-keepalive` | Off | When enabled, it checks the age of idle supplier threads and sends a short holding message to a qualifying acceptable/agreed thread while other supplier work proceeds. Runner can send independent thread messages concurrently. | Intended to prevent idle-thread timeouts/offer-ID changes. Covered by unit/simulator tests; assess latency and score on realistic RFQs before enabling. |
| Supplier relationship economics | `SUPPLIER_ECONOMICS=1` | Off | Estimates supplier economics from scoped `cost:` facts and includes relationship cost in evaluation. | `scripts/calibrate_relationship.py` compares estimates with saved P02/P03 Arena breakdowns. The documentation reports material calibration mismatch; leave off unless data semantics are independently checked. |
| Supplier archive evidence without CLI `--data` | `SUPPLIER_ARCHIVE_EVIDENCE=1` / `ARENA_DATA` | Off unless requested | Loads the package and Sunday release documents for supplier evidence. | Source/scope checked. Missing data should remain unknown. |
| Current working-tree response-trade menu | `UNIFIED_RESPONSE_TRADE_MENU=1` | Off | When on, unified can send up to three buyer-safe alternatives for an eligible response trade rather than just one. | One targeted P18 Arena run scored exactly the saved baseline; no demonstrated gain. Not committed. |
| Current working-tree riskier stopping mode | `UNIFIED_RISKIER=1` | Off | Requires one additional buyer round before ordinary opening-goal/negligible-improvement acceptance, when another safe proposal exists. | Tested on S01–S03 and two random Arena cases; no score or action change in those cases. Not committed. |
| Current working-tree bolder opening | `UNIFIED_BOLDER_OPENING=1` | Off | Current experiment raises the maximum discount from the default 5% to 30% (a 30/18/6% ladder; less when configured max is near 100%). Must-have, reservation-cost, and term-validity filters remain unchanged. | 30% underperformed the prior 15% setting on all three targeted cases (mean -12.69 points). Keep off; prior 15% setting remains the better-tested option. Not committed. |

Existing agents `supplier`, `packages`, `advanced`, `naive`, `llm`, and `unified`
remain runnable. Keep `unified` explicitly selected for its behavior; it has not
been made the CLI default.

### 5. Generalization and validation

- `scripts/validate_mvp.py` runs repeatable local comparisons or a preselected
  practice batch, records its seed/source fingerprint/quota before starting,
  saves decisions/replay IDs/results, and audits contract terms, must-haves,
  reservation limits, and evidence citations.
- `scripts/latency_probe.py` uses a fake clock to rehearse supplier reply delay,
  wave deadlines, timeouts, and closure offline.
- Tests cover unusual negotiated fields (including tooling, ppm, chargebacks,
  indexation, incoterms, volume, and zero-month contracts), runner failures,
  deadline behavior, RFQ timeouts, evidence scope, and package safety.
- The `origin/main` delta contains the then-current test additions and
  modifications. The current laptop working tree was most recently checked at
  **351 passed, 1 skipped, 15 subtests passed**; Ruff on the touched files was
  clean. These numbers include the uncommitted package-menu experiment.

## New negotiation modules

These committed modules are imported by or provide policy behavior to unified:

- `negotiator/buyer_arguments.py` — replies to supplier price/evidence questions
  with eligible, scoped buyer records or a candid non-evidence explanation.
- `negotiator/case_evidence.py` — loads and scopes supplier letters, facts,
  news, and release-package evidence; preserves citable IDs.
- `negotiator/dialogue_recovery.py` — handles missing terms, clarification,
  refusals, capacity issues, indicative alternatives, and constrained recovery
  messages.
- `negotiator/offer_restoration.py` — after an experiment worsens the offer,
  can request a fresh quote matching a previously better, valid complete sheet.
- `negotiator/proposal_safety.py` — validates proposal completeness, buyer
  reservation, standing-offer ceiling, duplicates, and package selection.
- `negotiator/response_signal.py` — records explicit response signals without
  asserting a hidden supplier motive.
- `negotiator/response_trades.py` — constructs bounded reciprocal trades (for
  example price vs. allowed index deadband) that retain buyer value and obey
  must-haves/reservation.
- `negotiator/supplier_alternatives.py` — evaluates a supplier's complete
  structured alternative sheet and requests confirmation when it is safe and
  better.
- `negotiator/supplier_economics.py` — estimates economics from data facts for
  the optional relationship-cost mode; not a reason to infer missing data.
- `negotiator/term_repair.py` — creates bounded proposals to restore previously
  requested commercial terms after a supplier changes one.

Modified modules `negotiator/package_policy.py`, `supplier_profile.py`,
`supplier_evidence.py`, `packages.py`, and `evaluator.py` connect these rules to
existing contracts without replacing the standalone comparison agents.

## Committed changes by commit

The 16 commits from `origin/main` to HEAD are:

1. `fed5a31 Complete MVP negotiation improvements and reports` — imported the
   benchmarked unified-agent working tree, policy modules, validation suite,
   project plans/reports, architecture map, and plain-language PDFs. This is the
   bulk of the negotiation/product changes described above.
2. `8a4220b Back up local working tree before integration` — preserved the
   laptop source tree on a backup branch before integrating; this commit also
   carried local configuration and rendered pages that were cleaned up later.
3. `1ccf9a2 Merge branch 'backup/local-working-tree-20261011-0035' into integration/final`
   — merged the backup baseline into integration, keeping its tested unified
   behavior.
4. `33476d4 Keep workstation artifacts out of integration` — removed temporary
   rendered review pages and local editor/agent configuration from the final
   tree; adjusted ignore/settings content. Those transient files are not in the
   current net file inventory.
5. `cbd5452 Sync uv lock with optional OCR dependencies` — updated `uv.lock`
   for the configured optional OCR-related dependency set.
6. `193d040 Keep final wave polling through transient failures` — retries the
   final-wave polling path after transient Arena/network errors and adds tests.
7. `3dfd474 Recover open cases after runner errors` — bounded per-case recovery,
   fresh thread state, and safe closing after decision/send/accept failure.
8. `f98c736 Add restartable Live Final runner` — adds the crash-restarting shell
   wrapper and recovery test; ignores its logs.
9. `a068c41 Bound final HTTP calls by wave deadline` — caps request/retry time
   by the known wave deadline; adds deadline-focused tests.
10. `6c985f1 Add offline supplier latency rehearsal` — adds fake-clock rehearsal
    and a small test.
11. `f5ac012 Add opt-in RFQ thread keepalive` — adds opt-in keepalive/concurrent
    thread servicing, simulator support, CLI plumbing, and tests.
12. `1c57d81 Add opt-in supplier economics and release evidence` — adds
    optional relationship-cost modeling/calibration and release evidence
    handling/tests.
13. `3e2f6ee Smoke test unified on unusual case terms` — adds synthetic
    generalization smoke cases, focused on crashes and contract shape, not
    score tuning.
14. `af7471d Document reliable Live Final launch` — updates run instructions,
    flags, defaults, and the explicit unified command.
15. `48424fb Preserve useful requests near wave deadlines` — reduces the number
    of HTTP retries when the remaining wave time cannot accommodate them, so
    each remaining attempt can finish before the deadline; updates the
    near-deadline simulator test.
16. `713820f Make validation batch summaries reproducible` — stable ordering
    and summary metadata/tests for saved validation runs.

The initial integration included a merge commit and backup commit in addition
to the benchmarked source commit. The workstation-artifact cleanup intentionally
undoes temporary/config files introduced by the backup; use the final tree,
not the backup branch alone, as the intended integration state.

## File inventory by area

### Runtime and negotiation code

- Modified: `.gitignore`, `README.md`, `arena_kit/agents/unified.py`,
  `arena_kit/cli.py`, `arena_kit/client.py`, `arena_kit/cost.py`,
  `arena_kit/data.py`, `arena_kit/play.py`, `arena_kit/sim.py`,
  `negotiator/evaluator.py`, `negotiator/package_policy.py`,
  `negotiator/packages.py`, `negotiator/supplier_evidence.py`,
  `negotiator/supplier_profile.py`, `uv.lock`.
- New committed modules: `negotiator/buyer_arguments.py`,
  `negotiator/case_evidence.py`, `negotiator/dialogue_recovery.py`,
  `negotiator/offer_restoration.py`, `negotiator/proposal_safety.py`,
  `negotiator/response_signal.py`, `negotiator/response_trades.py`,
  `negotiator/supplier_alternatives.py`, `negotiator/supplier_economics.py`,
  `negotiator/term_repair.py`.
- New committed runner/validation tools: `scripts/calibrate_relationship.py`,
  `scripts/latency_probe.py`, `scripts/run_final.sh`,
  `scripts/validate_mvp.py`.

### Tests

New committed tests:

`tests/test_buyer_arguments.py`, `test_case_evidence.py`, `test_deadline.py`,
`test_dialogue_recovery.py`, `test_full_suite_reflection.py`,
`test_generalization_smoke.py`, `test_latency_probe.py`,
`test_mvp_invariants.py`, `test_proposal_safety.py`, `test_response_signal.py`,
`test_response_trades.py`, `test_rfq_keepalive.py`, `test_runner_polling.py`,
`test_runner_recovery.py`, `test_stopping_policy.py`,
`test_supplier_alternatives.py`, `test_supplier_batch.py`,
`test_supplier_economics.py`, `test_term_repair.py`, `test_validate_mvp.py`.

Modified existing tests:

`tests/test_evaluator.py`, `test_package_policy.py`, `test_sim.py`,
`test_supplier_profile.py`, `test_unified.py`.

The handoff writer should run the relevant focused test beside any module it
ports. Runner integrations are especially coupled: changes in `play.py` depend
on the matching client, simulator, and recovery tests.

### Project documentation and artifacts

- Plans: `MVP_COMPLETION_PLAN.md`, `MVP_FULL_SUITE_PLAN.md`,
  `MVP_ITERATION_PLAN.md`, `MVP_ROUND2_PLAN.md`, `MVP_ROUND3_PLAN.md`.
- Results/reflections: `MVP_FULL_SUITE_REPORT.md`, `MVP_ITERATION_REPORT.md`,
  `MVP_ROUND2_REPORT.md`, `MVP_ROUND3_REPORT.md`, `MVP_VALIDATION_REPORT.md`.
- Contracts/architecture: `MVP_CORE_CHARACTERISTICS.md`,
  `MVP_EVALUATOR.md`, `MVP_INTELLIGENCE.md`, `TODO.md`, `README.md`.
  `MVP_CORE_CHARACTERISTICS.md` is Jonas's long-form strategy/core-contract
  reference; the round-three report records which recommendations were adopted,
  adapted, or deferred rather than treating every idea in it as proven.
- Visuals: `architecture-progress-map.html`,
  `architecture-progress-map.preview.html`, `architecture-progress-map.png`,
  and `architecture-status-2026-10-10.png`.
- Generated-but-tracked reports: `output/pdf/project-explained.pdf`,
  `output/pdf/system-and-13-run-review.pdf`, plus report source/support under
  `output/report_support/`. These PDFs explain the project; they are not runtime
  dependencies.

See the individual reports before adopting strategy changes. The recorded
full-ten mean is **50.30/100**. Follow-up samples varied by case, so those
reports explicitly do not claim a causal overall improvement. The full-suite
report records all 13 deals as valid, but also five idle-RFQ timeouts and two
relationship-cost discrepancies. The P02/P03 costs are why the optional
supplier-economics flag is documented as uncalibrated.

## Working-tree-only changes (not committed or pushed)

The local experiment currently touches seven tracked source/test files:

- `arena_kit/agents/unified.py` reads `UNIFIED_RESPONSE_TRADE_MENU`. Only when
  set to `1`, and only when the plan is a response trade, it asks the safety
  selector to retain up to three packages. Other proposal categories continue
  to emit one package.
- `negotiator/proposal_safety.py` adds bounded `max_packages` (integer 1–3),
  with default `1`; all existing completeness, must-have, reservation, current
  standing-cost, and duplicate-sheet checks still run before selection.
- `scripts/validate_mvp.py` adds exact hosted case selection using
  `--case-id case:P18`, captures the feature flags in the pre-run manifest, and
  records the requested case. It also adds `--count` for an exact number of
  randomly selected cases, used for the two-case experiment below. Local,
  three-random (default), and all-ten behavior remain supported.
- Tests in `tests/test_proposal_safety.py`, `test_response_trades.py`, and
  `test_validate_mvp.py` verify default-one behavior, opt-in menu bounds,
  safety, exact-case selection, and exact random sample size.

Reason: the saved P18 trace showed that the agent generated two valid
price/index-deadband response trades, but its selector sent only one. One
authorized hosted P18 session sent both options. The supplier rejected the
deadband alternatives and held the same €5.70, zero-deadband final quote; the
agent accepted the same standing offer. Score was **0.20244**, exactly the
saved P18 baseline. No audit errors, runner errors, or timeouts occurred. The
change therefore has **no demonstrated score gain** and should stay opt-in; it
is safe to omit if Jonas only wants proven improvements.

The current second experiment adds `UNIFIED_RISKIER=1`. It increases the
ordinary `minimum_rounds` threshold by exactly one, leaving final-offer,
deadline, must-have, reservation, and validity safeguards unchanged. The
intent is to take one more safe counter when such a candidate remains, rather
than immediately accepting at the usual goal/negligible-improvement threshold.
`tests/test_stopping_policy.py` verifies that the flag changes this threshold
and that the extra round does not block a final-offer acceptance. The
`--count 2` validation support and manifest flag recording are tested in
`tests/test_validate_mvp.py`.

Controlled local comparison with the flag off/on gave the same unified scores
for all three cases: S01 **0.34777**, S02 **0.34367**, S03 **0.40629**. All
closed as deals with no audit errors. Two uniformly random hosted cases were
selected with seed **1425056199**: P18 and P03. The results were P18 **0.20244**
and P03 **0.89983**, mean **0.55114**. Both are exactly equal to their saved
baseline outcomes and accepted terms; the decision history confirms
`riskier_mode_enabled=true`, but the tested policy change did not alter the
offers in these cases. No runner errors, audit errors, or timeouts occurred.
This small sample is not evidence that riskier stopping helps or hurts in
general.

The `UNIFIED_BOLDER_OPENING=1` experiment increases the default maximum
discount from 5% to 8% throughout the package ladder. It remains off by
default; proposals still pass the existing safety checks. Locally, unified
scored S01 **0.52166**, S02 **0.51551**, and S03 **0.52266** (mean **0.51994**),
versus flag-off scores **0.34777**, **0.34367**, and **0.40629** (mean
**0.36591**); all six runs dealt with no audit errors.

The bolder flag was then exercised once on each of the ten hosted practice
cases, with the other experiment flags off. Against the saved full-suite
historical scores, the mean rose from **0.50300** to **0.53392** (**+3.09 score
points**). Seven cases scored higher, one lower, and two tied:

| Case | Historical | Bolder opening | Change (points) |
|---|---:|---:|---:|
| P01 | 0.61606 | 0.68780 | +7.17 |
| P02 | 0.17688 | 0.16951 | -0.74 |
| P03 | 0.89983 | 0.89983 | 0.00 |
| P04 | 0.76607 | 0.76607 | 0.00 |
| P05 | 0.33458 | 0.35214 | +1.76 |
| P07 | 0.64719 | 0.67351 | +2.63 |
| P08 | 0.19584 | 0.21381 | +1.80 |
| P10 | 0.65510 | 0.67071 | +1.56 |
| P11 | 0.53598 | 0.61959 | +8.36 |
| P18 | 0.20244 | 0.28626 | +8.38 |

All ten were deals with zero runner or audit errors. P05 had two timeouts on
inactive rival threads; the other cases had none. These are historical,
non-paired comparisons, so Arena variance may contribute; the score movement is
promising but not conclusive enough to enable the flag by default. Detailed
run records are local-only under `/tmp/bolder-opening-*-20261011/`.

### More aggressive opening trial: 15% maximum discount

The next trial changes only the opt-in bonus: `UNIFIED_BOLDER_OPENING=1` now
adds up to 10 percentage points to the default 5% maximum, producing a
15%/9%/3% ladder (instead of the previous 8%/4.8%/1.6%). The flag-off policy
is unchanged. Reservation, must-have, and term-validity checks are unchanged.

Local unified scores were S01 **0.86943**, S02 **0.85918**, and S03 **0.29092**
(mean **0.67318**) versus the flag-off **0.34777**, **0.34367**, and **0.40629**
(mean **0.36591**). All dealt and passed audit; S03 dropped sharply while S01
and S02 rose sharply.

The 15% setting was exercised once on each of the ten hosted practice cases.
Across them the mean was **0.56748** versus the saved case-matched historical
mean **0.50300** (**+6.45 points**); versus the earlier 8% experiment mean
**0.53392**, this was **+3.36 points** on the same case set. Five cases rose,
three fell, and two tied against the saved benchmark:

| Case | Historical | 15% opening | Change (points) |
|---|---:|---:|---:|
| P01 | 0.61606 | 0.55825 | -5.78 |
| P02 | 0.17688 | 0.15103 | -2.59 |
| P03 | 0.89983 | 0.89983 | 0.00 |
| P04 | 0.76607 | 0.76607 | 0.00 |
| P05 | 0.33458 | 0.43248 | +9.79 |
| P07 | 0.64719 | 0.71957 | +7.24 |
| P08 | 0.19584 | 0.48287 | +28.70 |
| P10 | 0.65510 | 0.64729 | -0.78 |
| P11 | 0.53598 | 0.66474 | +12.88 |
| P18 | 0.20244 | 0.35265 | +15.02 |

All ten were deals, with zero audit or runner errors. There was one timeout on
an inactive P05 rival thread. The 15% setting improved the aggregate but was
materially worse on P01 and P02, and local S03 also regressed; these historical
comparisons are not paired controls. Keep it opt-in until repeated testing
confirms that the gains generalize. Detailed records are local-only under
`/tmp/bolder-opening-15pp-*-20261011/`.

### Extreme opening trial: 30% maximum discount

The opt-in bonus was increased again from +10 to +25 percentage points,
turning the default 5% maximum into a **30%/18%/6%** ladder. The default
flag-off behavior and proposal safety checks did not change. Unit test,
full-suite, Ruff, and local simulator checks passed. Local unified scores were
identical to the 15% experiment (mean **0.67318** vs flag-off **0.36591**).

The three cases that had improved most under 15%—P08, P18, and P11—were tested
once more. Their 30% scores were **0.21381**, **0.28626**, and **0.61959**
(mean **0.37322**), down from their 15% scores **0.48287**, **0.35265**, and
**0.66474** (mean **0.50009**; **-12.69 points**). All three dealt with no
timeouts, runner errors, or audit errors. Despite being above their older
5%-baseline mean (**0.31142**), the extra aggression lost ground versus 15%;
do not enable 30% based on these tests. Run records are local-only under
`/tmp/bolder-opening-30pp-top3-*-20261011/` and local comparisons under
`/tmp/bolder-opening-30pp-local-*-20261011/`.

Last full local validation: **353 passed, 1 skipped, 15 subtests passed**;
focused Ruff checks and `git diff --check` passed. The two-case hosted run
record is local-only at `/tmp/riskier-random-20261011/run.json`, with individual
records in that directory. The earlier response-menu experiment is recorded at
`/tmp/response-menu-p18-20261011/unified-P18.json`; neither output directory is
part of the repository.

## Practical handoff suggestions for Jonas

1. Treat `integration/final` as the committed integration source, not the
   backup branch. The latter exists to preserve the pre-integration laptop
   tree and includes temporary workstation material that was removed from the
   integration branch later.
2. First choose an area: evidence/profile, negotiation policy, reliability,
   or documentation. Copy a coherent module plus its tests; avoid taking only
   one half of coupled behavior.
3. If porting runner resilience, take the matching `arena_kit/play.py` and
   `client.py` changes with `test_runner_*`, `test_deadline.py`, simulator and
   CLI adjustments as applicable. Do not copy only the fallback-close code.
4. If porting negotiation features, retain the existing case/evidence and
   buyer-cost contracts, and keep optional flags off until separately
   validated. Read `MVP_CORE_CHARACTERISTICS.md` and the round reports for
   provenance/safety decisions.
5. The uncommitted response menu is an experiment, not an established gain.
   Ask before cherry-picking it or enabling it by default; its one P18 outcome
   matched baseline.
6. Run focused tests first, then `uv run python -m pytest -q`, a local
   simulation/generalization smoke test, and Ruff on touched files. Preserve
   `.env`, API keys, local output, and workstation settings outside any patch.

No changes in this handoff were pushed or merged. This report itself is the only
new deliverable file created by this request.
