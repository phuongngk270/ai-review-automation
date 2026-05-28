from pathlib import Path

from automation.config import (
    DASHBOARD_ID,
    DOC_BASE_DIR,
    DOC_FOLDER_SHORTCUTS,
    ENTITY_ID,
    FUND_DELAWARE_AMOUNT_FIELD_ID,
    FUND_SUB_ID,
    PROBE_INVESTOR_PREFIX,
    resolve_doc_path,
)


def test_constants_are_stable():
    assert FUND_SUB_ID == "txnqxned8j9qx1yp.fsbkg78"
    assert ENTITY_ID == "entd5ev6mge1xndv"
    assert FUND_DELAWARE_AMOUNT_FIELD_ID == "txnqxned8j9qx1yp.fsbkg78.ivfm3r"
    assert PROBE_INVESTOR_PREFIX == "PROBE-API-DISCOVERY-DELETE-ME"
    assert DASHBOARD_ID == "txnqxned8j9qx1yp.fsbkg78.fdieolm"


def test_resolve_doc_path_uses_shortcuts():
    p = resolve_doc_path("SUB/SUB-01_Individual_US_Clean.pdf")
    assert p == DOC_BASE_DIR / "0. Subscription Agreements" / "SUB-01_Individual_US_Clean.pdf"


def test_resolve_doc_path_rejects_unknown_shortcut():
    import pytest
    with pytest.raises(KeyError):
        resolve_doc_path("BOGUS/foo.pdf")


def test_doc_base_dir_exists():
    assert DOC_BASE_DIR.is_dir(), "test pack base dir missing — run pre-flight"
