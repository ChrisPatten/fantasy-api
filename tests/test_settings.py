from src.settings import Settings


def test_favorite_teams_alias_parsing():
    settings = Settings(
        FAVORITE_TEAMS="Alias One@461.l.123|461.l.123.t.1;461.l.456.t.2",
    )

    favorites = settings.favorite_teams()

    assert favorites == [
        {
            "league_key": "461.l.123",
            "team_key": "461.l.123.t.1",
            "alias": "Alias One",
        },
        {
            "league_key": "461.l.456",
            "team_key": "461.l.456.t.2",
            "alias": "fav2",
        },
    ]
