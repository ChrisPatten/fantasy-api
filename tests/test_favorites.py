from http import HTTPStatus


def test_favorites_enriched_with_names(client, settings):
    settings.FAVORITE_TEAMS = "My Team@423.l.12345|423.l.12345.t.7"

    response = client.get("/v1/favorites", headers={"X-API-Key": "test-key"})

    assert response.status_code == HTTPStatus.OK
    payload = response.json()
    favorites = payload["favorites"]
    assert len(favorites) == 1
    team = favorites[0]
    assert team["team_key"] == "423.l.12345.t.7"
    assert team["team_name"] == "Team Seven"
    assert team["roster"] == {
        "team_key": "423.l.12345.t.7",
        "players": [
            {
                "name": "Player A",
                "position": "QB",
                "slot": "QB",
                "status": None,
                "eligible_positions": ["QB"],
                "player_id": 1,
                "position_type": "O",
            },
            {
                "name": "Player B",
                "position": "RB",
                "slot": "BN",
                "status": "Q",
                "eligible_positions": ["RB"],
                "player_id": 2,
                "position_type": "O",
            },
        ],
    }
    settings = team["league_settings"]
    assert settings["league_key"] == "423.l.12345"
    assert settings["league_id"] == "12345"
    assert settings["name"] == "League 12345"
    assert settings["scoring_type"] == "headpoints"



def test_favorites_handles_missing_config(client, settings):
    settings.FAVORITE_TEAMS = ""

    response = client.get("/v1/favorites", headers={"X-API-Key": "test-key"})

    assert response.status_code == HTTPStatus.OK
    assert response.json() == {"favorites": []}
