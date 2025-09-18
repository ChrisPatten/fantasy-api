def test_roster_requires_team_key(client):
    r = client.get("/v1/roster", headers={"X-API-Key": "test-key"})
    assert r.status_code == 422
    body = r.json()
    assert body["code"] == "validation_error"


def test_roster_team_key_pattern(client):
    r = client.get("/v1/roster?team_key=bad-format", headers={"X-API-Key": "test-key"})
    assert r.status_code == 422


def test_roster_happy_path(client):
    r = client.get("/v1/roster?team_key=423.l.12345.t.7", headers={"X-API-Key": "test-key"})
    assert r.status_code == 200
    data = r.json()
    assert data["team_key"] == "423.l.12345.t.7"
    assert len(data["players"]) == 2
    assert data["players"][0]["slot"] == "QB"


def test_free_agents_requires_team_key(client):
    r = client.get("/v1/free-agents", headers={"X-API-Key": "test-key"})
    assert r.status_code == 422
    body = r.json()
    assert body["code"] == "validation_error"


def test_free_agents_team_key_pattern(client):
    r = client.get("/v1/free-agents?team_key=bad", headers={"X-API-Key": "test-key"})
    assert r.status_code == 422


def test_free_agents_happy_path(client):
    r = client.get(
        "/v1/free-agents?team_key=423.l.12345.t.7&positions=qb&positions=wr&limit=3",
        headers={"X-API-Key": "test-key"},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["team_key"] == "423.l.12345.t.7"
    assert data["positions"] == ["QB", "WR"]
    assert set(data["free_agents"].keys()) == {"QB", "WR"}


def test_waivers_requires_params(client):
    r = client.get("/v1/waivers", headers={"X-API-Key": "test-key"})
    assert r.status_code == 422


def test_waivers_happy_path(client):
    r = client.get("/v1/waivers?league_key=423.l.12345&team_key=423.l.12345.t.7", headers={"X-API-Key": "test-key"})
    assert r.status_code == 200
    data = r.json()
    assert set(data.keys()) == {"settings", "priority", "pending"}
