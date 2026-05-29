"""CLI entry points for the AI Review automation."""

from __future__ import annotations

import logging
import sys

from automation.anduin_client import AnduinClient
from automation.auth import bootstrap_bearer


def main(argv: list[str]) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    if len(argv) < 2:
        print(
            "usage: python -m automation {smoke|list-combos|run-one <profile>|run-next|run-all}",
            file=sys.stderr,
        )
        return 2
    cmd = argv[1]
    if cmd == "smoke":
        from automation.anduin_client import smoke
        return smoke()
    if cmd == "list-combos":
        from automation.combos import load_combos
        for c in load_combos():
            print(c.profile_name)
        return 0
    if cmd == "run-one":
        return _run_one(argv[2:])
    if cmd == "run-next":
        return _run_next(argv[2:])
    if cmd == "run-all":
        count = None
        for arg in argv[2:]:
            if arg.startswith("--count="):
                count = int(arg.split("=", 1)[1])
            elif arg == "--count" and len(argv) > argv.index(arg) + 1:
                count = int(argv[argv.index(arg) + 1])
        return _run_all(count=count)
    print(f"unknown command: {cmd}", file=sys.stderr)
    return 2


def _run_one(rest: list[str]) -> int:
    if not rest:
        print("usage: run-one <profile-name>", file=sys.stderr)
        return 2
    from automation.combos import load_combos
    from automation.config import DEFAULT_CLOSE_ID
    from automation.runner import run_combo

    profile_name = rest[0]
    combos = {c.profile_name: c for c in load_combos()}
    if profile_name not in combos:
        print(f"unknown profile: {profile_name}", file=sys.stderr)
        return 2
    # Opt out of sheet write with --no-sheet (useful for dry runs).
    write_sheet = "--no-sheet" not in rest[1:]

    client = AnduinClient(bearer=bootstrap_bearer())
    result = run_combo(client, combos[profile_name], close_id=DEFAULT_CLOSE_ID)
    for row in result.outcome_rows:
        print(row)
    if write_sheet and result.outcome_rows:
        from automation.sheets import connect, write_outcomes
        sheet_id = _read_sheet_id_from_env_or_skill_md()
        svc = connect()
        write_outcomes(svc, sheet_id=sheet_id, tab_name="Test Cases", rows=result.outcome_rows)
        print(f"wrote {len(result.outcome_rows)} row(s) to sheet {sheet_id}")
    return 0


def _run_next(rest: list[str]) -> int:
    """Pick the first combo not yet on the dashboard and run it via _run_one."""
    from automation.combos import load_combos
    from automation.investor import list_existing_probe_profiles

    client = AnduinClient(bearer=bootstrap_bearer())
    existing = {p.firm_name for p in list_existing_probe_profiles(client, prefix="C")}
    for combo in load_combos():
        if combo.profile_name not in existing:
            print(f"next: {combo.profile_name}", flush=True)
            # Delegate to _run_one with the resolved profile + any extra flags
            return _run_one([combo.profile_name, *rest])
    print("no combos left to run (all 67 already on the dashboard)", file=sys.stderr)
    return 0


def _run_all(count: int | None = None) -> int:
    from concurrent.futures import ThreadPoolExecutor, as_completed

    from automation.combos import load_combos
    from automation.config import DEFAULT_CLOSE_ID
    from automation.investor import list_existing_probe_profiles
    from automation.runner import run_combo
    from automation.sheets import OutcomeRow, connect, write_outcomes

    SHEET_ID = _read_sheet_id_from_env_or_skill_md()
    TAB_NAME = "Test Cases"
    PARALLELISM = 3
    FLUSH_THRESHOLD = 5

    client = AnduinClient(bearer=bootstrap_bearer())
    existing = {p.firm_name for p in list_existing_probe_profiles(client, prefix="C")}
    combos = [c for c in load_combos() if c.profile_name not in existing]
    if count is not None:
        combos = combos[:count]
    log = logging.getLogger(__name__)
    log.info("running %d combos (skipped %d already-done)", len(combos), 67 - len(combos))

    sheets = connect()
    rows_buffer: list[OutcomeRow] = []
    with ThreadPoolExecutor(max_workers=PARALLELISM) as pool:
        futures = {
            pool.submit(run_combo, client, c, close_id=DEFAULT_CLOSE_ID): c
            for c in combos
        }
        for fut in as_completed(futures):
            combo = futures[fut]
            try:
                result = fut.result()
            except Exception as exc:
                log.error("combo %s failed: %s", combo.profile_name, exc)
                continue
            rows_buffer.extend(result.outcome_rows)
            if len(rows_buffer) >= FLUSH_THRESHOLD:
                write_outcomes(sheets, sheet_id=SHEET_ID, tab_name=TAB_NAME, rows=rows_buffer)
                rows_buffer.clear()
    if rows_buffer:
        write_outcomes(sheets, sheet_id=SHEET_ID, tab_name=TAB_NAME, rows=rows_buffer)
    return 0


def _read_sheet_id_from_env_or_skill_md() -> str:
    import os
    import re
    from pathlib import Path
    if env := os.environ.get("ANDUIN_SHEET_ID"):
        return env
    text = (
        Path(__file__).resolve().parents[1] / "skills/ai-review-automation/SKILL.md"
    ).read_text()
    m = re.search(r"docs\.google\.com/spreadsheets/d/([\w-]+)", text)
    if not m:
        raise RuntimeError("ANDUIN_SHEET_ID env var not set and no sheet URL in SKILL.md")
    return m.group(1)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
