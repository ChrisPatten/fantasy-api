from __future__ import annotations

from functools import lru_cache
import re
from typing import List

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", case_sensitive=False)

    # Core config
    YAHOO_OAUTH_FILE: str = Field(default="/data/oauth2.json")
    API_KEY: str | None = Field(default=None)
    CORS_ALLOW_ORIGINS: str = Field(default="*")
    LOG_LEVEL: str = Field(default="INFO")
    PORT: int = Field(default=8000)

    # Rate limiting (per-IP)
    RATE_LIMIT_PER_MIN: int = Field(default=60, description="Allowed steady-state requests per minute per IP")
    RATE_LIMIT_BURST: int = Field(default=10, description="Allowed burst above steady rate")

    # Favorite leagues/teams (semicolon or comma-separated entries).
    # Each entry is "<league_key>|<team_key>" (pipe or colon supported as separator).
    FAVORITE_TEAMS: str = Field(default="", description="Configured favorite league/team pairs")

    def cors_origins(self) -> List[str]:
        raw = (self.CORS_ALLOW_ORIGINS or "").strip()
        if raw == "*" or raw == "":
            return ["*"]
        return [o.strip() for o in raw.split(",") if o.strip()]

    def favorite_teams(self) -> List[dict]:
        pairs: List[dict] = []
        raw = (self.FAVORITE_TEAMS or "").strip()
        if not raw:
            return pairs
        # Split entries by ';' or ','
        items = []
        for sep in [';', ',']:
            if sep in raw:
                items = [x for x in [p.strip() for p in raw.split(sep)] if x]
                break
        if not items:
            items = [raw]
        for idx, item in enumerate(items, start=1):
            # Allow either '|' or ':' between league and team keys
            if '|' in item:
                league_key, team_key = [s.strip() for s in item.split('|', 1)]
            elif ':' in item:
                league_key, team_key = [s.strip() for s in item.split(':', 1)]
            else:
                # Single token; treat as team_key only (derive league from team if possible)
                league_key, team_key = "", item
            # Derive league_key from team_key if not provided
            if not league_key and team_key:
                m = re.match(r"^(\d+\.l\.\d+)\.t\.\d+$", team_key)
                if m:
                    league_key = m.group(1)
            if team_key:
                pairs.append({
                    "league_key": league_key,
                    "team_key": team_key,
                    "alias": f"fav{idx}",
                })
        return pairs


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
