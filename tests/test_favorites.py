from http import HTTPStatus


def test_favorites_enriched_with_names(client, settings):
    settings.FAVORITE_TEAMS = "My Team@423.l.12345|423.l.12345.t.7"

    response = client.get("/v1/favorites", headers={"X-API-Key": "test-key"})

    assert response.status_code == HTTPStatus.OK
    payload = response.json()
    assert payload == {
        "favorites": [
            {
                "league_key": "423.l.12345",
                "team_key": "423.l.12345.t.7",
                "alias": "My Team",
                "team_name": "Team Seven",
                "league_name": "League 12345",
            }
        ]
    }



def test_favorites_handles_missing_config(client, settings):
    settings.FAVORITE_TEAMS = ""

    response = client.get("/v1/favorites", headers={"X-API-Key": "test-key"})

    assert response.status_code == HTTPStatus.OK
    assert response.json() == {"favorites": []}
