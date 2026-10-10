# MVP implementation and validation report

10 October 2026. Branch: `task/stefan-mvp-completion`.

## Outcome

The combined negotiation path now completes all three local cases and the three
randomly selected hosted practice cases. All hosted runs made deals and the Arena
confirmed that every deal met the buyer's must-haves. Their mean score was
**49.50/100**. The full automated suite passed: **180 tests, 1 skipped, and 15
subtests passed**. The skipped test is the separately configured hosted test fixture;
the three real runs below were executed through the validation harness.

This satisfies the basic MVP gate of passing tests, sourced decisions, valid deals
and at least two nonzero practice scores. It does not establish that unified is
better than the other agents across the Arena. The default remains `supplier`;
`unified` is explicitly selectable.

## What changed

1. **Relevant supplier letters now reach the agent.** With `--data data`, unified
   reads attributable supplier emails and letters, including the trigger document
   and downloaded release data. Supplier, part, author and date checks exclude
   unrelated or buyer-authored material. Evidence keeps its original document ID.
2. **More explicit supplier statements are recognized.** Requests for earlier
   payment or firm commitments can inform the profile. Ambiguous or contradictory
   statements remain unknown. Spreadsheet text is also available as sourced
   supplier evidence.
3. **Quality now has a limited, concrete trade.** A supplier's explicit numeric
   quality guarantee can support an allowed quality term and a softer price ask.
   A vague statement about quality does not establish a guarantee.
4. **Package choices and messages are clearer.** Identical commercial terms at
   different prices are reduced to the cheapest proposal. Distinct supported
   trades remain available, up to three packages. Emails state the proposed
   give/get. The documented two-percentage-point cap on supplier cost claims
   remains in the policy and decision log; the agent does not reveal that internal
   negotiating rule to the supplier.
5. **The negotiation loop now handles competing suppliers more carefully.** One
   supplier's final offer does not automatically end the whole case. Independent
   supplier messages can be dispatched concurrently, and closing is chosen
   globally. A configurable 0.1% cost threshold stops when even the remaining
   proposals offer negligible improvement; this is a proposal comparison, not a
   prediction of supplier acceptance.
6. **Contract handling is more faithful.** A supplier's explicit standard term is
   valid even when outside the case's listed options. Missing terms use those
   standards first; explicitly allowed no-index clauses are preserved. Unified
   will not accept missing commercial terms based only on buyer defaults.
7. **There is a repeatable validation harness.** It records the code fingerprint,
   local comparisons, random selection, decisions, transcripts, scores and replay
   links. Generated transcripts stay in an ignored local directory.

The earlier local coverage, must-have and monotonic-concession fixes were preserved.
No case-ID conditions, hidden supplier parameters or sample-specific price settings
were added.

## Local tests and reflection

Scores below are Arena-style scores multiplied by 100. They are not percentages of
purchase-price savings. The local supplier follows a script.

| Local case | Unified before this task | Unified after | Supplier baseline | Packages baseline | Advanced baseline |
|---|---:|---:|---:|---:|---:|
| S01 | 8.45 | 34.78 | 34.28 | 8.45 | 60.91 |
| S02 | 8.59 | 34.37 | 34.37 | 8.59 | 60.32 |
| S03 | 23.19 | 40.63 | 11.64 | 23.19 | 73.79 |

Every local run made a deal. Unified's recorded package/acceptance audits reported
no contract, must-have, source-link or reservation-cost violations. Its results with
and without the archive were identical on these three fixtures.

The initial comparison exposed redundant price options: offering identical terms
at a higher price gives a supplier an obvious choice against the buyer. Removing
that redundancy is a general negotiation correction, not a rule about the
simulator. The broader review also found the standard-term exception in the Arena
contract. Tests now cover preserving that value and an explicit null index clause.

Additional scenarios vary price, quantity, profile evidence and payment constraints.
They cover conflicting statements, unrelated/future documents, release data,
numeric quality ambiguity, the last available move, concurrent supplier responses,
and recovery from a session conflict. Changed Python files pass Ruff and
`git diff --check` passes. Three existing import-order lint findings remain in
untouched baseline/demo files; this is not a claim that repository-wide lint is clean.

The advanced baseline still wins the scripted score comparison. Local scores alone
therefore provide no reason to promote unified or to copy an aggressive strategy
without hosted comparison.

## Three random hosted cases

Seed: `1763222757`. Selection was uniform without replacement from the ten eligible
hosted cases, and persisted **before** any session was opened. Selected order:
P07, P18, P10. Exactly three sessions were opened; no cases were replaced or rerun.
The strategy was frozen before this draw and unchanged after seeing these results.

Runs completed on 10 October 2026, approximately 21:59:53-22:00:19 Europe/Berlin.

| Case | Situation | Score / 100 | Deal | Total-cost saving vs opening | Replay |
|---|---|---:|---|---:|---|
| P07 | Bundle a fastener kit | **62.74** | Yes | EUR 57,590.60 | [P07 replay](https://arena.tacto.ai/replay/16a1183e042b9299) |
| P18 | Alloy surcharge and base price | **20.24** | Yes | EUR 14,681.36 | [P18 replay](https://arena.tacto.ai/replay/412269df409230ef) |
| P10 | Secure seal supply under capacity pressure | **65.51** | Yes | EUR 395,395.38 | [P10 replay](https://arena.tacto.ai/replay/5d405e3832a0f47a) |

Mean: **49.50/100**. There were no run errors, recovery closes, or detected audit
violations. All three final costs matched the agent's accepted-offer cost calculation.
No supplier reply reported a contradicted claim. The cited archive documents are
context evidence; this does not mean the Arena independently verified every
supplier statement quoted in the emails.

### What the actual conversations show

**P07:** The agent proposed covering the full two-year need. The supplier explicitly
said the 24-month commitment enabled a better price. The opening was EUR 5.74 with
a 12-month contract; the deal was EUR 5.52 with 24 months and 30-day payment.
The agent stopped requesting a cost breakdown after the supplier refused it.
Most of the gain came from the complete package, not the small final price move.

**P10:** The opening covered only 19,890 units per year, below the buyer's minimum
of 22,230. Sourced capacity letters supported the proposal for 23,400 units per
year and a 24-month commitment. The supplier's final offer was EUR 31.80, with
that volume and duration and a 56-day lead time. The agent accepted the valid
final sheet. Delivery still carries EUR 33,600 of modeled lateness cost, so this
was not an ideal deal. The supplier also asked for evidence supporting the target
price; the agent's next message did not supply an independent price argument.

**P18:** The supplier reduced the base price from EUR 6.10 to EUR 5.70, but added
an alloy index clause for the longer contract. The agent included that clause's
cost and risk in its calculation, so it did not treat the nominal discount as
pure savings. It nevertheless accepted after one reply because the supplier
beat its previous price request and no new package was generated. It did not
explore the allowed index deadbands or better payment terms. This identifies a
general limitation: achieving a requested price can stop further work on other
terms. The replay does not prove which further trade the supplier would accept.

## What still needs work

- **Broader trade planning:** explore permissible risk/price/payment exchanges
  without inferring unsupported supplier motives. Commodity index clauses are a
  useful next category, but any change should be tested across several case types.
- **Stronger evidence-based arguments:** the current path mainly attributes
  supplier statements and uses explicit motives. It does not automatically build
  a complete argument from purchasing history, market series and buyer notes.
- **Hosted coverage:** these three cases each had one supplier. Concurrent RFQ
  handling and the new quality trade passed local tests but were not exercised
  in this random hosted sample. A matched comparison against baselines is also
  still needed before changing the default.
- **Uncertainty:** profile rules are narrow and mostly English. Supplier economic
  estimates remain unknown when unsupported; the strategic relationship-cost
  component cannot be reliably predicted without those estimates.
- **Final operation:** release loading was tested with fixtures. The actual Sunday
  release, event machine/network, timed final runner and submission/slides still
  need the event-day check described in `brief/submission.md`.

The next step should be a controlled, varied comparison and a general improvement
to non-price trade exploration. These three successful runs support an operational
MVP; they do not support a claim that the entire strategy is optimized or final-ready.

## Reproduce and inspect

Implementation base: `cb01512947a07d98ae020af3014d968d21ef06cd` plus working-tree changes.
Tested source SHA-256:
`66c19bf06df291816cde516d10319bf557a6c66c481ef1aa8752afce16cae3ec`.
The fingerprint covers code, tests, simulator JSON and project configuration.

- Plan: [MVP_COMPLETION_PLAN.md](MVP_COMPLETION_PLAN.md).
- Runner: [scripts/validate_mvp.py](scripts/validate_mvp.py).
- Local manifest: `output/validation/mvp-local-20261010/run.json`.
- Hosted manifest: `output/validation/mvp-hosted-20261010/run.json`.
- Per-case JSON files beside each manifest contain the transcripts and decisions.

Run the local comparison with a fresh output directory:

```bash
.venv/bin/python -m scripts.validate_mvp --mode local --out output/validation/local-next
.venv/bin/python -m pytest -q
```

Running the harness with `--mode hosted` consumes three practice sessions. The
current task's three sessions are already complete.
