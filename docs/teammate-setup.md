# Teammate setup: AI Review test runner

One-time setup so you can run `/run-test-combo` (or the underlying CLI) on your machine. Budget ~30 minutes the first time, then it's a one-command flow.

## What you'll be able to do

After setup, asking Claude/Sonnet "use /run-test-combo to run the next testing profile" will:
- create a fresh investor on the Magma Capital fund
- upload the subscription doc + supporting docs from the test pack
- wait ~13-15 min for the AI Review to complete
- fetch the 22 check results
- write the outcome to the master Google Sheet (Test Cases tab)

You can also drive it manually:
```bash
.venv/bin/python -m automation run-next                   # auto-pick next un-run combo
.venv/bin/python -m automation run-one C12-TC-XX-YY       # specific combo
.venv/bin/python -m automation list-combos                # list all 67
```

---

## 1. Repo + Python environment

```bash
git clone https://github.com/phuongngk270/ai-review-automation.git "Testing review agent"
cd "Testing review agent"

# Python 3.13 required (3.12 likely also works but untested)
python3.13 -m venv .venv
.venv/bin/pip install -r requirements.txt

# Verify
.venv/bin/pytest -q
# expect: 35 passed
```

If `python3.13` isn't installed on macOS: `brew install python@3.13`.

---

## 2. Test data pack

The PDFs (`AI Review Agent Test Pack/`) are gitignored — too large for the repo. Get the pack from Phuong (Slack DM or shared drive folder). Extract it at the repo root so the structure looks like:

```
Testing review agent/
├── automation/
├── AI Review Agent Test Pack/
│   └── Test Documents/
│       ├── 0. Subscription Agreements/
│       ├── 1. Tax Forms/
│       ├── 2. Withholding Statements/
│       ├── 3. Formation Documents/
│       ├── 4. Certificates of Good Standing/
│       ├── 5. Authorization Documents/
│       ├── 6. Government IDs/
│       ├── 7. Beneficial Ownership & AML/
│       └── 8. Source of Funds/
└── ...
```

Verify:
```bash
.venv/bin/python -c "from automation.combos import load_combos; [c.sub_doc_path.is_file() or print('MISSING', c.sub_doc_path) for c in load_combos()]; print('all 67 combos resolved')"
```

If anything prints `MISSING`, the test pack is incomplete — ping Phuong.

---

## 3. Anduin auth via gstack-browse

The runner needs a bearer JWT to talk to the Anduin API. It gets this by reading cookies from your Chrome browser — but it needs **gstack** installed to do that. gstack is an AI dev toolkit; you only need it for the cookie extraction step.

### 3a. Install gstack (one-time)

```bash
curl -fsSL https://install.garryslist.org | bash
```

This installs the `gstack` CLI and the headless browse daemon. After install, restart your terminal (or `source ~/.zshrc` / `source ~/.bashrc`).

Verify:
```bash
gstack --version
# expect: a version number like 5.1.0
```

If `curl` fails or you're on a managed machine, alternative: download the installer from https://garryslist.org/gstack and run it manually, or ask Phuong for the binary.

### 3b. Start the browse daemon

```bash
~/.claude/skills/gstack/browse/dist/browse status
```

If it says `NEEDS_SETUP` instead of `Status: healthy`, run:
```bash
cd ~/.claude/skills/gstack && ./setup
```

This takes ~10 seconds (installs Chromium headless). Only needed once.

### 3c. Log in to Anduin

```bash
B="$HOME/.claude/skills/gstack/browse/dist/browse"
$B goto https://fundsub-minas-tirith.anduin.dev/
```

A browser window opens. Log in with your `@anduintransact.com` Google SSO. Land on the Magma Capital - AI Agents fund dashboard (you should see the investor list).

You only need to do this once per machine. The session cookie is long-lived (~24h). If you get `401` errors later, re-run this command and log in again.

### 3d. Verify auth works end-to-end

```bash
cd "Testing review agent"
.venv/bin/python -m automation smoke
# expect: 200 OK with your profile JSON (firstName, lastName, email), exit 0
```

If smoke fails:
- `CalledProcessError` on `cookie-import-browser` → the browse daemon isn't running or you skipped step 3b. Re-run `$B goto https://fundsub-minas-tirith.anduin.dev/`.
- `401 from /api/...` → cookie imported but the session expired. Log in again via `$B goto ...`.
- `RuntimeError: no cookies found` → you didn't land on the Anduin dashboard in step 3c. Make sure you're fully logged in and the dashboard is visible before closing the browser window.

Do NOT proceed to step 4 until smoke passes.

---

## 4. Google Sheets OAuth

The runner writes outcomes to the master sheet using your Google account (so the edit history shows your name).

1. Open [Google Cloud Console](https://console.cloud.google.com/).
2. Create a project (or reuse one). Name doesn't matter — only you see it.
3. **APIs & Services → Library → search "Google Sheets API" → Enable.**
4. **APIs & Services → OAuth consent screen:**
   - User type: **Internal** if anduintransact is a Workspace (recommended) or **External** otherwise
   - App name: `anduin-automation-local` (anything works)
   - If External: add yourself under "Test users"
5. **APIs & Services → Credentials → Create Credentials → OAuth client ID:**
   - Application type: **Desktop app**
   - Name: `anduin-automation-local`
   - Click **Create** → **Download JSON**
6. Save the downloaded file to this exact path:
   ```
   ~/.cache/anduin-automation/oauth-client.json
   ```
   On macOS, the `.cache` folder is hidden. Quickest path:
   ```bash
   mkdir -p ~/.cache/anduin-automation && open ~/.cache/anduin-automation
   ```
   …then drag the downloaded JSON into the Finder window that opens. Rename to `oauth-client.json` if the filename is different.

First run consents your account:
```bash
.venv/bin/python -c "from automation.sheets import connect; connect(); print('OAuth OK')"
# A browser tab opens. Click through the consent screen.
# After consent, a token is cached at ~/.cache/anduin-automation/sheets-token.json.
# Subsequent runs are silent.
```

If you see a Google warning about "unverified app" (External consent screens), it's fine — click "Advanced → Go to anduin-automation-local". You're approving your own app to write to your own sheet.

You also need **edit** permission on the master sheet:
- Sheet: `https://docs.google.com/spreadsheets/d/1JbnPEFkSe0tbQwEcAYXHZM_PU-B2kBRKb5k9nRyF8Ks`
- Ask Phuong to grant your anduintransact account Editor access.

---

## 5. Verify end-to-end (dry run, no live API)

```bash
cd "Testing review agent"
.venv/bin/pytest -q                              # 35 passed
.venv/bin/python -m automation smoke             # 200 OK, profile dump
.venv/bin/python -m automation list-combos | wc -l   # 67
```

If all three are green, you're done with setup.

---

## 6. Run your first combo

```bash
.venv/bin/python -m automation run-next
```

This will:
- Pick the first un-run combo from the 67
- Create the investor, upload docs, wait ~13-15 min for AI Review, fetch results, write the outcome row(s) to the sheet
- Print `OutcomeRow(...)` lines and a `wrote N row(s) to sheet ...` confirmation

Wall time: ~15 minutes. Don't sleep the laptop during this — the polling pauses on sleep and may fail when waking. Use `caffeinate -i` on macOS:
```bash
caffeinate -i .venv/bin/python -m automation run-next
```

---

## 7. From Claude / Sonnet sessions

Once setup is done, in any Claude Code session opened from this repo:

> Use /run-test-combo to run the next testing profile.

Sonnet reads `skills/run-test-combo/SKILL.md` and executes the command above.

For batch runs (all remaining combos, ~4-5 hours wall time):

> Use /run-test-combo to run all remaining combos.

(Translates to `.venv/bin/python -m automation run-all` — writes outcomes to the sheet as combos complete, flushing every 5.)

---

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `pytest` fails | Stale .pyc or missing dep | `rm -rf automation/__pycache__ tests/__pycache__ && .venv/bin/pip install -r requirements.txt` |
| `smoke` returns 401 | Bearer JWT expired | Re-login in `$B goto https://fundsub-minas-tirith.anduin.dev/` |
| `smoke` returns "cookie-import-browser" error | gstack-browse session not logged in | Open the Anduin SPA in `$B` and sign in |
| `connect()` opens browser but errors | OAuth consent screen not configured | Step 4.4 above — add yourself as test user (External) or make the app Internal |
| `RuntimeError: 403` writing to sheet | No edit permission on master sheet | Ask Phuong to grant Editor access |
| `RuntimeError: could not find LP after create` | Dashboard eventual consistency, very rare | Re-run the same `run-next` — idempotency picks up the just-created LP |
| `RuntimeError: upload async-fetch did not complete within 60s` | Slow CloudFront upload | Re-run; idempotency reuses the investor |
| `TimeoutError: AI review did not complete within 900s` | AI Review server-side hang | Check the SPA's AI Review tab manually; if stuck there too, ping Anduin team. Otherwise bump `timeout` in `automation/review.py:wait_for_review` and retry |
| Investor appears on dashboard with status=1 and no docs | Run was interrupted mid-pipeline | Manually delete via SPA (dashboard → row → ellipsis → Remove from fund) before re-running |

---

## What you should NOT do

- **Don't run `run-all` unattended overnight without confirming.** Each combo creates a permanent investor on the shared dashboard. Run-all + 67 combos = ~80-100 sheet rows updated and ~60 new investors on the dashboard. Coordinate with the team before kicking it.
- **Don't modify the test PDFs.** They're the controlled inputs the expected outcomes assume.
- **Don't share your OAuth `oauth-client.json` or `sheets-token.json`.** Each teammate creates their own. The token is bound to your Google account.
- **Don't push commits that include `~/.cache/anduin-automation/*` or the test pack.** Both are gitignored — verify with `git status` before pushing.

---

## Architecture pointer

If you need to understand or modify the runner:
- **API endpoints**: `docs/anduin-api-reference.md` — every request/response shape captured live
- **Plan**: `docs/superpowers/plans/2026-05-28-phase2-runner.md` — the original 12-task TDD plan
- **Tests**: `tests/` — 35 tests, all mocked. `.venv/bin/pytest -v` runs them in ~0.2s.
- **Module layout**: each `automation/*.py` file is one concern (auth, client, files, investor, submissions, review, results, combos, sheets, runner). Read in that order.
