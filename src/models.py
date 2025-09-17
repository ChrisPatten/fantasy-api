from __future__ import annotations

from typing import Any, Dict, List, Optional

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
    team_name: str | None = None
    league_name: str | None = None


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
    league_name: str | None = None
    teams: List[LeagueTeam]


class TeamsResponse(BaseModel):
    leagues: List[LeagueSummary]


# Roster
class Player(BaseModel):
    name: str
    position: Optional[str] = None
    slot: Optional[str] = Field(default=None, description="Roster slot such as QB, WR, BN")
    status: Optional[str] = None
    eligible_positions: List[str] = Field(default_factory=list)
    player_id: Optional[int] = None
    position_type: Optional[str] = None


class RosterResponse(BaseModel):
    team_key: str
    players: List[Player]


class AvailablePlayer(BaseModel):
    player_id: Optional[int] = None
    name: str
    eligible_positions: List[str] = Field(default_factory=list)
    percent_owned: Optional[float] = None
    status: Optional[str] = None
    position_type: Optional[str] = None


class RosterAnalysisResponse(BaseModel):
    team_key: str
    roster: List[Player]
    waiver_recommendations: Dict[str, List[AvailablePlayer]]


class FreeAgentsResponse(BaseModel):
    team_key: str
    positions: List[str]
    free_agents: Dict[str, List[AvailablePlayer]]


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
