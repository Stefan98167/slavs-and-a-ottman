# Practice replay findings for tuning

Reviewed three completed Arena traces: P10 (`f3e9a076d965ebac`), P01 (`7651360e84d58d2a`), and P08 (`cd18f1275a74735a`). A second P10 trace (`a518c42badab7eac`) is included in the P10 diagnosis because it shows a materially different outcome. Replay links are included below. The quoted supplier wording is taken from each replay; the correspondence evidence ID is noted where relevant.

## Case P10 / Dichtungswerk Ravensteiner GmbH (`sup:70410`)

**Replay:** [P10, score 0.484](https://arena.tacto.ai/replay/f3e9a076d965ebac)  
**Comparison replay:** [P10, score 0.000](https://arena.tacto.ai/replay/a518c42badab7eac)  
**Supplier evidence:** `doc:20260918-70410-P10` (capacity email, 2026-09-18).

### Observed facts and sources

- The case email says: “due to very high capacity utilisation we cannot confirm your full forecast” and “We will prioritise customers with firm, long-term commitments.” This is explicit capacity/commitment evidence (`doc:20260918-70410-P10`).
- In the 0.484 replay, round 0 opens at **€32.20/unit, 19,890 units/year, 12 months, 54-day lead time**. The quote has no missing structured fields.
- At round 1, the buyer sends three packages at **€30.59, €31.23, and €31.88**, each for **23,400/year, 24 months, 35 days**. It asks the supplier to share a cost breakdown.
- The supplier says: “we do not disclose internal cost breakdowns” and “a lead time of 35 days is not feasible; 54 days is required.” Its message describes **€31.90 at 54 days** as an alternative, but the structured standing terms show **€34.90 and 35 days**. The text and structured terms conflict.
- The buyer's round 2 repeats the same cost-breakdown request and the same 35-day packages, merely repriced at €33.15/€33.85/€34.55. The supplier's final structured offer is **€34.70, 23,400/year, 24 months, 35 days**; the message also calls €34.70 its final price. The buyer accepts.
- Result: deal, must-haves satisfied, score **0.484**; deal cost **€1,640,121.60** versus best alternative **€1,328,926.89**. The 35-day lead time should be verified against the supplier's explicit statement that 54 days is required.
- In the comparison replay, opening terms are again €32.20, 19,890/year, 12 months, 54 days. The buyer offers €30.59 on those same terms. The supplier moves to €32.00, then a final **€31.90** on the same terms. The buyer accepts; must-haves fail and score is **0.000** (deal cost €1,926,485.40 versus best alternative €1,328,926.89).
- Supplier claims in the comparison replay: “Given the specialized nature of our products and our current capacity utilization, significant price reductions are not feasible” (round 1); “Our pricing flexibility is strictly limited by our current capacity utilization” (round 2). These support capacity sensitivity, not an assumption that the supplier will discount for any particular commitment.

### Concessions by round

| Replay | Round | Buyer move | Supplier move |
|---|---:|---|---|
| `f3e9a076d965ebac` | 0 | — | €32.20; 19,890/year; 12 months; 54 days |
|  | 1 | Three packages: €30.59/€31.23/€31.88; 23,400/year; 24 months; 35 days | Main structured offer €34.90 at 35 days; narrative says 35 days is not feasible and gives €31.90 at 54 days as alternative |
|  | 2 | Three packages: €33.15/€33.85/€34.55 at same terms; repeats request for cost breakdown | Final: €34.70; 23,400/year; 24 months; 35 days; buyer accepts |
| `a518c42badab7eac` | 0 | — | €32.20; 19,890/year; 12 months; 54 days |
|  | 1 | €30.59 at same terms | €32.00 at same terms; says capacity limits large cuts |
|  | 2 | €30.69 at same terms | Final €31.90 at same terms; says flexibility is strictly limited by capacity; buyer accepts |

### Likely supplier priority (with evidence)

- **Capacity certainty: supported.** The explicit case email says capacity is very high, the full forecast cannot be confirmed, and firm long-term customers are prioritized (`doc:20260918-70410-P10`). Replay language also says current capacity utilization limits price reductions.
- **Cost transparency: supplier refuses.** The replay says it will not disclose internal cost breakdowns. Repeating that request did not unlock information.
- **Price rigidity: not established.** In one replay it moves €32.20 → €32.00 → €31.90; in another the offer terms change substantially and the messages conflict. Do not encode a rigid/fixed-price profile from these samples.

### Possible give/get packages

1. **Observed offer, conditional on buyer feasibility:** accept 54 days in exchange for €31.90/unit only if 54 days meets the buyer's supply requirement. The supplier stated this price/date alternative in the replay; do not treat it as valid for 35 days.
2. **Hypothesis to test:** ask whether a buyer-approved firm tranche or longer commitment secures a confirmed allocation and a stated price. The email says such customers are prioritized, but the replay does not establish what commitment is sufficient or what price it earns.
3. **Hypothesis to test:** preserve 35 days only if the supplier confirms it can actually deliver that lead time and quotes a corresponding price in the structured terms. Do not accept a 35-day term when the narrative says 54 days is required.

### What the agent should ask next

> Your message says 35 days is not feasible and 54 days is required, while the structured offer lists 35 days. Please confirm the feasible lead time and provide one matching price and volume package. If 54 days is required, can you confirm the €31.90 alternative and the allocation you can guarantee?

### Diagnosis and tuning examples

- **Highest-impact failure:** the buyer repeats the same cost-breakdown request after an explicit refusal and fails to reconcile the supplier's structured terms with its prose. Its second-round packages still assume the rejected 35-day condition. Parse the latest response, distinguish standing offer from alternatives, and ask a targeted clarification before countering.
- **Jonas profile example:** `capacity_sensitive=likely` can cite `doc:20260918-70410-P10` and the replay supplier statements. A price-rigidity claim should remain unknown absent stronger evidence.
- **Stefan package/rationale example:** test that the agent does not accept a package whose narrative contradicts its structured delivery term; compare `c_deal` with `c_best`; reject the 0-score P10 accept even though the supplier's final price is below its opening price.

## Case P01 / Gießerei Brandlhuber GmbH & Co. KG (`sup:70110`)

**Replay:** [P01, score 0.655](https://arena.tacto.ai/replay/7651360e84d58d2a)  
**Supplier evidence:** `doc:20260911-70110-P01` (price adjustment letter, 2026-09-11).

### Observed facts and sources

- Round 0: **€138.55/unit**, effective 2026-11-01. The supplier says: “LCI-C rose 2.7 % in twelve months and is 30 % of our cost” and “PPI-C241 rose 6.5 % in twelve months and is 24 % of our cost.” Claims cite `idx:LCI-C@2025-06`, `idx:LCI-C@2026-06`, `idx:PPI-C241@2025-08`, and `idx:PPI-C241@2026-08`.
- `payment_days` is missing from the opening terms. After the buyer proposes 30 days net in round 1, the supplier includes 30 days in subsequent offers.
- Buyer counters by round: **€131.62, €132.70, €133.25, €133.55, €133.80, €133.90**. Supplier prices: **€138.55, €136.40, €135.30, €134.70, €134.20, €134.00, €134.00 final**.
- The supplier says at round 2: “Please understand that this is a significant step for us, as we must cover the substantial cost increases we have experienced” and “Our price reflects our costs; our calculation stays internal.” It does not disclose a cost breakdown.
- At round 6 it says: “€134.00 per unit is the absolute limit” and “this must be our final offer.” Buyer accepts €134.00, 30 days, effective 2026-11-01.
- Result: must-haves satisfied, score **0.655**; deal cost €1,116,453.13 vs best alternative €1,096,815.78.

### Concessions by round

| Round | Buyer price | Supplier price / result |
|---:|---:|---|
| 0 | — | €138.55; effective 2026-11-01; payment term missing |
| 1 | €131.62; proposes 30 days | €136.40; 30 days |
| 2 | €132.70 | €135.30; 30 days |
| 3 | €133.25 | €134.70; 30 days |
| 4 | €133.55 | €134.20; 30 days |
| 5 | €133.80 | €134.00; 30 days |
| 6 | €133.90 | €134.00 final; buyer accepts |

The negotiation stopped improving after round 5: the supplier repeated €134.00 in round 6 and called it its final offer.

### Likely supplier priority (with evidence)

- **Cost recovery:** supported as the supplier's stated rationale; its indexed cost claims and refusal to disclose its internal calculation are explicit. The claims do not independently prove the full proposed increase is warranted.
- **Price rigidity: not established.** The supplier made multiple price concessions from €138.55 to €134.00, despite saying it needed to cover cost increases.
- **Cash sensitivity: not established.** Payment terms were missing initially; the replay does not ask for earlier payment or link the 30-day term to a price change.

### Possible give/get packages

1. Ask for the buyer-approved 30-day payment term in exchange for a specific price step, as the buyer did; treat any causal price benefit as unproven unless supplier confirms it.
2. Ask whether the supplier will phase the increase or agree to a review date tied to the cited LCI-C/PPI-C241 references. This is a hypothesis; no phasing proposal appears in the replay.

### What the agent should ask next

> We note the LCI-C and PPI-C241 references and the 30-day payment term. Can you confirm whether €134.00 is your final price and whether any phased effective date is possible? Please identify the index basis for any future adjustment.

**Tuning examples:** give Jonas the source-backed index/cost statements but do not infer cash sensitivity. Give Stefan a test for bounded index-based opening adjustments with citations, and a round policy that holds or accepts at €134 after the supplier repeats its final price instead of spending another move for no gain.

## Case P08 / Edelstahl-Service Donautal GmbH (`sup:70710`)

**Replay:** [P08, score 0.109](https://arena.tacto.ai/replay/cd18f1275a74735a).

### Observed facts and sources

- Round 0 terms: **€6.05/unit**, 30 days, 12-month term, no index clause. The supplier says “AS-14404 rose 5.9 % in twelve months and is 45 % of our cost,” “LCI-C rose 2.7 % in twelve months and is 5 % of our cost,” and “PPI-C2431 rose 12.3 % in twelve months and is 38 % of our cost.” Claims cite `idx:AS-14404@2025-09`/`idx:AS-14404@2026-09`, `idx:LCI-C@2025-06`/`idx:LCI-C@2026-06`, and `idx:PPI-C2431@2025-08`/`idx:PPI-C2431@2026-08`.
- Buyer counters **€5.75, €5.81, €5.84, €5.85**. Supplier responds **€5.93, €5.88, €5.86**, then accepts **€5.85** at round 4. Payment, 12-month term, and no index clause remain unchanged.
- The supplier says at round 2: “Our price follows our main cost drivers: AS-14404, PPI-C2431, LCI-C.” It still reduces the price in later rounds and accepts the buyer's €5.85.
- No structured fields are marked missing. There are no explicit supplier concessions on payment, term, or index clause.
- Result: must-haves satisfied, score **0.109**; deal cost €1,116,800.88 vs best alternative €960,309.33.

### Concessions by round

| Round | Buyer price | Supplier price / result |
|---:|---:|---|
| 0 | — | €6.05 |
| 1 | €5.75 | €5.93 |
| 2 | €5.81 | €5.88 |
| 3 | €5.84 | €5.86 |
| 4 | €5.85 | Accepted |

There is no rejected plateau in this trace: the supplier accepts €5.85 at round 4. The best alternative remains materially cheaper in total cost, so a deal alone is not evidence of a good outcome.

### Likely supplier priority (with evidence)

- Supplier explicitly presents the three indices and their claimed cost shares as the price rationale. The supported fact is that it cites those drivers; the replay does not establish that it is price-rigid.
- The supplier accepts a 12-month fixed price with no index clause, and its unit price moves down each response. This argues against assuming that the index claims require an index clause or preclude further negotiation.
- No evidence supports cash, capacity, or quality sensitivity.

### Possible give/get packages

1. Hold the 12-month/no-index terms and offer a price near the supplier's current €5.86 in exchange for confirmation that no index adjustment applies during the term; the replay later confirms acceptance at €5.85, but does not show the term being traded.
2. Hypothesis: ask whether a transparent index clause with a cap/floor could exchange for a lower base price. The supplier did not propose this trade; do not add a clause without buyer approval.

### What the agent should ask next

> We note the AS-14404, LCI-C and PPI-C2431 references. Please confirm that the agreed 12-month price of €5.85 has no index adjustment for the contract term. If you need an adjustment mechanism, please propose the index and bounds separately.

**Tuning examples:** give Jonas a case where explicit index claims are evidence, but a price-rigidity state should not be inferred because the supplier continues to concede. Give Stefan a test ensuring the rationale cites the indices without turning them into an unsupported claim that the supplier requires an index clause.

## Highest-impact pattern for Stefan

P10 shows the biggest policy issue: the buyer repeated an unchanged request for cost breakdown after refusal, did not incorporate the supplier's stated 54-day constraint, and the replay has a mismatch between structured terms and the supplier's prose. Add a response-parsing/clarification step before repricing. Across P01 and P08, stop spending rounds when a final price repeats or the supplier accepts; compare total deal cost to the alternative before recommending acceptance.
