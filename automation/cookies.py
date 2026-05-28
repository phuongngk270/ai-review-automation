"""Pull Anduin cookies from the user's Chrome via gstack-browse."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

REQUIRED = ("CF_Authorization", "stargazer_cookie")

BROWSE_BIN = Path(os.environ.get(
    "GSTACK_BROWSE",
    Path.home() / ".claude/skills/gstack/browse/dist/browse",
))


def parse_cookies_json(payload: list[dict], domain: str) -> dict[str, str]:
    """Filter the gstack-browse cookies JSON down to the cookies we need for *domain*."""
    matched: dict[str, str] = {}
    for entry in payload:
        if entry.get("domain") != domain:
            continue
        name = entry.get("name")
        if name in REQUIRED:
            matched[name] = entry["value"]
    missing = [c for c in REQUIRED if c not in matched]
    if missing:
        raise RuntimeError(
            f"Missing required cookies for {domain}: {', '.join(missing)}. "
            "Open the Anduin GP dashboard in Chrome and log in, then retry."
        )
    return matched


def refresh_and_load(domain: str = "fundsub-minas-tirith.anduin.dev") -> dict[str, str]:
    """Re-import Chrome cookies into gstack-browse for *domain* and return them as a dict."""
    if not BROWSE_BIN.exists():
        raise RuntimeError(f"gstack-browse binary not found at {BROWSE_BIN}")
    subprocess.run([str(BROWSE_BIN), "goto", f"https://{domain}/"], check=True, capture_output=True)
    subprocess.run(
        [str(BROWSE_BIN), "cookie-import-browser", "chrome", "--domain", domain],
        check=True, capture_output=True,
    )
    out = subprocess.run(
        [str(BROWSE_BIN), "cookies"], check=True, capture_output=True, text=True,
    )
    payload = json.loads(out.stdout)
    return parse_cookies_json(payload, domain=domain)
