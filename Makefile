PYTHON ?= python3
ENV_FILE ?= docker/.env.runtime

# Derive PORT from .env for docker port mapping; default to 8000
HOST_PORT := $(shell awk -F= '/^PORT=/{print $$2}' $(ENV_FILE) 2>/dev/null | tail -n1)
HOST_PORT := $(if $(HOST_PORT),$(HOST_PORT),8000)

.PHONY: run test build docker-run

run:
	uvicorn src.app:app --reload --host 0.0.0.0 --port $${PORT:-8000}

test:
	pytest -q

build:
	docker build -t ghcr.io/$${OWNER:-your-gh-username}/fantasy-api:dev .

docker-run: build
	# Run detached to work in non-TTY environments
	docker rm -f fantasy-api-dev >/dev/null 2>&1 || true
	docker run -d --rm --name fantasy-api-dev --env-file $(ENV_FILE) -p $(HOST_PORT):$(HOST_PORT) -v $$(pwd)/oauth2.json:/data/oauth2.json:ro ghcr.io/$${OWNER:-your-gh-username}/fantasy-api:dev
