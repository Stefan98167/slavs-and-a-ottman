import math

from scripts.validate_mvp import order_records, summarize_records


def test_batch_summary_reports_mean_and_safety_counts():
    summary = summarize_records([
        {"result": {"score": 0.2, "deal": True, "ended": True},
         "timeout_counts": {"sup:A": 1}, "audit_errors": []},
        {"result": {"score": 0.8, "deal": False, "ended": True},
         "timeout_counts": {"sup:B": 0}, "audit_errors": ["invalid sheet"]},
        {"result": None, "run_error": "network error", "timeout_counts": None},
    ])

    assert summary == {
        "case_count": 3,
        "scored_cases": 2,
        "mean_score": 0.5,
        "deals": 1,
        "ended_sessions": 2,
        "runner_errors": 1,
        "audit_errors": 1,
        "timeouts": 1,
    }


def test_batch_summary_handles_no_valid_scores():
    summary = summarize_records([{"result": {"score": math.nan}}])

    assert summary["scored_cases"] == 0
    assert summary["mean_score"] is None


def test_saved_records_have_stable_order_after_parallel_runs():
    records = [
        {"case_id": "case:P02", "agent": "unified"},
        {"case_id": "case:P01", "agent": "advanced"},
        {"case_id": "case:P01", "agent": "unified"},
    ]

    assert order_records(records) == [
        {"case_id": "case:P01", "agent": "advanced"},
        {"case_id": "case:P01", "agent": "unified"},
        {"case_id": "case:P02", "agent": "unified"},
    ]
