# AI Review Automation — Script Conversion Design

**Date:** 2026-05-28
**Status:** Approved direction — Approach A primary, B and C as documented fallbacks.

## Background

`ai-review-automation.skill` is an LLM-driven runbook that uses a browser to drive the Anduin GP platform end-to-end across 67 remaining test combos. Each combo: create offline investor, upload subscription PDF + supporting docs, trigger AI Review, wait 5–6 min, read 22 check outcomes, write results to a Google Sheet.

The skill is expensive in both tokens (LLM reasons through every step of every combo) and wall time (sequential, with 5–6 min waits the LLM sits through). Almost every step is mechanical and would be cheaper as a script if a real API exists.

## Probe Findings (2026-05-28)

Used `gstack-browse` with cookies imported from the user's logged-in Chrome to load the GP dashboard and observe network traffic.

- **Auth:** Cloudflare Access (`CF_Authorization` cookie) + Anduin session (`stargazer_cookie`, httpOnly). Both extract cleanly from Chrome's cookie store. No CAPTCHA, no anti-bot beyond Cloudflare Access.
- **API surface:** REST-style `POST /api/v3/...` with descriptive endpoint names, plus a `/graphql` endpoint for some operations. Examples observed on dashboard load:
  - `/api/v3/account/get-user-profile`
  - `/api/v3/fundsub/admin/getLpDashboardItemList`
  - `/api/v3/admin/dashboard/getAdvancedDashboardData`
  - `/api/v3/fundsub/subscription/review/getFundSubSubscriptionDocReviewConfig`
- **Verdict:** the skill's UI steps are 1:1 calls to this internal API. A script can drive the entire flow without a browser or LLM at runtime.

## Approaches

### Approach A — Pure API script (primary)

Standalone script (Node or Python) that calls `/api/v3/...` and `/graphql` directly. Auth via `stargazer_cookie` + `CF_Authorization` extracted from Chrome at startup (re-imported when expired). Google Sheets writes via the official Sheets API with OAuth.

**Pros:** no browser at runtime; fully parallelizable; runtime floor = AI-review duration only; near-zero token cost; curl-able for debugging; trivial resumability (list existing `C##-*` profiles via API).

**Cons:** one-time endpoint discovery — must capture ~6 calls (create investor, upload init, upload file, send-to-fund-managers, trigger-AI-review, fetch-results) by performing each action once with DevTools or `gstack-browse` network watching.

**Risk:** internal API contract could change. Mitigation: structured logging on each call so a contract break is visible immediately.

### Approach B — Playwright + API hybrid (fallback for upload only)

Headless Playwright drives the file-upload steps using the existing Uppy injection + `anduin-file-menu-item` shadow-DOM techniques already proven in the current skill. Everything else (create investor, trigger review, fetch results, sheet writes) uses Approach A's HTTP layer.

**When to fall back to B:** only if the upload API turns out to be impractical to call directly — e.g., TUS chunked upload with non-trivial state machine, or multipart with signed headers we can't easily reproduce.

### Approach C — Script + LLM for result interpretation only

Script handles every stage except Stage 7. For Stage 7, dump the AI Review results payload (or DOM) and let an LLM parse the 22 check outcomes.

**When to fall back to C:** only if the fetch-results endpoint returns something genuinely unstructured (free-form text, inconsistent labels). Results in the UI are labeled Pass / Needs action / Not applicable — almost certainly structured in the response.

## Plan of Attack

1. **Endpoint discovery probe (one-time, ~30 min).** With cookies imported into `gstack-browse`, run one full combo end-to-end manually in the headless browser while watching the network. Capture request method, URL, headers, body, and response for each of the six key actions. Save as a reference doc (`docs/superpowers/notes/anduin-api-reference.md`).
2. **Implement Approach A** for create-investor, trigger-review, fetch-results, and sheet-write paths. Validate against the already-done SUB-01 combo (results known).
3. **Implement upload** within Approach A. If upload mechanism is direct-to-S3 or simple multipart, done. If genuinely hairy, swap upload step to Approach B (Playwright) and leave the rest as-is.
4. **Stage 7 parsing**: parse the fetch-results JSON directly. If shape is structured (expected), done. Only if it isn't, fall back to Approach C for that step.
5. **Resumability + parallelism**: at startup, query the API for existing `C##-*` profiles and the Sheet for filled rows (column M); compute the run list exactly as Stage 1 of the original skill does. Run N combos concurrently (start with N=3 to be safe).

## Out of Scope

- Replacing the test PDFs or the test plan.
- Changing how column N (Match?) is computed — that stays a Sheet formula.
- Re-running already-completed combos.

## Open Questions (resolved during probe step)

- File upload mechanism: direct-to-S3 presigned, TUS chunked, or companion-relayed?
- Does `/api/v3/...` accept anti-CSRF headers (e.g., `X-Stargazer-Token`) that we'll need to read off the page or initial response?
- Is there a single endpoint to fetch all 22 results, or per-check?
- Google Sheets: confirm OAuth (user creds) vs. service account access to the test-cases sheet.

## Findings During Implementation (Phase 1 Task 3, 2026-05-28)

Running the live smoke test surfaced one important correction to the probe findings:

- **Auth is bearer-based, not cookie-based.** The `/api/v3/...` endpoints require an `Authorization: Bearer <jwt>` header, NOT just session cookies on the request. The relevant JWT is `stargazer_token_v2_fundsub`, which the SPA stores in `localStorage` after a bifrost bootstrap (`id-minas-tirith/api/v3/bifrost-authentication/verify-cookie` → `fundsub/api/v3/bifrost-bootstrap/verifyBootstrapToken`).
- **Pragmatic auth path for the script:** drive `gstack-browse` to load the dashboard once per script run (the SPA performs the bootstrap), then read the bearer JWT from localStorage via `gstack-browse js localStorage.getItem('stargazer_token_v2_fundsub')`. All subsequent API calls in the run are pure `requests` with the Authorization header — no browser involvement after the bootstrap.
- **`gstack-browse` deliberately redacts cookie values and `storage` output** (replaces them with `[REDACTED — N chars]` strings whose em dash is not latin-1 encodable). The redaction does NOT apply to `js` eval results, which is why JS-based extraction works.
- **`browser_cookie3`** can read Chrome's cookies cleanly with Keychain approval, but we no longer need it once we switched to bearer-only auth.

The design's three approaches (A pure-API, B Playwright-for-upload, C LLM-for-results) still stand. We are still on path A; the only change is the auth shim. Phase 2 will likely keep this same gstack-browse bootstrap step.

## Success Criteria

- Running the script with no arguments completes all 67 remaining combos and writes 67 sets of results to the Google Sheet, with the same outcome the LLM-driven skill would have produced for already-known combos.
- Single-combo run time ≤ 7 minutes (≈ AI-review duration + overhead).
- Re-running after partial completion skips done work and resumes cleanly.
