import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from src import yahoo_client
from src.settings import Settings


def load_token_payload() -> dict:
    data_path = Path("tests/_data/yahoo_token_response.json")
    with data_path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def test_build_authorization_url_uses_defaults(tmp_path):
    oauth_file = tmp_path / "oauth2.json"
    settings = Settings(
        YAHOO_OAUTH_FILE=str(oauth_file),
        YAHOO_CONSUMER_KEY="client-id",
        YAHOO_CONSUMER_SECRET="client-secret",
        YAHOO_REDIRECT_URI="https://example.com/callback",
    )

    result = yahoo_client.build_authorization_url(settings)

    assert result["authorization_url"].startswith("https://api.login.yahoo.com/oauth2/request_auth?")
    assert "client-id" in result["authorization_url"]
    assert result["redirect_uri"] == "https://example.com/callback"


def test_exchange_authorization_code_persists_tokens(tmp_path, monkeypatch):
    oauth_file = tmp_path / "oauth2.json"
    settings = Settings(
        YAHOO_OAUTH_FILE=str(oauth_file),
        YAHOO_CONSUMER_KEY="client-id",
        YAHOO_CONSUMER_SECRET="client-secret",
    )

    payload = load_token_payload()

    class DummyResponse:
        status_code = 200

        def __init__(self, data: dict):
            self._data = data
            self.text = json.dumps(data)

        def json(self):
            return self._data

    def fake_post(url, data, headers, timeout):  # noqa: ANN001
        assert url == "https://api.login.yahoo.com/oauth2/get_token"
        assert data["code"] == "abc123"
        assert data["grant_type"] == "authorization_code"
        assert "Basic" in headers["Authorization"]
        return DummyResponse(payload)

    monkeypatch.setattr(yahoo_client.requests, "post", fake_post)

    result = yahoo_client.exchange_authorization_code(settings, code="abc123")

    assert result["status"] == "stored"
    assert result["guid"] == payload["xoauth_yahoo_guid"]
    assert isinstance(result["expires_at"], datetime)
    assert result["expires_at"].tzinfo is timezone.utc

    stored = json.loads(oauth_file.read_text(encoding="utf-8"))
    assert stored["access_token"] == payload["access_token"]
    assert stored["refresh_token"] == payload["refresh_token"]
    assert stored["token_type"] == payload["token_type"]


def test_exchange_authorization_code_missing_token(monkeypatch, tmp_path):
    oauth_file = tmp_path / "oauth2.json"
    settings = Settings(
        YAHOO_OAUTH_FILE=str(oauth_file),
        YAHOO_CONSUMER_KEY="client-id",
        YAHOO_CONSUMER_SECRET="client-secret",
    )

    invalid_payload = {"access_token": "only"}

    class DummyResponse:
        status_code = 200

        def __init__(self, data: dict):
            self._data = data
            self.text = json.dumps(data)

        def json(self):
            return self._data

    monkeypatch.setattr(
        yahoo_client.requests,
        "post",
        lambda *args, **kwargs: DummyResponse(invalid_payload),
    )

    with pytest.raises(yahoo_client.YahooOAuthError):
        yahoo_client.exchange_authorization_code(settings, code="abc123")
