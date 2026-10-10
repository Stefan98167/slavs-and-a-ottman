from threading import Barrier

import pytest
from test_kit import CASE
from test_unified import supplier

from arena_kit.agents.unified import UnifiedAgent
from arena_kit.client import ArenaError
from arena_kit.play import _send_batch, play


class TwoSupplierTable:
    """Each supplier needs its competitor's request to be in flight before replying."""
    def __init__(self):
        self.barrier = Barrier(2, timeout=2)
        self.sent = []
        self.closed = []

    def open(self, case_id):
        return CASE, {"sup:A": [supplier("open", 42)], "sup:B": [supplier("open", 41)]}

    def send(self, sid, message):
        self.sent.append(sid)
        self.barrier.wait()
        return supplier("final_offer", 39.5 if sid == "sup:A" else 40)

    def close(self, sid, message):
        self.closed.append(sid)
        return {"deal": True, "supplier_id": sid}


def test_rfq_sends_concurrently_and_closes_once_on_best_received_offer():
    table = TwoSupplierTable()
    result = play(table, CASE["case_id"], UnifiedAgent())
    assert result == {"deal": True, "supplier_id": "sup:A"}
    assert set(table.sent) == {"sup:A", "sup:B"}
    assert table.closed == ["sup:A"]


def test_batch_resumes_a_409_without_resending_a_move():
    class Table:
        def send(self, sid, message):
            raise ArenaError(409, "case ended")

        def missed(self, sid, error):
            return {"result": {"deal": False}}

    items = [{"supplier_id": "sup:A", "message": {"body": "hello"}}]
    results = list(_send_batch(Table(), items))
    assert results[0][2] == {"result": {"deal": False}}


def test_batch_refuses_duplicate_supplier_sends_and_closing_actions():
    item = {"supplier_id": "sup:A", "message": {"body": "hello"}}
    with pytest.raises(ValueError):
        list(_send_batch(None, [item, item]))
    with pytest.raises(ValueError):
        list(_send_batch(None, [{"supplier_id": "sup:A", "message": {"action": {"type": "walk_away"}}}]))
