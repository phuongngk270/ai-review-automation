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
