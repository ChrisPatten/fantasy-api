PYTHON ?= python3
ENV_FILE ?= docker/.env.runtime

# Derive PORT from .env for docker port mapping; default to 8000
HOST_PORT := $(shell awk -F= '/^PORT=/{print $$2}' $(ENV_FILE) 2>/dev/null | tail -n1)
HOST_PORT := $(if $(HOST_PORT),$(HOST_PORT),8000)

CORP_BUNDLE_FILE := $(wildcard corp-bundle.pem)
ifdef CORP_BUNDLE_FILE
CA_MOUNT_PATH := /etc/ssl/certs/corp-bundle.pem
DOCKER_CA_FLAGS := -v $(abspath $(CORP_BUNDLE_FILE)):$(CA_MOUNT_PATH):ro -e REQUESTS_CA_BUNDLE=$(CA_MOUNT_PATH) -e SSL_CERT_FILE=$(CA_MOUNT_PATH)
endif

ifdef FAVORITE_TEAMS
DOCKER_EXTRA_ENV := -e FAVORITE_TEAMS="$(FAVORITE_TEAMS)"
endif

.PHONY: run test build docker-run docker-dev

run:
	uvicorn src.app:app --reload --host 0.0.0.0 --port $${PORT:-8000}

test:
	pytest -q

build:
	docker build -t ghcr.io/$${OWNER:-your-gh-username}/fantasy-api:dev .

docker-run:
	# Run detached to work in non-TTY environments
	docker rm -f fantasy-api-dev >/dev/null 2>&1 || true
	docker run -d --rm --name fantasy-api-dev --env-file $(ENV_FILE) $(DOCKER_CA_FLAGS) $(DOCKER_EXTRA_ENV) -p $(HOST_PORT):$(HOST_PORT) -v $$(pwd)/oauth2.json:/data/oauth2.json:ro ghcr.io/$${OWNER:-your-gh-username}/fantasy-api:dev

docker-dev:
	# Bind-mount src for live code edits while reusing runtime config
	docker rm -f fantasy-api-dev-live >/dev/null 2>&1 || true
	docker run --rm --name fantasy-api-dev-live --env-file $(ENV_FILE) $(DOCKER_CA_FLAGS) $(DOCKER_EXTRA_ENV) -p $(HOST_PORT):$(HOST_PORT) \
		-v $$(pwd)/oauth2.json:/data/oauth2.json:ro \
		-v $$(pwd)/src:/app/src \
		--entrypoint sh ghcr.io/$${OWNER:-your-gh-username}/fantasy-api:dev \
		-c "uvicorn src.app:app --host 0.0.0.0 --port $${PORT:-8000} --reload"
