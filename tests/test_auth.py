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

