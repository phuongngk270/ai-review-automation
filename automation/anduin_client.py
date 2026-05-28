"""HTTP client for the Anduin GP platform."""

from __future__ import annotations

import logging
import sys
from typing import Any

import requests

from automation.auth import bootstrap_bearer

logger = logging.getLogger(__name__)


class AnduinClient:
    def __init__(self, bearer: str, base_url: str = "https://fundsub-minas-tirith.anduin.dev") -> None:
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        self.session.headers.update({
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": f"Bearer {bearer}",
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
    """Phase 1 acceptance: bootstrap a bearer JWT and fetch the user profile."""
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    bearer = bootstrap_bearer()
    logger.info("got bearer JWT, len=%d", len(bearer))
    client = AnduinClient(bearer=bearer)
    profile = client.post("/api/v3/account/get-user-profile", json={})
    print(profile, file=sys.stdout)
    user_info = profile.get("userInfo") or profile
    if "emailAddressStr" in user_info or "email" in user_info or "userName" in user_info:
        return 0
    print("WARN: profile response did not include an obvious user identifier", file=sys.stderr)
    return 1
