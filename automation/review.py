"""AI Review trigger, poll, and fetch.

Documented in docs/anduin-api-reference.md §5 and §6.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from automation.anduin_client import AnduinClient

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CheckResult:
    check_definition_id: str
    check_name: str
    assessment: str


@dataclass(frozen=True)
class RunHandle:
    run_id: str
    state: str


def trigger_rerun(client: "AnduinClient", *, lp_id: str, version: int = 1) -> str:
    resp = client.post(
        "/api/v3/checkreview/run",
        {"lpId": lp_id, "submissionVersionIndex": version},
    )
    return resp["runId"]


def wait_for_review(
    client: "AnduinClient",
    *,
    lp_id: str,
    version: int = 1,
    poll_interval: float = 30.0,
    timeout: float = 15 * 60,
) -> RunHandle:
    effective_interval = max(poll_interval, 1.0)
    max_attempts = max(1, int(timeout / effective_interval))
    PENDING_STATES = {"", "RUNNING", "NOT_STARTED", "PENDING", "QUEUED"}
    triggered = False
    for attempt in range(max_attempts):
        status = client.post(
            "/api/v3/checkreview/status",
            {"lpId": lp_id, "submissionVersionIndex": version},
        )
        state = status.get("state", "")
        run_id = status.get("latestRunId")
        logger.info("review %s state=%s run=%s", lp_id, state, run_id)
        if state not in PENDING_STATES and run_id:
            return RunHandle(run_id=run_id, state=state)
        # Auto-trigger fallback: if we sit in NOT_STARTED for >1 poll, kick it off.
        if not triggered and state == "NOT_STARTED" and attempt >= 1:
            try:
                trigger_rerun(client, lp_id=lp_id, version=version)
                triggered = True
            except Exception as exc:
                logger.warning("trigger_rerun failed (continuing to poll): %s", exc)
        time.sleep(poll_interval)
    raise TimeoutError(f"AI review for {lp_id} did not complete within {timeout:.0f}s")


def fetch_run_results(
    client: "AnduinClient",
    *,
    run_id: str,
    version: int = 1,
) -> list[CheckResult]:
    resp = client.post(
        "/api/v3/checkreview/getRun",
        {"runId": run_id, "submissionVersionIndex": version},
    )
    return [
        CheckResult(
            check_definition_id=r["checkDefinitionId"],
            check_name=r["checkName"],
            assessment=r["assessment"],
        )
        for r in resp.get("results", [])
    ]
