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
            "paramsOpt": json.dumps({"folderId": folder_id}, separators=(",", ":")),
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

    # Step 4: async complete
    async_op = client.post("/api/v3/files/completeDirectUpload/async-create", {})
    op_id = async_op["id"]
    client.post(
        "/api/v3/files/completeDirectUpload/async-run",
        {"id": op_id, "params": {"batchUploadId": batch_id}},
    )
    # Poll async-fetch until state transitions out of Running.
    import time
    deadline = time.monotonic() + 60.0
    while True:
        result = client.post(
            "/api/v3/files/completeDirectUpload/async-fetch",
            {"id": op_id},
        )
        state = result.get("state") or {}
        typename = state.get("__typename__")
        if typename == "AsyncApiStateSuccess":
            files = state["resp"]["r"]["files"]
            return files[0][0]
        if typename and typename != "AsyncApiStateRunning":
            raise RuntimeError(f"upload async-fetch failed: {state}")
        if time.monotonic() > deadline:
            raise RuntimeError(f"upload async-fetch did not complete within 60s: {state}")
        time.sleep(1.0)
