from http import HTTPStatus


def test_favorites_enriched_with_names(client, settings):
    settings.FAVORITE_TEAMS = "My Team@423.l.12345|423.l.12345.t.7"

    response = client.get("/v1/favorites", headers={"X-API-Key": "test-key"})

    assert response.status_code == HTTPStatus.OK
    payload = response.json()
    assert payload == {
        "favorites": [
            {
                "team_key": "423.l.12345.t.7",
                "team_name": "Team Seven",
                "roster": {
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
                },
                "league_settings": {
                    "league_key": "423.l.12345",
                    "name": "League 12345",
                    "scoring_type": "headpoints",
                },
            }
        ]
    }



def test_favorites_handles_missing_config(client, settings):
    settings.FAVORITE_TEAMS = ""

    response = client.get("/v1/favorites", headers={"X-API-Key": "test-key"})

    assert response.status_code == HTTPStatus.OK
    assert response.json() == {"favorites": []}
