# Slavs and an Ottoman

Buyer-agent project for the Tacto Negotiation Arena. The repository includes the arena's Python starter kit, case data, and brief. The upstream kit snapshot is from `tacto-ai/negotiation-arena-kit` commit `1b5516bb95ef28e37f69aa446dc62168864bca53`.

## Negotiator MVP components

- [MVP evaluator](MVP_EVALUATOR.md): deterministic evaluation of a proposed supplier deal using case and buyer data.
- [MVP intelligence](MVP_INTELLIGENCE.md): supplier-only normalization and traceable context built from live supplier messages, PDFs, and CSVs, including explicit-statement profile rules.
- [Package generator](negotiator/packages.py): deterministic selection of up to three valid, buyer-efficient packages; [package policy](negotiator/package_policy.py) derives a conservative price ladder and adds supported cash/capacity give-gets.
- [Unified agent](arena_kit/agents/unified.py): connects live supplier evidence to buyer-costed package selection and reservation-aware multi-round decisions.
- [Supplier CSV extraction](arena_kit/quote_extract.py): source-preserving CSV parsing, with an option to pass parsed rows into the intelligence component.

## Practice findings and MVP gate

The latest full-ten benchmark and three random follow-ups are in
[MVP_FULL_SUITE_REPORT.md](MVP_FULL_SUITE_REPORT.md), with its
[execution/reflection plan](MVP_FULL_SUITE_PLAN.md). Full-ten mean: **50.30/100**.
The follow-ups averaged **39.02**, versus **38.44** for the same three earlier cases.
All 13 deals were valid, but the full benchmark recorded five idle-RFQ timeouts
and two hidden-relationship-cost discrepancies. The latest changes add bounded
dialogue recovery, prior quote renewal and authoritative pre-close state refresh;
they do not solve independent per-thread scheduling or unknown supplier economics.
The plain-language graphical report is `output/pdf/system-and-13-run-review.pdf`.

The preceding review is in [MVP_ROUND3_REPORT.md](MVP_ROUND3_REPORT.md) with its
[round-three plan](MVP_ROUND3_PLAN.md). It selectively applies Jonas's
[core-characteristics reference](MVP_CORE_CHARACTERISTICS.md) without merging:
one selected proposal, no-giveback checks, whole-package progress, bounded
response trades and anchored stopping. Supplier motives still require evidence;
late exploratory trades do not create profile traits. Numerical supplier-claim
softening now defaults to zero and remains explicitly configurable up to two
percentage points. Arena's hidden relationship cost may differ from our model;
completed runs report that difference rather than infer supplier economics.

The prior review is in [MVP_ROUND2_REPORT.md](MVP_ROUND2_REPORT.md)
with its [round-two plan](MVP_ROUND2_PLAN.md). It covers grader-compatible evidence,
bounded response trades and current structured supplier alternatives. All nine
hosted deals were valid, but overall score improvement is not demonstrated.
The previous round is in [MVP_ITERATION_REPORT.md](MVP_ITERATION_REPORT.md)
with its [iteration plan](MVP_ITERATION_PLAN.md). The earlier implementation and
validation are documented in [MVP_VALIDATION_REPORT.md](MVP_VALIDATION_REPORT.md); the execution checklist is in
[MVP_COMPLETION_PLAN.md](MVP_COMPLETION_PLAN.md). The current unified path supports
supplier-authored archive documents, sourced cash/capacity/quality trades,
distinct package choices, and concurrent supplier requests within an RFQ. The
quality trade requires a concrete supplier ppm guarantee; a generic quality
statement cannot authorize an invented target.

## Run the final

The unified agent's standard opening discount is 15%, with buyer must-haves and reservation-cost
checks still applied to every package. The 20% and adaptive opening experiments are opt-in and
remain off by default.

Set `ARENA_URL` and `ARENA_API_KEY` in `.env` (names only; never commit the file), then install the
locked dependencies with `uv sync`. After the organizers publish the Sunday data at 08:00, run
`uv run arena data` to unpack it under `data/`. Unified reads that archive when explicitly started
with `--data data`, or when `ARENA_DATA=data` is set.

```bash
uv run arena run --set final --agent unified --parallel 10 --waves 5 -v
```

For unattended restarts, use `scripts/run_final.sh`; it waits for five waves, resumes open sessions
after a crash, and appends logs under the ignored `logs/` directory. Optional behavior is off by
default: `--rfq-keepalive` holds qualifying idle RFQ threads, `SUPPLIER_ECONOMICS=1` includes
fact-based supplier relationship cost, and `SUPPLIER_ARCHIVE_EVIDENCE=1` loads archived
release letters/news without passing `--data`. Fact-based relationship costs are not calibrated
closely to saved P02/P03 Arena costs, so leave that flag off for the Live Final unless the team
validates the cost-fact semantics first. `UNIFIED_PROACTIVE_PRICE_EVIDENCE=1` cites qualifying
same-part price history in the first counter; it is off by default, and the local scripted suppliers
do not test whether this argument changes a real supplier's response.

Approach: prepare each case from its permitted data, read the supplier's current offer and
evidence, compare complete packages against buyer requirements and reservation cost, then accept
the best valid standing offer or walk away before the wave deadline.

```bash
# Include relevant supplier-authored letters from the package and Sunday release.
.venv/bin/python -m arena_kit.cli play case:P01 --agent unified --data data

# Repeatable local comparison; choose a fresh output directory for each run.
.venv/bin/python -m scripts.validate_mvp --mode local --out output/validation/local-new

# Consumes exactly three practice sessions, randomly selected before any session opens.
.venv/bin/python -m scripts.validate_mvp --mode hosted --out output/validation/hosted-new

# Consumes exactly ten sessions, one per hosted practice case, without replacements.
.venv/bin/python -m scripts.validate_mvp --mode hosted --selection all --out output/validation/full-new

# Start before the final begins; this waits for its five waves.
.venv/bin/python -m arena_kit.cli run --set final --agent unified --data data --parallel 10
```

Validation stores the selection seed, source fingerprint, actual transcripts,
decisions, scores, replay links and contract audits under the ignored
`output/validation/` directory. These files contain no copied environment keys.
The CLI's legacy default remains `supplier`; the Live Final command above explicitly selects
`unified`, while `supplier`, `packages`, `advanced`, `naive`, and `llm` remain runnable comparisons.

[Ahmet's replay findings](brief/replay-findings-tuning.md) cover hosted P10, P01, and P08
negotiations. The `unified` agent uses those lessons to avoid repeating a refused cost-breakdown
request and to seek clarification when a supplier explicitly rejects the lead time in its own
standing sheet. It keeps that conflict open until the supplier confirms a feasible matching term.
Outbound package messages list the actual term-sheet options and describe a profile-based trade
only when the sent package really changes the supplier-favourable term.

[Georgi's quality gate](QUALITY_GATE.md) and [score log](PRACTICE_SCORE_LOG.md) are a historical
review of worktree `b56b7ff+dirty`. Their local scores belong to `StrategicAgent`, which is not
present in this checkout; they are not scores for `unified`. The LLM factual-claim restriction in
that review still applies. Keep `unified` selectable with `--agent unified` until current hosted
practice replays demonstrate the MVP gate in [TODO.md](TODO.md).

## Supplier-only input policy

The supplier parser and intelligence component use only supplier-uploaded files and
identities supplied by the caller from the live thread. Known bundled `data/data/`
CSV sources are rejected. A filename cannot establish provenance; callers must
supply genuine supplier data. The deal evaluator remains a separate MVP that reads
case and buyer data; it is not used by supplier evidence extraction.

Unified optionally uses a separate archive adapter through `--data`. That adapter
accepts only dated supplier-authored emails/letters whose supplier and part scope
match the case. It rejects buyer-authored meeting notes, unrelated suppliers and
future documents. This does not relax the supplier CSV parser's input policy.

## Run locally (offline)

The CSV extractor and supplier intelligence path need only Python's standard
library. Explicit supplier input is required; there is no demo-data fallback.
Run commands from this repository's root.

```bash
# Extract rows and build auditable supplier context in one step
python -m arena_kit.quote_extract supplier_quote.csv --context --supplier-id sup:from-live-thread > supplier_context.json

# If the upload contains multiple parts, the parser emits a context per part.
# Scope a single-part attachment explicitly when its rows have no part IDs:
python -m arena_kit.quote_extract supplier_quote.csv --context --supplier-id sup:from-live-thread --part-id part:from-live-thread > supplier_context.json
```

```python
from arena_kit.quote_extract import extract_supplier_context

result = extract_supplier_context(["supplier_quote.csv"], supplier_id="sup:from-live-thread")
```

The resulting JSON contains the unchanged extracted `records` plus one or more
`contexts`. Each context includes normalized evidence, quote history with source
references, evidence-backed supplier profile fields, and evidence gaps. Narrow
explicit-statement rules can mark a profile dimension `likely`; missing, ambiguous,
or conflicting evidence stays `unknown`. Quote history alone never establishes a trait.

During Arena sessions the runner parses incoming supplier CSV attachments into
`csv_records` and reads PDFs as text. The supplier agent combines these with each
supplier offer and explicit index/cost-share claims into one sourced context. The
context retains quote terms and history, normalized claims, and source references to
the originating attachment, CSV row, or supplier message.
The PDF parser handles text PDFs directly. For scanned PDFs, install the optional
`ocr` extra (`pip install -e '.[ocr]'`) and the Tesseract and Poppler system tools;
the live runner records an explanatory `pdf_parse_error` if a scan cannot be read.

## Run the supplier-only agent

The Arena-compatible `SupplierContextAgent` ignores the case argument and uses only
live supplier messages, offers, and parsed supplier attachments. It carries explicit
commercial values from supplier evidence into counteroffers, uses same-context
supplier quote history as a price anchor when comparable, and moves its counter by a
configurable share of each supplier concession. Supplier-claimed index movement and
cost share can soften or strengthen the opening discount, bounded to 2 percentage
points by default. This uses the supplier's assertion as a negotiation input; it does
not verify that claim. It also cites the supplier's
highest-priority evidence in its rationale. It accepts offers that meet its target;
when a supplier makes a final offer or the agent runs out of moves, it accepts the
best complete standing offer as a last resort rather than walking away and scoring
zero. It walks away only when no complete offer can be accepted. This supplier-only
baseline does not use the buyer-side profile give/get policy; that integration is in
the selectable `unified` agent. Neither path infers buyer budgets or supplier traits
that the evidence does not establish.

```bash
# Local scripted Arena simulation
python -m arena_kit.cli simulate case:S01 --agent supplier --out negotiation.json -v

# Hosted Arena practice session; .env needs ARENA_URL and the team's ARENA_API_KEY
python -m arena_kit.cli play case:P01 --agent supplier
```

The Arena runner still downloads the supplier attachments and sends the agent's
messages. A local simulation uses scripted supplier fixtures and is not a hosted
session.

## LLM-generated extraction priorities

`arena_kit/priority.py` ranks only the supplied information: 1 = direct commercial
evidence, 2 = operational leverage, 3 = background or unclear relevance. The LLM
must not add external estimates or benchmarks. Values and sources stay intact.

```python
from arena_kit.quote_extract import extract

records = extract(["supplier_quote.csv"], priority="llm")
```

The extractor CLI loads `.env`. Configure `LLM_PROVIDER`, `LLM_MODEL`, and either
`LLM_BASE_URL` / `LLM_API_KEY` for a compatible endpoint, or `ANTHROPIC_API_KEY`
for Anthropic (requires its optional SDK). A compatible local model server can
also be used. Python function calls read the environment directly.

```bash
python -m arena_kit.quote_extract supplier_quote.csv --priority llm > supplier_information.json
```

`prioritize(records, complete=my_llm_call, batch_size=25)` supports custom model
callbacks. Invalid or incomplete responses raise errors. Heuristic extraction
and supplier-context generation do not make model calls.

## Deal evaluator status

`negotiator.evaluator.evaluate_deal()` evaluates one proposed term sheet using the
arena case's buyer costs, must-haves, and alternative. It is not a supplier-only
negotiation agent and is not called by the CSV parser or the existing `play()` loop.
Do not use it as a supplier-only decision policy without first changing its inputs
and cost model.

## Try the deterministic package agent

The case-aware package agent derives a bounded 5% / 3% / 1% price ladder from a supplier's
standing offer, evaluates every allowed term combination by buyer cost, and sends up to three
valid packages. It adds reciprocal payment or commitment terms only when supplied with an explicit
supplier profile; unknown supplier traits remain unknown.

```bash
python -m arena_kit.cli simulate case:S01 --agent packages -v
```

## Run local negotiations with the provided tests

The `sim` fixture in `tests/conftest.py` starts a simulator on a temporary
localhost port. The tests register a local team and negotiate against scripted
suppliers. They need no Tacto key or LLM credentials. The scripted LLM in the
tests returns fixed responses rather than contacting a model provider.

```bash
# A project-local environment is already set up; activate it
source .venv/bin/activate

# Full negotiations with both example agents on the first three simulator cases
python -m pytest 'tests/test_sim.py::test_both_agents_play_unchanged[sim]' -v

# Run the local simulator and kit checks, excluding hosted tests explicitly
env -u ARENA_TEST_URL -u ARENA_TEST_KEY python -m pytest tests/test_sim.py tests/test_kit.py -q -k 'not hosted'
```

For a fresh checkout, create the environment and install the test dependencies
first:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install httpx openpyxl pypdf fastapi uvicorn pytest
```

`test_both_agents_play_unchanged` exercises the naive and scripted LLM agents. The
localhost simulator implements the negotiation API and scripted supplier replies; it does not
reproduce the hosted suppliers' strategy.

## Run the hosted baseline agent

Requires Python 3.12 and `uv`.

```bash
uv sync --all-extras
cp .env.example .env   # then set ARENA_API_KEY and any LLM credentials
uv run arena me
uv run arena play case:P01
```

`arena me` checks the arena key and quota. `arena play` starts a hosted practice session and uses one session from the team's rolling 24-hour quota. The CLI's default is the supplier-only `SupplierContextAgent`; the team's Live Final command explicitly chooses `--agent unified`.

To download the data package for the LLM agent and local data tools:

```bash
uv run arena data
uv run arena play case:P01 --agent llm
```

Read [the challenge brief](brief/brief.md), [API docs](brief/api.md), and [starter-kit guide](STARTER_KIT.md). The case data and supplier documents are in `data/`; `data/README.md` explains the CSV, SQLite database, facts, and document IDs.

## Develop the agent

The default strategy lives in `arena_kit/agents/naive.py`. Its `decide(case, threads)` method returns a supplier ID and a message. The runner and HTTP client handle sessions, email messages, replies, and closing actions. The LLM example is in `arena_kit/agents/llm.py`.

## Entire session tracking

This repository uses [Entire](https://entire.io/) to save coding-agent session context alongside Git history. Contributors using Codex can install and enable the Entire CLI from the repository:

```sh
curl -fsSL https://entire.io/install.sh | bash
entire enable
```

Verify the setup with:

```sh
entire status
entire doctor
```

After Codex makes a real file change and that change is committed, Entire should push a checkpoint ref. Review the repository's hooks with `/hooks` before trusting them.
