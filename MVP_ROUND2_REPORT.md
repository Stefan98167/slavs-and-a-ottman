# Second three-cycle improvement report

10 October 2026. This round covers iterations **4–6** of `unified`, following
the earlier three-cycle report. Existing user work was preserved. No commit,
push, default-agent change, or replacement of weak random results is authorized
or performed by this round.

## Results

Completed all three cycles: changes, local comparisons/full tests, three random
hosted cases, then transcript review. Exactly **nine new sessions**, no replacement
attempts. All nine ended in deals meeting must-haves, with no contract-audit,
runner or evidence-loader errors. Predicted accepted cost matched Arena's actual
accepted cost to the cent in every run.

| Cycle | Random cases and scores /100 | Mean /100 |
| --- | --- | ---: |
| 4 | P03 **82.39**, P05 **30.08**, P11 **61.96** | 58.14 |
| 5 | P05 **30.08**, P08 **7.07**, P04 **0.00** | 12.38 |
| 6 | P02 **9.22**, P07 **62.74**, P01 **26.79** | 32.92 |

Overall: **34.48/100**. These different random case mixes are not a controlled
before/after experiment. The earlier round averaged 44.35; neither the lower new
mean nor movement between these batches establishes the changes' causal effect.
The repeated cases did not improve. We fixed concrete behavior, but **have not
demonstrated an overall scoring improvement**.

The final suite has **223 passed, 1 skipped, 15 subtests passed**, up from 202
tests at this round's start. Changed-file Ruff and `git diff --check` pass.
The `supplier`, `packages` and `advanced` comparison agents remain available;
the default remains `supplier`, not `unified`.

## Scoring review

The rules in `brief/brief.md` §6 and `brief/api.md` “What counts” change how we
should judge progress:

- The accepted contract earns the score, not our proposed price or eloquence.
  `score = clip((C_open − C_deal) / (C_open − C_best), 0, 1)`.
- C is the whole cost: bought volume, uncovered demand, financing, freight,
  lateness, defects, tooling, index exposure and sometimes supplier-health cost.
  A higher unit price can be a better deal if another cost falls further.
- C_best is hidden and fixed. It is read here only in completed-run results to
  explain the grade; the policy does not receive it or target hidden floors.
- Breaking a must-have gives zero. But a valid deal can also score zero if it
  saves nothing. P04 in iteration five is exactly this second kind of zero.
- A correct citation is not bonus points and does not guarantee a concession.
  The API recognizes case-referenced quotes/rival live offers, 2–8 same-part
  purchase orders, defined index windows, and other specified fact types.
  An arbitrary historic quote ID can be true yet irrelevant to its checker.
- Final waves average case scores, rather than ranking teams by raw euros saved.
  Small cases deserve attention: one missed narrow improvement can lose a large
  portion of a case's available points.

Sources are the bundled hackathon rules, not an invented scoring model or a
live leaderboard. No prohibited final-results/event feeds were read.

## Iteration four

**Change:** fixed the citation mismatch found in the previous round. Price-basis
replies now use eligible case quotes, or two dated same-part/same-supplier
purchase orders with known currency/unit basis. Arbitrary historical quotes
are excluded. The wording separates transaction history from supplier costs
or identical current terms. Indirect requests for a missing cited document are
recognized, but only previously cited verified supplier sources can be sent.

**Local gate:** 207 passed, 1 skipped, 15 subtests passed; all local comparisons
unchanged and contract audits clean. Changed-file Ruff/diff checks passed.

Seed `764067330`; source
`72399d0899dd821eacfc849164e777276a62bddf40cf5a2762982d50be3db57e`.

| Case | Score /100 | Replay |
| --- | ---: | --- |
| P03 | 82.39 | [Renewal](https://arena.tacto.ai/replay/f2c265615a86e7ec) |
| P05 | 30.08 | [Three-supplier RFQ](https://arena.tacto.ai/replay/352149c1105c45ae) |
| P11 | 61.96 | [Quality](https://arena.tacto.ai/replay/5dff7ff26ab9f712) |

All valid deals, no contract-audit or runner errors. P05 exercised parallel
requests to the two competitive suppliers and closed globally with the lower
total-cost bidder. The third supplier's generated packages exceeded the
reservation; it was not sent a counter. There were no reported timeouts.
No case needed a new price-evidence citation, so this batch did not prove that
the citation change improves grades.

**Reflection:** P03's coverage extension produced most of its benefit. Later
the supplier explicitly said longer payment terms would require a higher
price. We asked for details but never costed that exchange. P11 satisfied its
quality ceiling and reduced price; no evidence justified assuming stronger
quality guarantees. P05 got a valid accelerated-delivery quote but stalled
after its unit price rose relative to an invalid slower opening quote.

## Iteration five

**Change:** added a separate bounded response-trade module. When the price
ladder stalls, explicit price-linked invitations can lead to a higher-price
proposal with a better term. For quoted index clauses it can propose permitted
deadbands without changing the series, material share or base month. Every
proposal retains at least half the modeled benefit, obeys buyer constraints,
fits the reservation and is attempted only once per supplier. Vague invitations
still get clarification. No hidden motive or acceptance is assumed.

**Local gate:** 213 passed, 1 skipped, 15 subtests passed; local case scores and
baseline behavior unchanged. Tests include negative/zero index paths, buyer
constraints, no invitation, repeat prevention and a payment/price exchange.
A retrospective calculation on P03 found a 90-day/EUR 433.03 proposal costing
EUR 26,330.72 less than its 30-day/EUR 430.15 standing deal. That was only a
modeled proposal, **not an accepted hosted saving**.

Seed `1968169352`; source
`29ae56bed2949245c81cf925ca4f0d37aa6ae7b68a92f49210c25b315f7fded3`.

| Case | Score /100 | Replay |
| --- | ---: | --- |
| P05 | 30.08 | [Three-supplier RFQ](https://arena.tacto.ai/replay/b994bd86b832b32d) |
| P08 | 7.07 | [Raw material](https://arena.tacto.ai/replay/5bba4691eed84b64) |
| P04 | 0.00 | [Bearing renewal](https://arena.tacto.ai/replay/f2256a262695f8f1) |

All three deals met must-haves with no runner/contract-audit errors. None of
these cases triggered the new response trade; its hosted benefit remained
unknown. P05 repeated its previous outcome. P08 again stopped after a modest
price move, without exploring other useful exchanges.

**Reflection:** P04 exposed a concrete multi-option bug. The supplier's first
reply contained a primary sheet at EUR 4.96/12 months and a second complete
sheet at EUR 4.88/24 months. The agent examined only the first. It asked a generic
question, the alternative disappeared, and it accepted the original cost.
The score was `(198846.33 − 198846.33) / (198846.33 − 196529.32) = 0` despite
meeting every constraint. The unused alternative modeled EUR 197,071.33,
EUR 1,775 lower than the eventual deal, if the supplier would confirm it.

## Iteration six

**Change:** use current structured supplier alternatives, not just the first
sheet. A cheaper complete option is checked against all allowed values,
must-haves and reservation cost, then sent back with its exact terms to obtain
a matching standing quote. We do **not** assume an alternative ID can be
accepted: the API documents acceptance of the standing ID. Stale, incomplete,
prose-only, invalid, repeated and more expensive alternatives are excluded.
Concrete small savings bypass the stopping threshold used for speculative
proposals. One complete option is sent; there are no duplicate supplier sends.

**Local gate:** 223 passed, 1 skipped, 15 subtests passed. Added tests cover
standing confirmation before acceptance, total-cost ordering, constraints,
expiry by later messages, exact field sets, duplicates and small real savings.
All three local cases and comparison baselines remained unchanged.

Seed `1169296111`; source
`8047ab679d7d55006808b487bcf663e3432a3d534ec15006c1efa6aefe1ec154`.

| Case | Score /100 | Replay |
| --- | ---: | --- |
| P02 | 9.22 | [Motor cost increase](https://arena.tacto.ai/replay/5c99454ae0cf077c) |
| P07 | 62.74 | [Fastener commitment](https://arena.tacto.ai/replay/e7e3c3882e6eb93a) |
| P01 | 26.79 | [Foundry increase](https://arena.tacto.ai/replay/15aee8fe28f14925) |

All valid deals; no runner, audit or evidence-loader errors. Neither the new
response-trade branch nor the structured-alternative branch was triggered by
this random sample. Their hosted performance remains unproven; P04 was not
rerun after its fix.

**Reflection:** P01 exercised the evidence correction. The supplier requested
the missing document and price support; we attached the cited supplier-authored
excerpt and cited two qualifying purchase orders. Arena returned `verified`.
The supplier explicitly said that valid historical prices did not change its
current calculation. It accepted EUR 136.69 with 30-day payment, the same result
as the prior round. Better evidence compliance did not produce a better score.

P07 again secured 24-month coverage at EUR 5.52, matching the prior outcome.
P02 reduced EUR 370.96 to EUR 370.25, then stalled. The supplier described its
price as covering material/labor increases, refused to disclose its cost
breakdown and mentioned copper indexation in prose without complete clause
terms. We did not invent those terms. The policy eventually accepted a safe but
weak improvement with moves still available. A broad refusal to cut price is
not proof that no worthwhile package exists.

## Local comparisons and reproducibility

Scores /100 were identical across all three local batches:

| Agent | S01 | S02 | S03 |
| --- | ---: | ---: | ---: |
| unified | 34.78 | 34.37 | 40.63 |
| supplier | 34.28 | 34.37 | 11.64 |
| packages | 8.45 | 8.59 | 23.19 |
| advanced | 60.91 | 60.32 | 73.79 |

The scripted local cases do not exercise every hosted dialogue branch. Their
unchanged scores show no observed local regression, not hosted superiority.
`advanced` still scores higher on these local cases; this is another reason not
to promote `unified` without a controlled hosted comparison.

Each batch's local and hosted source fingerprints match. The final source still
matches iteration six. Seeds and samples were saved before session creation;
no strategy edits were made while a hosted batch ran. Manifests, full
transcripts, decisions, scores and audit results are retained under
`output/validation/iteration-{4,5,6}-{local,hosted}/` (ignored output), with
replay links above. Git base:
`cb01512947a07d98ae020af3014d968d21ef06cd`; these are working-tree versions,
not committed releases. No fourth cycle was silently added.

## Final reflection and remaining work

The cost calculator and safe closing are consistent with Arena's results in
these nine runs. The weaker area is turning supplier responses into accepted,
valuable exchanges. Safety is necessary; it is not the same as a strong grade.

What improved:

- Evidence selection now matches the checker; a real hosted citation verified.
- Explicitly invited exchanges can be costed instead of merely acknowledged.
  New local tests prove bounded buyer benefit and constraint checks, not
  supplier willingness to accept.
- A complete, cheaper secondary offer is no longer silently ignored. Local
  tests verify exact-term confirmation and acceptance of the resulting standing
  ID, including small genuine savings. The P04 missed saving remains a modeled
  opportunity, not a claimed live gain.

Recommended next work, in order:

1. **Value-aware counter movements.** The price ladder currently reacts mainly
   to unit-price concessions. P05's supplier made an invalid slow quote valid
   by accelerating delivery while increasing price; our ladder did not value
   that move and stalled. Cost whole-package changes and feasibility repairs,
   while preserving reservation limits and preventing concessions for a worse
   package. Test synthetic combinations, not case IDs or hidden floors.
2. **Clarify useful but incomplete trade invitations.** P02's prose-only copper
   clause cannot safely become a contract. Ask for a complete structured clause
   when the expected buyer benefit justifies another move. Likewise request
   specific quality commitments rather than assuming them. Avoid repeating
   questions the supplier has already refused.
3. **Validate opening/stopping policy with matched comparisons.** The fixed
   opening discount and 0.1% speculative-improvement threshold are heuristics,
   not the grading formula. P08 stops early; P02 holds a large price gap. Test
   bounded alternatives on the same predetermined cases and report every
   outcome, including failures. Do not tune to exposed post-run C_best values.
4. **Prove the new branches live before changing defaults.** A future approved
   practice round should compare the response-trade and structured-alternative
   paths against the previous behavior on matching cases. Keep baselines and
   record acceptance, score, costs and trade-offs, not only valid packages.

These are explicit remaining tasks, not completed claims. The work is local;
nothing was committed or pushed. The documents skill was used for the report
workflow; with its document connector unavailable, the durable deliverable is
this repository Markdown report.
