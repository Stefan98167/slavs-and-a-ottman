# Quality gate and MVP evaluation

**Status: BLOCKED — do not mark the MVP ready yet.**

This is a quality-review record for the current worktree (`b56b7ff+dirty`) at
2026-10-10.  It intentionally makes no production-code changes.  Local
simulation results are evidence of contract correctness only; they are not
Hackathon practice results or a prediction of hidden-supplier performance.

## Scope and evidence

The reviewed controlled batch used the local `SimTable` cases S01–S03:

- `StrategicAgent`, default settings: 20 outbound proposal emails;
- `RLAgent`, default local policy: 16 outbound proposal emails;
- `SupplierContextAgent`, default settings: 6 outbound proposal emails.

Every proposal in that normal-run sample carried exactly the case's
`negotiable` fields.  The audit also exercised the capacity-sensitive package
branch, the strategic/RL final-package branch, and an intentionally false
LLM response with a real data ID.  No hosted Arena session was opened.

## What passed

| Check | Result | Evidence |
| --- | --- | --- |
| Term-sheet shape in normal samples | Pass | All 42 sampled proposal sheets contained exactly the negotiable fields. |
| Normal strategic factual claims | Pass | The OTD statements match the case facts: S01 `84.6%`, S02 `88.5%` / `76.0%`, and S03 `81.1%`. |
| Clear request to respond | Partial pass | Normal messages ask the supplier to confirm/approve a package. |
| Automated test suite | Pass | `92 passed, 2 skipped, 15 subtests passed`; skipped tests require unavailable hosted/MCP dependencies. |
| Controlled non-zero scores | Pass, local only | S01 `1.0000`, S02 `0.9901`, S03 `1.0000`; see [PRACTICE_SCORE_LOG.md](PRACTICE_SCORE_LOG.md). |

The OTD claims are grounded in [S01.json](arena_kit/sim_cases/S01.json),
[S02.json](arena_kit/sim_cases/S02.json), and
[S03.json](arena_kit/sim_cases/S03.json), not inferred from supplier motive.

## Blocking findings

| ID | Severity | Finding | Why it fails the gate |
| --- | --- | --- | --- |
| QG-01 | P1 | A capacity-profile message can say it exchanges “greater commitment” even when no supplier-favourable non-price term changes. | This is an unsupported give/get claim. |
| QG-02 | P1 | Strategic/RL say “We can confirm at your stated price” while attaching extra terms that form a new counter-offer. | The wording is ambiguous and lacks a clear request to accept the changed terms. |
| QG-03 | P1 if LLM mode is deployable | The LLM guard preserves invented prices, dates, and motives when the output includes a known ID. | A known ID does not verify the surrounding numeric claim. |
| QG-04 | P2 | Generic package text does not state the offered price or exact give/get in prose. | A supplier must inspect an attachment to know what is being requested. |
| QG-05 | P2 | The supplier-context agent can call a quote “comparable” across currencies when the current offer has no known currency. | That can create an unsupported price-history claim. |

### QG-01 reproduction

With a capacity signal on S03, the capacity branch generated these two sheets:

```json
{"unit_price": 215.60, "payment_days": 90, "contract_months": 24, "incoterm": "DAP"}
{"unit_price": 219.91, "payment_days": 90, "contract_months": 24, "incoterm": "DAP"}
```

Only price changes, but the body says the alternative exchanges greater
commitment.  The same problem can occur when only one package is emitted.
The cause is that the message is chosen from a supplier profile rather than
the actual difference between term sheets; see
[`StrategicAgent._friendly_terms`](arena_kit/agents/strategic.py) and
[`StrategicAgent._body`](arena_kit/agents/strategic.py).  The older package
policy has the same pattern in `negotiator/package_policy.py`.

### QG-02 reproduction

In S02 the supplier's final sheet is price-only (`15.49`).  The strategic and
RL agents attach a complete sheet with `payment_days=90` and
`lead_time_days=21`, but say they are confirming the supplier's price.  This
must be described as a counter-proposal unless it is an exact acceptance of
the standing term sheet.

### QG-03 deployment restriction

Do not use `--agent llm` for a live case until its guard validates stated
figures/claims against the referenced record, not merely the existence of an
ID.  The same review should be applied to the legacy email generator.  This
is a deployment restriction, not a code change made in this review.

## MVP acceptance checklist

| Requirement | State | Notes |
| --- | --- | --- |
| All tests green | Pass with caveat | Tests are green; local Ruff is unavailable, so CI still needs to verify lint. |
| No unsupported message claims in reviewed samples | **Fail** | QG-01 is reproduced; QG-03 and QG-05 are reachable factual-risk paths. |
| Every package has understandable give/get wording and a clear call to action | **Fail** | QG-01, QG-02, and QG-04. |
| Non-zero result in at least two controlled cases | Pass, local only | Three local controlled cases qualify for a simulator gate, not hosted-practice validation. |
| Hosted practice score and replay evidence | Not started | No Arena URL/key or hosted replay is configured in this workspace. |

## One change for Stefan's next iteration

**Make the strategic message renderer derive its wording from the exact
term-sheet delta.**  Only name a supplier benefit when a corresponding
supplier-favourable field truly changes; otherwise omit the claimed trade.
When a same-price sheet adds or changes terms, call it a counter-proposal and
ask the supplier to approve those named changes rather than saying
“confirm.”

This single change directly addresses the highest-impact failure pattern:
template/profile-driven prose that does not faithfully describe the attached
package.  Re-run this checklist after that change before tuning anything else.

## Next evidence needed

Once credentials are supplied, run a small hosted practice batch and add one
row per completed session to [PRACTICE_SCORE_LOG.md](PRACTICE_SCORE_LOG.md),
including the actual replay URL and the supplier's stated reason.  Do not
record API keys in the log.
