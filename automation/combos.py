"""Parse the 67-combo test plan out of the SKILL.md runbook."""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import cache
from pathlib import Path

from automation.config import resolve_doc_path

_SKILL_FILE = (
    Path(__file__).resolve().parents[1]
    / "skills"
    / "ai-review-automation"
    / "SKILL.md"
)


@dataclass(frozen=True)
class RowMapping:
    row: int
    scenario_id: str
    cnum: str  # C1, C2, ..., C22 (skipping C16)


@dataclass(frozen=True)
class Combo:
    profile_name: str
    sub_doc_shorthand: str
    supporting_doc_shorthands: tuple[str, ...]
    rows: tuple[RowMapping, ...]

    @property
    def sub_doc_path(self) -> Path:
        return resolve_doc_path(self.sub_doc_shorthand)

    @property
    def supporting_doc_paths(self) -> tuple[Path, ...]:
        return tuple(resolve_doc_path(s) for s in self.supporting_doc_shorthands)


_COMBO_HEADER = re.compile(r"^### (C\d+)\s*$")
_PROFILE = re.compile(r"\*\*Profile name\*\*:\s*`([^`]+)`")
_SUB_DOC = re.compile(r"\*\*Sub doc\*\*:\s*`([^`]+)`")
_SUPP_DOC = re.compile(r"^-\s*`([^`]+)`\s*$")
_ROW_LINE = re.compile(r"^\|\s*(\d+)\s*\|\s*([\w-]+)\s*\|\s*(C\d+)\s*\|")


@cache
def load_combos() -> list[Combo]:
    text = _SKILL_FILE.read_text()
    lines = text.splitlines()
    combos: list[Combo] = []
    i = 0
    while i < len(lines):
        if _COMBO_HEADER.match(lines[i]):
            i, combo = _parse_one(lines, i)
            combos.append(combo)
            continue
        i += 1
    return combos


def _parse_one(lines: list[str], i: int) -> tuple[int, Combo]:
    profile = sub = None
    supporting: list[str] = []
    rows: list[RowMapping] = []
    in_supporting = False
    in_rows = False
    j = i + 1
    while j < len(lines):
        line = lines[j]
        if line.startswith("---") or _COMBO_HEADER.match(line):
            break
        if m := _PROFILE.search(line):
            profile = m.group(1)
        elif m := _SUB_DOC.search(line):
            sub = m.group(1)
        elif line.strip().startswith("**Supporting docs"):
            in_supporting = True
        elif in_supporting and (m := _SUPP_DOC.match(line)):
            supporting.append(m.group(1))
        elif "Rows to update" in line:
            in_supporting = False
            in_rows = True
        elif in_rows and (m := _ROW_LINE.match(line)):
            rows.append(RowMapping(
                row=int(m.group(1)),
                scenario_id=m.group(2),
                cnum=m.group(3),
            ))
        j += 1
    assert profile and sub, f"combo missing fields at line {i}"
    return j, Combo(
        profile_name=profile,
        sub_doc_shorthand=sub,
        supporting_doc_shorthands=tuple(supporting),
        rows=tuple(rows),
    )


def iter_combos():
    yield from load_combos()
