"""HTTP waits and retries respect the per-wave deadline."""

import time

import httpx
import pytest

from arena_kit.agents import UnifiedAgent
from arena_kit.client import ArenaClient
from arena_kit.play import play
from arena_kit.sim import SimTable


def test_http_timeouts_and_retries_fit_inside_deadline_budget():
    timeouts = []

    def handler(request):
        timeouts.append(request.extensions["timeout"])
        if len(timeouts) == 1:
            return httpx.Response(503, headers={"Retry-After": "0"}, json={"detail": "retry"})
        return httpx.Response(200, json=[])

    client = ArenaClient("https://arena.invalid", transport=httpx.MockTransport(handler), retries=1, rate=1000)
    cap = time.time() + 8
    with client.request_deadline(cap):
        assert client.cases("final") == []

    assert len(timeouts) == 2
    max_phase = max(timeout[phase] for timeout in timeouts for phase in ("connect", "read", "write", "pool"))
    assert max_phase < client.timeout
    assert 4 * len(timeouts) * max_phase + 5 <= 8


def test_expired_deadline_does_not_start_an_http_request():
    calls = []
    client = ArenaClient(
        "https://arena.invalid",
        transport=httpx.MockTransport(lambda request: calls.append(request) or httpx.Response(200, json=[])),
        retries=0,
        rate=1000,
    )
    with client.request_deadline(time.time() - 1), pytest.raises(httpx.TimeoutException):
        client.cases("final")
    assert calls == []


def test_wave_cap_closes_unified_agent_without_an_extra_round():
    table, agent = SimTable(), UnifiedAgent()
    result = play(table, "case:S01", agent, deadline=time.time())
    session = table.sim.sessions[table.session_id]
    assert result["ended"]
    assert sum(message.get("from") == "buyer" for thread in session["threads"].values()
               for message in thread["messages"]) == 0
    assert agent.decision_history[-1]["action"] in {"accept", "walk_away"}
