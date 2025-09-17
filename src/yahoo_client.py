from __future__ import annotations

import base64
import json
import logging
import os
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode

import requests
from yahoo_oauth import OAuth2

try:
    import yahoo_fantasy_api as yfa
except Exception:  # pragma: no cover - library not available during some test runs
    yfa = None  # type: ignore

from .settings import Settings


def _to_int_or_none(value: Any) -> Optional[int]:
    try:
        if value is None:
            return None
        return int(value)
    except (TypeError, ValueError):
        return None

log = logging.getLogger(__name__)


class YahooOAuthError(RuntimeError):
    """Raised when there is an unrecoverable Yahoo OAuth error."""

    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


def _oauth_file_path(settings: Settings) -> Path:
    return Path(settings.YAHOO_OAUTH_FILE)


def _load_oauth_data(settings: Settings) -> Dict[str, Any]:
    path = _oauth_file_path(settings)
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except json.JSONDecodeError as exc:
        raise YahooOAuthError(f"Invalid JSON in OAuth file {path}", status_code=500) from exc


def _write_oauth_data(settings: Settings, data: Dict[str, Any]) -> None:
    path = _oauth_file_path(settings)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(prefix="oauth2_", suffix=".json", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2, sort_keys=True)
            handle.write("\n")
        os.replace(tmp_path, path)
        try:
            os.chmod(path, 0o600)
        except PermissionError:
            # Not fatal; continue with current permissions.
            pass
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


def _resolve_credentials(settings: Settings, data: Dict[str, Any]) -> Dict[str, str]:
    consumer_key = settings.YAHOO_CONSUMER_KEY or data.get("consumer_key")
    consumer_secret = settings.YAHOO_CONSUMER_SECRET or data.get("consumer_secret")
    if not consumer_key or not consumer_secret:
        raise YahooOAuthError("Yahoo consumer key/secret not configured", status_code=500)
    redirect_uri = data.get("redirect_uri") or settings.YAHOO_REDIRECT_URI or "oob"
    return {
        "consumer_key": consumer_key,
        "consumer_secret": consumer_secret,
        "redirect_uri": redirect_uri,
    }


def _basic_auth_header(consumer_key: str, consumer_secret: str) -> str:
    raw = f"{consumer_key}:{consumer_secret}".encode("utf-8")
    return base64.b64encode(raw).decode("ascii")


def build_authorization_url(settings: Settings, *, state: Optional[str] = None, redirect_uri: Optional[str] = None) -> Dict[str, Any]:
    """Return an authorization URL that the user can visit to start OAuth."""

    data = _load_oauth_data(settings)
    creds = _resolve_credentials(settings, data)
    redirect = redirect_uri or creds["redirect_uri"]
    params = {
        "client_id": creds["consumer_key"],
        "redirect_uri": redirect,
        "response_type": "code",
    }
    if state:
        params["state"] = state
    url = "https://api.login.yahoo.com/oauth2/request_auth?" + urlencode(params)
    return {
        "authorization_url": url,
        "redirect_uri": redirect,
        "state": state,
    }


def exchange_authorization_code(
    settings: Settings,
    *,
    code: str,
    redirect_uri: Optional[str] = None,
    state: Optional[str] = None,
) -> Dict[str, Any]:
    """Exchange a user-provided authorization code for tokens and persist them."""

    if not code.strip():
        raise YahooOAuthError("Authorization code is required")

    data = _load_oauth_data(settings)
    creds = _resolve_credentials(settings, data)
    redirect = redirect_uri or creds["redirect_uri"]

    headers = {
        "Authorization": f"Basic {_basic_auth_header(creds['consumer_key'], creds['consumer_secret'])}",
        "Content-Type": "application/x-www-form-urlencoded",
    }
    payload = {
        "code": code,
        "redirect_uri": redirect,
        "grant_type": "authorization_code",
    }
    try:
        response = requests.post(
            "https://api.login.yahoo.com/oauth2/get_token",
            data=payload,
            headers=headers,
            timeout=30,
        )
    except requests.RequestException as exc:
        log.error("oauth.exchange.network_error", error=str(exc))
        raise YahooOAuthError("Failed to reach Yahoo OAuth service", status_code=502) from exc

    if response.status_code >= 400:
        log.warning(
            "oauth.exchange.failed",
            status=response.status_code,
            body=response.text[:256],
        )
        raise YahooOAuthError("Yahoo rejected the authorization code", status_code=response.status_code)

    try:
        token_payload = response.json()
    except ValueError as exc:
        log.error("oauth.exchange.invalid_json", response_text=response.text[:256])
        raise YahooOAuthError("Yahoo returned an invalid OAuth response", status_code=502) from exc

    access_token = token_payload.get("access_token")
    refresh_token = token_payload.get("refresh_token")
    token_type = token_payload.get("token_type")
    if not access_token or not refresh_token or not token_type:
        raise YahooOAuthError("Yahoo did not provide required OAuth tokens", status_code=502)

    token_time = time.time()
    stored = dict(data)
    stored.update(
        {
            "consumer_key": creds["consumer_key"],
            "consumer_secret": creds["consumer_secret"],
            "redirect_uri": redirect,
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": token_type,
            "token_time": token_time,
        }
    )

    optional_keys = {
        "expires_in": token_payload.get("expires_in"),
        "scope": token_payload.get("scope"),
        "guid": token_payload.get("xoauth_yahoo_guid"),
        "id_token": token_payload.get("id_token"),
        "state": state,
    }
    for key, value in optional_keys.items():
        if value is not None:
            stored[key] = value

    _write_oauth_data(settings, stored)

    expires_at = None
    expires_in = token_payload.get("expires_in")
    if isinstance(expires_in, (int, float)):
        expires_at = datetime.fromtimestamp(token_time + float(expires_in), tz=timezone.utc)

    return {
        "status": "stored",
        "token_type": stored.get("token_type"),
        "guid": stored.get("guid"),
        "scope": stored.get("scope"),
        "expires_at": expires_at,
    }


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
        league_name = meta.get("name") or meta.get("league_name")
        if not league_name and hasattr(lg, "metadata"):
            try:
                metadata = lg.metadata()
                if isinstance(metadata, dict):
                    league_name = metadata.get("name") or metadata.get("league_name")
            except Exception:
                league_name = None
        teams_raw = lg.teams()
        teams_list: List[Dict[str, Any]] = []
        # teams() returns dict keyed by team_key
        for tkey, tdata in teams_raw.items():
            teams_list.append({
                "team_key": tkey,
                "team_name": tdata.get("name") or tdata.get("team_name") or "",
                "waiver_priority": _to_int_or_none(tdata.get("waiver_priority")),
            })
        leagues.append({
            "league_id": str(lid),
            "league_key": str(league_key),
            "league_name": league_name if league_name else None,
            "teams": teams_list,
        })
    return leagues


def enrich_favorites(settings: Settings, favorites: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not favorites:
        return []
    try:
        leagues = list_teams(settings, season=None)
    except Exception as exc:  # pragma: no cover - defensive logging path
        log.warning("favorites.enrichment_failed", error=str(exc))
        return favorites

    league_lookup: Dict[str, Dict[str, Any]] = {}
    team_lookup: Dict[str, Dict[str, Any]] = {}
    for league in leagues:
        league_key = str(league.get("league_key")) if league.get("league_key") is not None else ""
        league_lookup[league_key] = {
            "league_key": league_key,
            "league_name": league.get("league_name"),
        }
        for team in league.get("teams", []):
            team_key = team.get("team_key")
            if not team_key:
                continue
            team_lookup[str(team_key)] = {
                "league_key": league_key,
                "league_name": league.get("league_name"),
                "team_name": team.get("team_name"),
            }

    enriched: List[Dict[str, Any]] = []
    for fav in favorites:
        entry = dict(fav)
        info = team_lookup.get(entry.get("team_key"))
        if info:
            entry.setdefault("league_key", info.get("league_key"))
            entry["team_name"] = info.get("team_name")
            entry["league_name"] = info.get("league_name")
        elif entry.get("league_key"):
            league_info = league_lookup.get(str(entry["league_key"]))
            if league_info:
                entry["league_name"] = league_info.get("league_name")
        enriched.append(entry)
    return enriched


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
