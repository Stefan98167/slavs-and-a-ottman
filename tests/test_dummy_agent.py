import json
from copy import deepcopy
from unittest.mock import patch

import pytest

from arena_kit.agents import DummyAgent
from arena_kit.cli import agent_factory, main
from arena_kit.client import ArenaClient
from arena_kit.play import RemoteTable, fetch_documents, play
from arena_kit.sim import SimTable


def evidence(priority=1):
    return {"Information": {"supplier_id": "sup:70270", "part_id": "part:320050",
                            "note": "Please explain the proposed price change"},
            "Source": "supplier_quote.csv:2", "Priority (Argument wise)": priority}


@pytest.mark.parametrize("case_id", ["case:S01", "case:S02", "case:S03"])
def test_dummy_negotiates_in_process(case_id):
    agent, table = DummyAgent([evidence()]), SimTable()
    with patch("socket.socket", side_effect=AssertionError("Network access attempted")), patch(
        "arena_kit.agents.llm.llm_from_env", side_effect=AssertionError("LLM access attempted")
    ):
        result = play(table, case_id, agent)
    assert result["ended"] and result["deal"] and result["must_haves_ok"]
    assert 0 <= result["score"] <= 1
    assert len(agent.decision_history) > 1
    print(json.dumps({"case_id": case_id, "agent": "DummyAgent", "result": result}, indent=2))
    if case_id == "case:S01":
        first = agent.decision_history[0]
        assert first["evidence_count"] == 1
        assert first["decision"]["lead_argument"]["Source"] == "supplier_quote.csv:2"
        assert "Please explain the proposed price change" in first["message"]["body"]
    for item in agent.decision_history:
        for sheet in item["message"].get("term_sheets", []):
            assert set(sheet["terms"]) == set(table.sim.cases[case_id]["negotiable"])
    # The simulator keeps its own history, unaffected by play() appending locally.
    session = table.sim.sessions[table.session_id]
    messages = [m for t in session["threads"].values() for m in t["messages"] if m.get("from") == "buyer"]
    assert len(messages) == sum("action" not in item["message"] for item in agent.decision_history)


def test_dummy_agent_against_http_sim(sim):
    url, _, _ = sim
    key = ArenaClient(url).register("dummy-test", "sim")["api_key"]
    agent = DummyAgent([evidence()])
    result = play(RemoteTable(ArenaClient(url, key)), "case:S01", agent)
    assert result["ended"] and result["deal"]
    assert agent.decision_history[0]["decision"]["lead_argument"]["Source"] == "supplier_quote.csv:2"


def test_priority_selects_evidence_but_never_replaces_live_price():
    table = SimTable()
    case, threads = table.open("case:S01")
    for events in threads.values():
        for event in events:
            fetch_documents(table, event)
    important = evidence(2)
    historical = evidence(1)
    historical["Information"] = {**historical["Information"], "unit_price": "0.10", "note": "Historical quote"}
    historical["Source"] = "history.csv:3"
    unrelated = evidence(1)
    unrelated["Information"] = {**unrelated["Information"], "supplier_id": "sup:OTHER"}
    agent = DummyAgent([important, historical, unrelated])
    move = agent.decide(case, threads)
    assert move["message"]["term_sheets"][0]["terms"]["unit_price"] == 16.60
    assert move["message"]["term_sheets"][0]["terms"]["payment_days"] == 14
    decision = agent.decision_history[-1]
    assert decision["decision"]["Information"]["unit_price"] == 17.47
    assert decision["evidence_count"] == 2
    assert decision["decision"]["lead_argument"]["Source"] == "history.csv:3"
    agent.records[0]["Priority (Argument wise)"] = 1
    agent.records[1]["Priority (Argument wise)"] = 3
    agent.decide(case, threads)
    assert agent.decision_history[-1]["decision"]["lead_argument"]["Source"] == "supplier_quote.csv:2"


def test_final_offer_above_supplier_derived_target_walks_away():
    table = SimTable()
    case, threads = table.open("case:S01")
    event = threads["sup:70270"][-1]
    event["status"] = "final_offer"
    assert DummyAgent().decide(case, threads)["message"]["action"]["type"] == "walk_away"


def test_case_data_is_never_read_even_at_deadline():
    class ForbiddenCase:
        def __getitem__(self, name):
            raise AssertionError(f"Case field read: {name}")

        def get(self, *args):
            raise AssertionError("Case read attempted")

    table = SimTable()
    _, threads = table.open("case:S01")
    for events in threads.values():
        for event in events:
            fetch_documents(table, event)
    agent = DummyAgent([evidence()])
    with patch("arena_kit.data.DataPackage", side_effect=AssertionError("Package access attempted")):
        move = agent.decide(ForbiddenCase(), threads)
        assert move["message"]["term_sheets"][0]["terms"] == {"unit_price": 16.60, "payment_days": 14}
        assert agent.close(ForbiddenCase(), threads)["message"]["action"]["type"] == "walk_away"


def test_missing_supplier_terms_are_requested_not_filled_from_case():
    table = SimTable()
    case, threads = table.open("case:S01")
    # Attachment text has not been supplied to the agent yet.
    move = DummyAgent().decide(case, threads)
    assert move["message"]["term_sheets"] == []
    assert "payment_days" in move["message"]["body"]


def test_no_part_identity_is_inferred_from_case():
    table = SimTable()
    case, threads = table.open("case:S01")
    first = evidence()
    second = deepcopy(first)
    second["Information"]["part_id"] = "part:OTHER"
    agent = DummyAgent([first, second])
    agent.decide(case, threads)
    assert agent.decision_history[-1]["evidence_count"] == 0
    assert agent.decision_history[-1]["decision"]["Information"]["part_id"] is None


def test_bundled_evidence_is_rejected():
    record = evidence()
    record["Source"] = "data/data/quotes.csv:2"
    with pytest.raises(ValueError, match="Bundled"):
        DummyAgent([record])


def test_runner_deadline_does_not_use_buyer_case_closing_rules():
    import importlib

    runner = importlib.import_module("arena_kit.play")
    with patch.object(runner, "closing_move", side_effect=AssertionError("Buyer facts used")):
        result = play(SimTable(), "case:S01", DummyAgent(), deadline=0.01)
    assert result["ended"] and not result["deal"]


def test_factory_and_cli_simulate_without_arena_client(tmp_path, capsys):
    path = tmp_path / "evidence.json"
    path.write_text(json.dumps([evidence()]))
    assert isinstance(agent_factory("dummy", None, path)(), DummyAgent)
    output = tmp_path / "negotiation.json"
    with patch("arena_kit.cli.load_env"), patch("arena_kit.cli.ArenaClient", side_effect=AssertionError("API used")):
        main(["simulate", "case:S01", "--evidence", str(path), "--out", str(output)])
    assert json.loads(capsys.readouterr().out)["deal"]
    replay = json.loads(output.read_text())
    assert replay["result"]["deal"] and replay["threads"] and replay["decisions"]
    assert replay["decisions"][0]["decision"]["lead_argument"]["Source"] == "supplier_quote.csv:2"
