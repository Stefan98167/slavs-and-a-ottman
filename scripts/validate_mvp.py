"""Local comparisons, three random hosted runs, or the complete ten-case set.

Run from the repository root: python -m scripts.validate_mvp --mode local|hosted.
This script never changes strategy, selects replacements, or reads final feeds.
"""

import argparse
import hashlib
import json
import logging
import math
import os
import random
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from pathlib import Path

from arena_kit.cli import agent_factory, load_env
from arena_kit.client import ArenaClient
from arena_kit.cost import must_haves_ok
from arena_kit.data import DataPackage
from arena_kit.play import RemoteTable, hosted, play
from arena_kit.sim import Sim, SimTable, load_cases
from negotiator.evaluator import evaluate_deal

ROOT = Path(__file__).resolve().parents[1]


def source_version():
    digest = hashlib.sha256()
    files = sorted(p for folder in ("arena_kit", "negotiator", "scripts", "tests")
                   for p in (ROOT / folder).rglob("*") if p.suffix in {".py", ".json"})
    files.append(ROOT / "pyproject.toml")
    for path in files:
        digest.update(str(path.relative_to(ROOT)).encode() + b"\0" + path.read_bytes())
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    return {"head": head, "source_sha256": digest.hexdigest(), "working_tree": True}


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8")


def summarize_records(records):
    """Return a consistent score and safety summary for a validation batch."""
    scores = [(record.get("result") or {}).get("score") for record in records]
    scores = [score for score in scores
              if isinstance(score, (int, float)) and math.isfinite(score)]
    return {
        "case_count": len(records),
        "scored_cases": len(scores),
        "mean_score": sum(scores) / len(scores) if scores else None,
        "deals": sum(bool((record.get("result") or {}).get("deal")) for record in records),
        "ended_sessions": sum(bool((record.get("result") or {}).get("ended")) for record in records),
        "runner_errors": sum(bool(record.get("run_error") or record.get("recovery_error"))
                              for record in records),
        "audit_errors": sum(len(record.get("audit_errors") or []) for record in records),
        "timeouts": sum(sum((record.get("timeout_counts") or {}).values()) for record in records),
    }


def order_records(records):
    """Make saved parallel-run records stable regardless of completion order."""
    return sorted(records, key=lambda record: (str(record.get("case_id", "")),
                                               str(record.get("agent", ""))))


def audit_decisions(case, decisions):
    errors = []
    for index, decision in enumerate(decisions):
        msg = decision.get("message", {})
        sheets = msg.get("term_sheets") or []
        if len(sheets) > 3 or len(msg.get("body", "")) > 8000:
            errors.append(f"decision {index}: Arena size limit")
        standard = decision.get("supplier_standard_terms") or {}
        for sheet in sheets:
            terms = sheet["terms"]
            evaluated = evaluate_deal(case, terms, standard)
            if set(terms) != set(case["negotiable"]) or not evaluated["valid_for_negotiation"]:
                errors.append(f"decision {index}: invalid sheet")
            if evaluated["buyer"]["total_cost"] > decision.get("reservation_cost", float("inf")) + 0.01:
                errors.append(f"decision {index}: proposal exceeds reservation")
        if decision.get("action") == "accept":
            if decision["standing_total_cost"] > decision["reservation_cost"] + 0.01:
                errors.append(f"decision {index}: acceptance exceeds reservation")
            if not must_haves_ok(case, decision["accepted_terms"], standard):
                errors.append(f"decision {index}: accepted must-have violation")
        for trade in decision.get("trade_hypotheses", []):
            if not trade.get("evidence") or any(not e.get("id") or not e.get("source") for e in trade["evidence"]):
                errors.append(f"decision {index}: unsourced trade")
    return errors


def reconcile_cost(result, decisions):
    """Post-run observation only; never feeds hidden supplier economics to policy."""
    accepted = [decision for decision in decisions if decision.get("action") == "accept"]
    if not result or not result.get("deal") or not accepted:
        return None
    decision = accepted[-1]
    expected = decision.get("predicted_cost_breakdown") or {}
    actual = result.get("cost_breakdown") or {}
    return {"predicted": decision["standing_total_cost"], "actual": result["c_deal"],
            "difference": round(result["c_deal"] - decision["standing_total_cost"], 2),
            "component_differences": {key: round(value - expected.get(key, 0), 2)
                                      for key, value in actual.items()} if expected else None,
            "note": "Server cost is authoritative; missing supplier economics are not inferred."}


def select_cases(cases, seed, selection="random", case_id=None, count=3):
    eligible = sorted(hosted(cases), key=lambda case: case["case_id"])
    if len({case["case_id"] for case in eligible}) != len(eligible):
        raise ValueError("duplicate eligible case IDs")
    if case_id is not None:
        selected = [case for case in eligible if case["case_id"] == case_id]
        if len(selected) != 1:
            raise ValueError(f"requested case is not an eligible hosted case: {case_id}")
        return eligible, selected
    if selection == "all":
        if len(eligible) != 10:
            raise ValueError("full-suite benchmark requires exactly ten eligible hosted cases")
        return eligible, list(eligible)
    if selection != "random":
        raise ValueError("unknown selection mode")
    if type(count) is not int or not 1 <= count <= len(eligible):
        raise ValueError("random selection count must be between one and the eligible case count")
    return eligible, random.Random(seed).sample(eligible, count)


def local_runs(factory, out, data_root="data"):
    records = []
    facts = DataPackage(data_root).facts
    for name in ("unified", "supplier", "packages", "advanced"):
        for case_id in ("case:S01", "case:S02", "case:S03"):
            agent = factory() if name == "unified" else agent_factory(name, None)()
            table = SimTable(Sim(load_cases(), facts=facts, no_clock=True))
            result = play(table, case_id, agent)
            session = table.sim.sessions[table.session_id]
            decisions = getattr(agent, "decision_history", [])
            record = {"case_id": case_id, "agent": name, "result": result,
                      "threads": {sid: thread["messages"] for sid, thread in session["threads"].items()},
                      "decisions": decisions,
                      "audit_errors": audit_decisions(session["case"], decisions) if name == "unified" else []}
            records.append(record)
            write_json(out / f"{name}-{case_id.split(':')[-1]}.json", record)
            print(json.dumps({"agent": name, "case": case_id, "score": result.get("score"),
                              "deal": result.get("deal"), "audit_errors": record["audit_errors"]}), flush=True)
    return records


def hosted_run(client, factory, case, out):
    agent, table = factory(), RemoteTable(client, case)
    record = {"case_id": case["case_id"], "agent": "unified", "case": case}
    try:
        record["result"] = play(table, case["case_id"], agent)
    except Exception as exc:
        record["run_error"] = f"{type(exc).__name__}: {exc}"
        # Recover the same session, never consume an extra practice attempt.
        if table.session_id:
            try:
                state = client.session(table.session_id)
                if state.get("status") == "open":
                    threads = table.refresh_threads({})
                    close = agent.close(case, threads)
                    record["result"] = table.close(close["supplier_id"], close["message"])
                    record["recovered_by_safe_close"] = True
                else:
                    record["result"] = state.get("result")
            except Exception as recovery:
                record["recovery_error"] = f"{type(recovery).__name__}: {recovery}"
    record["session_id"] = table.session_id
    if table.session_id:
        try:
            state = client.session(table.session_id)
            record["session_status"] = state.get("status")
            record["replay_url"] = state.get("replay_url")
            record["threads"] = {sid: client.thread(table.session_id, sid) for sid in state.get("threads", {})}
        except Exception as exc:
            record["replay_fetch_error"] = f"{type(exc).__name__}: {exc}"
    record["decisions"] = agent.decision_history
    record["cost_reconciliation"] = reconcile_cost(record.get("result"), agent.decision_history)
    record["evidence_warnings"] = agent.evidence_warnings
    record["timeout_counts"] = {sid: len(thread.get("timeouts") or [])
                                for sid, thread in record.get("threads", {}).items()}
    record["audit_errors"] = audit_decisions(case, agent.decision_history)
    write_json(out / f"unified-{case['case_id'].split(':')[-1]}.json", record)
    result = record.get("result") or {}
    print(json.dumps({"case": case["case_id"], "session_id": table.session_id,
                      "score": result.get("score"), "deal": result.get("deal"),
                      "replay_url": record.get("replay_url"), "audit_errors": record["audit_errors"],
                      "timeout_counts": record["timeout_counts"],
                      "run_error": record.get("run_error")}), flush=True)
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("local", "hosted"), required=True)
    parser.add_argument("--data", default="data")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--seed", type=int)
    parser.add_argument("--selection", choices=("random", "all"), default="random")
    parser.add_argument("--count", type=int, default=3,
                        help="number of random hosted cases to select (default: 3)")
    parser.add_argument("--case-id", help="run exactly this eligible hosted case (for controlled tests)")
    args = parser.parse_args()
    if args.case_id and args.mode != "hosted":
        parser.error("--case-id is only available in hosted mode")
    if args.selection == "all" and args.count != 3:
        parser.error("--count applies only to random selection")
    if args.case_id and args.count != 3:
        parser.error("--count cannot be combined with --case-id")
    args.out.mkdir(parents=True, exist_ok=True)
    if (args.out / "run.json").exists():
        raise ValueError("output already contains a run; choose a new directory to preserve evidence")
    manifest = {"mode": args.mode, "started_at": datetime.now(UTC).isoformat(), **source_version()}
    factory = agent_factory("unified", args.data)
    if args.mode == "local":
        records = local_runs(factory, args.out, args.data)
    else:
        load_env()
        client = ArenaClient()
        quota = client.me().get("practice", {})
        seed = args.seed if args.seed is not None else random.SystemRandom().randrange(2**32)
        eligible, selected = select_cases(client.cases("practice"), seed, args.selection,
                                           args.case_id, args.count)
        if quota.get("left", 0) < len(selected):
            raise ValueError("insufficient practice sessions for the requested complete batch")
        manifest.update(seed=seed, selection=("case" if args.case_id else args.selection),
                        requested_case_id=args.case_id, quota_before=quota,
                        experiment_flags={
                            "UNIFIED_RISKIER": os.environ.get("UNIFIED_RISKIER", "0"),
                            "UNIFIED_BOLDER_OPENING": os.environ.get("UNIFIED_BOLDER_OPENING", "0"),
                            "UNIFIED_OPENING_DISCOUNT_PCT": os.environ.get(
                                "UNIFIED_OPENING_DISCOUNT_PCT", "15 (default)"
                            ),
                            "UNIFIED_ADAPTIVE_OPENING": os.environ.get("UNIFIED_ADAPTIVE_OPENING", "0"),
                            "UNIFIED_ADAPTIVE_OPENING_V2": os.environ.get("UNIFIED_ADAPTIVE_OPENING_V2", "0"),
                            "UNIFIED_RESPONSE_TRADE_MENU": os.environ.get("UNIFIED_RESPONSE_TRADE_MENU", "0"),
                            "UNIFIED_PROACTIVE_PRICE_EVIDENCE": os.environ.get(
                                "UNIFIED_PROACTIVE_PRICE_EVIDENCE", "0"
                            ),
                            "SUPPLIER_ECONOMICS": os.environ.get("SUPPLIER_ECONOMICS", "0"),
                        },
                        population=[case["case_id"] for case in eligible],
                        selected=[case["case_id"] for case in selected])
        write_json(args.out / "run.json", manifest)  # Persist before the first POST.
        print(json.dumps({"seed": seed, "selected": manifest["selected"]}), flush=True)
        logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
        with ThreadPoolExecutor(max_workers=min(3, len(selected))) as pool:
            futures = [pool.submit(hosted_run, client, factory, case, args.out) for case in selected]
            records = [future.result() for future in as_completed(futures)]
        client.http.close()
    manifest["finished_at"] = datetime.now(UTC).isoformat()
    manifest["results"] = [{key: record.get(key) for key in
                            ("case_id", "agent", "result", "audit_errors", "session_id",
                             "replay_url", "run_error", "timeout_counts")}
                           for record in order_records(records)]
    manifest["summary"] = summarize_records(records)
    write_json(args.out / "run.json", manifest)
    print(json.dumps({"summary": manifest["summary"]}), flush=True)


if __name__ == "__main__":
    main()
