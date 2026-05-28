"""Obtain a bearer JWT for the Anduin fundsub API.

The Anduin SPA bootstraps a JWT (``stargazer_token_v2_fundsub``) into
``localStorage`` after the user authenticates via Cloudflare Access + SSO. The
fundsub REST API authenticates pure-HTTP requests with that JWT as a Bearer
token; no cookies on the request itself are required.

We reproduce the SPA's bootstrap by driving ``gstack-browse``: import the user's
Chrome cookies, navigate to the dashboard so the SPA performs its handshake,
then read the JWT out of localStorage via JS eval. Subsequent API calls in this
process are pure ``requests`` — no browser involvement.
"""

from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path

DASHBOARD_URL = (
    "https://fundsub-minas-tirith.anduin.dev/"
    "#/entd5ev6mge1xndv/txnqxned8j9qx1yp.fsbkg78?tab=ad"
)
BEARER_STORAGE_KEY = "stargazer_token_v2_fundsub"

BROWSE_BIN = Path(os.environ.get(
    "GSTACK_BROWSE",
    Path.home() / ".claude/skills/gstack/browse/dist/browse",
))


def _run(*args: str, timeout: float = 30.0) -> str:
    res = subprocess.run(
        [str(BROWSE_BIN), *args],
        check=True, capture_output=True, text=True, timeout=timeout,
    )
    return res.stdout


def bootstrap_bearer(
    dashboard_url: str = DASHBOARD_URL,
    poll_interval: float = 1.0,
    poll_timeout: float = 30.0,
) -> str:
    """Drive gstack-browse to obtain a fresh bearer JWT.

    Assumes the user is logged in to Anduin in their normal Chrome browser.
    Imports Chrome cookies into the browse session, loads the dashboard so the
    SPA writes the bearer to localStorage, then reads it back.

    Raises RuntimeError if the JWT does not appear within ``poll_timeout``
    seconds.
    """
    if not BROWSE_BIN.exists():
        raise RuntimeError(f"gstack-browse binary not found at {BROWSE_BIN}")

    # 1. Refresh cookies from the user's Chrome (Anduin splits auth across two
    #    subdomains; the SPA bootstrap needs both).
    for domain in ("id-minas-tirith.anduin.dev", "fundsub-minas-tirith.anduin.dev"):
        _run("goto", f"https://{domain}/")
        _run("cookie-import-browser", "chrome", "--domain", domain)

    # 2. Load the dashboard. The SPA performs the bifrost bootstrap and writes
    #    the bearer JWT to localStorage.
    _run("goto", dashboard_url)

    # 3. Poll localStorage until the bearer appears.
    deadline = time.monotonic() + poll_timeout
    while True:
        bearer = _run("js", f"localStorage.getItem('{BEARER_STORAGE_KEY}')").strip()
        if bearer and bearer != "null":
            return bearer
        if time.monotonic() > deadline:
            raise RuntimeError(
                f"Bearer JWT did not appear in localStorage[{BEARER_STORAGE_KEY!r}] "
                f"within {poll_timeout:.0f}s. Check that Chrome is logged in to "
                "Anduin and the dashboard URL is reachable."
            )
        time.sleep(poll_interval)
