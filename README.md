# Slavs and an Ottoman

Buyer-agent project for the Tacto Negotiation Arena. The repository includes the arena's Python starter kit, case data, and brief. The upstream kit snapshot is from `tacto-ai/negotiation-arena-kit` commit `1b5516bb95ef28e37f69aa446dc62168864bca53`.

## Negotiator MVP components

- [MVP evaluator](MVP_EVALUATOR.md): deterministic evaluation of a proposed supplier deal.
- [MVP intelligence](MVP_INTELLIGENCE.md): ingestion and traceable supplier context from the data-analysis team's JSON evidence output.
- [Supplier CSV extraction](arena_kit/quote_extract.py): source-preserving conversion of supplier attachments into the shared evidence JSON format; optional priority ranking is available to the data-preparation team.

## Supplier-only input policy

The dummy uses only supplier-uploaded CSV/JSON and the live supplier's messages
and attachments. It does not read buyer baselines, case facts, market indices,
alternatives, company history or the buyer cost model. Known bundled `data/data/`
sources are rejected. This also rejects the old `output.json` and `output_llm.json`
generated from that directory. Extract new JSON from the supplier's actual files.
A filename cannot establish provenance; callers must supply genuine supplier data.

## Run locally (offline)

The CSV extractor and static dummy decision engine need only Python's standard
library. Explicit supplier input is required; there is no demo-data fallback.
Run commands from this repository's root (`slavs-and-a-ottman`).

```bash
# The file must be an actual supplier upload
python -m arena_kit.quote_extract supplier_quote.csv > supplier_information.json
python -m arena_kit.local --json supplier_information.json --out decisions.json

# Or extract and decide in one step
python -m arena_kit.local supplier_quote.csv --out decisions.json
```

```python
from arena_kit.local import run_local

result = run_local(["supplier_quote.csv"])
```

The static engine suggests 5% below each supplier quote. It orders decisions and
supporting arguments by priority, selects a `lead_argument`, and produces a
suggested `message`. Missing prices produce clarification requests. Records
share arguments only with matching explicit supplier and part IDs.

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
and the local decision runner do not make model calls.

## Negotiate with the supplier-only dummy

`DummyAgent` implements the existing `decide(case, threads)` interface but never
reads `case`. The existing `play()` loop and simulator are reused. Its policy
target is 5% below the supplier's opening price, with quoted standard terms kept
as supplied. It requests missing terms, accepts prices within its target, and
walks away if a final offer remains above it. Discount and maximum rounds are
strategy settings, not external factual inputs. Part identity must come from
the supplier offer or be unambiguous in that supplier's supplied records.

```bash
# Only the simulated supplier's live offers and attachments
python -m arena_kit.cli simulate case:S01 --out negotiation_supplier_only.json -v

# Add an actual supplier's extracted evidence
python -m arena_kit.cli simulate case:S01 --evidence supplier_information.json --out negotiation.json -v

python -m pytest tests/test_dummy_agent.py -v -s
```

The saved transcript contains supplier/buyer `threads`, per-round `decisions`,
the supplier-derived target source, priorities, and the messages actually sent.
The simulator uses case fixtures to generate supplier replies and calculate its
score; these fixture facts and evaluation costs are not inputs to the dummy.
This policy also applies to the dummy's deadline handler.

The HTTP runner supports `play ... --agent dummy --evidence supplier_information.json`
and uses `ARENA_URL`. Use `simulate` for a fully local run. The upstream naive and
LLM example agents remain as legacy comparison implementations; the supplier-only
policy described here applies to the dummy engine.

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

`test_both_agents_play_unchanged` exercises the naive and scripted LLM agents;
`tests/test_dummy_agent.py` exercises the integrated dummy. The localhost simulator
implements the negotiation API and scripted supplier replies; it does not
reproduce the hosted suppliers' strategy.

## Run the hosted baseline agent

Requires Python 3.12 and `uv`.

```bash
uv sync --all-extras
cp .env.example .env   # then set ARENA_API_KEY and any LLM credentials
uv run arena me
uv run arena play case:P01
```

`arena me` checks the arena key and quota. `arena play` starts a hosted practice session and uses one session from the team's rolling 24-hour quota. The default agent is the naive baseline in `arena_kit/agents/naive.py`.

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
