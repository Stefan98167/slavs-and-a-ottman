#!/usr/bin/env python3
"""Rehearse supplier reply latency against arena-sim without HTTP or Arena calls.

Example: python scripts/latency_probe.py unified case:S02 55 480
"""

import argparse
import importlib
import threading

from arena_kit.cli import agent_factory
from arena_kit.play import play
from arena_kit.sim import Sim, SimTable, load_cases


class FakeClock:
    def __init__(self, start=1_000_000.0):
        self.now = start
        self.lock = threading.Lock()

    def __call__(self):
        return self.time()

    def time(self):
        with self.lock:
            return self.now

    def monotonic(self):
        return self.time()

    def advance(self, seconds):
        with self.lock:
            self.now += seconds
            return self.now

    def sleep(self, seconds):
        self.advance(seconds)


class LatencyTable(SimTable):
    def __init__(self, sim, clock, reply_s):
        super().__init__(sim)
        self.clock, self.reply_s = clock, reply_s

    def send(self, supplier_id, message):
        reply = super().send(supplier_id, message)
        accepted = message.get("action", {}).get("type") == "accept" and reply.get("result", {}).get("deal")
        if "result" not in reply or accepted:
            with self.sim.lock:
                new_time = self.clock.advance(self.reply_s)
                self.sim.sessions[self.session_id]["threads"][supplier_id]["last_at"] = new_time
        return reply


def probe(agent_name, case_id, reply_s, cap_s):
    clock = FakeClock()
    sim = Sim(load_cases(), clock=clock, no_clock=False)
    table = LatencyTable(sim, clock, reply_s)
    agent = agent_factory(agent_name, None)()
    play_module = importlib.import_module("arena_kit.play")
    original_time = play_module.time
    play_module.time = clock
    started = clock.time()
    try:
        result = play(table, case_id, agent, deadline=started + cap_s)
    finally:
        play_module.time = original_time
    session = sim.sessions[table.session_id]
    return {
        "agent": agent_name,
        "case_id": case_id,
        "reply_s": reply_s,
        "wave_cap_s": cap_s,
        "elapsed_fake_s": round(clock.time() - started, 2),
        "deal": result.get("deal"),
        "end_reason": session.get("end_reason"),
        "score": round(100 * (result.get("score") or 0), 2),
        "threads": {
            supplier_id: {
                "buyer_messages": sum(message.get("from") == "buyer" for message in thread["messages"]),
                "timeouts": len(thread["late"]),
                "closed": thread["closed"],
            }
            for supplier_id, thread in session["threads"].items()
        },
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    parser.add_argument("agent", choices=["supplier", "packages", "advanced", "naive", "llm", "unified"])
    parser.add_argument("case_id")
    parser.add_argument("reply_s", type=float)
    parser.add_argument("cap_s", type=float)
    args = parser.parse_args(argv)
    import json

    print(json.dumps(probe(args.agent, args.case_id, args.reply_s, args.cap_s), indent=2))


if __name__ == "__main__":
    main()
