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
