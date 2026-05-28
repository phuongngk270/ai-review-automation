from automation.cookies import parse_cookies_json


def test_parse_cookies_json_extracts_required_cookies():
    payload = [
        {"name": "CF_Authorization", "value": "cf-token", "domain": "fundsub-minas-tirith.anduin.dev"},
        {"name": "stargazer_cookie", "value": "sg-token", "domain": "fundsub-minas-tirith.anduin.dev"},
        {"name": "unrelated", "value": "x", "domain": "other.example.com"},
    ]
    cookies = parse_cookies_json(payload, domain="fundsub-minas-tirith.anduin.dev")
    assert cookies == {"CF_Authorization": "cf-token", "stargazer_cookie": "sg-token"}


def test_parse_cookies_json_raises_when_session_missing():
    payload = [
        {"name": "CF_Authorization", "value": "cf-token", "domain": "fundsub-minas-tirith.anduin.dev"},
    ]
    import pytest
    with pytest.raises(RuntimeError, match="stargazer_cookie"):
        parse_cookies_json(payload, domain="fundsub-minas-tirith.anduin.dev")
