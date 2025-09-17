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
                "league_name": "League 12345",
                "teams": [
                    {"team_key": "423.l.12345.t.1", "team_name": "Team One", "waiver_priority": 3},
                    {"team_key": "423.l.12345.t.7", "team_name": "Team Seven", "waiver_priority": 1},
                ],
            }
        ]

    def fake_roster(settings, team_key):
        return {
            "team_key": team_key,
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

    def fake_build_auth_url(settings, state=None, redirect_uri=None):
        return {
            "authorization_url": "https://login.yahoo.com/authorize?foo=bar",
            "redirect_uri": redirect_uri or "oob",
            "state": state,
        }

    def fake_exchange_auth_code(settings, *, code, redirect_uri=None, state=None):
        assert code == "test-code"
        return {
            "status": "stored",
            "token_type": "bearer",
            "guid": "guid123",
            "scope": "fspt-r",
            "expires_at": "2024-01-01T00:00:00+00:00",
        }

    def fake_roster_analysis(settings, team_key, positions=None, per_position=5):
        roster = fake_roster(settings, team_key)
        recs = {
            "QB": [
                {
                    "player_id": 1001,
                    "name": "Free QB",
                    "eligible_positions": ["QB"],
                    "percent_owned": 12.5,
                    "status": None,
                    "position_type": "O",
                }
            ],
            "WR": [
                {
                    "player_id": 1002,
                    "name": "Free WR",
                    "eligible_positions": ["WR"],
                    "percent_owned": 24.0,
                    "status": None,
                    "position_type": "O",
                }
            ],
            "RB": [
                {
                    "player_id": 1003,
                    "name": "Free RB",
                    "eligible_positions": ["RB"],
                    "percent_owned": 31.0,
                    "status": "P",
                    "position_type": "O",
                }
            ],
            "TE": [
                {
                    "player_id": 1004,
                    "name": "Free TE",
                    "eligible_positions": ["TE"],
                    "percent_owned": 8.5,
                    "status": None,
                    "position_type": "O",
                }
            ],
        }
        return {"team_key": team_key, "roster": roster["players"], "waiver_recommendations": recs}

    def fake_free_agents(settings, team_key, positions=None, per_position=25):
        normalized = [p.upper() for p in (positions or ["QB", "RB"]) if p]
        agents = {}
        for idx, pos in enumerate(normalized, start=1):
            agents[pos] = [
                {
                    "player_id": 2000 + idx,
                    "name": f"Free {pos} {idx}",
                    "eligible_positions": [pos],
                    "percent_owned": 10.0 * idx,
                    "status": None,
                    "position_type": "O",
                }
            ]
        return {"team_key": team_key, "positions": normalized, "free_agents": agents}

    monkeypatch.setattr(yahoo_client, "list_teams", fake_list)
    monkeypatch.setattr(yahoo_client, "get_roster", fake_roster)
    monkeypatch.setattr(yahoo_client, "get_waivers", fake_waivers)
    monkeypatch.setattr(yahoo_client, "build_authorization_url", fake_build_auth_url)
    monkeypatch.setattr(yahoo_client, "exchange_authorization_code", fake_exchange_auth_code)
    monkeypatch.setattr(yahoo_client, "get_roster_analysis", fake_roster_analysis)
    monkeypatch.setattr(yahoo_client, "get_free_agents", fake_free_agents)

    app = create_app(settings)
    return TestClient(app)
