# Slavs and an Ottoman

Buyer-agent project for the Tacto Negotiation Arena. The repository includes the arena's Python starter kit, case data, and brief. The upstream kit snapshot is from `tacto-ai/negotiation-arena-kit` commit `1b5516bb95ef28e37f69aa446dc62168864bca53`.

## Negotiator MVP components

- [MVP evaluator](MVP_EVALUATOR.md): deterministic evaluation of a proposed supplier deal.
- [MVP intelligence](MVP_INTELLIGENCE.md): ingestion and traceable supplier context from the data-analysis team's JSON evidence output.

## Run the baseline agent

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
