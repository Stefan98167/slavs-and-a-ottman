"""Open cases are refreshed and safely closed after agent or close-action failures."""

import httpx

from arena_kit.client import ArenaClient, ArenaError
from arena_kit.play import RemoteTable, closing_move, play
from arena_kit.sim import SimTable


class RefreshableSimTable(SimTable):
    def __init__(self):
        super().__init__()
        self.refresh_count = 0

    def refresh_threads(self, previous):
        self.refresh_count += 1
        session = self.sim.sessions[self.session_id]
        return {sid: [dict(message) for message in thread["messages"]]
                for sid, thread in session["threads"].items()}


def test_decision_exception_refreshes_and_closes_case():
    class BrokenAgent:
        def decide(self, case, threads):
            raise RuntimeError("deliberate decision failure")

    table = RefreshableSimTable()
    result = play(table, "case:S01", BrokenAgent())
    assert table.refresh_count == 1
    assert result["ended"] and isinstance(result["deal"], bool)


def test_stale_accept_422_refreshes_and_retries_current_offer():
    class StaleOnceTable(RefreshableSimTable):
        def __init__(self):
            super().__init__()
            self.close_calls = 0

        def close(self, supplier_id, message):
            self.close_calls += 1
            if self.close_calls == 1:
                raise ArenaError(422, "not a standing offer in this session")
            return super().close(supplier_id, message)

    class StaleAgent:
        def __init__(self):
            self.refreshed_offer_id = None

        def decide(self, case, threads):
            sid = next(iter(threads))
            return {"supplier_id": sid, "message": {"action": {"type": "accept", "term_sheet_id": "offer:stale"}}}

        def close(self, case, threads):
            decision = closing_move(case, threads)
            self.refreshed_offer_id = decision["message"].get("action", {}).get("term_sheet_id")
            return decision

    table, agent = StaleOnceTable(), StaleAgent()
    result = play(table, "case:S01", agent)
    assert table.refresh_count == 1
    assert table.close_calls == 2
    assert agent.refreshed_offer_id != "offer:stale"
    assert result["ended"] and isinstance(result["deal"], bool)


def test_remote_table_resumes_final_duplicate_session():
    case = {"case_id": "case:S01", "buyer": {}, "suppliers": ["sup:1"]}
    opening = {"from": "supplier", "status": "open", "term_sheets": [
        {"term_sheet_id": "offer:1-1", "terms": {"unit_price": 10}},
    ], "attachments": []}
    calls = []

    def handler(request):
        calls.append((request.method, request.url.path))
        if request.method == "POST" and request.url.path.endswith("/sessions"):
            return httpx.Response(409, json={"detail": "one session per case in the final: sim-final"})
        if request.method == "GET" and request.url.path.endswith("/sessions/sim-final"):
            return httpx.Response(200, json={"status": "open", "threads": {"sup:1": {"status": "open"}}})
        if request.method == "GET" and request.url.path.endswith("/threads/sup:1"):
            return httpx.Response(200, json={"supplier_id": "sup:1", "offer_id": "offer:1-1",
                                             "status": "open", "messages": [opening], "timeouts": []})
        raise AssertionError(f"unexpected request {request.method} {request.url}")

    client = ArenaClient("https://arena.invalid", transport=httpx.MockTransport(handler), retries=0)
    table = RemoteTable(client, case)
    resumed_case, threads = table.open(case["case_id"])
    assert resumed_case == case and threads["sup:1"][0]["term_sheets"][0]["term_sheet_id"] == "offer:1-1"
    assert calls == [
        ("POST", "/v1/sessions"),
        ("GET", "/v1/sessions/sim-final"),
        ("GET", "/v1/sessions/sim-final/threads/sup:1"),
    ]


def test_restart_resumes_and_closes_existing_final_session():
    case = {"case_id": "case:S01", "buyer": {}, "suppliers": ["sup:1"]}
    opening = {"from": "supplier", "status": "agreed", "term_sheets": [
        {"term_sheet_id": "offer:1-1", "terms": {"unit_price": 10}},
    ], "attachments": []}
    calls = []

    def handler(request):
        calls.append((request.method, request.url.path))
        if request.method == "POST" and request.url.path.endswith("/sessions"):
            return httpx.Response(409, json={"detail": "one session per case in the final: sim-final"})
        if request.method == "GET" and request.url.path.endswith("/sessions/sim-final"):
            return httpx.Response(200, json={"status": "open", "threads": {"sup:1": {"status": "agreed"}}})
        if request.method == "GET" and request.url.path.endswith("/threads/sup:1"):
            return httpx.Response(200, json={"supplier_id": "sup:1", "offer_id": "offer:1-1",
                                             "status": "agreed", "messages": [opening], "timeouts": []})
        if request.method == "POST" and request.url.path.endswith("/threads/sup:1/messages"):
            return httpx.Response(200, json={"result": {"ended": True, "deal": True, "supplier_id": "sup:1"}})
        raise AssertionError(f"unexpected request {request.method} {request.url}")

    client = ArenaClient("https://arena.invalid", transport=httpx.MockTransport(handler), retries=0)

    class Buyer:
        def decide(self, case, threads):
            return {"supplier_id": "sup:1", "message": {
                "action": {"type": "accept", "term_sheet_id": "offer:1-1"},
            }}

    result = play(RemoteTable(client, case), case["case_id"], Buyer())
    assert result == {"ended": True, "deal": True, "supplier_id": "sup:1"}
    assert calls.count(("POST", "/v1/sessions")) == 1
    assert calls.count(("POST", "/v1/sessions/sim-final/threads/sup:1/messages")) == 1
    assert ("GET", "/v1/sessions/sim-final") in calls
    assert ("GET", "/v1/sessions/sim-final/threads/sup:1") in calls
