# Usage:
#   make deploy    - Full deployment (down + build + up)
#   make up        - Start services
#   make down      - Stop services
#   make logs      - View logs (all services)
#   make build     - Build images
#   make clean     - Remove containers, volumes, images
# ═══════════════════════════════════════════════════════════════════════════════

.PHONY: deploy up down build build-fresh logs logs-api logs-ui status clean prune help check-env

# Default target
.DEFAULT_GOAL := help

# ═══════════════════════════════════════════════════════════════════════════════
# MAIN TARGETS
# ═══════════════════════════════════════════════════════════════════════════════

## deploy: Full deployment - stop, build and start all services
deploy: check-env
	@echo "Starting deployment..."
	docker compose down
	docker compose up -d --build
	docker image prune -f
	@echo "Deployment complete!"
	@$(MAKE) status

## up: Start all services (without rebuild)
up: check-env
	@echo "Starting services..."
	docker compose up -d
	@$(MAKE) status

## down: Stop all services
down:
	@echo "Stopping services..."
	docker compose down

## build: Build docker images
build: check-env
	@echo "Building images..."
	docker compose build

## build-fresh: Build images without cache
build-fresh: check-env
	@echo "Building images (no cache)..."
	docker compose build --no-cache

# ═══════════════════════════════════════════════════════════════════════════════
# LOGS & STATUS
# ═══════════════════════════════════════════════════════════════════════════════

## logs: View logs from all services (follow mode)
logs:
	docker compose logs -f

## logs-api: View logs from medical-api only
logs-api:
	docker compose logs -f medical-api

## logs-ui: View logs from medical-ui only
logs-ui:
	docker compose logs -f medical-ui

## logs-neo4j: View logs from neo4j only
logs-neo4j:
	docker compose logs -f neo4j

## status: Show running containers
status:
	@echo "Running services:"
	@docker compose ps

# ═══════════════════════════════════════════════════════════════════════════════
# CLEANUP
# ═══════════════════════════════════════════════════════════════════════════════

## clean: Stop services and remove volumes
clean:
	@echo "Cleaning up..."
	docker compose down -v

## clean-all: Remove everything including images
clean-all:
	@echo "Full cleanup (containers, volumes, images)..."
	docker compose down -v --rmi local
	docker image prune -f

## prune: Remove unused Docker resources
prune:
	@echo "Pruning unused Docker resources..."
	docker system prune -f

# ═══════════════════════════════════════════════════════════════════════════════
# DEVELOPMENT
# ═══════════════════════════════════════════════════════════════════════════════

## restart-api: Restart only the API service
restart-api:
	docker compose restart medical-api

## restart-ui: Restart only the UI service
restart-ui:
	docker compose restart medical-ui

## shell-api: Open shell in API container
shell-api:
	docker compose exec medical-api /bin/bash

## shell-neo4j: Open cypher-shell in Neo4j
shell-neo4j:
	docker compose exec neo4j cypher-shell

# ═══════════════════════════════════════════════════════════════════════════════
# UTILITIES
# ═══════════════════════════════════════════════════════════════════════════════

## check-env: Verify .env file exists
check-env:
	@if [ ! -f .env ]; then \
		echo "ERROR: .env file is missing!"; \
		exit 1; \
	fi

## help: Show this help message
help:
	@echo "═══════════════════════════════════════════════════════════════════"
	@echo "  Medical AI Agent - Available Commands"
	@echo "═══════════════════════════════════════════════════════════════════"
	@grep -E '^## ' $(MAKEFILE_LIST) | sed 's/## /  /' | sort
	@echo "═══════════════════════════════════════════════════════════════════"
