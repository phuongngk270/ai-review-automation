"""Static configuration: fund ids, file paths, naming conventions."""

from __future__ import annotations

from pathlib import Path

ENTITY_ID = "entd5ev6mge1xndv"
FUND_SUB_ID = "txnqxned8j9qx1yp.fsbkg78"
FUND_DELAWARE_AMOUNT_FIELD_ID = "txnqxned8j9qx1yp.fsbkg78.ivfm3r"
DASHBOARD_ID = "txnqxned8j9qx1yp.fsbkg78.fdieolm"

PROBE_INVESTOR_PREFIX = "PROBE-API-DISCOVERY-DELETE-ME"

DOC_BASE_DIR = (
    Path(__file__).resolve().parents[1]
    / "AI Review Agent Test Pack"
    / "Test Documents"
)

DOC_FOLDER_SHORTCUTS: dict[str, str] = {
    "SUB":  "0. Subscription Agreements",
    "TAX":  "1. Tax Forms",
    "WHS":  "2. Withholding Statements",
    "FORM": "3. Formation Documents",
    "CERT": "4. Certificates of Good Standing",
    "AUTH": "5. Authorization Documents",
    "ID":   "6. Government IDs",
    "BO":   "7. Beneficial Ownership & AML",
    "SOF":  "8. Source of Funds",
}


def resolve_doc_path(shorthand: str) -> Path:
    """Turn ``"SUB/SUB-01_…pdf"`` into the absolute path on disk."""
    short, _, rest = shorthand.partition("/")
    folder = DOC_FOLDER_SHORTCUTS[short]  # KeyError on unknown
    return DOC_BASE_DIR / folder / rest
