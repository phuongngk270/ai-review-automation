from unittest.mock import MagicMock, patch

from automation.sheets import OutcomeRow, write_outcomes


def test_write_outcomes_batches_updates_per_row():
    service = MagicMock()
    rows = [
        OutcomeRow(row=5, tester="C04-TC-01-PASS", outcome="PASS", date="2026-05-28", notes=""),
        OutcomeRow(row=13, tester="C04-TC-01-PASS", outcome="NOT_APPLICABLE", date="2026-05-28", notes=""),
    ]
    write_outcomes(service, sheet_id="sid", tab_name="Test Cases", rows=rows)
    batch_update = service.spreadsheets().values().batchUpdate
    assert batch_update.called
    body = batch_update.call_args.kwargs["body"]
    # Two rows × 4 cell ranges (M, O, P, Q) — column N is formula, skipped.
    assert len(body["data"]) == 8
    ranges = [d["range"] for d in body["data"]]
    assert "Test Cases!M5" in ranges
    assert "Test Cases!O5" in ranges
    assert "Test Cases!P5" in ranges
    assert "Test Cases!Q5" in ranges
    assert "Test Cases!N5" not in ranges  # formula column never touched


def test_outcome_row_skips_notes_when_empty():
    rows = [OutcomeRow(row=5, tester="t", outcome="PASS", date="d", notes="")]
    service = MagicMock()
    write_outcomes(service, sheet_id="s", tab_name="T", rows=rows)
    body = service.spreadsheets().values().batchUpdate.call_args.kwargs["body"]
    q = next(d for d in body["data"] if d["range"].endswith("Q5"))
    assert q["values"] == [[""]]
