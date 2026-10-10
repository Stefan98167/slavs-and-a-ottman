# Full-suite benchmark and three random follow-ups

## Outcome

Exactly **13 new hosted sessions** completed: all ten eligible hosted practice
cases on one frozen version, then three uniformly random cases after reflection
and targeted changes. No replacements, merge, commit, push or default promotion.

The graphical plain-language report is
`output/pdf/system-and-13-run-review.pdf`. It explains the challenge, scoring,
the original architecture, components, observed failures and next decisions.

| Case | Ten-case benchmark /100 | Random follow-up /100 |
| --- | ---: | ---: |
| P01 | 61.61 | 61.61 |
| P02 | 17.69 | - |
| P03 | 89.98 | - |
| P04 | 76.61 | - |
| P05 | 33.46 | 35.21 |
| P07 | 64.72 | - |
| P08 | 19.58 | - |
| P10 | 65.51 | - |
| P11 | 53.60 | - |
| P18 | 20.24 | 20.24 |

Ten-case mean: **50.2996837/100**. Follow-up mean: **39.0213466/100**.
Those same three cases previously averaged **38.4360300/100**; observed paired
change **+0.5853167 points**. Different case mixes must not be compared as a
causal overall gain. Three practice repeats are not an unseen holdout.

## Before the full benchmark

Implemented the pending targeted dialogue/protocol recommendations: per-term
clarification memory with a two-question thread budget, incomplete-offer
recovery without guessed terms, explicit capacity-refusal follow-up, current
indicative-alternative clarification and specific internal infeasibility
diagnostics. Final offers remain conservatively closed, not pushed for an
unconfirmed alternative. Added full-ten selection to the validation harness.

Local gate: **288 passed, 1 skipped, 15 subtests passed**. All local S01-S03
scores for unified, supplier, packages and advanced remained unchanged. Lint
on touched code and `git diff --check` passed.

Source: `7e618c0819fff26779815ce74e75759cd3034208cf6a89b4c6be5bb92de44400`.
Evidence: `output/validation/full-suite-10-hosted/` and
`output/validation/full-suite-before-local/`. The complete selection was saved
before opening any session. The source was held fixed throughout the batch.

## Reflection after reading all ten conversations

- **P01:** 14-day payment supported by a supplier letter led to 133.80. One
  purchase-order argument verified. The earlier acknowledgement/disclosure fix
  now has hosted confirmation: subsequent acknowledgements sent no extra history.
- **P02:** targeted clarification produced an index-linked secondary quote, then
  primary confirmation at 348.03. This exercised both branches live. However,
  modeled cost understated Arena by **EUR 115,648.66**, entirely relationship
  cost. Do not fit private supplier economics from the result.
- **P03:** later payment at a higher price again lowered actual total cost;
  score 89.98. Relationship cost added EUR 259.63 beyond the model.
- **P04:** the 24-month package worked; verified history did not win a further
  price reduction. Respecting the final offer closed at 4.88.
- **P05:** repaired delivery from invalid 52 days to valid 42 days. A later-payment
  experiment then worsened the supplier's standing whole-cost offer by EUR 1,442.
  The agent had no request to recover the earlier actually quoted package. A
  statement describing current payment terms also triggered an unnecessary
  clarification. The inactive suppliers recorded **five timeouts**: two on the
  early agreed supplier and three on the uncompetitive supplier, which withdrew.
  Clean contract audits alone did not mean the run was operationally clean.
- **P07:** 24-month coverage and a reciprocal counter reached 5.49; supplier agreed.
- **P08:** confirmed the supplier's 5% index deadband at 5.72, improving on earlier
  development outcomes. The lower-price alternative carried more index exposure.
- **P10:** repaired deficient volume and retained valid coverage/delivery; 65.51.
- **P11:** quality improved to 1,500 ppm but price ended at 46.00, worse than the
  older 45.50 result. Feasibility-credit settings merit a controlled comparison;
  reply variability and multiple historical changes prevent isolated attribution.
- **P18:** the supplier rejected the improved index band and made a final offer.
  A cost-saving hypothetical proposal does not guarantee commercial acceptance.

Every message, term sheet, status, argument result and returned timeout was
reviewed, including all three P05 suppliers. All ten deals met must-haves and
actual reservation limits. No runner or contract-audit errors. Eight modeled
accepted costs matched Arena exactly; the two disclosed exceptions were P02/P03.

## General changes made before the follow-ups

1. Added `negotiator/offer_restoration.py`: after a cost-worsening experiment,
   ask once to renew complete, valid, better prior primary terms, under current
   standards. Only open threads qualify. This is a fresh conditional proposal,
   never permission to accept a historical offer ID.
2. Restricted trade invitations to first-hand prospective sentences, excluding
   quotations, refusals and descriptions of already extended payment terms.
3. Added honest evidence/source replies to clarification and hold messages,
   not only numeric counters. Quoted/negated document requests cannot disclose
   sources. This closes the dropped-question behavior observed in P02.
4. Added authoritative remote-state refresh before unified closes, reconciling
   separately returned timeout IDs/terms and rechecking buyer safety. Superseded
   unsent closing decisions remain labeled in the trace. Added explicit timeout
   counts to run records and summaries.

Focused tests initially exposed restoration losing precedence to another
hypothetical package. The corrected rule prefers renewal of a previously
actually quoted safe package after a failed experiment, unless a better current
structured alternative exists. Tests vary prices and include missing terms,
invalid requirements, one-shot behavior, final offers, source provenance,
stale IDs and over-budget refreshed offers. Saved P05 input produced the intended
32.50/45-day restoration request before any new live result was known.

Final local gate: **305 passed, 1 skipped, 15 subtests passed**; all local scores
unchanged, lint and diff checks clean. Source:
`c41b464d4c12b9aa4a77b391265ddb6ff5a1b8003df779b85bdc4a4183559511`.
Local evidence: `output/validation/full-suite-after-local/`.

## Three random follow-ups and final reflection

Seed **2742409430**, saved before sessions opened, selected **P05, P18, P01**
uniformly without replacement from all ten. No case was selected because it
would exercise the new branch. Source matched the preceding local gate.

- **P05:** restoration exercised live. Supplier agreed a new standing quote at
  32.50/45 days/42-day delivery. Actual cost fell from EUR 278,069.12 to
  **EUR 276,627.12**, improving the score from 33.46 to **35.21**. The strategy
  recovered a self-inflicted loss; it did not discover a new cheaper frontier.
- **P01:** unchanged **61.61**, with one verified history argument and no later
  needless disclosure. Pre-close state refresh worked.
- **P18:** unchanged **20.24**. The better-band trade was again refused. This
  work did not solve the underlying commercial weakness.

All three met must-haves and actual reservation. No runner/audit errors, evidence
warnings or recorded timeouts. Actual accepted costs matched the model. Replies
were much faster than the full benchmark; zero timeouts cannot be attributed
to a scheduler fix, because independent per-thread scheduling was not implemented.
No policy code changed after these runs. The mixed 13-run mean is about 47.70,
but combines two versions and repeats three cases; use the full-ten mean as
the headline benchmark.

**Keep:** sourced profiles; conservative unknowns; full cost and constraint gates;
one selected proposal; concrete alternative confirmation; bounded trades; prior
quote renewal after a failed experiment; fresh standing-ID acceptance.

**Still weak:** mostly English phrase matching; hidden relationship economics;
unproven concession/feasibility-credit settings; idle RFQ timing; arbitrary/mixed
scanned documents and locale conflicts. Broader parser rewrites and shared guards
changing comparison baselines remain separately scoped, not silently claimed done.

**Next:** independent supplier scheduling under slow/uneven responses; predeclared
matched policy comparisons with one change per arm; explicit cost uncertainty
diagnostics; isolated parser hardening; Sunday release and final-machine rehearsal.
Never infer a floor from C_best, add case-ID tactics, cherry-pick replacements or
promote unified from these thirteen observations. Advanced still scores better on
the simple local simulator; no overall baseline superiority has been established.

## Replays

| Phase / case | Replay |
| --- | --- |
| Ten / P01 | https://arena.tacto.ai/replay/1e995020ca5f4f6f |
| Ten / P02 | https://arena.tacto.ai/replay/da4c937cb970d8fb |
| Ten / P03 | https://arena.tacto.ai/replay/278b82835e069cdc |
| Ten / P04 | https://arena.tacto.ai/replay/1fade1b5c9678110 |
| Ten / P05 | https://arena.tacto.ai/replay/ad91c4cbafd812d1 |
| Ten / P07 | https://arena.tacto.ai/replay/229583c08bb6c760 |
| Ten / P08 | https://arena.tacto.ai/replay/a91a2355894277f1 |
| Ten / P10 | https://arena.tacto.ai/replay/a31120c6c6816049 |
| Ten / P11 | https://arena.tacto.ai/replay/413fd2afb055a2f2 |
| Ten / P18 | https://arena.tacto.ai/replay/cd6b0e6cddb93461 |
| Follow-up / P05 | https://arena.tacto.ai/replay/3a8f872fd7caf8b0 |
| Follow-up / P18 | https://arena.tacto.ai/replay/985c50501cf01ff5 |
| Follow-up / P01 | https://arena.tacto.ai/replay/191a2683bd93fb32 |

Git base remains `cb01512947a07d98ae020af3014d968d21ef06cd`; the worktree was
already dirty and unrelated user changes were preserved. Generated raw evidence
is ignored by Git. PDF uses ReportLab and is rendered with Poppler for page-by-page
visual verification. A code fingerprint does not lock dependencies or server behavior.
