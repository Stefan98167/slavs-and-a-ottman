import math

import pytest

from scripts.validate_mvp import order_records, select_cases, summarize_records


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


def test_case_selection_can_target_exactly_one_eligible_hosted_case():
    cases = [
        {"case_id": "case:P18", "hosted": True},
        {"case_id": "case:P17", "hosted": True},
        {"case_id": "case:S01", "hosted": False},
    ]
    eligible, selected = select_cases(cases, seed=1, case_id="case:P18")
    assert [case["case_id"] for case in eligible] == ["case:P17", "case:P18"]
    assert [case["case_id"] for case in selected] == ["case:P18"]

    with pytest.raises(ValueError, match="not an eligible hosted case"):
        select_cases(cases, seed=1, case_id="case:S01")


def test_random_case_count_is_exact_and_without_replacement():
    cases = [{"case_id": f"case:P{i:02d}", "hosted": True} for i in range(10)]
    _, selected = select_cases(cases, seed=17, count=2)
    assert len(selected) == 2
    assert len({case["case_id"] for case in selected}) == 2


@pytest.mark.parametrize("count", [0, -1, 11, True, 1.5])
def test_random_case_count_rejects_invalid_values(count):
    cases = [{"case_id": f"case:P{i:02d}", "hosted": True} for i in range(10)]
    with pytest.raises(ValueError, match="random selection count"):
        select_cases(cases, seed=17, count=count)
