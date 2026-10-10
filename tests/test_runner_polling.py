"""The final-wave loop retries temporary listing failures instead of abandoning later waves."""

import importlib

import httpx

from arena_kit.client import ArenaError
from arena_kit.play import play_waves


def test_wave_poll_survives_server_and_transport_failures(monkeypatch):
    play_module = importlib.import_module("arena_kit.play")
    case = {"case_id": "case:S01", "wave": 1, "theme": "test", "open": True, "seconds_left": 480}

    class Listing:
        def __init__(self):
            self.calls = 0

        def cases(self, set_):
            self.calls += 1
            if self.calls == 1:
                raise ArenaError(503, "temporary unavailable")
            if self.calls == 2:
                raise httpx.ConnectError("Wi-Fi dropped")
            if self.calls == 3:
                return [case]
            return [{**case, "open": False, "seconds_left": 0}]

    client, started = Listing(), []
    monkeypatch.setattr(
        play_module, "play", lambda table, case_id, agent, deadline: started.append(case_id) or {"ended": True}
    )
    results = play_waves(client, lambda: object(), waves=1, parallel=1, poll=0)
    assert client.calls == 4
    assert started == ["case:S01"]
    assert results["case:S01"] == {"ended": True}
