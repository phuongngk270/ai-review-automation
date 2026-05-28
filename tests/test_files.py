import io
from unittest.mock import MagicMock, patch

import pytest

from automation.files import upload_file


def make_client():
    """Return a MagicMock with deterministic post() responses keyed by path."""
    calls = []
    def fake_post(path: str, json):
        calls.append((path, json))
        if path == "/api/v3/files/createDirectUpload":
            return {"batchUploadId": "bup1"}
        if path == "/api/v3/files/getDirectUploadUrl":
            return {
                "uploadUrl": "https://document-host/uploads/x/y/file.pdf?sig=z",
                "contentType": "application/pdf",
            }
        if path == "/api/v3/files/completeDirectUpload/async-create":
            return {"id": "asy1"}
        if path == "/api/v3/files/completeDirectUpload/async-run":
            return {}
        if path == "/api/v3/files/completeDirectUpload/async-fetch":
            return {
                "state": {
                    "__typename__": "AsyncApiStateSuccess",
                    "resp": {"r": {"files": [["FILE_ID_123", "file.pdf"]]}},
                }
            }
        raise AssertionError(f"unexpected path: {path}")
    client = MagicMock()
    client.post.side_effect = fake_post
    return client, calls


def test_upload_file_returns_file_item_id(tmp_path):
    pdf = tmp_path / "file.pdf"
    pdf.write_bytes(b"%PDF-1.4 fake")
    client, calls = make_client()
    with patch("automation.files.requests.put") as put:
        put.return_value = MagicMock(status_code=200, text="")
        file_id = upload_file(client, pdf, folder_id="FOLDER_X")
    assert file_id == "FILE_ID_123"
    assert put.call_count == 1
    args, kwargs = put.call_args
    assert args[0].startswith("https://document-host/")
    assert kwargs["data"] == b"%PDF-1.4 fake"
    assert "Authorization" not in (kwargs.get("headers") or {})


def test_upload_file_threads_folder_id_into_step_1(tmp_path):
    pdf = tmp_path / "file.pdf"
    pdf.write_bytes(b"")
    client, calls = make_client()
    with patch("automation.files.requests.put") as put:
        put.return_value = MagicMock(status_code=200)
        upload_file(client, pdf, folder_id="FOLDER_X")
    create_call_body = next(c[1] for c in calls if c[0].endswith("createDirectUpload"))
    assert '"folderId":"FOLDER_X"' in create_call_body["paramsOpt"]


def test_upload_file_raises_on_async_failure(tmp_path):
    pdf = tmp_path / "file.pdf"
    pdf.write_bytes(b"")
    client = MagicMock()
    client.post.side_effect = [
        {"batchUploadId": "b"},
        {"uploadUrl": "https://h/u?s=1", "contentType": "application/pdf"},
        {"id": "a"},
        {},
        {"state": {"__typename__": "AsyncApiStateError", "msg": "boom"}},
    ]
    with patch("automation.files.requests.put") as put:
        put.return_value = MagicMock(status_code=200)
        with pytest.raises(RuntimeError, match="boom"):
            upload_file(client, pdf, folder_id="FOLDER_X")
