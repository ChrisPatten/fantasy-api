def test_requires_api_key(client):
    # health is public
    assert client.get("/health").status_code == 200
    # protected endpoint without key
    r = client.get("/v1/teams")
    assert r.status_code == 401
    assert r.json()["code"] == "unauthorized"


def test_with_api_key_ok(client):
    headers = {"X-API-Key": "test-key"}
    r = client.get("/v1/teams", headers=headers)
    assert r.status_code == 200
    body = r.json()
    assert "leagues" in body
    assert isinstance(body["leagues"], list)


def test_get_auth_url(client):
    headers = {"X-API-Key": "test-key"}
    r = client.get("/v1/auth/url", headers=headers)
    assert r.status_code == 200
    body = r.json()
    assert body["authorization_url"].startswith("https://login.yahoo.com/")
    assert body["redirect_uri"] == "oob"


def test_exchange_auth_code(client):
    headers = {"X-API-Key": "test-key"}
    payload = {"code": "test-code"}
    r = client.post("/v1/auth/token", headers=headers, json=payload)
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "stored"
    assert body["token_type"] == "bearer"
