---
name: run-test-combo
description: Run a single AI Review test combo end-to-end against the live Anduin GP API and write the outcome to the master Google Sheet. Use when asked to "run test combo C##-...", "run a test case", "run the next testing profile", "run the next combo", "execute combo XX", or "validate the AI review pipeline on profile YY".
---

# run-test-combo

Run one Anduin AI Review test combo end-to-end: create the offline investor, upload the subscription PDF, upload supporting docs, wait for AI Review to complete, fetch results, and write the outcome rows to the master Google Sheet.

## When to use

- The user names a specific combo: `C12-TC-XX-YY` or `C07-...`
- The user asks for a "smoke test" or "run a test case" on the AI Review automation
- After a code change to the runner, to validate end-to-end before re-running the full 67-combo sweep

For the full 67-combo sweep, use `python -m automation run-all` directly (4-5 hours wall time). This skill is for one-at-a-time execution.

## Prerequisites (the harness handles this — verify once)

Working directory: `/Users/phuongnguyen/Documents/Claude/Projects/Testing review agent`

Required:
- `.venv/bin/python` exists (Python 3.13, project venv)
- `.venv/bin/pytest` passes (35/35 tests)
- `~/.cache/anduin-automation/oauth-client.json` exists (Google OAuth client for Sheets)
- `~/.cache/anduin-automation/sheets-token.json` exists (cached OAuth token; if missing, the first run will open a browser for consent — must be done interactively once)
- A live `gstack-browse` session signed into the Anduin SPA (used by `automation/auth.py` to bootstrap the JWT)
- The investor named `<combo profile>` is NOT already on the dashboard, OR if it is, it's in a valid completed state (the runner is idempotent: if a matching `firmName` exists, it reuses the LP id instead of creating a duplicate)

Pre-flight check (run this once at the start of every session):

```bash
cd "/Users/phuongnguyen/Documents/Claude/Projects/Testing review agent"
.venv/bin/pytest -q                            # expect 35 passed
.venv/bin/python -m automation smoke           # expect 200 OK + user profile
```

If either fails, STOP and report. Common causes:
- pytest fails → code regression; do not run live
- smoke fails 401 → bearer JWT expired; the user needs to re-authenticate in `gstack-browse` (open the SPA, log in, then retry)
- smoke fails on network → user is offline or VPN dropped

## Execution

Two entry points. Pick based on what the user asked for.

**A. "Run the next test profile" / "run the next combo"** — the runner picks the first un-run combo for you:

```bash
.venv/bin/python -m automation run-next
```

Prints `next: C##-TC-XX-YY` then proceeds with the full pipeline. Resumability filter: any combo whose `profile_name` already appears on the dashboard (firmName) is skipped.

**B. "Run combo C##-..."** — the user named a specific one:

```bash
.venv/bin/python -m automation run-one <PROFILE_NAME>
```

`<PROFILE_NAME>` is the combo name from `automation/combos.py` (e.g. `C07-TC-12-PASS`). List options with `.venv/bin/python -m automation list-combos`.

What this command does, end to end:
1. Bootstraps a bearer JWT via `gstack-browse` (~3-5s).
2. Looks up the LP on the dashboard by `firmName`. If absent, creates it; otherwise reuses.
3. Uploads the subscription PDF (CloudFront direct upload, 4-step async, ~3-5s).
4. Submits the signed subscription doc with the default $100,000 commitment.
5. Uploads each supporting doc (same 4-step) and submits via the v2 supporting-doc endpoint.
6. Polls `/api/v3/checkreview/status` every 30s. AI Review auto-triggers on submit; if the state stays `NOT_STARTED` after 2 polls, the runner calls `/checkreview/run` as a fallback. The wait_for_review timeout is 15 minutes.
7. Fetches the run results, maps each `checkDefinitionId` to its C-number, builds `OutcomeRow`s.
8. Prints each `OutcomeRow(...)` to stdout.
9. Writes the outcome rows to the master Google Sheet's `Test Cases` tab (columns M/O/P/Q).
10. Exits 0 on success.

Wall time: **~13-15 minutes per combo** in practice (server-side AI review is the long pole; plan said 5-6 minutes but observed runs are consistently in the 12-15 minute range).

Pass `--no-sheet` after the profile name to skip the sheet write (useful for dry runs against new combos before you trust the pipeline).

## Reading the output

A combo can target one or many rows. The runner prints one `OutcomeRow` line per target row, like:

```
OutcomeRow(row=9, tester='C06-TC-01-FAIL-4', outcome='FAIL', date='2026-05-29', notes='')
wrote 1 row(s) to sheet 1JbnPEFkSe0tbQwEcAYXHZM_PU-B2kBRKb5k9nRyF8Ks
```

Map each row to expected outcome in `SKILL.md` Stage 9 (the 67-combo table) to verify. If `outcome` doesn't match `Expected\nOutcome` in column F of the sheet, that's either a bug in the test data, a bug in the AI Review, or a flake — report it; do NOT silently retry.

## Failure modes and how to handle them

**RuntimeError: 401 from /api/...** — Bearer JWT expired mid-run. The `gstack-browse` session needs to be re-authed. Ask the user to re-login in the SPA tab, then retry.

**RuntimeError: could not find LP after create** — Dashboard eventual consistency. Already retried 10×2s in the code; if it still fires, the create probably failed silently. Check the dashboard UI; if the investor exists, the issue is the dashboard query timing — wait 30s and re-run with the same profile (idempotency will reuse). If the investor does NOT exist, escalate.

**RuntimeError: upload async-fetch did not complete within 60s** — The CloudFront upload took longer than expected. The investor was created but no docs were uploaded. Re-run with the same profile — the idempotency check picks up the existing investor and tries upload again.

**TimeoutError: AI review for ... did not complete within 900s** — Server-side review is hung or unusually slow. Investigate via the AI Review tab in the SPA; if it's still running there, increase `timeout=` in `automation/review.py:wait_for_review` and retry. If the SPA shows it stuck, ping the Anduin team.

**HttpError 403 from sheets** — OAuth token revoked. Delete `~/.cache/anduin-automation/sheets-token.json` and re-run; user will be prompted to re-consent.

**Combo creates but no outcome rows printed** — All rows in `combo.rows` have a `cnum` that wasn't in the results. Print the raw results: `python -c "from automation.results import CHECK_DEFINITION_ID_TO_CNUM; print(CHECK_DEFINITION_ID_TO_CNUM)"` and check whether the fixture is missing an id. May need to add to `tests/fixtures/check_definitions.json`.

## Cleanup notes

Each run leaves an investor named `<profile>` on the GP dashboard. They accumulate. To wipe a specific test:
- Delete via the SPA: dashboard → investor row → ellipsis → "Remove from fund".
- The runner is idempotent — leaving them is harmless and is what makes `run-all` resumable.

Known leftover state in the test fund (Magma Capital - AI Agents, `txnqxned8j9qx1yp.fsbkg78`) as of 2026-05-29:
- `PROBE-API-DISCOVERY-DELETE-ME` and `PROBE-API-DISCOVERY-DELETE-ME-2` — Phase 1 endpoint discovery probes; safe to delete.
- `C01-TC-12-PASS` has two copies; one (`lppxzg4e9n`, status=1) has no docs (orphaned from the Task 11 polling-bug iteration). The other (`lpp61qwywn`, status=9) is the historical pre-Phase-2 result. Both are skipped by the resumability filter (firmName starts with `C`).
- `C05-TC-09-FAIL` (`lppjo5oql6`) has docs uploaded but no AI review ran (orphaned from the NOT_STARTED bug iteration). Delete this one before re-running C05.

## Reporting back

After a successful run, report:
- The combo that ran
- The outcome row(s) with row number, outcome value, and the expected outcome from the spec
- A one-line PASS/FAIL/MISMATCH verdict (PASS = actual == expected, MISMATCH = actual != expected, FAIL = combo errored out before producing outcomes)
- Wall time
- Sheet rows updated (M, O, P, Q on the row number(s))

Example:
> Ran `C06-TC-01-FAIL-4` in 16 min. Expected FAIL on C1 (Tax Form Field Completeness). Got `OutcomeRow(row=9, outcome='FAIL')`. Verdict: PASS (matches expected). Wrote M9=FAIL, O9='C06-TC-01-FAIL-4', P9='2026-05-29', Q9='' to the Test Cases tab.

## What this skill does NOT do

- Run all 67 combos. For that, use `.venv/bin/python -m automation run-all` (4-5 hours, background it under `caffeinate -i` if running locally).
- Delete dashboard investors. Manual via the SPA.
- Modify the test PDFs in `AI Review Agent Test Pack/`.
- Re-run a combo that's already completed. The idempotency check skips creation but DOES re-upload + re-submit, which can create duplicate AI Review runs. To truly re-test a combo, delete the investor from the SPA first.

## Reference

- Runner code: `automation/runner.py:run_combo`
- CLI dispatch: `automation/__main__.py:_run_one`
- Sheet writer: `automation/sheets.py:write_outcomes`
- Combo table: `automation/combos.py` (parsed from `skills/ai-review-automation/SKILL.md` Stage 9)
- API endpoint shapes: `docs/anduin-api-reference.md`
- Original LLM-driven skill (now obsolete): `skills/ai-review-automation/SKILL.md`
