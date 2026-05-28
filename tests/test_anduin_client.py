from unittest.mock import patch, MagicMock

from automation.anduin_client import AnduinClient


def test_post_includes_auth_cookies():
    cookies = {"CF_Authorization": "cf", "stargazer_cookie": "sg"}
    client = AnduinClient(cookies=cookies, base_url="https://example.test")
    with patch.object(client.session, "post") as post:
        post.return_value = MagicMock(status_code=200, text="ok", json=lambda: {"ok": True})
        client.post("/api/v3/account/get-user-profile", json={})
        args, kwargs = post.call_args
        assert args[0] == "https://example.test/api/v3/account/get-user-profile"
        assert client.session.cookies.get("CF_Authorization") == "cf"
        assert client.session.cookies.get("stargazer_cookie") == "sg"


def test_post_raises_on_non_2xx():
    client = AnduinClient(cookies={"CF_Authorization": "x", "stargazer_cookie": "y"}, base_url="https://example.test")
    with patch.object(client.session, "post") as post:
        post.return_value = MagicMock(status_code=401, text="unauthorized")
        import pytest
        with pytest.raises(RuntimeError, match="401"):
            client.post("/api/v3/account/get-user-profile", json={})
