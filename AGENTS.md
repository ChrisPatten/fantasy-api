# Repository Guidelines

This repository hosts a production-ready FastAPI service that exposes Yahoo Fantasy NFL data with OpenAPI, Docker packaging, and Portainer deployment artifacts.

## Project Structure & Module Organization
- `src/` – application code
  - `src/app.py` (FastAPI app + routes), `src/deps.py` (dependencies), `src/models.py` (Pydantic schemas), `src/settings.py` (env/config), `src/yahoo_client.py` (Yahoo API helpers)
- `openapi/openapi.yaml` – OpenAPI 3 spec
- `tests/` – pytest suite; use `tests/_data/` for fixtures
- `docker/portainer-stack.yaml` – Portainer stack
- CI at `.github/workflows/docker.yml`; packaging via `Dockerfile`; developer helpers in `Makefile`, `.env.example`.

## Build, Test, and Development Commands
- `make run` – start dev server (`uvicorn src.app:app --reload`)
- `make test` – run pytest locally
- `make build` – build Docker image
- `make docker-run` – run image (reads `/data/oauth2.json`)
Examples:
```
pytest -q
docker build -t ghcr.io/<OWNER>/fantasy-api:dev .
docker run --rm -p 8000:8000 -v $(pwd)/oauth2.json:/data/oauth2.json:ro ghcr.io/<OWNER>/fantasy-api:dev
```

## Coding Style & Naming Conventions
- Python 3.11, 4-space indent, type hints required; docstrings for public functions.
- Naming: `snake_case` for functions/vars, `PascalCase` for classes, constants `UPPER_SNAKE`.
- FastAPI: keep request/response models in `models.py`; dependencies in `deps.py`; configuration in `settings.py`.
- Logging: use structured JSON logging (no `print`).

## Testing Guidelines
- Framework: `pytest` with `httpx.AsyncClient` and mocked Yahoo calls (`respx`/`responses`).
- Place sanitized payloads in `tests/_data/` and avoid secrets.
- Name tests `test_*.py`; write one test per behavior; validate schemas and error codes.
- Run `make test` before any PR.

## Commit & Pull Request Guidelines
- Use Conventional Commits: `feat:`, `fix:`, `chore:`, `docs:`, `test:`, `refactor:`.
- PRs must include: concise description, linked issues, validation steps (e.g., `curl -H "X-API-Key: ..." http://localhost:8000/health`).
- Keep changes focused; update `openapi/openapi.yaml`, tests, and docs when endpoints change.

## Security & Configuration Tips
- Never commit tokens; mount `oauth2.json` read-only at `/data/oauth2.json`.
- In production, set `API_KEY` and restrict `CORS_ALLOW_ORIGINS`.
- Prefer reverse proxy TLS termination (e.g., Nginx Proxy Manager) for `fantasy_api.chrispatten.dev`.

## Agent-Specific Instructions
- Follow this layout and keep diffs small and surgical.
- If you change interfaces, update OpenAPI, fixtures, and README in the same PR.
