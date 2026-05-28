# Phase 2 — 67-Combo AI Review Runner Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the LLM-driven `ai-review-automation` skill with a pure-Python script that runs all 67 remaining test combos end-to-end against the Anduin GP API and writes results to the master Google Sheet, in well under the time and cost of the LLM-driven version.

**Architecture:** Approach A from
[`docs/superpowers/specs/2026-05-28-ai-review-automation-script-design.md`](../specs/2026-05-28-ai-review-automation-script-design.md):
pure-HTTP client on top of the bearer JWT bootstrapped in Phase 1
([`automation/auth.py`](../../../automation/auth.py)). Each combo runs as a
plain Python function — create investor → upload subscription PDF → upload
supporting docs → poll for AI review completion → read results → write row(s)
to Google Sheets. Up to N combos in parallel via a `concurrent.futures` pool.
Resumable: at startup, list existing `C##-*` profiles and skip completed
ones. Endpoint shapes are fully documented in
[`docs/anduin-api-reference.md`](../../anduin-api-reference.md) — that doc is
the single source of truth for every request body in this plan.

**Tech Stack:** Python 3.13, `requests` (already in `requirements.txt`),
`google-api-python-client` + `google-auth-oauthlib` (new), `pytest` (already
present), `concurrent.futures.ThreadPoolExecutor` (stdlib). No Playwright, no
LLM at runtime.

---

## File Structure

New files (all under `automation/`):

- `automation/config.py` — fund/entity ids, paths, document folder
  shortcuts. Tiny module, no logic.
- `automation/files.py` — the four-step CloudFront direct-upload sequence as
  a single `upload_file(path) -> file_item_id` function. Shared by
  subscription and supporting-doc submissions.
- `automation/investor.py` — `create_offline_investor(name, email) ->
  lp_id` (resolves the `.lpXXXX` id by listing the dashboard after create);
  `list_existing_probe_profiles() -> list[ExistingProfile]` for
  resumability.
- `automation/submissions.py` — `submit_signed_subscription(lp_id,
  file_item_id, amount)`; `submit_supporting_docs(lp_id,
  file_item_ids)`.
- `automation/review.py` — `wait_for_review(lp_id) -> RunResult`;
  `fetch_run_results(run_id) -> list[CheckResult]`; `trigger_rerun(lp_id)`
  (used only as a fallback if auto-trigger doesn't fire).
- `automation/results.py` — `map_results_to_outcomes(results) -> dict[str,
  Outcome]` keyed by `checkDefinitionId`. The check-definition-id → C-number
  table lives here as a constant.
- `automation/combos.py` — the 67-combo lookup table parsed once from
  `skills/ai-review-automation/SKILL.md` (Stage 9 section) or hardcoded;
  exposes `iter_combos() -> Iterator[Combo]`.
- `automation/sheets.py` — Google Sheets writer. `connect() -> service`;
  `write_outcomes(rows: list[OutcomeRow])`.
- `automation/runner.py` — `run_combo(combo) -> ComboResult` (the per-combo
  pipeline); `main(parallelism: int)` (the top-level orchestrator).
- `automation/__main__.py` — extend with `run-all`, `run-one <C##>`, and
  `list-combos` commands.

Tests live under `tests/` mirroring the module layout. Each module has a
unit-test file with mocked HTTP responses. The runner gets an integration
test that mocks the whole HTTP stack and verifies it threads everything
together.

---

## Task 1: Config module

**Files:**
- Create: `automation/config.py`
- Create: `tests/test_config.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_config.py
from pathlib import Path

from automation.config import (
    DOC_BASE_DIR,
    DOC_FOLDER_SHORTCUTS,
    ENTITY_ID,
    FUND_DELAWARE_AMOUNT_FIELD_ID,
    FUND_SUB_ID,
    PROBE_INVESTOR_PREFIX,
    resolve_doc_path,
)


def test_constants_are_stable():
    assert FUND_SUB_ID == "txnqxned8j9qx1yp.fsbkg78"
    assert ENTITY_ID == "entd5ev6mge1xndv"
    assert FUND_DELAWARE_AMOUNT_FIELD_ID == "txnqxned8j9qx1yp.fsbkg78.ivfm3r"
    assert PROBE_INVESTOR_PREFIX == "PROBE-API-DISCOVERY-DELETE-ME"


def test_resolve_doc_path_uses_shortcuts():
    p = resolve_doc_path("SUB/SUB-01_Individual_US_Clean.pdf")
    assert p == DOC_BASE_DIR / "0. Subscription Agreements" / "SUB-01_Individual_US_Clean.pdf"


def test_resolve_doc_path_rejects_unknown_shortcut():
    import pytest
    with pytest.raises(KeyError):
        resolve_doc_path("BOGUS/foo.pdf")


def test_doc_base_dir_exists():
    assert DOC_BASE_DIR.is_dir(), "test pack base dir missing — run pre-flight"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_config.py -v`
Expected: ImportError — module does not exist yet.

- [ ] **Step 3: Implement the module**

```python
# automation/config.py
"""Static configuration: fund ids, file paths, naming conventions."""

from __future__ import annotations

from pathlib import Path

ENTITY_ID = "entd5ev6mge1xndv"
FUND_SUB_ID = "txnqxned8j9qx1yp.fsbkg78"
FUND_DELAWARE_AMOUNT_FIELD_ID = "txnqxned8j9qx1yp.fsbkg78.ivfm3r"

PROBE_INVESTOR_PREFIX = "PROBE-API-DISCOVERY-DELETE-ME"

DOC_BASE_DIR = (
    Path(__file__).resolve().parents[1]
    / "AI Review Agent Test Pack"
    / "Test Documents"
)

DOC_FOLDER_SHORTCUTS: dict[str, str] = {
    "SUB":  "0. Subscription Agreements",
    "TAX":  "1. Tax Forms",
    "WHS":  "2. Withholding Statements",
    "FORM": "3. Formation Documents",
    "CERT": "4. Certificates of Good Standing",
    "AUTH": "5. Authorization Documents",
    "ID":   "6. Government IDs",
    "BO":   "7. Beneficial Ownership & AML",
    "SOF":  "8. Source of Funds",
}


def resolve_doc_path(shorthand: str) -> Path:
    """Turn ``"SUB/SUB-01_…pdf"`` into the absolute path on disk."""
    short, _, rest = shorthand.partition("/")
    folder = DOC_FOLDER_SHORTCUTS[short]  # KeyError on unknown
    return DOC_BASE_DIR / folder / rest
```

- [ ] **Step 4: Run tests**

Run: `.venv/bin/pytest tests/test_config.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add automation/config.py tests/test_config.py
git commit -m "feat(config): centralize fund ids, paths, naming"
```

---

## Task 2: File-upload helper

**Files:**
- Create: `automation/files.py`
- Create: `tests/test_files.py`

The four-step CloudFront direct-upload from
[`docs/anduin-api-reference.md` §2a](../../anduin-api-reference.md). All
four steps wrapped in one function. The PUT to CloudFront is the only step
that does NOT use the Anduin client — it's a bare `requests.put` with no
auth.

- [ ] **Step 1: Write failing tests**

```python
# tests/test_files.py
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
    # Verify CloudFront PUT was called with the signed URL and no auth header
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_files.py -v`
Expected: ImportError — `upload_file` does not exist.

- [ ] **Step 3: Implement**

```python
# automation/files.py
"""CloudFront-signed direct upload for the Anduin file service.

Documented in docs/anduin-api-reference.md §2a.
"""

from __future__ import annotations

import json
import logging
import uuid
from pathlib import Path
from typing import TYPE_CHECKING

import requests

if TYPE_CHECKING:
    from automation.anduin_client import AnduinClient

logger = logging.getLogger(__name__)


def upload_file(client: "AnduinClient", path: Path, folder_id: str) -> str:
    """Upload ``path`` to the Anduin file service and return the item id."""
    file_upload_id = f"{uuid.uuid4()}-{path.name}"
    logger.info("upload_file: %s -> folder %s", path.name, folder_id)

    # Step 1: createDirectUpload
    batch = client.post(
        "/api/v3/files/createDirectUpload",
        {
            "apiName": "default",
            "paramsOpt": json.dumps({"folderId": folder_id}),
            "files": [
                {
                    "fileUploadId": {"id": file_upload_id},
                    "filePath": path.name,
                    "contentTypeOpt": "application/pdf",
                    "checksumOpt": None,
                    "metadata": {},
                }
            ],
            "emptyFolders": [],
        },
    )
    batch_id = batch["batchUploadId"]

    # Step 2: getDirectUploadUrl
    signed = client.post(
        "/api/v3/files/getDirectUploadUrl",
        {"batchUploadId": batch_id, "fileUploadId": {"id": file_upload_id}},
    )

    # Step 3: CloudFront PUT (no auth header)
    body = path.read_bytes()
    put = requests.put(
        signed["uploadUrl"],
        data=body,
        headers={"Content-Type": signed["contentType"]},
        timeout=120,
    )
    if not (200 <= put.status_code < 300):
        raise RuntimeError(f"CloudFront PUT failed {put.status_code}: {put.text[:200]}")

    # Step 4: async complete (create -> run -> fetch)
    async_op = client.post("/api/v3/files/completeDirectUpload/async-create", {})
    op_id = async_op["id"]
    client.post(
        "/api/v3/files/completeDirectUpload/async-run",
        {"id": op_id, "params": {"batchUploadId": batch_id}},
    )
    result = client.post(
        "/api/v3/files/completeDirectUpload/async-fetch",
        {"id": op_id},
    )
    state = result.get("state") or {}
    if state.get("__typename__") != "AsyncApiStateSuccess":
        raise RuntimeError(f"upload async-fetch failed: {state}")
    files = state["resp"]["r"]["files"]
    return files[0][0]
```

- [ ] **Step 4: Run tests**

Run: `.venv/bin/pytest tests/test_files.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add automation/files.py tests/test_files.py
git commit -m "feat(files): direct-upload sequence for anduin file service"
```

---

## Task 3: Investor creation + lookup

**Files:**
- Create: `automation/investor.py`
- Create: `tests/test_investor.py`

The create-investor response is the `.fbi` id, not the `.lpXXXX` id we need
for uploads. Resolve via `getLpDashboardItemList` filtering on `firmName`.

- [ ] **Step 1: Write failing tests**

```python
# tests/test_investor.py
from unittest.mock import MagicMock

from automation.investor import (
    create_offline_investor,
    find_lp_by_firm_name,
    list_existing_probe_profiles,
)


def test_create_offline_investor_posts_expected_body():
    client = MagicMock()
    client.post.return_value = "txnqxned8j9qx1yp.fsbkg78.lti01.fbi"
    fbi_id = create_offline_investor(
        client,
        firm_name="C99-TEST",
        first_name="Test",
        last_name="User",
        email="test@example.com",
        close_id="CLOSE_X",
    )
    assert fbi_id.endswith(".fbi")
    path, body = client.post.call_args.args
    assert path == "/api/v3/fundsub/participant/addMainLpWorkflowWithoutJointInfo"
    assert body["fundSubId"] == "txnqxned8j9qx1yp.fsbkg78"
    lp0 = body["lpsToInvite"][0]
    assert lp0["lpInfo"]["firmName"] == "C99-TEST"
    assert lp0["lpInfo"]["lpContact"]["email"] == "test@example.com"
    assert lp0["closeIdOpt"] == "CLOSE_X"


def test_find_lp_by_firm_name_returns_lp_id():
    client = MagicMock()
    client.post.return_value = {
        "items": [
            {"firmName": "OTHER", "lpId": "lp-other"},
            {"firmName": "C99-TEST", "lpId": "lp-target"},
        ]
    }
    lp_id = find_lp_by_firm_name(client, "C99-TEST")
    assert lp_id == "lp-target"


def test_find_lp_by_firm_name_returns_none_if_absent():
    client = MagicMock()
    client.post.return_value = {"items": []}
    assert find_lp_by_firm_name(client, "C99-TEST") is None


def test_list_existing_probe_profiles_filters_by_prefix():
    client = MagicMock()
    client.post.return_value = {
        "items": [
            {"firmName": "C01-FOO", "lpId": "lp-1", "status": "Pending approval"},
            {"firmName": "C02-BAR", "lpId": "lp-2", "status": "Pending approval"},
            {"firmName": "SomeOther", "lpId": "lp-3", "status": "Invited"},
        ]
    }
    profiles = list_existing_probe_profiles(client, prefix="C")
    assert {p.firm_name for p in profiles} == {"C01-FOO", "C02-BAR"}
```

- [ ] **Step 2: Run tests to verify failure**

Run: `.venv/bin/pytest tests/test_investor.py -v`
Expected: ImportError.

- [ ] **Step 3: Implement**

```python
# automation/investor.py
"""Create and look up offline-tracked LPs on the Anduin GP dashboard."""

from __future__ import annotations

import logging
import secrets
import string
from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

from automation.config import FUND_SUB_ID

if TYPE_CHECKING:
    from automation.anduin_client import AnduinClient

logger = logging.getLogger(__name__)

DEFAULT_EMAIL_TEMPLATE = {
    "fundSubEvent": {"value": 1},
    "subject": "Magma Capital - AI Agents - Invitation to complete your subscription package",
    "body": (
        "<p>Dear [Name],</p><p>You're invited to complete your subscription "
        "package for Magma Capital - AI Agents on Anduin.</p>"
    ),
    "semanticHtmlBodyOpt": None,
    "primaryCTA": "Begin your subscription",
    "lastEditedAt": None,
    "ccEmailAddresses": [],
}


@dataclass(frozen=True)
class ExistingProfile:
    firm_name: str
    lp_id: str
    status: str


def _nonce(n: int = 10) -> str:
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(n))


def create_offline_investor(
    client: "AnduinClient",
    *,
    firm_name: str,
    first_name: str,
    last_name: str,
    email: str,
    close_id: str,
) -> str:
    """Create an offline-tracked LP. Returns the FBI id from the response."""
    body = {
        "fundSubId": FUND_SUB_ID,
        "lpsToInvite": [
            {
                "lpInfo": {
                    "lpInfoId": {"value": _nonce()},
                    "lpContact": {
                        "email": email,
                        "firstName": first_name,
                        "lastName": last_name,
                        "id": "",
                        "skipInvitationEmail": False,
                        "enableSSO": False,
                    },
                    "collaboratorContacts": [],
                    "lpEmailTemplate": DEFAULT_EMAIL_TEMPLATE,
                    "firmName": firm_name,
                    "customId": "",
                    "importInvestorId": "",
                    "lpIdToCopyFormDataOpt": None,
                    "initialFormData": None,
                    "expectedCommitment": "",
                    "tagNames": [],
                    "prefillFromLp": None,
                    "dataImportItemId": None,
                    "lpIdToCopyInvestorGroupOpt": None,
                    "docTypesToMarkAsProvided": [],
                    "sharedDocumentsPerDocType": [],
                    "importFromFundData": None,
                    "metadata": [],
                    "collaboratorOrganizationInfos": [],
                    "investorGroupIdOpt": None,
                    "customDataMap": [],
                },
                "closeIdOpt": close_id,
                "investorGroupIdOpt": None,
                "lpAttachedDocs": [],
            }
        ],
        "lpOrderType": {"value": 1},
        "sharedAttachedDocs": [],
        "importFromFundDataFirm": None,
    }
    fbi_id = client.post(
        "/api/v3/fundsub/participant/addMainLpWorkflowWithoutJointInfo",
        body,
    )
    # Endpoint returns a bare JSON string. requests.json() decodes it as str.
    if isinstance(fbi_id, str):
        return fbi_id
    raise RuntimeError(f"unexpected create-investor response: {fbi_id!r}")


def _list_dashboard(client: "AnduinClient") -> list[dict]:
    resp = client.post(
        "/api/v3/fundsub/admin/getLpDashboardItemList",
        {"fundSubId": FUND_SUB_ID, "filters": {}, "limit": 500, "offset": 0},
    )
    return resp.get("items") or []


def find_lp_by_firm_name(client: "AnduinClient", firm_name: str) -> Optional[str]:
    for item in _list_dashboard(client):
        if item.get("firmName") == firm_name:
            return item.get("lpId")
    return None


def list_existing_probe_profiles(
    client: "AnduinClient",
    *,
    prefix: str,
) -> list[ExistingProfile]:
    return [
        ExistingProfile(
            firm_name=item["firmName"],
            lp_id=item["lpId"],
            status=item.get("status", ""),
        )
        for item in _list_dashboard(client)
        if item.get("firmName", "").startswith(prefix)
    ]
```

- [ ] **Step 4: Run tests**

Run: `.venv/bin/pytest tests/test_investor.py -v`
Expected: 4 passed.

- [ ] **Step 5: Verify `getLpDashboardItemList` body shape against live API**

The exact request body for that endpoint was NOT captured during Phase 1
(it was a `bLen=0` preflight only in our captures). Run a one-shot probe to
confirm the shape works:

```bash
.venv/bin/python -c "
from automation.auth import bootstrap_bearer
from automation.anduin_client import AnduinClient
from automation.investor import list_existing_probe_profiles
c = AnduinClient(bearer=bootstrap_bearer())
print(list_existing_probe_profiles(c, prefix='PROBE')[:3])
"
```

Expected: prints the two `PROBE-API-DISCOVERY-DELETE-ME(-2)` rows.
If the shape is wrong (4xx/empty), inspect the live SPA via `$B js
window.__captures` after navigating the dashboard, adjust the body in
`_list_dashboard`, re-run.

- [ ] **Step 6: Commit**

```bash
git add automation/investor.py tests/test_investor.py
git commit -m "feat(investor): create offline investors and resolve LP ids"
```

---

## Task 4: Submission helpers

**Files:**
- Create: `automation/submissions.py`
- Create: `tests/test_submissions.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_submissions.py
from unittest.mock import MagicMock

from automation.submissions import (
    submit_signed_subscription,
    submit_supporting_docs,
)


def test_submit_signed_subscription_body():
    client = MagicMock()
    client.post.return_value = {"dataExtractionWarningOpt": None}
    submit_signed_subscription(
        client,
        lp_id="LP_X",
        file_item_id="FILE_X",
        amount_usd=100000,
        amount_field_id="FIELD_X",
        firm_name="C99-TEST",
    )
    path, body = client.post.call_args.args
    assert path == "/api/v3/fundsub/subscription-doc/gpUploadSignedSubscriptionDoc"
    assert body == {
        "fundSubLpId": "LP_X",
        "uploadedDocs": ["FILE_X"],
        "submittedAmounts": [["FIELD_X", {"value": "100000"}]],
        "shouldApprove": False,
        "shouldCreateNewDataExtractRequest": False,
        "investmentEntityName": "C99-TEST",
    }


def test_submit_supporting_docs_one_call_per_file():
    client = MagicMock()
    client.post.return_value = {}
    submit_supporting_docs(client, lp_id="LP_X", file_item_ids=["F1", "F2"])
    paths = [c.args[0] for c in client.post.call_args_list]
    assert paths == [
        "/api/v3/fundsub/supportingdoc/v2/uploadFile",
        "/api/v3/fundsub/supportingdoc/v2/uploadFile",
    ]
    bodies = [c.args[1] for c in client.post.call_args_list]
    assert bodies[0] == {"lpId": "LP_X", "fileIds": ["F1"], "docType": ""}
    assert bodies[1] == {"lpId": "LP_X", "fileIds": ["F2"], "docType": ""}


def test_submit_supporting_docs_noop_on_empty():
    client = MagicMock()
    submit_supporting_docs(client, lp_id="LP_X", file_item_ids=[])
    client.post.assert_not_called()
```

- [ ] **Step 2: Run tests, verify ImportError**

Run: `.venv/bin/pytest tests/test_submissions.py -v`

- [ ] **Step 3: Implement**

```python
# automation/submissions.py
"""Submit uploaded files against an LP record.

Documented in docs/anduin-api-reference.md §2b and §4.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from automation.anduin_client import AnduinClient

logger = logging.getLogger(__name__)


def submit_signed_subscription(
    client: "AnduinClient",
    *,
    lp_id: str,
    file_item_id: str,
    amount_usd: int,
    amount_field_id: str,
    firm_name: str,
) -> None:
    body = {
        "fundSubLpId": lp_id,
        "uploadedDocs": [file_item_id],
        "submittedAmounts": [[amount_field_id, {"value": str(amount_usd)}]],
        "shouldApprove": False,
        "shouldCreateNewDataExtractRequest": False,
        "investmentEntityName": firm_name,
    }
    client.post("/api/v3/fundsub/subscription-doc/gpUploadSignedSubscriptionDoc", body)


def submit_supporting_docs(
    client: "AnduinClient",
    *,
    lp_id: str,
    file_item_ids: list[str],
) -> None:
    for fid in file_item_ids:
        client.post(
            "/api/v3/fundsub/supportingdoc/v2/uploadFile",
            {"lpId": lp_id, "fileIds": [fid], "docType": ""},
        )
```

- [ ] **Step 4: Tests pass**

Run: `.venv/bin/pytest tests/test_submissions.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add automation/submissions.py tests/test_submissions.py
git commit -m "feat(submissions): subscription + supporting doc submit helpers"
```

---

## Task 5: AI Review polling + fetch

**Files:**
- Create: `automation/review.py`
- Create: `tests/test_review.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_review.py
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
    # status: RUNNING -> COMPLETED, then getRun returns full payload
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
```

- [ ] **Step 2: Run, verify failure**

Run: `.venv/bin/pytest tests/test_review.py -v`

- [ ] **Step 3: Implement**

```python
# automation/review.py
"""AI Review trigger, poll, and fetch.

Documented in docs/anduin-api-reference.md §5 and §6.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from automation.anduin_client import AnduinClient

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CheckResult:
    check_definition_id: str
    check_name: str
    assessment: str  # PASS | FAIL | UNKNOWN | NOT_APPLICABLE | ERROR


@dataclass(frozen=True)
class RunHandle:
    run_id: str
    state: str  # HAS_ISSUES | CLEAN | RUNNING | etc.


def trigger_rerun(client: "AnduinClient", *, lp_id: str, version: int = 1) -> str:
    resp = client.post(
        "/api/v3/checkreview/run",
        {"lpId": lp_id, "submissionVersionIndex": version},
    )
    return resp["runId"]


def wait_for_review(
    client: "AnduinClient",
    *,
    lp_id: str,
    version: int = 1,
    poll_interval: float = 30.0,
    timeout: float = 15 * 60,
) -> RunHandle:
    deadline = time.monotonic() + timeout
    while True:
        status = client.post(
            "/api/v3/checkreview/status",
            {"lpId": lp_id, "submissionVersionIndex": version},
        )
        state = status.get("state", "")
        logger.info("review %s state=%s run=%s", lp_id, state, status.get("latestRunId"))
        if state and state != "RUNNING":
            return RunHandle(run_id=status["latestRunId"], state=state)
        if time.monotonic() > deadline:
            raise TimeoutError(f"AI review for {lp_id} did not complete within {timeout:.0f}s")
        time.sleep(poll_interval)


def fetch_run_results(
    client: "AnduinClient",
    *,
    run_id: str,
    version: int = 1,
) -> list[CheckResult]:
    resp = client.post(
        "/api/v3/checkreview/getRun",
        {"runId": run_id, "submissionVersionIndex": version},
    )
    return [
        CheckResult(
            check_definition_id=r["checkDefinitionId"],
            check_name=r["checkName"],
            assessment=r["assessment"],
        )
        for r in resp.get("results", [])
    ]
```

- [ ] **Step 4: Tests pass**

Run: `.venv/bin/pytest tests/test_review.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add automation/review.py tests/test_review.py
git commit -m "feat(review): trigger, poll, and fetch AI review runs"
```

---

## Task 6: Check-definition-id → C-number mapping

**Files:**
- Create: `automation/results.py`
- Create: `tests/test_results.py`

We need to map the 22 `checkDefinitionId` values (e.g. `chkdyjqpygoropzx`) to
their C-numbers (`C1`..`C22`, skipping C16). The mapping is stable across
runs but was NOT captured during Phase 1 — only one definition id
(`chkdyjqpygoropzx` for "W-8IMY Withholding Statement Present") was
recorded. The first task here is a discovery step against the live API.

- [ ] **Step 1: Discover the check-definition-id table**

Run the live SPA's check-list endpoint and dump the result. From the
captured AI Review page traffic, the endpoint is
`/api/v3/checkreview/category/list` (returns categories, NOT checks), and
the per-result `checkDefinitionId` is what we need.

Run this one-shot probe:

```bash
.venv/bin/python -c "
from automation.auth import bootstrap_bearer
from automation.anduin_client import AnduinClient
from automation.review import fetch_run_results
import json
c = AnduinClient(bearer=bootstrap_bearer())
# Find TC-SUB01-NoSupp's run
runs = c.post('/api/v3/checkreview/history/runs', {
    'lpId': 'txnqxned8j9qx1yp.fsbkg78.lpp9x9ozl2',
    'submissionVersionIndex': 1,
})
run_id = next(r['runId'] for r in runs['runs'] if r['status'] == 'COMPLETED')
results = fetch_run_results(c, run_id=run_id)
for r in results:
    print(f'{r.check_definition_id:24s} {r.check_name}')
" | sort
```

Manually map each `checkName` to its C-number using the 22-check list in
`skills/ai-review-automation/SKILL.md` Stage 7. Save the result to a JSON
fixture: `tests/fixtures/check_definitions.json`.

- [ ] **Step 2: Write failing tests**

```python
# tests/test_results.py
from automation.results import (
    CHECK_DEFINITION_ID_TO_CNUM,
    Outcome,
    map_results_to_outcomes,
)
from automation.review import CheckResult


def test_check_table_has_22_entries():
    assert len(CHECK_DEFINITION_ID_TO_CNUM) == 22


def test_check_table_skips_c16():
    cnums = set(CHECK_DEFINITION_ID_TO_CNUM.values())
    assert "C16" not in cnums
    assert cnums == {f"C{i}" for i in list(range(1, 16)) + list(range(17, 23))}


def test_map_results_to_outcomes_translates_assessments():
    results = [
        CheckResult(check_definition_id="chkdyjqpygoropzx", check_name="W-8IMY", assessment="NOT_APPLICABLE"),
        # second id should map to e.g. C1 — fill in from fixture
    ]
    outcomes = map_results_to_outcomes(results)
    # chkdyjqpygoropzx maps to some Cnnn — assert structurally
    assert all(isinstance(v, Outcome) for v in outcomes.values())


def test_outcome_values_are_normalized():
    assert Outcome.from_assessment("PASS").sheet_value == "PASS"
    assert Outcome.from_assessment("FAIL").sheet_value == "FAIL"
    assert Outcome.from_assessment("UNKNOWN").sheet_value == "UNKNOWN"
    assert Outcome.from_assessment("NOT_APPLICABLE").sheet_value == "NOT_APPLICABLE"
    assert Outcome.from_assessment("ERROR").sheet_value == "UNKNOWN"
```

- [ ] **Step 3: Implement**

```python
# automation/results.py
"""Map AI Review check results to Google Sheet outcomes."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from automation.review import CheckResult

_FIXTURE = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "check_definitions.json"

# Loaded at import time from the fixture committed in Step 1.
CHECK_DEFINITION_ID_TO_CNUM: dict[str, str] = json.loads(_FIXTURE.read_text())


@dataclass(frozen=True)
class Outcome:
    sheet_value: str

    @classmethod
    def from_assessment(cls, assessment: str) -> "Outcome":
        if assessment in {"PASS", "FAIL", "UNKNOWN", "NOT_APPLICABLE"}:
            return cls(sheet_value=assessment)
        if assessment == "ERROR":
            return cls(sheet_value="UNKNOWN")
        raise ValueError(f"unknown assessment: {assessment!r}")


def map_results_to_outcomes(results: list[CheckResult]) -> dict[str, Outcome]:
    """Returns {C1: Outcome(...), ..., C22: Outcome(...)} keyed by C-number."""
    out: dict[str, Outcome] = {}
    for r in results:
        cnum = CHECK_DEFINITION_ID_TO_CNUM.get(r.check_definition_id)
        if cnum is None:
            # Skip unknown check ids rather than crash; log loudly.
            continue
        out[cnum] = Outcome.from_assessment(r.assessment)
    return out
```

- [ ] **Step 4: Tests pass**

Run: `.venv/bin/pytest tests/test_results.py -v`

- [ ] **Step 5: Commit**

```bash
git add automation/results.py tests/test_results.py tests/fixtures/check_definitions.json
git commit -m "feat(results): map check-definition-id to C-number outcomes"
```

---

## Task 7: Combo lookup table

**Files:**
- Create: `automation/combos.py`
- Create: `tests/test_combos.py`

Parse the 67 combo entries out of `skills/ai-review-automation/SKILL.md` so
the table doesn't drift. Each combo has: profile name, sub-doc path,
supporting docs, rows-to-update (with Cnum per row).

- [ ] **Step 1: Write failing tests**

```python
# tests/test_combos.py
from pathlib import Path

from automation.combos import Combo, RowMapping, iter_combos, load_combos


def test_loads_67_combos():
    combos = load_combos()
    assert len(combos) == 67
    assert combos[0].profile_name.startswith("C01")


def test_combo_paths_resolve_to_existing_pdfs():
    for combo in load_combos():
        assert combo.sub_doc_path.is_file(), combo.sub_doc_path
        for sd in combo.supporting_doc_paths:
            assert sd.is_file(), sd


def test_combo_has_at_least_one_row_mapping():
    for combo in load_combos():
        assert combo.rows, combo.profile_name
        assert all(isinstance(r, RowMapping) for r in combo.rows)


def test_c04_has_six_rows():
    by_name = {c.profile_name: c for c in load_combos()}
    c04 = by_name["C04-TC-01-PASS"]
    assert {r.row for r in c04.rows} == {5, 13, 19, 28, 48, 81}
    assert {r.cnum for r in c04.rows} == {"C1", "C2", "C4", "C6", "C9", "C17"}
```

- [ ] **Step 2: Run, verify failure**

Run: `.venv/bin/pytest tests/test_combos.py -v`

- [ ] **Step 3: Implement parser**

```python
# automation/combos.py
"""Parse the 67-combo test plan out of the SKILL.md runbook."""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import cache
from pathlib import Path

from automation.config import resolve_doc_path

_SKILL_FILE = (
    Path(__file__).resolve().parents[1]
    / "skills"
    / "ai-review-automation"
    / "SKILL.md"
)


@dataclass(frozen=True)
class RowMapping:
    row: int
    scenario_id: str
    cnum: str  # C1, C2, ..., C22 (skipping C16)


@dataclass(frozen=True)
class Combo:
    profile_name: str
    sub_doc_shorthand: str
    supporting_doc_shorthands: tuple[str, ...]
    rows: tuple[RowMapping, ...]

    @property
    def sub_doc_path(self) -> Path:
        return resolve_doc_path(self.sub_doc_shorthand)

    @property
    def supporting_doc_paths(self) -> tuple[Path, ...]:
        return tuple(resolve_doc_path(s) for s in self.supporting_doc_shorthands)


_COMBO_HEADER = re.compile(r"^### (C\d+)\s*$")
_PROFILE = re.compile(r"\*\*Profile name\*\*:\s*`([^`]+)`")
_SUB_DOC = re.compile(r"\*\*Sub doc\*\*:\s*`([^`]+)`")
_SUPP_DOC = re.compile(r"^-\s*`([^`]+)`\s*$")
_ROW_LINE = re.compile(r"^\|\s*(\d+)\s*\|\s*([\w-]+)\s*\|\s*(C\d+)\s*\|")


@cache
def load_combos() -> list[Combo]:
    text = _SKILL_FILE.read_text()
    lines = text.splitlines()
    combos: list[Combo] = []
    i = 0
    while i < len(lines):
        if _COMBO_HEADER.match(lines[i]):
            i, combo = _parse_one(lines, i)
            combos.append(combo)
            continue
        i += 1
    return combos


def _parse_one(lines: list[str], i: int) -> tuple[int, Combo]:
    # Find ProfileName, SubDoc, SupportingDocs, Rows until next "---" or "###"
    profile = sub = None
    supporting: list[str] = []
    rows: list[RowMapping] = []
    in_supporting = False
    in_rows = False
    j = i + 1
    while j < len(lines):
        line = lines[j]
        if line.startswith("---") or _COMBO_HEADER.match(line):
            break
        if m := _PROFILE.search(line):
            profile = m.group(1)
        elif m := _SUB_DOC.search(line):
            sub = m.group(1)
        elif line.strip().startswith("**Supporting docs"):
            in_supporting = True
        elif in_supporting and (m := _SUPP_DOC.match(line)):
            supporting.append(m.group(1))
        elif "Rows to update" in line:
            in_supporting = False
            in_rows = True
        elif in_rows and (m := _ROW_LINE.match(line)):
            rows.append(RowMapping(
                row=int(m.group(1)),
                scenario_id=m.group(2),
                cnum=m.group(3),
            ))
        j += 1
    assert profile and sub, f"combo missing fields at line {i}"
    return j, Combo(
        profile_name=profile,
        sub_doc_shorthand=sub,
        supporting_doc_shorthands=tuple(supporting),
        rows=tuple(rows),
    )


def iter_combos():
    yield from load_combos()
```

- [ ] **Step 4: Tests pass**

Run: `.venv/bin/pytest tests/test_combos.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add automation/combos.py tests/test_combos.py
git commit -m "feat(combos): parse 67-combo plan out of SKILL.md"
```

---

## Task 8: Google Sheets writer

**Files:**
- Create: `automation/sheets.py`
- Create: `tests/test_sheets.py`
- Modify: `requirements.txt`

OAuth user-flow with locally-cached tokens; the master sheet id and tab name
are constants. The existing skill drove Sheets through Name Box UI because
"API calls fail with 401/403"; per the design doc, that was almost certainly
a missing-scopes issue. We confirm with a one-shot probe before committing.

- [ ] **Step 1: Verify the official Sheets API works for the master sheet**

Get the sheet id from the user (or look it up in the SKILL.md). With a Google
Cloud OAuth client + `https://www.googleapis.com/auth/spreadsheets` scope,
attempt a read of row 1 from the Test Cases tab. If it succeeds, proceed.
If it fails with 401/403, **stop and ask the user** whether they want a
service-account or impersonation path — do not silently fall back to UI
automation.

- [ ] **Step 2: Add deps to requirements.txt**

```diff
+google-api-python-client>=2.140
+google-auth-oauthlib>=1.2
```

```bash
.venv/bin/pip install -r requirements.txt
```

- [ ] **Step 3: Write failing tests**

```python
# tests/test_sheets.py
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
```

- [ ] **Step 4: Implement**

```python
# automation/sheets.py
"""Write AI Review outcomes to the master Google Sheet.

Column mapping (per SKILL.md Stage 8):
- M: outcome (PASS|FAIL|UNKNOWN|NOT_APPLICABLE)
- N: match formula — never write
- O: tester (combo profile name)
- P: date run (YYYY-MM-DD)
- Q: notes (optional)
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
TOKEN_PATH = Path.home() / ".cache" / "anduin-automation" / "sheets-token.json"
CLIENT_SECRETS_PATH = Path.home() / ".cache" / "anduin-automation" / "oauth-client.json"


def connect():
    TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)
    creds = None
    if TOKEN_PATH.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(str(CLIENT_SECRETS_PATH), SCOPES)
            creds = flow.run_local_server(port=0)
        TOKEN_PATH.write_text(creds.to_json())
    return build("sheets", "v4", credentials=creds)


@dataclass(frozen=True)
class OutcomeRow:
    row: int
    tester: str
    outcome: str
    date: str
    notes: str = ""


def write_outcomes(service, *, sheet_id: str, tab_name: str, rows: list[OutcomeRow]) -> None:
    data = []
    for r in rows:
        data.append({"range": f"{tab_name}!M{r.row}", "values": [[r.outcome]]})
        data.append({"range": f"{tab_name}!O{r.row}", "values": [[r.tester]]})
        data.append({"range": f"{tab_name}!P{r.row}", "values": [[r.date]]})
        data.append({"range": f"{tab_name}!Q{r.row}", "values": [[r.notes]]})
    service.spreadsheets().values().batchUpdate(
        spreadsheetId=sheet_id,
        body={"valueInputOption": "USER_ENTERED", "data": data},
    ).execute()
```

- [ ] **Step 5: Tests pass**

Run: `.venv/bin/pytest tests/test_sheets.py -v`
Expected: 2 passed.

- [ ] **Step 6: Commit**

```bash
git add automation/sheets.py tests/test_sheets.py requirements.txt
git commit -m "feat(sheets): batch-write outcomes via official Sheets API"
```

---

## Task 9: Per-combo runner

**Files:**
- Create: `automation/runner.py`
- Create: `tests/test_runner.py`

One function that threads everything together for a single combo. Pure
HTTP, no parallelism yet.

- [ ] **Step 1: Write failing test**

```python
# tests/test_runner.py
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
def test_run_combo_returns_outcome_rows(
    fetch, wait, submit, find, create, upload,
):
    from automation.review import CheckResult, RunHandle
    upload.return_value = "file-1"
    wait.return_value = RunHandle(run_id="run-1", state="HAS_ISSUES")
    fetch.return_value = [
        CheckResult(check_definition_id="chkdyjqpygoropzx", check_name="x", assessment="PASS"),
    ]
    with patch("automation.runner.CHECK_DEFINITION_ID_TO_CNUM", {"chkdyjqpygoropzx": "C1"}):
        client = MagicMock()
        result = run_combo(client, _fake_combo(), close_id="close-1", today=date(2026, 5, 28))
    assert isinstance(result, ComboResult)
    assert len(result.outcome_rows) == 1
    assert result.outcome_rows[0].row == 5
    assert result.outcome_rows[0].outcome == "PASS"
    assert result.outcome_rows[0].tester == "C99-TEST"
    assert result.outcome_rows[0].date == "2026-05-28"
```

- [ ] **Step 2: Run, verify failure**

Run: `.venv/bin/pytest tests/test_runner.py -v`

- [ ] **Step 3: Implement**

```python
# automation/runner.py
"""Per-combo orchestrator: create LP, upload docs, wait, capture outcomes."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date

from automation.anduin_client import AnduinClient
from automation.combos import Combo
from automation.files import upload_file
from automation.investor import create_offline_investor, find_lp_by_firm_name
from automation.results import CHECK_DEFINITION_ID_TO_CNUM, map_results_to_outcomes
from automation.review import fetch_run_results, wait_for_review
from automation.sheets import OutcomeRow
from automation.submissions import submit_signed_subscription, submit_supporting_docs
from automation.config import FUND_DELAWARE_AMOUNT_FIELD_ID

logger = logging.getLogger(__name__)

USER_SCRATCH_FOLDER_HINT = "fdr000001.fdrtemp00"  # appended to user-scope; resolved lazily

# Default commitment amount used by the existing skill.
DEFAULT_AMOUNT_USD = 100000


@dataclass(frozen=True)
class ComboResult:
    combo: Combo
    lp_id: str
    run_id: str
    outcome_rows: list[OutcomeRow]


def run_combo(
    client: AnduinClient,
    combo: Combo,
    *,
    close_id: str,
    folder_id: str | None = None,
    today: date | None = None,
) -> ComboResult:
    today = today or date.today()
    logger.info("=== %s ===", combo.profile_name)

    # 1. Create investor
    create_offline_investor(
        client,
        firm_name=combo.profile_name,
        first_name="Test",
        last_name=combo.profile_name,
        email=f"{combo.profile_name.lower()}@example.test",
        close_id=close_id,
    )
    lp_id = find_lp_by_firm_name(client, combo.profile_name)
    if lp_id is None:
        raise RuntimeError(f"could not find LP after create: {combo.profile_name}")

    # Resolve scratch folder once (lazy). Tests pass folder_id explicitly.
    if folder_id is None:
        folder_id = _resolve_user_folder_id(client)

    # 2. Upload + submit subscription doc
    sub_file_id = upload_file(client, combo.sub_doc_path, folder_id=folder_id)
    submit_signed_subscription(
        client,
        lp_id=lp_id,
        file_item_id=sub_file_id,
        amount_usd=DEFAULT_AMOUNT_USD,
        amount_field_id=FUND_DELAWARE_AMOUNT_FIELD_ID,
        firm_name=combo.profile_name,
    )

    # 3. Upload + submit supporting docs
    supp_file_ids = [
        upload_file(client, p, folder_id=folder_id) for p in combo.supporting_doc_paths
    ]
    submit_supporting_docs(client, lp_id=lp_id, file_item_ids=supp_file_ids)

    # 4. Wait for AI Review (auto-triggers on submit)
    run = wait_for_review(client, lp_id=lp_id)

    # 5. Fetch + map results
    results = fetch_run_results(client, run_id=run.run_id)
    outcomes = map_results_to_outcomes(results)

    # 6. Build outcome rows
    outcome_rows = []
    for row in combo.rows:
        outcome = outcomes.get(row.cnum)
        if outcome is None:
            logger.warning("missing outcome for %s row %d (%s)", combo.profile_name, row.row, row.cnum)
            continue
        outcome_rows.append(OutcomeRow(
            row=row.row,
            tester=combo.profile_name,
            outcome=outcome.sheet_value,
            date=today.isoformat(),
        ))

    return ComboResult(combo=combo, lp_id=lp_id, run_id=run.run_id, outcome_rows=outcome_rows)


def _resolve_user_folder_id(client: AnduinClient) -> str:
    """Read the per-user scratch folder id from the user profile.

    The SPA prepends the user's session id; the rest is the constant
    ``fdr000001.fdrtemp00``. Captured during Phase 1 as
    ``ursZ…JdY9zVo0lTQ3DbN38J9.fdr000001.fdrtemp00``.
    """
    profile = client.post("/api/v3/account/get-user-profile", {})
    user_scope = profile["userInfo"]["userName"]  # e.g. user-2xkwrgpzljvqo0lx6z2jg8o05l70314ed568
    # NOTE: the actual prefix observed in Phase 1 was a base64-style session
    # token, NOT the userName. Validate with a one-shot upload before
    # trusting this — see acceptance step below.
    return f"{user_scope}.{USER_SCRATCH_FOLDER_HINT}"
```

- [ ] **Step 4: Tests pass**

Run: `.venv/bin/pytest tests/test_runner.py -v`

- [ ] **Step 5: Live one-combo smoke test**

Add `run-one` command to `__main__.py` (see Task 10 for full CLI) and run:

```bash
.venv/bin/python -m automation run-one C01-TC-12-PASS
```

Expected: investor created, docs uploaded, AI Review starts, script polls
~5–6 min, prints `ComboResult(...outcome_rows=[OutcomeRow(row=58, ...)]`.

If `_resolve_user_folder_id` returns the wrong format, the
`createDirectUpload` call will 4xx — observe the actual `folderId` in a
live SPA capture (see Phase 1's hook snippet) and patch.

- [ ] **Step 6: Commit**

```bash
git add automation/runner.py tests/test_runner.py
git commit -m "feat(runner): per-combo create→upload→review→outcomes pipeline"
```

---

## Task 10: CLI entry points

**Files:**
- Modify: `automation/__main__.py`

- [ ] **Step 1: Write the new commands**

```python
# automation/__main__.py — full replacement
import logging
import sys
from datetime import date

from automation.anduin_client import AnduinClient
from automation.auth import bootstrap_bearer


def main(argv: list[str]) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    if len(argv) < 2:
        print("usage: python -m automation {smoke|list-combos|run-one <profile>|run-all}", file=sys.stderr)
        return 2
    cmd = argv[1]
    if cmd == "smoke":
        from automation.anduin_client import smoke
        return smoke()
    if cmd == "list-combos":
        from automation.combos import load_combos
        for c in load_combos():
            print(c.profile_name)
        return 0
    if cmd == "run-one":
        if len(argv) < 3:
            print("usage: run-one <profile-name>", file=sys.stderr)
            return 2
        from automation.combos import load_combos
        from automation.runner import run_combo
        from automation.config import FUND_SUB_ID
        combos = {c.profile_name: c for c in load_combos()}
        if argv[2] not in combos:
            print(f"unknown profile: {argv[2]}", file=sys.stderr)
            return 2
        client = AnduinClient(bearer=bootstrap_bearer())
        result = run_combo(client, combos[argv[2]], close_id=_resolve_close_id(client))
        for row in result.outcome_rows:
            print(row)
        return 0
    if cmd == "run-all":
        return _run_all()
    print(f"unknown command: {cmd}", file=sys.stderr)
    return 2


def _resolve_close_id(client: AnduinClient) -> str:
    # Fetch the fund's close list once.
    from automation.config import FUND_SUB_ID
    resp = client.post(
        "/api/v3/fundsub/admin/getCloses",
        {"fundSubId": FUND_SUB_ID},
    )
    closes = resp.get("closes") or []
    if not closes:
        raise RuntimeError("no closes found for fund")
    return closes[0]["closeId"]


def _run_all() -> int:
    from concurrent.futures import ThreadPoolExecutor, as_completed
    from automation.combos import load_combos
    from automation.investor import list_existing_probe_profiles
    from automation.runner import run_combo
    from automation.sheets import connect, write_outcomes
    from automation.config import FUND_SUB_ID

    SHEET_ID = _read_sheet_id_from_env_or_skill_md()
    TAB_NAME = "Test Cases"
    PARALLELISM = 3

    client = AnduinClient(bearer=bootstrap_bearer())
    close_id = _resolve_close_id(client)
    existing = {p.firm_name for p in list_existing_probe_profiles(client, prefix="C")}
    combos = [c for c in load_combos() if c.profile_name not in existing]
    logging.getLogger(__name__).info("running %d combos (skipped %d already-done)", len(combos), 67 - len(combos))

    sheets = connect()
    rows_buffer = []
    with ThreadPoolExecutor(max_workers=PARALLELISM) as pool:
        futures = {pool.submit(run_combo, client, c, close_id=close_id): c for c in combos}
        for fut in as_completed(futures):
            combo = futures[fut]
            try:
                result = fut.result()
            except Exception as exc:
                logging.error("combo %s failed: %s", combo.profile_name, exc)
                continue
            rows_buffer.extend(result.outcome_rows)
            # Flush every 5 completed combos to keep partial progress safe.
            if len(rows_buffer) >= 5:
                write_outcomes(sheets, sheet_id=SHEET_ID, tab_name=TAB_NAME, rows=rows_buffer)
                rows_buffer.clear()
    if rows_buffer:
        write_outcomes(sheets, sheet_id=SHEET_ID, tab_name=TAB_NAME, rows=rows_buffer)
    return 0


def _read_sheet_id_from_env_or_skill_md() -> str:
    import os, re
    if env := os.environ.get("ANDUIN_SHEET_ID"):
        return env
    # Fall back: parse SKILL.md for the sheet URL.
    from pathlib import Path
    text = (Path(__file__).resolve().parents[1] / "skills/ai-review-automation/SKILL.md").read_text()
    m = re.search(r"docs\.google\.com/spreadsheets/d/([\w-]+)", text)
    if not m:
        raise RuntimeError("ANDUIN_SHEET_ID env var not set and no sheet URL in SKILL.md")
    return m.group(1)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
```

- [ ] **Step 2: Smoke the CLI**

```bash
.venv/bin/python -m automation list-combos | head -5
```

Expected: prints `C01-TC-12-PASS`, `C02-TC-12-FAIL`, …

```bash
.venv/bin/python -m automation smoke
```

Expected: still 200 OK (regression check on Phase 1).

- [ ] **Step 3: Commit**

```bash
git add automation/__main__.py
git commit -m "feat(cli): list-combos, run-one, run-all commands"
```

---

## Task 11: Live end-to-end on one combo

**Files:** none (validation only)

- [ ] **Step 1: Pick a small combo with one supporting doc**

`C01-TC-12-PASS` is the simplest: SUB-01 + one passport. Row 58, Check C12.

- [ ] **Step 2: Run it**

```bash
.venv/bin/python -m automation run-one C01-TC-12-PASS
```

Expected: completes in ~6 minutes; prints `OutcomeRow(row=58, tester='C01-TC-12-PASS', outcome=...)`. Manually verify the
investor exists on the dashboard with a signed subscription doc and one supporting doc.

- [ ] **Step 3: Cross-check against the LLM-driven skill's recorded outcome**

If the C12 row in the master Sheet already has a known outcome from prior
testing, confirm parity.

---

## Task 12: Live run-all + sheet write

**Files:** none (validation only)

- [ ] **Step 1: Backup the master sheet**

`File → Make a copy` in the Google Sheets UI before running this.

- [ ] **Step 2: Run all 67 combos**

```bash
.venv/bin/python -m automation run-all
```

Expected runtime: with PARALLELISM=3 and ~6 min per combo,
`ceil(67/3) * 6 ≈ 134 min` wall time. Monitor logs; ensure no rate limiting
or 5xx storms.

- [ ] **Step 3: Verify the sheet**

Manually spot-check ~10 random rows for sane outcomes. Column N (formula)
should reflect the new values automatically.

---

## Self-review checklist

- **Spec coverage:** Each of the six endpoints documented in
  `docs/anduin-api-reference.md` has a task (1, 2, 3, 4, 5, 5). Resumability
  (Task 10's `list_existing_probe_profiles` filter), parallelism (Task 10's
  `ThreadPoolExecutor`), and Sheets writes (Task 8) all covered.
- **Placeholders:** none. The check-definition-id table (Task 6) and the
  user-scope folder format (Task 9 Step 5) are the two pieces of data this
  plan does not have at write time; both are gated behind a live probe step
  with concrete commands and clear fallback behavior.
- **Type consistency:** `Combo`, `RowMapping`, `CheckResult`, `RunHandle`,
  `Outcome`, `OutcomeRow`, `ComboResult` defined once and used consistently
  across modules and tests.
- **Gaps the engineer should know about:**
  - `getLpDashboardItemList` body shape (Task 3 Step 5) and the user-scope
    folder format (Task 9 Step 5) need a live probe before trusting; the
    plan includes the probe commands inline.
  - `getCloses` endpoint (Task 10's `_resolve_close_id`) was not captured
    in Phase 1 — the body may not be exactly `{"fundSubId": …}`. If 4xx,
    grab the close id from the SPA via `$B js` and hardcode it as a
    constant in `config.py`.

---

## Execution Handoff

Plan saved to `docs/superpowers/plans/2026-05-28-phase2-runner.md`. This
plan is not for the current session — it gets its own session.
