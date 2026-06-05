"""Create and look up offline-tracked LPs on the Anduin GP dashboard."""

from __future__ import annotations

import logging
import secrets
import string
from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

from automation.config import DASHBOARD_ID, FUND_SUB_ID

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
    if isinstance(fbi_id, str):
        return fbi_id
    raise RuntimeError(f"unexpected create-investor response: {fbi_id!r}")


def _list_dashboard(client: "AnduinClient") -> list[dict]:
    """Return a list of rowMetadata dicts from the advanced dashboard."""
    # getRecentDashboardId is a required preflight — Anduin added it as a
    # server-side session initialiser. Returns empty body but must be called first.
    try:
        client.post("/api/v3/fundsub/admin/getRecentDashboardId", {"fundSubId": FUND_SUB_ID})
    except Exception:
        pass  # non-fatal: proceed with hardcoded DASHBOARD_ID
    dashboard_id = DASHBOARD_ID
    resp = client.post(
        "/api/v3/admin/dashboard/getAdvancedDashboardData",
        {
            "fundSubId": FUND_SUB_ID,
            "dashboardId": dashboard_id,
            "queryParams": {
                "filterPresetIdOpt": None,
                "filters": [],
                "searchText": "",
                "sortedBy": "contact",
                "reversed": False,
                "pageIndex": 0,
                "pageSizeOpt": 500,
            },
            "shouldApplyLatestFilter": True,
        },
    )
    rows = resp.get("dashboardData", {}).get("rows") or []
    return [row["rowMetadata"] for row in rows if "rowMetadata" in row]


def find_lp_by_firm_name(client: "AnduinClient", firm_name: str) -> Optional[str]:
    for row_meta in _list_dashboard(client):
        if row_meta.get("lpInvestmentEntity") == firm_name:
            return row_meta.get("lpId")
    return None


def list_existing_probe_profiles(
    client: "AnduinClient",
    *,
    prefix: str,
) -> list[ExistingProfile]:
    return [
        ExistingProfile(
            firm_name=row_meta["lpInvestmentEntity"],
            lp_id=row_meta["lpId"],
            status=str(row_meta.get("status", {}).get("value", "")),
        )
        for row_meta in _list_dashboard(client)
        if row_meta.get("lpInvestmentEntity", "").startswith(prefix)
    ]
