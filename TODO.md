# MVP finish plan

Goal: turn the current end-to-end `unified` negotiation path into a reliable, evidence-backed MVP. The path already reads supplier evidence, prices packages with buyer cost, and enforces a reservation value. The remaining work is supplier intelligence, negotiation strategy, reliability, and practice validation.

## Shared rules

- Work on a short-lived branch named `task/<owner>-<topic>`.
- Keep commits small and single-purpose. Do not reformat unrelated files.
- Do not commit `.env`, API keys, generated transcripts, local configuration, or screenshots.
- Add or update focused tests with every code change. Run `pytest -q` before opening a merge request.
- Preserve source provenance. A supplier trait, claim, or rationale must cite explicit supplier evidence; otherwise its state is `unknown`.
- Do not change another person's owned files without asking first. Add a new module when that avoids an overlap.

## Merge order and integration contract

1. Jonas defines and implements the supplier-profile output.
2. Stefan consumes that stable output in the unified negotiation policy.
3. Ahmet and Georgi supply replay findings and message-review examples for tuning.
4. Stefan integrates the resulting policy changes, runs practice cases, and promotes `unified` only when it is demonstrably better.

The profile contract used between Jonas and Stefan is deliberately small:

```json
{
  "cash_sensitive": {"state": "likely|unknown", "confidence": 0.0, "evidence": []},
  "capacity_sensitive": {"state": "likely|unknown", "confidence": 0.0, "evidence": []},
  "quality_sensitive": {"state": "likely|unknown", "confidence": 0.0, "evidence": []},
  "price_rigid": {"state": "likely|unknown", "confidence": 0.0, "evidence": []}
}
```

Each `evidence` entry must retain an evidence ID and source. Existing callers that only read `state` and `confidence` must continue to work.

## Jonas — supplier intelligence and profile v1

**Owns:** `negotiator/intelligence.py`, `negotiator/supplier_evidence.py`, relevant evidence fixtures and tests.

**Do:**

1. Implement a deterministic supplier-profile v1 from explicit supplier evidence only.
2. Add narrowly scoped rules for each dimension. Examples: an explicit request for earlier payment can support `cash_sensitive`; an explicit capacity limit can support `capacity_sensitive`; an explicit quality commitment or quality-risk statement can support `quality_sensitive`; repeated explicit refusal or fixed-price language can support `price_rigid`.
3. Attach confidence and source IDs to every non-unknown state.
4. Keep quote history safe: never compare prices across different currencies, price units, volume, or materially different commercial terms.
5. Keep PDF/CSV/email extraction source-traceable and robust. OCR remains optional; unreadable scans must be reported, not fabricated.

**Do not:** infer motivation from price history alone, buyer cost data, or missing documents.

**Done when:**

- A supplier context returns the contract above.
- Tests cover one positive and one `unknown` case for every profile dimension.
- Every `likely` result links to supplier evidence.
- Existing extraction and supplier-policy tests pass.

## Stefan — unified policy, packages, and Arena orchestration

**Owns:** `arena_kit/agents/unified.py`, `negotiator/package_policy.py`, `arena_kit/cli.py`, `tests/test_unified.py`, and the current simulator assertion repair in `tests/test_sim.py`.

**Do:**

1. Repair the one red simulator assertion so it accepts quote-parser metadata (`currency`, `price_unit`) while still checking the Arena contract terms.
2. Consume Jonas's profile contract without reinterpreting evidence. Unknown profile values must keep the conservative price-only ladder.
3. Move the existing bounded supplier-claim adjustment into the unified policy. Supplier index/cost-share claims may adjust an opening ask only within a documented cap and must be cited in the message.
4. Add a hypothesis/trade layer that maps a `likely` profile to a concrete give/get: for example, earlier payment or commitment only when the evidence supports it. Every package must still satisfy buyer must-haves and reservation cost.
5. Improve multi-round behavior: choose whether to re-package, hold, accept, or walk away using the current offer, remaining moves, reservation cost, and supplier response.
6. Keep the existing `supplier`, `packages`, and `advanced` agents runnable as comparison baselines. Keep `unified` selectable until practice results support making it the default.

**Done when:**

- `unified` selects the lowest total-cost valid package across active suppliers.
- A supported profile changes a reciprocal term; an unknown profile does not.
- Final offers above the alternative or fallback reservation are rejected.
- Unit tests cover multi-supplier choice, supported/unknown profile behavior, claim cap, final offer, and remaining-moves behavior.
- Full test suite is green.

## Ahmet — supplier and replay research

**Owns:** evidence-review notes and replay findings; no code changes required.

**Do:**

1. Review practice replays, beginning with P10, and record for each supplier: opening offer, concessions, final offer, explicit supplier claims, missing terms, and the exact point where the negotiation stopped improving.
2. Separate facts from hypotheses. Write the exact supplier wording/source for every claim.
3. Propose no more than three plausible give/get trades per supplier, each tied to an observed fact. Mark uncertain ideas as hypotheses, not facts.
4. Give Jonas representative examples for profile rules and Stefan examples for package/rationale tests.

**Deliverable template:**

```text
Case / supplier:
Observed facts and sources:
Concessions by round:
Likely supplier priority (with evidence):
Possible give/get packages:
What the agent should ask next:
```

**Done when:** at least three reviewed supplier traces include evidence-linked trade ideas and one P10 diagnosis.

## Georgi — quality gate and MVP evaluation

**Owns:** acceptance checklist, message review, and practice-score log; no code changes required.

**Do:**

1. Review generated supplier messages for fact fidelity: no invented prices, deadlines, supplier motives, or unsupported claims.
2. Check every proposed package for understandable give/get wording and a clear call to action.
3. Maintain a small practice log: case, agent version, deal/no-deal, score, supplier selected, key reason, and replay link.
4. Define the MVP gate: all tests green, no unsupported message claims in reviewed samples, and non-zero score in at least two controlled practice cases.
5. Report the highest-impact failure pattern after each small practice batch so Stefan can tune one thing at a time.

**Done when:** the checklist and score log support a clear go/no-go decision for making `unified` the default.

## Definition of done for the MVP

- All automated tests pass.
- Supplier evidence is sourced and profile states are either evidence-backed or `unknown`.
- The unified agent produces valid, buyer-efficient packages and never accepts above the buyer reservation value.
- Generated messages cite only available supplier evidence and make a concrete, reciprocal ask when a profile supports one.
- Controlled practice results include at least two non-zero scores and documented replays.
