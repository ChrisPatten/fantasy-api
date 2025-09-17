from __future__ import annotations

from typing import Any, List, Optional

from datetime import datetime

from pydantic import AnyHttpUrl, BaseModel, Field


class Error(BaseModel):
    code: str
    message: str
    details: Optional[Any] = None


class Health(BaseModel):
    status: str = "ok"


class FavoriteTeam(BaseModel):
    league_key: str | None = None
    team_key: str
    alias: str | None = None


class FavoritesResponse(BaseModel):
    favorites: List[FavoriteTeam]


# Teams
class LeagueTeam(BaseModel):
    team_key: str
    team_name: str
    waiver_priority: Optional[int] = None


class LeagueSummary(BaseModel):
    league_id: str
    league_key: str
    teams: List[LeagueTeam]


class TeamsResponse(BaseModel):
    leagues: List[LeagueSummary]


# Roster
class Player(BaseModel):
    name: str
    position: Optional[str] = None
    status: Optional[str] = None


class RosterResponse(BaseModel):
    team_key: str
    week: Optional[int] = None
    players: List[Player]


# Waivers
class WaiverSettings(BaseModel):
    waiver_type: Optional[str] = None
    waiver_rule: Optional[str] = None
    uses_faab: Optional[bool] = None
    waiver_time: Optional[int] = Field(default=None, description="Time in seconds players remain on waivers")


class WaiverPriorityItem(BaseModel):
    team_name: str
    team_key: str
    priority: Optional[int] = None


class WaiverClaim(BaseModel):
    player: str
    action_type: str
    source_team_key: Optional[str] = None
    destination_team_key: Optional[str] = None
    faab_bid: Optional[float] = None


class WaiversResponse(BaseModel):
    settings: WaiverSettings
    priority: List[WaiverPriorityItem]
    pending: List[WaiverClaim]


# OAuth flow
class AuthUrlResponse(BaseModel):
    authorization_url: AnyHttpUrl
    redirect_uri: str
    state: Optional[str] = None


class AuthCodeRequest(BaseModel):
    code: str = Field(..., min_length=1)
    redirect_uri: Optional[str] = None
    state: Optional[str] = None


class AuthCodeResponse(BaseModel):
    status: str = Field(default="stored")
    token_type: Optional[str] = None
    guid: Optional[str] = None
    scope: Optional[str] = None
    expires_at: Optional[datetime] = None
