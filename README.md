# Fantasy NFL API (FastAPI)

A production-ready FastAPI service exposing Yahoo Fantasy NFL data (teams, rosters, waivers) with OpenAPI docs, Docker packaging, and Portainer deployment.

## Setup

1. Provide Yahoo OAuth consumer credentials (client ID/secret). Set `YAHOO_CONSUMER_KEY` / `YAHOO_CONSUMER_SECRET` in your environment, or create an `oauth2.json` with those keys. The service defaults to the out-of-band (`oob`) redirect, but you can override with `YAHOO_REDIRECT_URI`.

2. Generate Yahoo tokens using the built-in flow (recommended):
   - `curl -H "X-API-Key: change-me" http://localhost:8000/v1/auth/url` → follow the `authorization_url` in a browser.
   - After approving, Yahoo shows a short code. Send it to the API:
     ```bash
     curl -H "X-API-Key: change-me" \
          -X POST http://localhost:8000/v1/auth/token \
          -d '{"code": "PASTE_CODE_HERE"}' \
          -H 'Content-Type: application/json'
     ```
   - The service persists the tokens to `YAHOO_OAUTH_FILE` (default `/data/oauth2.json`). Keep this file secret and mount it read-only in production.

   Legacy option: run `scripts/yahoo_auth.py` or `yahoo-oauth` manually if you prefer to handle the OAuth flow outside the API.

   Corporate TLS note: If your device uses a self-signed corporate CA for TLS inspection, append it to a cert bundle and export:
   - `export SSL_CERT_FILE=/path/to/corp-bundle.pem`
   - `export REQUESTS_CA_BUNDLE=$SSL_CERT_FILE`
   The helper script prints which bundle is being used and performs a preflight HTTPS check.

3. Run locally with Docker (recommended):
```
docker build -t ghcr.io/<OWNER>/fantasy-api:dev .
docker run --rm -it -p 8000:8000 \
  -e API_KEY=change-me \
  -v $(pwd)/oauth2.json:/data/oauth2.json:ro \
  ghcr.io/<OWNER>/fantasy-api:dev
```

Makefile helpers (uses a clean runtime env by default):
```
# Build locally (tagged to GHCR-style name)
OWNER=<your-gh-username> make build

# Run the container with sanitized env and oauth token mounted
make docker-run

# Override env file if needed
ENV_FILE=.env make docker-run
```

- Docs: `http://localhost:8000/docs`
- Health: `curl http://localhost:8000/health`
- Auth example: `curl -H "X-API-Key: change-me" http://localhost:8000/v1/teams`

## Endpoints
- `GET /health` – returns `{\"status\":\"ok\"}`
- `GET /v1/teams?nfl_season={int?}` – leagues and teams
- `GET /v1/roster?team_key={string}&week={int?}` – roster
- `GET /v1/waivers?team_key={string}[&league_key={string}]` – waiver settings, priority, pending claims (league_key optional; derived from team_key)
- `GET /v1/favorites` – configured favorite league/team pairs from env (enriched with league/team names when available)
- `GET /v1/auth/url` – Yahoo OAuth authorization link
- `POST /v1/auth/token` – exchange the pasted Yahoo code and persist tokens
- Nice-to-have: `GET /version`, `GET /metrics` (guarded by API key)

When integrating assistants (e.g., ChatGPT Actions), always start the conversation by calling
`GET /v1/teams` to discover the user's leagues. Do not assume favorite teams exist.

## Configuration (env vars)
- `YAHOO_OAUTH_FILE` (default `/data/oauth2.json`)
- `YAHOO_CONSUMER_KEY` / `YAHOO_CONSUMER_SECRET` – optional when `oauth2.json` already includes them
- `YAHOO_REDIRECT_URI` (default `oob`)
- `API_KEY` (optional; if set, required via `X-API-Key`)
- `CORS_ALLOW_ORIGINS` (default `*`, comma-separated)
- `LOG_LEVEL` (default `INFO`)
- `PORT` (default `8000`)
- `SERVER_URL` (optional) Absolute base URL for OpenAPI servers; set this when integrating with ChatGPT Actions so the schema contains a valid server URL.
- Rate limit (optional): `RATE_LIMIT_PER_MIN` (60), `RATE_LIMIT_BURST` (10)
- Favorites: `FAVORITE_TEAMS` semicolon-separated; each entry can be just `team_key`, `<league_key>|<team_key>`, or `<alias>@<league_key>|<team_key>` (alias optional). `/v1/favorites` resolves league/team names automatically when credentials allow.
  - Examples:
    - `461.l.1323091.t.10;461.l.840347.t.9` (league inferred)
    - `461.l.1323091|461.l.1323091.t.10;461.l.840347|461.l.840347.t.9`
    - `Sunday Squad@461.l.1323091|461.l.1323091.t.10` (custom alias returned from `/v1/favorites`)

## Portainer Deployment
1. Open Portainer → Stacks → Add stack → paste `docker/portainer-stack.yaml`.
2. Set environment (e.g., `API_KEY`) and bind-mount `oauth2.json` as read-only to `/data/oauth2.json`.
3. Deploy on an internal network; place behind a reverse proxy.

### Reverse Proxy (Nginx Proxy Manager)
- Add Proxy Host `fantasy_api.chrispatten.dev` → Forward to container internal IP:8000.
- Enable HTTP/2, Websockets, and Let’s Encrypt certificate.

## OpenAPI
- Spec is in `openapi/openapi.yaml`; live docs at `/docs`, JSON at `/openapi.json`.

## Security Notes
- `oauth2.json` is sensitive; never commit. Mount read-only.
- Keep the API private or guard with `API_KEY` and reverse proxy auth.

## Development
- `make run` / `make test` / `make build` / `make docker-run`

Notes
- Extra env vars are ignored, so you can safely reuse your project `.env` files.
- On Apple Silicon under Colima, images build for `linux/arm64` by default. Use `--platform linux/amd64` if you must run x86 images.
