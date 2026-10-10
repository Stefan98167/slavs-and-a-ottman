"""The optional RFQ keepalive repeats only an existing buyer term sheet."""

import importlib


def test_keepalive_runs_concurrently_and_repeats_the_last_terms(monkeypatch):
    play_module = importlib.import_module("arena_kit.play")
    case = {"negotiable": ["unit_price", "payment_days"]}
    repeated_terms = {"unit_price": 11.25, "payment_days": 30}
    threads = {
        "sup:main": [{"from": "supplier", "status": "open", "term_sheets": []}],
        "sup:idle": [
            {"from": "supplier", "status": "open", "term_sheets": []},
            {"from": "buyer", "term_sheets": [{"terms": repeated_terms}]},
            {"from": "supplier", "status": "agreed", "term_sheets": [
                {"term_sheet_id": "offer:idle", "terms": repeated_terms},
            ]},
        ],
    }

    class Table:
        refreshed = False

        def thread_age(self, supplier_id):
            return 40 if supplier_id == "sup:idle" else 5

        def refresh_threads(self, old):
            self.refreshed = True
            return old

    def acceptable(case, one_thread):
        sid = next(iter(one_thread))
        return {"supplier_id": sid, "message": {"action": {"type": "accept", "term_sheet_id": "offer:idle"}}}

    monkeypatch.setattr(play_module, "closing_move", acceptable)
    decision, refreshed = {"supplier_id": "sup:main", "message": {"body": "main move"}}, threads
    (moves, refreshed) = play_module._keepalive_decisions(Table(), case, refreshed, [decision])
    assert len(moves) == 2
    hold = moves[1]
    assert hold["supplier_id"] == "sup:idle"
    assert hold["message"]["term_sheets"] == [{"terms": repeated_terms}]
    assert "still reviewing" in hold["message"]["body"]


def test_s02_latency_probe_flag_does_not_reduce_score_or_increase_timeouts():
    from scripts.latency_probe import probe

    ordinary = probe("unified", "case:S02", 60, 480)
    protected = probe("unified", "case:S02", 60, 480, rfq_keepalive=True)
    assert protected["score"] >= ordinary["score"]
    assert sum(t["timeouts"] for t in protected["threads"].values()) <= sum(
        t["timeouts"] for t in ordinary["threads"].values()
    )
    assert protected["end_reason"] == ordinary["end_reason"] == "accepted"
