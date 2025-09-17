from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import requests
from yahoo_oauth import OAuth2

try:
    import yahoo_fantasy_api as yfa
except Exception:  # pragma: no cover - library not available during some test runs
    yfa = None  # type: ignore

from .settings import Settings

log = logging.getLogger(__name__)


def _get_oauth(settings: Settings) -> OAuth2:
    # Disable file writes so we can mount oauth2.json read-only in containers.
    # yahoo-oauth will otherwise attempt to persist tokens back to from_file.
    oauth = OAuth2(None, None, from_file=settings.YAHOO_OAUTH_FILE, store_file=False)
    if not oauth.token_is_valid():
        log.info("oauth.refresh", file=settings.YAHOO_OAUTH_FILE)
        oauth.refresh_access_token()
    return oauth


def get_session(settings: Settings) -> requests.Session:
    oauth = _get_oauth(settings)
    if not oauth.token_is_valid():
        oauth.refresh_access_token()
    token = getattr(oauth, "access_token", None)
    if not token:
        oauth.refresh_access_token()
        token = getattr(oauth, "access_token", None)
    if not token:
        raise RuntimeError("Yahoo OAuth did not provide an access_token")
    s = requests.Session()
    s.headers.update({
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "User-Agent": "fantasy-api/1.0",
    })
    return s


def list_teams(settings: Settings, season: Optional[int]) -> List[Dict[str, Any]]:
    """Return list of leagues with teams.

    Each item: {league_id, league_key, teams: [{team_key, team_name, waiver_priority}...]}
    """
    oauth = _get_oauth(settings)
    if yfa is None:
        raise RuntimeError("yahoo_fantasy_api not available")
    gm = yfa.Game(oauth, "nfl")
    league_ids = gm.league_ids(year=season) if season else gm.league_ids()
    leagues: List[Dict[str, Any]] = []
    for lid in league_ids:
        lg = yfa.League(oauth, lid)
        meta = lg.league_settings() if hasattr(lg, "league_settings") else {"league_key": lid}
        league_key = meta.get("league_key", lid)
        teams_raw = lg.teams()
        teams_list: List[Dict[str, Any]] = []
        # teams() returns dict keyed by team_key
        for tkey, tdata in teams_raw.items():
            teams_list.append({
                "team_key": tkey,
                "team_name": tdata.get("name") or tdata.get("team_name") or "",
                "waiver_priority": tdata.get("waiver_priority"),
            })
        leagues.append({
            "league_id": str(lid),
            "league_key": str(league_key),
            "teams": teams_list,
        })
    return leagues


def get_roster(settings: Settings, team_key: str, week: Optional[int]) -> Dict[str, Any]:
    oauth = _get_oauth(settings)
    if yfa is None:
        raise RuntimeError("yahoo_fantasy_api not available")
    tm = yfa.Team(oauth, team_key)
    roster = tm.roster(week=week) if week else tm.roster()
    players = []
    for p in roster:
        name = p.get("name") or p.get("full") or p.get("full_name") or p.get("display_position") or ""
        players.append({
            "name": name,
            "position": p.get("position") or p.get("selected_position") or None,
            "status": p.get("status") or None,
        })
    return {"team_key": team_key, "week": week, "players": players}


def _parse_waiver_transactions(data: Dict[str, Any]) -> List[Dict[str, Any]]:
    pending: List[Dict[str, Any]] = []
    # The Yahoo API JSON has a nested structure; we aim to extract essentials.
    try:
        transactions = data["fantasy_content"]["league"][1]["transactions"]
    except Exception:
        return pending
    # transactions can be a dict with index keys or a list
    if isinstance(transactions, dict):
        iterable = transactions.values()
    elif isinstance(transactions, list):
        iterable = transactions
    else:
        iterable = []
    for t in iterable:
        if not isinstance(t, dict) or "transaction" not in t:
            continue
        trx = t.get("transaction", {})
        t_type = trx.get("type", "waiver")
        actions = trx.get("players", {})
        faab = None
        try:
            faab = float(trx.get("faab_bid")) if trx.get("faab_bid") is not None else None
        except Exception:
            faab = None
        # actions can be dict or list in some responses
        if isinstance(actions, dict):
            action_iter = actions.values()
        elif isinstance(actions, list):
            action_iter = actions
        else:
            action_iter = []
        for a in action_iter:
                if not isinstance(a, dict) or "player" not in a:
                    continue
                player = a["player"][0].get("name", {}).get("full") or ""
                # Some structures: a["transaction_data"]["type"], source_type/dest_type
                txd = a.get("transaction_data", {})
                action_type = txd.get("type", t_type)
                src = txd.get("source_team_key")
                dst = txd.get("destination_team_key")
                pending.append({
                    "player": player,
                    "action_type": action_type,
                    "source_team_key": src,
                    "destination_team_key": dst,
                    "faab_bid": faab,
                })
    return pending


def get_waivers(settings: Settings, league_key: str, team_key: str) -> Dict[str, Any]:
    oauth = _get_oauth(settings)
    if yfa is None:
        raise RuntimeError("yahoo_fantasy_api not available")
    lg = yfa.League(oauth, league_key)
    st = lg.settings()
    teams_raw = lg.teams()
    priority: List[Dict[str, Any]] = []
    for tkey, tdata in teams_raw.items():
        priority.append({
            "team_name": tdata.get("name") or tdata.get("team_name") or "",
            "team_key": tkey,
            "priority": tdata.get("waiver_priority"),
        })
    # transactions via REST
    session = get_session(settings)
    base = "https://fantasysports.yahooapis.com/fantasy/v2"
    url = f"{base}/league/{league_key}/transactions;types=waiver;team_key={team_key}?format=json"
    resp = session.get(url, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    pending = _parse_waiver_transactions(data)
    settings_out = {
        "waiver_type": st.get("waiver_type"),
        "waiver_rule": st.get("waiver_rule"),
        "uses_faab": st.get("uses_faab"),
        "waiver_time": st.get("waiver_time"),
    }
    return {"settings": settings_out, "priority": priority, "pending": pending}
