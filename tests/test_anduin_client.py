from unittest.mock import patch, MagicMock

import pytest

from automation.anduin_client import AnduinClient


def test_post_includes_bearer_header():
    client = AnduinClient(bearer="abc.def.ghi", base_url="https://example.test")
    assert client.session.headers["Authorization"] == "Bearer abc.def.ghi"
    with patch.object(client.session, "post") as post:
        post.return_value = MagicMock(status_code=200, text='{"ok":true}', json=lambda: {"ok": True})
        client.post("/api/v3/account/get-user-profile", json={})
        args, _ = post.call_args
        assert args[0] == "https://example.test/api/v3/account/get-user-profile"


def test_post_raises_on_non_2xx():
    client = AnduinClient(bearer="x.y.z", base_url="https://example.test")
    with patch.object(client.session, "post") as post:
        post.return_value = MagicMock(status_code=401, text="unauthorized")
        with pytest.raises(RuntimeError, match="401"):
            client.post("/api/v3/account/get-user-profile", json={})


def test_post_returns_empty_dict_for_blank_response():
    client = AnduinClient(bearer="x.y.z", base_url="https://example.test")
    with patch.object(client.session, "post") as post:
        post.return_value = MagicMock(status_code=200, text="")
        assert client.post("/api/v3/anything", json={}) == {}
