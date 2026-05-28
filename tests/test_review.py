from unittest.mock import MagicMock

import pytest

from automation.review import (
    CheckResult,
    fetch_run_results,
    trigger_rerun,
    wait_for_review,
)


def test_wait_for_review_returns_when_status_completes(monkeypatch):
    client = MagicMock()
    statuses = [
        {"state": "RUNNING", "latestRunId": "run1"},
        {"state": "RUNNING", "latestRunId": "run1"},
        {"state": "HAS_ISSUES", "latestRunId": "run1"},
    ]
    def fake_post(path, body):
        if path == "/api/v3/checkreview/status":
            return statuses.pop(0)
        if path == "/api/v3/checkreview/getRun":
            return {
                "runId": "run1",
                "status": "COMPLETED",
                "checksTotal": 22,
                "results": [],
            }
        raise AssertionError(path)
    client.post.side_effect = fake_post
    monkeypatch.setattr("automation.review.time.sleep", lambda s: None)
    run = wait_for_review(client, lp_id="LP_X", poll_interval=0.0, timeout=10.0)
    assert run.run_id == "run1"
    assert run.state == "HAS_ISSUES"


def test_wait_for_review_times_out(monkeypatch):
    client = MagicMock()
    client.post.return_value = {"state": "RUNNING", "latestRunId": "run1"}
    monkeypatch.setattr("automation.review.time.monotonic", lambda: 9999.0)
    with pytest.raises(TimeoutError):
        wait_for_review(client, lp_id="LP_X", poll_interval=0.0, timeout=0.1)


def test_fetch_run_results_parses_assessment_per_check():
    client = MagicMock()
    client.post.return_value = {
        "runId": "run1",
        "status": "COMPLETED",
        "results": [
            {
                "checkResultId": "cr1",
                "checkDefinitionId": "chk-a",
                "checkName": "Check A",
                "assessment": "PASS",
                "confidence": "HIGH",
                "reasoning": "...",
            },
            {
                "checkResultId": "cr2",
                "checkDefinitionId": "chk-b",
                "checkName": "Check B",
                "assessment": "FAIL",
                "confidence": "HIGH",
                "reasoning": "...",
            },
        ],
    }
    results = fetch_run_results(client, run_id="run1")
    assert results == [
        CheckResult(check_definition_id="chk-a", check_name="Check A", assessment="PASS"),
        CheckResult(check_definition_id="chk-b", check_name="Check B", assessment="FAIL"),
    ]


def test_trigger_rerun_posts_run_endpoint():
    client = MagicMock()
    client.post.return_value = {"runId": "new-run", "status": "RUNNING"}
    run_id = trigger_rerun(client, lp_id="LP_X")
    assert run_id == "new-run"
    path, body = client.post.call_args.args
    assert path == "/api/v3/checkreview/run"
    assert body == {"lpId": "LP_X", "submissionVersionIndex": 1}
