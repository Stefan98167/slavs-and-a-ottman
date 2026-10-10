# Slavs and an Ottoman

Buyer-agent project for the Tacto Negotiation Arena. The repository includes the arena's Python starter kit, case data, and brief. The upstream kit snapshot is from `tacto-ai/negotiation-arena-kit` commit `1b5516bb95ef28e37f69aa446dc62168864bca53`.

## Negotiator MVP components

- [MVP evaluator](MVP_EVALUATOR.md): deterministic evaluation of a proposed supplier deal using case and buyer data.
- [MVP intelligence](MVP_INTELLIGENCE.md): supplier-only normalization and traceable context built directly from supplier CSV extracts.
- [Supplier CSV extraction](arena_kit/quote_extract.py): source-preserving CSV parsing, with an option to pass parsed rows into the intelligence component.

## Supplier-only input policy

The supplier parser and intelligence component use only supplier-uploaded files and
identities supplied by the caller from the live thread. Known bundled `data/data/`
CSV sources are rejected. A filename cannot establish provenance; callers must
supply genuine supplier data. The deal evaluator remains a separate MVP that reads
case and buyer data; it is not used by supplier evidence extraction.

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
references, supplier profile fields, and evidence gaps. It does not invent buyer
targets or supplier traits from quote history.

During Arena sessions the runner parses incoming supplier CSV attachments and adds
`csv_records` and `supplier_context` to that supplier's thread. The supplier agent
reads those fields alongside the supplier's live offers.

## Run the supplier-only agent

The Arena-compatible `SupplierContextAgent` ignores the case argument and uses only
live supplier messages, offers, and parsed supplier attachments. It carries explicit
commercial values from supplier evidence into counteroffers, uses same-context
supplier quote history as a price anchor when comparable, and moves its counter by a
configurable share of each supplier concession. It also cites the supplier's
highest-priority evidence in its rationale. It accepts offers that meet its target;
when a supplier makes a final offer or the agent runs out of moves, it accepts the
best complete standing offer as a last resort rather than walking away and scoring
zero. It walks away only when no complete offer can be accepted. It does not infer
buyer budgets or supplier traits that the input does not establish; profile dimensions
in the current context remain unknown.

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

`arena me` checks the arena key and quota. `arena play` starts a hosted practice session and uses one session from the team's rolling 24-hour quota. The default agent is the supplier-only `SupplierContextAgent`; pass `--agent naive` or `--agent llm` only to run a legacy comparison agent.

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
