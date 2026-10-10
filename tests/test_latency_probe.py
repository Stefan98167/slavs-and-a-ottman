from scripts.latency_probe import probe


def test_latency_probe_uses_fake_reply_delay_and_reports_thread_state():
    report = probe("unified", "case:S02", reply_s=60, cap_s=480)
    assert report["elapsed_fake_s"] == 300
    assert report["end_reason"] == "accepted"
    assert report["score"] == 34.37
    assert all(thread["timeouts"] == 0 for thread in report["threads"].values())
    assert all(thread["closed"] == "accepted" for thread in report["threads"].values())
