COMPOSE_FILE := infra/docker/docker-compose.yml
ENV_FILE     := infra/docker/.env
APP_ENV      ?= development
NODE         ?= node
PNPM         ?= pnpm
DOCKER       ?= docker

.PHONY: help infra-up infra-down infra-build infra-logs infra-status \
        migrate migrate-create psql validate validate-all lint typecheck test \
        clean clean-all setup redis-cli

help: ## Show this help
	@echo "Usage:"
	@echo "  make [target]"
	@echo ""
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)

infra-up: ## Start all infrastructure services
	@docker compose -f $(COMPOSE_FILE) --env-file $(ENV_FILE) up -d --wait

infra-down: ## Stop all infrastructure services
	@docker compose -f $(COMPOSE_FILE) --env-file $(ENV_FILE) down

infra-build: ## Build infrastructure images
	@docker compose -f $(COMPOSE_FILE) --env-file $(ENV_FILE) build

infra-logs: ## Tail infrastructure logs
	@docker compose -f $(COMPOSE_FILE) --env-file $(ENV_FILE) logs -f --tail=100

infra-status: ## Show service status
	@docker compose -f $(COMPOSE_FILE) --env-file $(ENV_FILE) ps

migrate: ## Run Alembic migrations
	@docker compose -f $(COMPOSE_FILE) --env-file $(ENV_FILE) run --rm migrate

migrate-create: ## Create a new migration (usage: make migrate-create MSG="description")
	@if [ -z "$(MSG)" ]; then echo "ERROR: MSG is required. Usage: make migrate-create MSG='add_users_table'"; exit 1; fi
	@docker compose -f $(COMPOSE_FILE) --env-file $(ENV_FILE) run --rm --entrypoint "/opt/venv/bin/alembic" migrate -c migrations/alembic.ini revision --autogenerate -m "$(MSG)"

psql: ## Open psql shell on the database
	@docker compose -f $(COMPOSE_FILE) --env-file $(ENV_FILE) exec postgres psql -U $${POSTGRES_USER:-app} -d $${POSTGRES_DB:-saas}

validate: ## Validate docker-compose configuration
	@docker compose -f $(COMPOSE_FILE) config --quiet 2>&1 && echo "✓ Compose configuration is valid."

validate-all: ## Full validation: compose config + health checks
	@$(MAKE) validate
	@echo ""
	@echo "Checking service health..."
	@docker compose -f $(COMPOSE_FILE) --env-file $(ENV_FILE) ps --format json 2>/dev/null | python3 -c "import json, sys; data = sys.stdin.read(); sys.exit(0)" || true
	@echo "✓ All validations passed."

lint: ## Run linting on all packages
	@$(PNPM) nx run-many -t lint

typecheck: ## Run type checking on all packages
	@$(PNPM) nx run-many -t typecheck

test: ## Run tests on all packages
	@$(PNPM) nx run-many -t test

clean: ## Remove containers and orphans (preserves volumes)
	@docker compose -f $(COMPOSE_FILE) --env-file $(ENV_FILE) down --remove-orphans

clean-all: ## Nuclear option: remove everything including images
	@docker compose -f $(COMPOSE_FILE) --env-file $(ENV_FILE) down -v --rmi all --remove-orphans
	@docker system prune -f --volumes

setup: ## Initial project setup: check prerequisites, install deps, build
	@echo "Checking prerequisites..."
	@$(NODE) --version >/dev/null 2>&1 || { echo "ERROR: Node.js is not installed."; exit 1; }
	@$(PNPM) --version >/dev/null 2>&1 || { echo "ERROR: pnpm is not installed."; exit 1; }
	@$(DOCKER) compose version >/dev/null 2>&1 || { echo "ERROR: Docker Compose v2 is not installed."; exit 1; }
	@echo "✓ Prerequisites satisfied."
	@echo ""
	@echo "Installing Node dependencies..."
	@$(PNPM) install --frozen-lockfile
	@echo ""
	@echo "Building infrastructure images..."
	@$(MAKE) infra-build
	@echo ""
	@echo "✓ Setup complete. Run 'make infra-up' to start services, then 'make migrate' to apply migrations."

redis-cli: ## Open redis-cli
	@docker compose -f $(COMPOSE_FILE) --env-file $(ENV_FILE) exec redis valkey-cli
