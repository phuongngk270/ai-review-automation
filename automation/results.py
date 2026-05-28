"""Map AI Review check results to Google Sheet outcomes."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from automation.review import CheckResult

_FIXTURE = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "check_definitions.json"

# Loaded at import time from the fixture committed in Step 1.
CHECK_DEFINITION_ID_TO_CNUM: dict[str, str] = json.loads(_FIXTURE.read_text())


@dataclass(frozen=True)
class Outcome:
    sheet_value: str

    @classmethod
    def from_assessment(cls, assessment: str) -> "Outcome":
        if assessment in {"PASS", "FAIL", "UNKNOWN", "NOT_APPLICABLE"}:
            return cls(sheet_value=assessment)
        if assessment == "ERROR":
            return cls(sheet_value="UNKNOWN")
        raise ValueError(f"unknown assessment: {assessment!r}")


def map_results_to_outcomes(results: list[CheckResult]) -> dict[str, Outcome]:
    """Returns {C1: Outcome(...), ..., C22: Outcome(...)} keyed by C-number.

    Check definition ids not in the fixture (e.g. the noise "test" id) are skipped.
    """
    out: dict[str, Outcome] = {}
    for r in results:
        cnum = CHECK_DEFINITION_ID_TO_CNUM.get(r.check_definition_id)
        if cnum is None:
            continue
        out[cnum] = Outcome.from_assessment(r.assessment)
    return out
