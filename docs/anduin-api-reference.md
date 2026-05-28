# Anduin Fundsub API — Reference

Captured 2026-05-28 by driving the GP dashboard end-to-end in `gstack-browse`
with a `fetch`/XHR monkey-patch installed via JS eval. Every request and
response shown below is real traffic from the live `fundsub-minas-tirith.anduin.dev`
host, against a throwaway investor named `PROBE-API-DISCOVERY-DELETE-ME(-2)`
on the Magma Capital - AI Agents fund (`fundSubId =
txnqxned8j9qx1yp.fsbkg78`). The captured Bearer JWT and signed S3 URLs in this
file have already expired — values shown are the *shape*, not credentials.

## Common request shape

All Fundsub REST calls share the same wrapper:

- **Host:** `https://fundsub-minas-tirith.anduin.dev`
- **Method:** `POST` (always, even for read-only calls)
- **Headers:**
  - `Authorization: Bearer <stargazer_token_v2_fundsub JWT>` — see
    [automation/auth.py](../automation/auth.py)
  - `Content-Type: application/json`
  - `x-anduin-tab-id: <uuid>` — generated client-side; any UUIDv4 works
- **Body:** JSON
- **Cookies on the request:** none required (the Cloudflare Access cookie is
  on the *browser* path; pure `requests` calls skip the SPA host and hit the
  API host directly with the bearer alone)

Some endpoints are routed through the SPA's preflight-then-real-call pattern:
the SPA issues an OPTIONS-shaped POST with an empty body first (the entry
appears as `bLen=0` in captures), then immediately re-fires the same URL with
the real JSON body. Only the second call carries data; reproducing only the
real call from a script is sufficient.

## IDs cheat sheet

| Concept | Format example | Notes |
| --- | --- | --- |
| Entity (workspace) | `entd5ev6mge1xndv` | URL-only, not in API payloads. |
| FundSub (fund) | `txnqxned8j9qx1yp.fsbkg78` | Required on most calls. |
| LP (investor) | `txnqxned8j9qx1yp.fsbkg78.lpp45mr8x6` | Returned by `addMainLpWorkflowWithoutJointInfo` (the response is the LP's *form-built-investor* id `…fbi`; the `.lpXXXX` id is reached separately, see below). |
| Close | `txnqxned8j9qx1yp.fsbkg78.fscxy1j64m` | Provided by the SPA in the create-investor body. Fetched at runtime via a fund-config lookup; for a script, observe once and reuse. |
| InvestmentFund/order field | `txnqxned8j9qx1yp.fsbkg78.ivfm3r` | The commitment-amount field id for the Delaware fund. Captured from the upload-subscription-doc body. |
| File item (uploaded doc) | `ursZ…fdr000001.fdrtemp00.filj2koyk9ed` | Returned by the direct-upload sequence and referenced by submission endpoints. |
| AI Review run | `…lpp9x9ozl2.ckrnrq6zv` | Returned by `checkreview/run`; results are fetched by `getRun` with this id. |

The id returned from create-investor is a `…fbi` id, but every subsequent
endpoint expects the `…lpXXXX` LP id. The LP id appears in the "View
documents" link href on the dashboard row and in the response of
`getLpDashboardItemList` (use the latter from a script).

---

## 1. createOfflineInvestor

Creates an offline-tracked LP under a fund close.

- **URL:** `POST /api/v3/fundsub/participant/addMainLpWorkflowWithoutJointInfo`
- **UI trigger:** GP dashboard → **+ Add investor** → **Track offline
  subscriptions** → fill name/email → **Add**.

**Request body** (real, redacted to one row):

```json
{
  "fundSubId": "txnqxned8j9qx1yp.fsbkg78",
  "lpsToInvite": [
    {
      "lpInfo": {
        "lpInfoId": {"value": "9MwhlsvtTj"},
        "lpContact": {
          "email": "probe-delete-me-2@example.com",
          "firstName": "PROBE2",
          "lastName": "DELETEME2",
          "id": "",
          "skipInvitationEmail": false,
          "enableSSO": false
        },
        "collaboratorContacts": [],
        "lpEmailTemplate": {
          "fundSubEvent": {"value": 1},
          "subject": "Magma Capital - AI Agents - Invitation to complete your subscription package",
          "body": "<p>Dear [Name],</p>…",
          "semanticHtmlBodyOpt": null,
          "primaryCTA": "Begin your subscription",
          "lastEditedAt": null,
          "ccEmailAddresses": []
        },
        "firmName": "PROBE-API-DISCOVERY-DELETE-ME-2",
        "customId": "",
        "importInvestorId": "",
        "lpIdToCopyFormDataOpt": null,
        "initialFormData": null,
        "expectedCommitment": "",
        "tagNames": [],
        "prefillFromLp": null,
        "dataImportItemId": null,
        "lpIdToCopyInvestorGroupOpt": null,
        "docTypesToMarkAsProvided": [],
        "sharedDocumentsPerDocType": [],
        "importFromFundData": null,
        "metadata": [],
        "collaboratorOrganizationInfos": [],
        "investorGroupIdOpt": null,
        "customDataMap": []
      },
      "closeIdOpt": "txnqxned8j9qx1yp.fsbkg78.fscxy1j64m",
      "investorGroupIdOpt": null,
      "lpAttachedDocs": []
    }
  ],
  "lpOrderType": {"value": 1},
  "sharedAttachedDocs": [],
  "importFromFundDataFirm": null
}
```

**Response body:**

```json
"txnqxned8j9qx1yp.fsbkg78.ltidy5rj1np81w3.fbi"
```

A bare JSON string — the form-built-investor id. To resolve the real LP id
needed by the upload endpoints, list the dashboard with
`getLpDashboardItemList` and match by `firmName`/email.

**Notes:**

- `lpInfoId.value` is a short opaque token (`9MwhlsvtTj`); the SPA generates
  it client-side as a nonce. Any 10-char alphanumeric string works.
- `skipInvitationEmail: false` here despite the modal description claiming
  "system will not email investors unless the fund manager chooses to". For
  offline-tracking flows, no email is sent regardless because there is no
  separate invite step.
- The `lpEmailTemplate` block is required even though no email goes out for
  offline tracking. Copy the SPA's default body verbatim once and reuse.
- `lpOrderType.value: 1` = offline tracking. (Value `2` would be the
  online-invite flow — not used by this script.)

---

## 2. uploadSubscriptionDoc

Submits a previously-uploaded subscription PDF as the LP's signed
subscription document and records commitment amounts. Two phases:

### 2a. Direct-upload sequence (also used by `uploadSupportingDoc`)

Every file upload — subscription PDFs, AML/KYC docs, supporting docs — goes
through the same four-step direct-upload sequence. Steps 1, 2 and 4 are
JSON POSTs to the API; step 3 is the actual file `PUT` to a signed
CloudFront/S3-style URL on a different host.

**Step 1 — get a batchUploadId**

```
POST /api/v3/files/createDirectUpload
{
  "apiName": "default",
  "paramsOpt": "{\"folderId\":\"<userScope>.fdr000001.fdrtemp00\"}",
  "files": [
    {
      "fileUploadId": {"id": "<uuid>-<filename>"},
      "filePath": "<filename>",
      "contentTypeOpt": "application/pdf",
      "checksumOpt": null,
      "metadata": {}
    }
  ],
  "emptyFolders": []
}
→ {"batchUploadId": "bupo41xmk20ny9q9"}
```

The `folderId` is a per-user scratch folder. It is stable across uploads
within the same session — fetch it once from the SPA via
`getDirectUploadUrl` echo (it surfaces in the response of step 2) or pull it
from the user's profile-scoped folder list at startup.

**Step 2 — get the signed PUT URL**

```
POST /api/v3/files/getDirectUploadUrl
{
  "batchUploadId": "bupo41xmk20ny9q9",
  "fileUploadId": {"id": "<uuid>-<filename>"}
}
→ {
    "uploadUrl": "https://document-minas-tirith.anduin.app/uploads/bupo41xmk20ny9q9/<uuid>/<filename>?Expires=…&Signature=…&Key-Pair-Id=KZOF12HJ4T98J",
    "contentType": "application/pdf"
  }
```

The signed URL is on `document-minas-tirith.anduin.app` — a separate host
from the SPA. Key-Pair-Id and signature format are CloudFront's; the bearer
JWT is **not** sent on this PUT.

**Step 3 — PUT the file bytes**

```
PUT <uploadUrl>
Content-Type: application/pdf

<raw file bytes>
→ 200 OK (empty body)
```

XHR call from the SPA; from a Python script use `requests.put(url, data=open(path, 'rb'), headers={"Content-Type": "application/pdf"})`. No auth header on this request.

**Step 4 — complete + resolve the file id**

```
POST /api/v3/files/completeDirectUpload/async-create
{}
→ {"id": "<asyncOpId>"}

POST /api/v3/files/completeDirectUpload/async-run
{"id": "<asyncOpId>", "params": {"batchUploadId": "bupo41xmk20ny9q9"}}
→ {}

POST /api/v3/files/completeDirectUpload/async-fetch
{"id": "<asyncOpId>"}
→ {
    "state": {
      "__typename__": "AsyncApiStateSuccess",
      "resp": {
        "r": {
          "files": [[
            "<userScope>.fdr000001.fdrtemp00.filj2koyk9ed",
            "ID-01_Passport_JohnSmith_Valid.pdf"
          ]]
        }
      }
    }
  }
```

The `filj2koyk9ed`-shaped id is the file's permanent itemId. Pass it as the
`uploadedDocs` / `fileIds` reference in the submission endpoint below.

**Upload mechanism classification:** direct-to-CloudFront-signed-PUT, with a
three-step Anduin-controlled batch wrapper. **Not** TUS, not multipart, not
Uppy companion-relayed. From a script, a synchronous `requests`
sequence works fine.

### 2b. Submit signed subscription doc

- **URL:** `POST /api/v3/fundsub/subscription-doc/gpUploadSignedSubscriptionDoc`
- **UI trigger:** LP page → **Upload** dropdown → **Investor-signed
  documents** → choose file → fill commitment → **Submit**.

**Request body:**

```json
{
  "fundSubLpId": "txnqxned8j9qx1yp.fsbkg78.lpp45mr8x6",
  "uploadedDocs": [
    "ursZ3alW1dz5TaVAYdlbl6sM7dYRVrKVcjDvJBW96xT7YPmRdgvJtJdY9zVo0lTQ3DbN38J9.fdr000001.fdrtemp00.filvl0dv3pwy"
  ],
  "submittedAmounts": [
    ["txnqxned8j9qx1yp.fsbkg78.ivfm3r", {"value": "100000"}]
  ],
  "shouldApprove": false,
  "shouldCreateNewDataExtractRequest": false,
  "investmentEntityName": "PROBE-API-DISCOVERY-DELETE-ME"
}
```

**Response body:**

```json
{"dataExtractionWarningOpt": null}
```

**Notes:**

- `submittedAmounts` is an array of `[investmentFundFieldId, {value: amount}]`
  tuples. For Magma Capital - AI Agents, the Delaware fund's commitment-amount
  field id is `txnqxned8j9qx1yp.fsbkg78.ivfm3r`. Discover the equivalent for
  other funds via the existing `FundSubAdminRestrictedModel.investmentFunds`
  GraphQL query.
- `shouldApprove: false` leaves the doc in "Pending approval" state. AI
  Review still runs against the submitted version regardless of approval.
- `investmentEntityName` is just the firm name surfaced in the modal; it has
  to be populated even though it was already supplied at create-investor
  time.

---

## 3. sendToFundManagers — **Not applicable for the offline-tracking flow**

The handoff doc lists this as a separate endpoint expected to fire from an
Uppy modal checkbox. That UI surface exists only on the LP-side portal,
where an investor uploads their own subscription docs and chooses whether to
share them with the fund manager.

In the GP-side offline-tracking flow this script automates, the GP **is**
the fund manager. The equivalent "send to fund managers" affordance is the
`shouldApprove` boolean on `gpUploadSignedSubscriptionDoc` (§2b):

- `shouldApprove: false` (default) — doc lands in the GP review queue as
  "Pending approval". AI Review still runs.
- `shouldApprove: true` — GP self-approves the doc as part of the upload.

Phase 2 does not need a separate request for this. Leave `shouldApprove` at
`false` to mirror what the current LLM-driven skill does.

---

## 4. uploadSupportingDoc

Attaches AML/KYC and other supporting documents to an LP. Uses the same
direct-upload sequence as §2a, followed by one submission call.

- **URL:** `POST /api/v3/fundsub/supportingdoc/v2/uploadFile`
- **UI trigger:** LP page → **Upload on behalf** under *AML / KYC and other
  documents* → choose file → **Submit**.

**Request body:**

```json
{
  "lpId": "txnqxned8j9qx1yp.fsbkg78.lpp45mr8x6",
  "fileIds": [
    "ursZ3alW1dz5TaVAYdlbl6sM7dYRVrKVcjDvJBW96xT7YPmRdgvJtJdY9zVo0lTQ3DbN38J9.fdr000001.fdrtemp00.filj2koyk9ed"
  ],
  "docType": ""
}
```

**Response body:**

```json
{}
```

**Notes:**

- `docType` is a free-form string used by the GP to categorize the doc (e.g.
  "passport", "w9"). Empty string is allowed and is what the SPA sends when
  the GP uses *Upload on behalf* without a type selection.
- Multiple files can be uploaded in one call by including all their file ids
  in `fileIds`. The SPA submits one call per file when uploaded sequentially;
  batching is equivalent and saves round-trips.
- Upload mechanism: identical CloudFront-signed PUT to §2a. Re-use the same
  `batchUploadId` for multiple supporting docs.

---

## 5. triggerAiReview

Starts a fresh AI Review run for an LP's submitted subscription package.

- **URL:** `POST /api/v3/checkreview/run`
- **UI trigger:** Dashboard → **Review Dashboard** tab → **Reviewed
  Submissions** → click investor row → **Re-run AI Review** button. AI
  Review also auto-triggers when a subscription package is first submitted;
  this endpoint is only needed for the explicit re-run path.

**Request body:**

```json
{
  "lpId": "txnqxned8j9qx1yp.fsbkg78.lpp9x9ozl2",
  "submissionVersionIndex": 1
}
```

**Response body:**

```json
{
  "runId": "txnqxned8j9qx1yp.fsbkg78.lpp9x9ozl2.ckrnz368m",
  "status": "RUNNING"
}
```

**Notes:**

- `submissionVersionIndex` increments each time the LP re-submits a new
  subscription doc. For first-time uploads it is `1`. Fetch the current
  value via `getSubscriptionVersionBasicInfoWithErrorHandler` if uncertain.
- Status transitions: `RUNNING` → `COMPLETED` (5–6 min typical). Poll via
  `checkreview/status` (see §6) until `state` ≠ `RUNNING`.
- This endpoint does NOT need to be called when the script first submits a
  subscription package — submission auto-triggers a run. Only call it when
  forcing a re-run on already-submitted docs.

---

## 6. fetchAiReviewResults

Reads the 22 check outcomes for the most recent (or a specified) AI Review
run.

For the script, two endpoints together cover the workflow:

### 6a. Poll for completion

- **URL:** `POST /api/v3/checkreview/status`
- **UI trigger:** Opening the *Reviewed Submissions* detail page (fires
  alongside `getRun`).

**Request body:**

```json
{
  "lpId": "txnqxned8j9qx1yp.fsbkg78.lpp9x9ozl2",
  "submissionVersionIndex": 1
}
```

**Response body (real, completed run):**

```json
{
  "state": "HAS_ISSUES",
  "latestRunId": "txnqxned8j9qx1yp.fsbkg78.lpp9x9ozl2.ckrnrq6zv",
  "checksTotal": 22,
  "checksPassed": 0,
  "checksFailed": 4,
  "checksUnknown": 7,
  "checksError": 0,
  "checksNotApplicable": 11,
  …
}
```

`state` values observed: `HAS_ISSUES` (completed with at least one
FAIL/UNKNOWN), `CLEAN` (completed all-pass — not yet observed in this
fund's data), `RUNNING` (still in progress).

### 6b. Read the full result set

- **URL:** `POST /api/v3/checkreview/getRun`
- **UI trigger:** Same Reviewed Submissions detail page open.

**Request body:**

```json
{
  "runId": "txnqxned8j9qx1yp.fsbkg78.lpp9x9ozl2.ckrnrq6zv",
  "submissionVersionIndex": 1
}
```

**Response body (excerpt — one of 22 checks):**

```json
{
  "runId": "txnqxned8j9qx1yp.fsbkg78.lpp9x9ozl2.ckrnrq6zv",
  "status": "COMPLETED",
  "checksTotal": 22,
  "checksPassed": 0,
  "checksFailed": 4,
  "checksUnknown": 7,
  "checksError": 0,
  "checksNotApplicable": 11,
  "results": [
    {
      "checkResultId": "txnqxned8j9qx1yp.fsbkg78.lpp9x9ozl2.ckrnrq6zv.chkr04z1j",
      "checkName": "W-8IMY Withholding Statement Present",
      "category": "txnqxned8j9qx1yp.fsbkg78.ccat61l1j",
      "assessment": "NOT_APPLICABLE",
      "confidence": "HIGH",
      "reasoning": "…",
      "summary": "No W-8IMY is present for this LP; …",
      "sources": […],
      "ruleApplied": "NOT_APPLICABLE if no W-8IMY is uploaded …",
      "recommendation": null,
      "costUsd": 0.12981474,
      "executionTimeMs": 42261,
      "traceModelTier": "SONNET",
      "createdAt": "2026-05-23T04:30:06.616306406Z",
      "checkDefinitionId": "chkdyjqpygoropzx",
      "resolution": null,
      "checkType": "DOCUMENT_VALIDATION"
    }
    /* …21 more results… */
  ]
}
```

**This is the gold endpoint for Stage 7 of the runner.** No DOM-scraping
needed; every datum the LLM-driven skill reads from "Needs action" and
"Passed" sub-tabs is right here:

- `assessment` ∈ `{PASS, FAIL, UNKNOWN, NOT_APPLICABLE}` maps directly to
  the four-state outcome the script writes to column M of the Google Sheet.
- `checkName` is the human-readable label; `checkDefinitionId` is the
  stable id and is what should be used to map results back to test-case
  rows (the C1..C22 numbering in the original skill).
- `confidence`, `reasoning`, `summary`, `sources` are optional context that
  can be logged for debugging without affecting the outcome write.

To extract `runId` from scratch when only the LP id is known, call
`POST /api/v3/checkreview/history/runs` first:

```
{"lpId": "…lpp9x9ozl2", "submissionVersionIndex": 1}
→ {"runs": [{"runId": "…ckrnrq6zv", "runNumber": 1, "status": "COMPLETED", …}]}
```

Pick the most recent `COMPLETED` run, then call `getRun` with its id.

---

## Auth header reminder

A Bearer JWT bootstrapped via [automation/auth.py](../automation/auth.py)
worked for every endpoint listed above. No CSRF token, no per-request
nonce, no signature scheme beyond the standard bearer header. The
`x-anduin-tab-id` header is generated client-side and the API does not
appear to validate it.

---

## Probe leftovers

Running this discovery created two throwaway investors on the dashboard,
both prefixed `PROBE-API-DISCOVERY-DELETE-ME`. The user-facing intent is
that these be deleted by hand; the script can also clean them up via the
`removeLp`-shaped endpoints if needed (not captured in this probe — out of
scope for Phase 1).

A `Re-run AI Review` was also triggered against `TC-SUB01-NoSupp` to capture
the trigger endpoint; that run will complete on its own in ~5 minutes and is
identical to the one whose results were already recorded.
