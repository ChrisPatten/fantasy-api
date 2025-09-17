import os
import pytest
from fastapi.testclient import TestClient

from src.app import create_app
from src.settings import Settings


@pytest.fixture()
def settings():
    return Settings(API_KEY="test-key", YAHOO_OAUTH_FILE="/tmp/does-not-matter.json")


@pytest.fixture()
def client(settings: Settings, monkeypatch):
    # Patch yahoo_client functions to avoid external calls
    from src import yahoo_client

    def fake_list(settings, season):
        return [
            {
                "league_id": "12345",
                "league_key": "423.l.12345",
                "teams": [
                    {"team_key": "423.l.12345.t.1", "team_name": "Team One", "waiver_priority": 3},
                    {"team_key": "423.l.12345.t.7", "team_name": "Team Seven", "waiver_priority": 1},
                ],
            }
        ]

    def fake_roster(settings, team_key, week):
        return {
            "team_key": team_key,
            "week": week,
            "players": [
                {"name": "Player A", "position": "QB", "status": None},
                {"name": "Player B", "position": "RB", "status": "Q"},
            ],
        }

    def fake_waivers(settings, league_key, team_key):
        return {
            "settings": {"waiver_type": "faab", "waiver_rule": "cont", "uses_faab": True, "waiver_time": 172800},
            "priority": [
                {"team_name": "Team Seven", "team_key": team_key, "priority": 1},
                {"team_name": "Team One", "team_key": "423.l.12345.t.1", "priority": 2},
            ],
            "pending": [
                {"player": "Player C", "action_type": "add", "destination_team_key": team_key, "faab_bid": 12.0}
            ],
        }

    monkeypatch.setattr(yahoo_client, "list_teams", fake_list)
    monkeypatch.setattr(yahoo_client, "get_roster", fake_roster)
    monkeypatch.setattr(yahoo_client, "get_waivers", fake_waivers)

    app = create_app(settings)
    return TestClient(app)

