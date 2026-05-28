from datetime import date
from unittest.mock import MagicMock, patch

from automation.combos import Combo, RowMapping
from automation.runner import ComboResult, run_combo


def _fake_combo():
    return Combo(
        profile_name="C99-TEST",
        sub_doc_shorthand="SUB/SUB-01_Individual_US_Clean.pdf",
        supporting_doc_shorthands=(),
        rows=(RowMapping(row=5, scenario_id="TC-01-PASS", cnum="C1"),),
    )


@patch("automation.runner.upload_file")
@patch("automation.runner.create_offline_investor", return_value="fbi-1")
@patch("automation.runner.find_lp_by_firm_name", return_value="lp-1")
@patch("automation.runner.submit_signed_subscription")
@patch("automation.runner.wait_for_review")
@patch("automation.runner.fetch_run_results")
def test_run_combo_returns_outcome_rows(fetch, wait, submit, find, create, upload):
    from automation.review import CheckResult, RunHandle
    upload.return_value = "file-1"
    wait.return_value = RunHandle(run_id="run-1", state="HAS_ISSUES")
    fetch.return_value = [
        CheckResult(check_definition_id="chkdlg3d7o6lg5lw", check_name="x", assessment="PASS"),
    ]
    client = MagicMock()
    result = run_combo(
        client, _fake_combo(),
        close_id="close-1",
        folder_id="FOLDER_X",
        today=date(2026, 5, 28),
    )
    assert isinstance(result, ComboResult)
    assert len(result.outcome_rows) == 1
    assert result.outcome_rows[0].row == 5
    assert result.outcome_rows[0].outcome == "PASS"
    assert result.outcome_rows[0].tester == "C99-TEST"
    assert result.outcome_rows[0].date == "2026-05-28"


def test_resolve_user_folder_id_extracts_session_prefix():
    from automation.runner import _resolve_user_folder_id
    import json, base64
    # Build a fake JWT with the userSessionId we expect
    header = base64.urlsafe_b64encode(b'{"alg":"none"}').rstrip(b"=").decode()
    body = json.dumps({"body": json.dumps({"userSessionId": "ursABC123.usiXYZ"})})
    payload = base64.urlsafe_b64encode(body.encode()).rstrip(b"=").decode()
    fake_jwt = f"{header}.{payload}.sig"
    client = MagicMock()
    client.bearer = fake_jwt
    folder_id = _resolve_user_folder_id(client)
    assert folder_id == "ursABC123.fdr000001.fdrtemp00"
