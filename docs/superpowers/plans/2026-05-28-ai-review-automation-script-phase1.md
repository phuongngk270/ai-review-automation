# AI Review Automation Script — Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stand up a Python project that can authenticate to the Anduin GP platform with cookies imported from Chrome, run smoke calls against the live REST API, and produce a fully-documented endpoint reference covering the six write operations the combo runner will need (create offline investor, upload subscription doc, send-to-fund-managers, upload supporting doc, trigger AI Review, fetch AI Review results). The reference becomes the input to a Phase 2 plan that builds the actual 67-combo runner.

**Architecture:** Single-process Python script. Auth via `stargazer_cookie` + `CF_Authorization` extracted from the user's Chrome through `gstack-browse cookie-import-browser` and read out as JSON. Requests via `requests.Session` so cookies and headers are reused. Logging on every call (method, URL, status, body sizes) so future contract breaks are obvious. Endpoint discovery is done by driving one full real combo manually via `gstack-browse` while a network capture runs, then parsing the capture into a Markdown reference doc.

**Tech Stack:** Python 3.11+, `requests`, `pytest`, `gstack-browse` (for cookie refresh and network capture). No Selenium, Playwright, or LLM at runtime.

---

## File Structure

- `automation/__init__.py` — package marker
- `automation/cookies.py` — pull live Anduin cookies from Chrome via `gstack-browse`
- `automation/anduin_client.py` — `requests.Session` wrapper with logging and auth-cookie injection
- `automation/__main__.py` — Phase 1 CLI: `python -m automation smoke` runs the auth smoke test
- `tests/__init__.py`
- `tests/test_cookies.py`
- `tests/test_anduin_client.py`
- `requirements.txt`
- `docs/anduin-api-reference.md` — produced by the probe task; Phase 2 plan reads from this

---

## Task 1: Project Scaffold

**Files:**
- Create: `automation/__init__.py`
- Create: `automation/__main__.py`
- Create: `tests/__init__.py`
- Create: `requirements.txt`
- Create: `pytest.ini`
- Create: `.gitignore`

- [ ] **Step 1: Create the directory structure and empty files**

```bash
cd "/Users/phuongnguyen/Documents/Claude/Projects/Testing review agent"
mkdir -p automation tests
touch automation/__init__.py tests/__init__.py
```

- [ ] **Step 2: Write `requirements.txt`**

```
requests==2.32.3
pytest==8.3.3
```

- [ ] **Step 3: Write `pytest.ini`**

```ini
[pytest]
testpaths = tests
python_files = test_*.py
addopts = -v
```

- [ ] **Step 4: Write `.gitignore`**

```
__pycache__/
*.pyc
.venv/
.pytest_cache/
.cookies-cache.json
```

- [ ] **Step 5: Write a minimal `automation/__main__.py`**

```python
import sys


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("usage: python -m automation <command>", file=sys.stderr)
        return 2
    cmd = argv[1]
    if cmd == "smoke":
        from automation.anduin_client import smoke
        return smoke()
    print(f"unknown command: {cmd}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
```

- [ ] **Step 6: Create and activate a venv, install deps**

Run:
```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

Expected: `Successfully installed requests-2.32.3 pytest-8.3.3` (plus transitive deps).

- [ ] **Step 7: Verify pytest runs (no tests yet)**

Run: `.venv/bin/pytest`
Expected: `no tests ran` exit code 5. That's fine — the suite is wired up.

- [ ] **Step 8: Initialize git and commit**

```bash
git init
git add automation tests requirements.txt pytest.ini .gitignore
git commit -m "feat: scaffold automation package"
```

---

## Task 2: Cookie Extraction Helper

**Files:**
- Create: `automation/cookies.py`
- Test: `tests/test_cookies.py`

The helper shells out to `gstack-browse` to import Chrome's Anduin cookies into the browse session, then reads them as JSON. This gives the script a fresh `stargazer_cookie` + `CF_Authorization` every run without re-implementing Chrome's encrypted cookie store.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_cookies.py
from automation.cookies import parse_cookies_json


def test_parse_cookies_json_extracts_required_cookies():
    payload = [
        {"name": "CF_Authorization", "value": "cf-token", "domain": "fundsub-minas-tirith.anduin.dev"},
        {"name": "stargazer_cookie", "value": "sg-token", "domain": "fundsub-minas-tirith.anduin.dev"},
        {"name": "unrelated", "value": "x", "domain": "other.example.com"},
    ]
    cookies = parse_cookies_json(payload, domain="fundsub-minas-tirith.anduin.dev")
    assert cookies == {"CF_Authorization": "cf-token", "stargazer_cookie": "sg-token"}


def test_parse_cookies_json_raises_when_session_missing():
    payload = [
        {"name": "CF_Authorization", "value": "cf-token", "domain": "fundsub-minas-tirith.anduin.dev"},
    ]
    import pytest
    with pytest.raises(RuntimeError, match="stargazer_cookie"):
        parse_cookies_json(payload, domain="fundsub-minas-tirith.anduin.dev")
```

- [ ] **Step 2: Run the test, confirm it fails**

Run: `.venv/bin/pytest tests/test_cookies.py -v`
Expected: `ModuleNotFoundError: No module named 'automation.cookies'`.

- [ ] **Step 3: Write `automation/cookies.py`**

```python
"""Pull Anduin cookies from the user's Chrome via gstack-browse."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

REQUIRED = ("CF_Authorization", "stargazer_cookie")

BROWSE_BIN = Path(os.environ.get(
    "GSTACK_BROWSE",
    Path.home() / ".claude/skills/gstack/browse/dist/browse",
))


def parse_cookies_json(payload: list[dict], domain: str) -> dict[str, str]:
    """Filter the gstack-browse cookies JSON down to the cookies we need for *domain*."""
    matched: dict[str, str] = {}
    for entry in payload:
        if entry.get("domain") != domain:
            continue
        name = entry.get("name")
        if name in REQUIRED:
            matched[name] = entry["value"]
    missing = [c for c in REQUIRED if c not in matched]
    if missing:
        raise RuntimeError(
            f"Missing required cookies for {domain}: {', '.join(missing)}. "
            "Open the Anduin GP dashboard in Chrome and log in, then retry."
        )
    return matched


def refresh_and_load(domain: str = "fundsub-minas-tirith.anduin.dev") -> dict[str, str]:
    """Re-import Chrome cookies into gstack-browse for *domain* and return them as a dict."""
    if not BROWSE_BIN.exists():
        raise RuntimeError(f"gstack-browse binary not found at {BROWSE_BIN}")
    # Navigate first so the import has a current page domain to validate against.
    subprocess.run([str(BROWSE_BIN), "goto", f"https://{domain}/"], check=True, capture_output=True)
    subprocess.run(
        [str(BROWSE_BIN), "cookie-import-browser", "chrome", "--domain", domain],
        check=True, capture_output=True,
    )
    out = subprocess.run(
        [str(BROWSE_BIN), "cookies"], check=True, capture_output=True, text=True,
    )
    payload = json.loads(out.stdout)
    return parse_cookies_json(payload, domain=domain)
```

- [ ] **Step 4: Re-run the unit test, confirm it passes**

Run: `.venv/bin/pytest tests/test_cookies.py -v`
Expected: 2 passed.

- [ ] **Step 5: Manual smoke run against real Chrome**

Run: `.venv/bin/python -c "from automation.cookies import refresh_and_load; print(list(refresh_and_load().keys()))"`
Expected: `['CF_Authorization', 'stargazer_cookie']`. If Chrome prompts for Keychain access, approve once.

- [ ] **Step 6: Commit**

```bash
git add automation/cookies.py tests/test_cookies.py
git commit -m "feat: cookie extraction helper via gstack-browse"
```

---

## Task 3: HTTP Client Wrapper

**Files:**
- Create: `automation/anduin_client.py`
- Test: `tests/test_anduin_client.py`

A thin `requests.Session` wrapper that injects auth cookies and logs every request. The `smoke()` function calls `/api/v3/account/get-user-profile` — the lightest read endpoint we already observed during the probe — to confirm auth works end-to-end.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_anduin_client.py
from unittest.mock import patch, MagicMock

from automation.anduin_client import AnduinClient


def test_post_includes_auth_cookies():
    cookies = {"CF_Authorization": "cf", "stargazer_cookie": "sg"}
    client = AnduinClient(cookies=cookies, base_url="https://example.test")
    with patch.object(client.session, "post") as post:
        post.return_value = MagicMock(status_code=200, text="ok", json=lambda: {"ok": True})
        client.post("/api/v3/account/get-user-profile", json={})
        args, kwargs = post.call_args
        assert args[0] == "https://example.test/api/v3/account/get-user-profile"
        # cookies live on session.cookies, set in __init__; verify they are there
        assert client.session.cookies.get("CF_Authorization") == "cf"
        assert client.session.cookies.get("stargazer_cookie") == "sg"


def test_post_raises_on_non_2xx():
    client = AnduinClient(cookies={"CF_Authorization": "x", "stargazer_cookie": "y"}, base_url="https://example.test")
    with patch.object(client.session, "post") as post:
        post.return_value = MagicMock(status_code=401, text="unauthorized")
        import pytest
        with pytest.raises(RuntimeError, match="401"):
            client.post("/api/v3/account/get-user-profile", json={})
```

- [ ] **Step 2: Run the test, confirm it fails**

Run: `.venv/bin/pytest tests/test_anduin_client.py -v`
Expected: `ModuleNotFoundError: No module named 'automation.anduin_client'`.

- [ ] **Step 3: Write `automation/anduin_client.py`**

```python
"""HTTP client for the Anduin GP platform."""

from __future__ import annotations

import logging
import sys
from typing import Any

import requests

from automation.cookies import refresh_and_load

logger = logging.getLogger(__name__)


class AnduinClient:
    def __init__(self, cookies: dict[str, str], base_url: str = "https://fundsub-minas-tirith.anduin.dev") -> None:
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        for name, value in cookies.items():
            # Set with no explicit domain so requests sends them to any host this session talks to.
            self.session.cookies.set(name, value)
        self.session.headers.update({
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "anduin-automation/0.1 (+phase1-smoke)",
        })

    def post(self, path: str, json: dict[str, Any] | None = None) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        logger.info("POST %s body=%d bytes", url, len(str(json or "")))
        resp = self.session.post(url, json=json or {})
        logger.info("  -> %d %d bytes", resp.status_code, len(resp.text))
        if not (200 <= resp.status_code < 300):
            raise RuntimeError(f"{resp.status_code} from {path}: {resp.text[:200]}")
        if resp.text:
            return resp.json()
        return {}


def smoke() -> int:
    """Phase 1 acceptance: fetch the logged-in user profile via /api/v3."""
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    cookies = refresh_and_load()
    client = AnduinClient(cookies=cookies)
    profile = client.post("/api/v3/account/get-user-profile", json={})
    print(profile, file=sys.stdout)
    if "email" in profile or "userId" in profile or "id" in profile:
        return 0
    print("WARN: profile response did not include an obvious user identifier", file=sys.stderr)
    return 1
```

- [ ] **Step 4: Re-run the unit tests, confirm they pass**

Run: `.venv/bin/pytest tests/test_anduin_client.py -v`
Expected: 2 passed.

- [ ] **Step 5: Smoke run against the live platform**

Run: `.venv/bin/python -m automation smoke`
Expected: prints a JSON object containing your user profile (email `phuongnguyen@anduintransact.com` should appear), exit code 0.
If you see `401` or `400`, the cookies have expired — open Chrome, reload the GP dashboard, retry.

- [ ] **Step 6: Commit**

```bash
git add automation/anduin_client.py automation/__main__.py tests/test_anduin_client.py
git commit -m "feat: anduin http client + smoke command"
```

---

## Task 4: Endpoint Discovery Probe

This task captures the six write endpoints by performing one full real combo end-to-end through `gstack-browse` while logging network traffic. Pick a low-stakes combo: **C01 (sub doc + one passport)** — a single supporting doc, a single result row to verify.

**Files:**
- Create: `docs/anduin-api-reference.md`
- Create: `automation/probe_capture.py` — small helper that polls `gstack-browse network` and snapshots the log to disk
- Test: none (this task is observation, not code under test)

- [ ] **Step 1: Write the network snapshot helper**

```python
# automation/probe_capture.py
"""Snapshot gstack-browse's network log to a file."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from automation.cookies import BROWSE_BIN


def snapshot(path: Path) -> None:
    out = subprocess.run([str(BROWSE_BIN), "network"], check=True, capture_output=True, text=True)
    path.write_text(out.stdout)
    print(f"wrote {len(out.stdout)} bytes to {path}", file=sys.stderr)


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("usage: python -m automation.probe_capture <out-path>", file=sys.stderr)
        return 2
    snapshot(Path(argv[1]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
```

- [ ] **Step 2: Open the GP dashboard in `gstack-browse` and clear the network buffer**

```bash
B=$HOME/.claude/skills/gstack/browse/dist/browse
$B cookie-import-browser chrome --domain fundsub-minas-tirith.anduin.dev
$B goto "https://fundsub-minas-tirith.anduin.dev/#/entd5ev6mge1xndv/txnqxned8j9qx1yp.fsbkg78?tab=ad"
sleep 3
$B network --clear
```

- [ ] **Step 3: Drive the create-investor flow manually**

Follow Stages 2–3 of the original skill in `gstack-browse`:
- Click "+ Add investor" → "Track offline subscriptions"
- Fill the modal with profile name `C01-TC-12-PASS`, contact `Phuong / Nguyen / phuongnguyen@anduintransact.com`
- Click "Add"
- Hover the new row → "View details" → "···" → "Access investor's subscription"

Use `$B snapshot -i` + `$B click @eN` for each click.

After the LP page loads, snapshot the network and label it:
```bash
.venv/bin/python -m automation.probe_capture /tmp/probe-01-create-investor.log
$B network --clear
```

- [ ] **Step 4: Drive the subscription PDF upload**

Follow Stage 4 in `gstack-browse`. Use the same Uppy injection from the original skill (`anduin-file-button` won't work — keep the JS injection). After the modal closes and the status reads "Pending approval", snapshot:

```bash
.venv/bin/python -m automation.probe_capture /tmp/probe-02-upload-sub.log
$B network --clear
```

- [ ] **Step 5: Drive the supporting-doc upload**

Follow Stage 5 once, with `ID/ID-01_Passport_JohnSmith_Valid.pdf`. After the "Document submitted" toast:

```bash
.venv/bin/python -m automation.probe_capture /tmp/probe-03-upload-supporting.log
$B network --clear
```

- [ ] **Step 6: Trigger AI Review from the GP side**

Navigate back to the dashboard, open the investor's side panel, click "AI Review" → "Run AI Review". Once the spinner starts:

```bash
.venv/bin/python -m automation.probe_capture /tmp/probe-04-trigger-review.log
$B network --clear
```

- [ ] **Step 7: Wait for the AI Review to finish, then capture the fetch-results traffic**

After ~5–6 minutes, refresh the AI Review tab so the fetch calls fire freshly:

```bash
$B reload
sleep 5
.venv/bin/python -m automation.probe_capture /tmp/probe-05-fetch-results.log
```

- [ ] **Step 8: Write `docs/anduin-api-reference.md`**

Open each `/tmp/probe-0*-*.log` and identify the actionable POST(s) per stage. For each, record:
- HTTP method + URL
- Trigger (what UI action fires it)
- Request body shape (representative JSON, with values redacted where they contain PII)
- Response status + body shape
- Notes (auth headers beyond cookies, anti-CSRF tokens, idempotency keys)

Use the request body / response body retrieved by running `$B cdp Network.getResponseBody '{"requestId":"..."}'` for any call whose body the basic `network` command did not include. For each captured call also note whether the upload-related calls use direct-to-S3 (look for `*.amazonaws.com` PUTs), TUS (`Upload-Length` / `Tus-Resumable` headers), or multipart to an Anduin endpoint.

The doc must have one section per endpoint:

```markdown
## createOfflineInvestor

- **Trigger:** "+ Add investor" → "Track offline subscriptions" → "Add"
- **Method + URL:** POST https://fundsub-minas-tirith.anduin.dev/api/v3/<path-from-probe>
- **Request body:**
  ```json
  { "investmentEntity": "C01-TC-12-PASS", "contactFirstName": "...", ... }
  ```
- **Response:**
  ```json
  { "lpId": "...", ... }
  ```
- **Notes:** ...
```

Sections required: `createOfflineInvestor`, `accessInvestorSubscription` (if it requires an API call beyond the URL pattern), `uploadSubscriptionDoc` (and any prerequisite presigned-url or init calls), `sendToFundManagers`, `uploadSupportingDoc` (and any prerequisites), `triggerAiReview`, `fetchAiReviewResults`.

- [ ] **Step 9: Commit**

```bash
git add automation/probe_capture.py docs/anduin-api-reference.md
git commit -m "docs: captured anduin API reference from probe combo C01"
```

---

## Task 5: Acceptance Check

The phase is complete when all of the following are true. Verify each line, do not skip.

- [ ] `python -m automation smoke` prints a real user profile and exits 0.
- [ ] `docs/anduin-api-reference.md` has a section per endpoint listed in Task 4 Step 8, each with a real request body and real response body.
- [ ] The upload mechanism is classified as one of: direct-to-S3 presigned, TUS, or Anduin-multipart. The classification is written in the reference doc.
- [ ] At least one combo (C01) has actually completed end-to-end in the platform, proving the manually-driven flow works as a baseline before automating it.
- [ ] All tests pass: `.venv/bin/pytest -v` → green.

If anything in Task 5 fails, do not move to Phase 2 — fix it first.

---

## Phase 2 Preview (not part of this plan)

After this phase produces `docs/anduin-api-reference.md`, a separate plan (`2026-05-28-ai-review-automation-script-phase2.md`) will be written covering:
- Implementations for each captured endpoint as methods on `AnduinClient`
- The combo lookup table (already in the original skill) ported to a Python data structure
- The 67-combo runner with parallelism, resumability, and the Google Sheets writer
- Stage 7 result parsing from the real `fetchAiReviewResults` payload

The Phase 2 plan can quote real JSON because the reference doc will exist by then.

---

## Self-Review Notes

- **Spec coverage:** the spec's "Plan of attack" item 1 (endpoint discovery probe) maps to Task 4; items 2–5 are deferred to Phase 2 as explicitly noted. The probe step is the gating dependency for the rest of the spec, so a Phase 1 / Phase 2 split is the correct decomposition.
- **No placeholders:** the only "fill from probe" content is inside `docs/anduin-api-reference.md`, which is the *output* of this plan, not a code placeholder. All Python code in the plan is complete.
- **Type consistency:** `parse_cookies_json` returns `dict[str, str]`, consumed by `AnduinClient(cookies=...)` as `dict[str, str]`. `refresh_and_load()` returns the same type. Consistent.
