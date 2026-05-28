from unittest.mock import MagicMock

from automation.investor import (
    create_offline_investor,
    find_lp_by_firm_name,
    list_existing_probe_profiles,
)


def test_create_offline_investor_posts_expected_body():
    client = MagicMock()
    client.post.return_value = "txnqxned8j9qx1yp.fsbkg78.lti01.fbi"
    fbi_id = create_offline_investor(
        client,
        firm_name="C99-TEST",
        first_name="Test",
        last_name="User",
        email="test@example.com",
        close_id="CLOSE_X",
    )
    assert fbi_id.endswith(".fbi")
    path, body = client.post.call_args.args
    assert path == "/api/v3/fundsub/participant/addMainLpWorkflowWithoutJointInfo"
    assert body["fundSubId"] == "txnqxned8j9qx1yp.fsbkg78"
    lp0 = body["lpsToInvite"][0]
    assert lp0["lpInfo"]["firmName"] == "C99-TEST"
    assert lp0["lpInfo"]["lpContact"]["email"] == "test@example.com"
    assert lp0["closeIdOpt"] == "CLOSE_X"


def _dashboard_response(*rows):
    """Build a fake getAdvancedDashboardData response from rowMetadata dicts."""
    return {
        "dashboardData": {
            "rows": [{"rowMetadata": r, "cellsData": []} for r in rows]
        }
    }


def test_find_lp_by_firm_name_returns_lp_id():
    client = MagicMock()
    client.post.return_value = _dashboard_response(
        {"lpInvestmentEntity": "OTHER", "lpId": "lp-other",
         "lpInfo": {}, "status": {"value": 9}},
        {"lpInvestmentEntity": "C99-TEST", "lpId": "lp-target",
         "lpInfo": {}, "status": {"value": 9}},
    )
    lp_id = find_lp_by_firm_name(client, "C99-TEST")
    assert lp_id == "lp-target"


def test_find_lp_by_firm_name_returns_none_if_absent():
    client = MagicMock()
    client.post.return_value = _dashboard_response()
    assert find_lp_by_firm_name(client, "C99-TEST") is None


def test_list_existing_probe_profiles_filters_by_prefix():
    client = MagicMock()
    client.post.return_value = _dashboard_response(
        {"lpInvestmentEntity": "C01-FOO", "lpId": "lp-1",
         "lpInfo": {}, "status": {"value": 9}},
        {"lpInvestmentEntity": "C02-BAR", "lpId": "lp-2",
         "lpInfo": {}, "status": {"value": 9}},
        {"lpInvestmentEntity": "SomeOther", "lpId": "lp-3",
         "lpInfo": {}, "status": {"value": 5}},
    )
    profiles = list_existing_probe_profiles(client, prefix="C")
    assert {p.firm_name for p in profiles} == {"C01-FOO", "C02-BAR"}
    assert all(p.status == "9" for p in profiles if p.firm_name.startswith("C"))
