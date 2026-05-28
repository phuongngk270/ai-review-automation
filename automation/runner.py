"""Per-combo orchestrator: create LP, upload docs, wait, capture outcomes."""

from __future__ import annotations

import base64
import json
import logging
from dataclasses import dataclass
from datetime import date

from automation.anduin_client import AnduinClient
from automation.combos import Combo
from automation.config import FUND_DELAWARE_AMOUNT_FIELD_ID
from automation.files import upload_file
from automation.investor import create_offline_investor, find_lp_by_firm_name
from automation.results import CHECK_DEFINITION_ID_TO_CNUM, map_results_to_outcomes
from automation.review import fetch_run_results, wait_for_review
from automation.sheets import OutcomeRow
from automation.submissions import submit_signed_subscription, submit_supporting_docs

logger = logging.getLogger(__name__)

DEFAULT_AMOUNT_USD = 100000
USER_SCRATCH_FOLDER_SUFFIX = "fdr000001.fdrtemp00"


@dataclass(frozen=True)
class ComboResult:
    combo: Combo
    lp_id: str
    run_id: str
    outcome_rows: list[OutcomeRow]


def run_combo(
    client: AnduinClient,
    combo: Combo,
    *,
    close_id: str,
    folder_id: str | None = None,
    today: date | None = None,
) -> ComboResult:
    today = today or date.today()
    logger.info("=== %s ===", combo.profile_name)

    # Idempotency: if an LP with this firm name already exists, reuse it
    # instead of creating a duplicate. The dashboard returns a list; we pick
    # the first match.
    import time
    lp_id = find_lp_by_firm_name(client, combo.profile_name)
    if lp_id is None:
        create_offline_investor(
            client,
            firm_name=combo.profile_name,
            first_name="Test",
            last_name=combo.profile_name,
            email=f"{combo.profile_name.lower()}@example.test",
            close_id=close_id,
        )
        # Eventual consistency: the just-created LP may not appear on the
        # dashboard for a few seconds. Retry with backoff.
        for attempt in range(10):
            time.sleep(2.0)
            lp_id = find_lp_by_firm_name(client, combo.profile_name)
            if lp_id is not None:
                break
        if lp_id is None:
            raise RuntimeError(f"could not find LP after create: {combo.profile_name}")

    if folder_id is None:
        folder_id = _resolve_user_folder_id(client)

    sub_file_id = upload_file(client, combo.sub_doc_path, folder_id=folder_id)
    submit_signed_subscription(
        client,
        lp_id=lp_id,
        file_item_id=sub_file_id,
        amount_usd=DEFAULT_AMOUNT_USD,
        amount_field_id=FUND_DELAWARE_AMOUNT_FIELD_ID,
        firm_name=combo.profile_name,
    )

    supp_file_ids = [
        upload_file(client, p, folder_id=folder_id) for p in combo.supporting_doc_paths
    ]
    submit_supporting_docs(client, lp_id=lp_id, file_item_ids=supp_file_ids)

    run = wait_for_review(client, lp_id=lp_id)
    results = fetch_run_results(client, run_id=run.run_id)
    outcomes = map_results_to_outcomes(results)

    outcome_rows = []
    for row in combo.rows:
        outcome = outcomes.get(row.cnum)
        if outcome is None:
            logger.warning("missing outcome for %s row %d (%s)", combo.profile_name, row.row, row.cnum)
            continue
        outcome_rows.append(OutcomeRow(
            row=row.row,
            tester=combo.profile_name,
            outcome=outcome.sheet_value,
            date=today.isoformat(),
        ))

    return ComboResult(combo=combo, lp_id=lp_id, run_id=run.run_id, outcome_rows=outcome_rows)


def _resolve_user_folder_id(client: AnduinClient) -> str:
    """Build the per-user scratch folder id from the bearer JWT's userSessionId.

    Format: ``<userSessionId.split('.')[0]>.fdr000001.fdrtemp00``.
    The userSessionId is the value of ``body.userSessionId`` inside the inner
    JSON-encoded ``body`` claim of the JWT. Probed live on 2026-05-29.
    """
    parts = client.bearer.split(".")
    if len(parts) < 2:
        raise RuntimeError(f"bearer JWT does not look like a JWT: {client.bearer[:40]}...")
    payload_b64 = parts[1] + "=" * (-len(parts[1]) % 4)
    payload = json.loads(base64.urlsafe_b64decode(payload_b64))
    inner = json.loads(payload["body"])
    session_id = inner["userSessionId"]
    prefix = session_id.split(".")[0]
    return f"{prefix}.{USER_SCRATCH_FOLDER_SUFFIX}"
