from __future__ import annotations

import os
import time
from typing import Optional, List
import logging

import structlog
from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from . import yahoo_client
from .deps import APIKeyChecker, RateLimiter, get_api_key_checker, get_rate_limiter, request_id_generator
from .models import (
    AuthCodeRequest,
    AuthCodeResponse,
    AuthUrlResponse,
    Error,
    FavoriteTeam,
    FavoritesResponse,
    Health,
    RosterResponse,
    TeamsResponse,
    WaiversResponse,
    FreeAgentsResponse,
)
from .settings import Settings, get_settings


def _configure_logging(level: str) -> None:
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(numeric_level),
    )


def create_app(settings: Optional[Settings] = None) -> FastAPI:
    settings = settings or get_settings()
    _configure_logging(settings.LOG_LEVEL)

    servers = None
    if settings.SERVER_URL:
        servers = [{"url": settings.SERVER_URL}]
    app = FastAPI(
        title="Fantasy NFL API",
        version="1.0.0",
        docs_url="/docs",
        openapi_url="/openapi.json",
        servers=servers,
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins(),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"]
    )

    api_key_dep = get_api_key_checker(settings)
    rate_limiter = get_rate_limiter(settings)

    @app.middleware("http")
    async def request_id_middleware(request: Request, call_next):
        rid = request_id_generator(request)
        start = time.perf_counter()
        response = None
        try:
            response = await call_next(request)
            response.headers["X-Request-Id"] = rid
            return response
        finally:
            elapsed = (time.perf_counter() - start) * 1000.0
            structlog.get_logger().info(
                "request",
                request_id=rid,
                method=request.method,
                path=request.url.path,
                status=getattr(response, "status_code", None),
                latency_ms=round(elapsed, 2),
            )

    # Error handling
    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        return JSONResponse(status_code=422, content=Error(code="validation_error", message="Validation failed", details=exc.errors()).model_dump())

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        detail = exc.detail
        if isinstance(detail, dict) and "code" in detail:
            return JSONResponse(status_code=exc.status_code, content=detail)
        return JSONResponse(status_code=exc.status_code, content=Error(code="error", message=str(detail)).model_dump())

    # Routes
    @app.get("/health", response_model=Health, operation_id="getHealth")
    async def health() -> Health:
        return Health()

    @app.get("/version", operation_id="getVersion")
    async def version():
        return {
            "git_sha": os.environ.get("GIT_SHA", "dev"),
            "build_time": os.environ.get("BUILD_TIME", "dev"),
        }

    try:
        from starlette_exporter import PrometheusMiddleware, handle_metrics

        app.add_middleware(PrometheusMiddleware)

        @app.get("/metrics", dependencies=[Depends(api_key_dep)], operation_id="getMetrics")
        async def metrics(request: Request):
            return await handle_metrics(request)
    except Exception:
        # Metrics optional
        pass

    @app.get(
        "/v1/teams",
        response_model=TeamsResponse,
        dependencies=[Depends(rate_limiter), Depends(api_key_dep)],
        operation_id="listTeams",
    )
    async def get_teams(nfl_season: Optional[int] = Query(default=None, ge=2000, le=2100)):
        leagues = yahoo_client.list_teams(settings, nfl_season)
        return {"leagues": leagues}

    @app.get(
        "/v1/roster",
        response_model=RosterResponse,
        dependencies=[Depends(rate_limiter), Depends(api_key_dep)],
        operation_id="getRoster",
    )
    async def get_roster(team_key: str = Query(..., pattern=r"^\d+\.l\.\d+\.t\.\d+$")):
        result = yahoo_client.get_roster(settings, team_key)
        return result

    @app.get(
        "/v1/free-agents",
        response_model=FreeAgentsResponse,
        dependencies=[Depends(rate_limiter), Depends(api_key_dep)],
        operation_id="getFreeAgents",
    )
    async def get_free_agents(
        team_key: str = Query(..., pattern=r"^\d+\.l\.\d+\.t\.\d+$"),
        positions: Optional[List[str]] = Query(default=None),
        limit: int = Query(default=5, ge=1, le=50),
    ):
        result = yahoo_client.get_free_agents(
            settings,
            team_key,
            positions=positions,
            per_position=limit,
        )
        return result

    @app.get(
        "/v1/waivers",
        response_model=WaiversResponse,
        dependencies=[Depends(rate_limiter), Depends(api_key_dep)],
        operation_id="getWaivers",
    )
    async def get_waivers(
        team_key: str = Query(..., pattern=r"^\d+\.l\.\d+\.t\.\d+$"),
        league_key: Optional[str] = Query(default=None, description="Optional; derived from team_key if omitted"),
    ):
        lk = league_key or team_key.split(".t.")[0]
        result = yahoo_client.get_waivers(settings, lk, team_key)
        return result

    @app.get(
        "/v1/favorites",
        response_model=FavoritesResponse,
        dependencies=[Depends(rate_limiter), Depends(api_key_dep)],
        operation_id="getFavorites",
    )
    async def get_favorites():
        favs = settings.favorite_teams()
        enriched = yahoo_client.enrich_favorites(settings, favs)
        return {"favorites": [FavoriteTeam(**f) for f in enriched]}

    @app.get(
        "/v1/auth/url",
        response_model=AuthUrlResponse,
        dependencies=[Depends(rate_limiter), Depends(api_key_dep)],
        operation_id="getAuthUrl",
    )
    async def get_auth_url(
        state: Optional[str] = Query(default=None, min_length=1, max_length=255),
        redirect_uri: Optional[str] = Query(default=None, max_length=2048),
    ):
        try:
            return yahoo_client.build_authorization_url(settings, state=state, redirect_uri=redirect_uri)
        except yahoo_client.YahooOAuthError as exc:
            raise HTTPException(
                status_code=exc.status_code,
                detail=Error(code="oauth_error", message=str(exc)).model_dump(),
            ) from exc

    @app.post(
        "/v1/auth/token",
        response_model=AuthCodeResponse,
        dependencies=[Depends(rate_limiter), Depends(api_key_dep)],
        operation_id="exchangeAuthCode",
    )
    async def exchange_auth_code(payload: AuthCodeRequest):
        try:
            return yahoo_client.exchange_authorization_code(
                settings,
                code=payload.code,
                redirect_uri=payload.redirect_uri,
                state=payload.state,
            )
        except yahoo_client.YahooOAuthError as exc:
            raise HTTPException(
                status_code=exc.status_code,
                detail=Error(code="oauth_error", message=str(exc)).model_dump(),
            ) from exc

    return app


app = create_app()
