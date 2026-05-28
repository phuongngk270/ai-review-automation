from unittest.mock import MagicMock

from automation.submissions import (
    submit_signed_subscription,
    submit_supporting_docs,
)


def test_submit_signed_subscription_body():
    client = MagicMock()
    client.post.return_value = {"dataExtractionWarningOpt": None}
    submit_signed_subscription(
        client,
        lp_id="LP_X",
        file_item_id="FILE_X",
        amount_usd=100000,
        amount_field_id="FIELD_X",
        firm_name="C99-TEST",
    )
    path, body = client.post.call_args.args
    assert path == "/api/v3/fundsub/subscription-doc/gpUploadSignedSubscriptionDoc"
    assert body == {
        "fundSubLpId": "LP_X",
        "uploadedDocs": ["FILE_X"],
        "submittedAmounts": [["FIELD_X", {"value": "100000"}]],
        "shouldApprove": False,
        "shouldCreateNewDataExtractRequest": False,
        "investmentEntityName": "C99-TEST",
    }


def test_submit_supporting_docs_one_call_per_file():
    client = MagicMock()
    client.post.return_value = {}
    submit_supporting_docs(client, lp_id="LP_X", file_item_ids=["F1", "F2"])
    paths = [c.args[0] for c in client.post.call_args_list]
    assert paths == [
        "/api/v3/fundsub/supportingdoc/v2/uploadFile",
        "/api/v3/fundsub/supportingdoc/v2/uploadFile",
    ]
    bodies = [c.args[1] for c in client.post.call_args_list]
    assert bodies[0] == {"lpId": "LP_X", "fileIds": ["F1"], "docType": ""}
    assert bodies[1] == {"lpId": "LP_X", "fileIds": ["F2"], "docType": ""}


def test_submit_supporting_docs_noop_on_empty():
    client = MagicMock()
    submit_supporting_docs(client, lp_id="LP_X", file_item_ids=[])
    client.post.assert_not_called()
