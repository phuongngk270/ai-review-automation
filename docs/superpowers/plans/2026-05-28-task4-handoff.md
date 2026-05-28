# Task 4 Handoff — Endpoint Discovery Probe

> Continue Phase 1 of the AI Review Automation script. Tasks 1–3 are landed and verified. Only Task 4 remains.

## Current State (verified working)

- Repo: `/Users/phuongnguyen/Documents/Claude/Projects/Testing review agent`
- Branch: `main`, 5 commits
- `python -m automation smoke` lives at `automation/__main__.py`, calls `auth.bootstrap_bearer()` then `/api/v3/account/get-user-profile`, returns the real user profile end-to-end. Confirmed 200 OK.
- Test suite: 3/3 passing (`tests/test_anduin_client.py`)
- Auth model documented in `docs/superpowers/specs/2026-05-28-ai-review-automation-script-design.md` (see "Findings During Implementation" section)
- Design + Phase 1 plan committed under `docs/superpowers/`

## What's Left

Capture the **six write/read endpoints** that Phase 2 needs and write them up in `docs/anduin-api-reference.md`. Each section must contain method + URL + real request body + real response body + trigger description.

1. `createOfflineInvestor` — "+ Add investor" → "Track offline subscriptions" → "Add"
2. `uploadSubscriptionDoc` — Uppy flow on LP page (may be multiple calls: presigned-URL fetch, then S3 PUT, then confirm)
3. `sendToFundManagers` — checkbox + "Send to fund managers" inside the Uppy modal
4. `uploadSupportingDoc` — "Add document" → "Upload documents" on LP page (shadow-DOM injection)
5. `triggerAiReview` — "Run AI Review" button on GP-side AI Review tab
6. `fetchAiReviewResults` — fires when the AI Review tab is opened for an investor with completed results

## Important Constraints

- **Do NOT pollute the shared dashboard.** Use a single throwaway investor named `PROBE-API-DISCOVERY-DELETE-ME` for endpoints 1–5. After capturing, leave it for the user to delete (or capture the delete endpoint too and clean up).
- **For endpoint 6 (`fetchAiReviewResults`),** do not run a fresh AI Review (5–6 min wait). Instead, open the existing investor named **`TC-SUB01-NoSupp`** (the SUB-01 baseline that's already DONE per the original skill), click its AI Review tab, and capture the network call there.
- **Use a minimal supporting doc** for endpoint 4 — a tiny PDF, or `AI Review Agent Test Pack/Test Documents/6. Government IDs/ID-01_Passport_JohnSmith_Valid.pdf` if you need a real one.
- The subscription PDF for the probe: `AI Review Agent Test Pack/Test Documents/0. Subscription Agreements/SUB-01_Individual_US_Clean.pdf` (smallest, already known-good).

## How to Capture Request Bodies

`gstack-browse network` only shows method + URL + status — not bodies. To get bodies, inject a `fetch`/`XHR` monkey-patch before performing the UI action, then read captured data after.

Recommended hook (run via `$B js` on the dashboard page before each probe stage):

```javascript
(() => {
  if (window.__probeInstalled) return 'already';
  window.__probeInstalled = true;
  window.__captures = [];
  const origFetch = window.fetch;
  window.fetch = async function(input, init) {
    const url = typeof input === 'string' ? input : input.url;
    const method = (init && init.method) || (typeof input !== 'string' && input.method) || 'GET';
    const body = init && init.body ? String(init.body).slice(0, 4000) : null;
    const res = await origFetch.apply(this, arguments);
    const cloned = res.clone();
    let respBody = '';
    try { respBody = (await cloned.text()).slice(0, 4000); } catch (e) {}
    window.__captures.push({method, url, body, status: res.status, response: respBody, ts: Date.now()});
    return res;
  };
  return 'installed';
})();
```

After each UI stage:
```bash
$B js 'JSON.stringify(window.__captures.filter(c => c.url.includes("/api/v3/")), null, 2)'
```

Then `window.__captures.length = 0` to clear between stages.

(Note: `$B js` is NOT redacted by gstack-browse — only `cookies` and `storage` are. Verified during Phase 1.)

## Auth (Already Working)

Cookies and bearer are bootstrapped automatically by `automation/auth.py:bootstrap_bearer()`. For the probe, you just need a live `gstack-browse` session — same one that's used for the auth bootstrap.

## Acceptance

- `docs/anduin-api-reference.md` exists, with six sections (one per endpoint), each documenting method + URL + real request body + real response body + UI trigger + notes (Bearer header? extra headers? upload mechanism classification).
- For the upload endpoints, classify the upload mechanism: direct-to-S3 presigned, TUS, or Anduin-multipart.
- The `PROBE-API-DISCOVERY-DELETE-ME` investor exists on the dashboard (or has been cleaned up if delete endpoint was captured too).
- Commit: `docs(probe): captured anduin API reference`

After this lands, Phase 2 plan can be written with real JSON in every step instead of placeholders.

## Recommended Skill to Run

Use the same SDD flow: in a fresh session, ask the controller to dispatch this handoff as Task 4 work. Or just open this file and follow it manually.
