# Parameters
PROJECT        = infrastructure-template
ENV_FILE       = .env

# Executables: local only
DOCKER_COMPOSE = docker compose
DOCKER         = docker

# Executables
PULUMI         = pulumi
EXEC_APP       = $(DOCKER_COMPOSE) exec app

# Misc
.DEFAULT_GOAL  = help
.RECIPEPREFIX  +=
.PHONY: $(filter-out vendor node_modules,$(MAKECMDGOALS))

help:
	@printf "\033[33mUsage:\033[0m\n  make [target] [arg=\"val\"...]\n\n\033[33mTargets:\033[0m\n"
	@grep -E '^[-a-zA-Z0-9_\.\/]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[32m%-15s\033[0m %s\n", $$1, $$2}'

start: ## Docker container with terraspace and terraform
	${DOCKER_COMPOSE} up -d --build
#"${PULUMI} login --local && ${PULUMI} install"

up: ## Start the container for development
	$(DOCKER_COMPOSE) up --detach

build: ## Builds the images (PHP, caddy)
	$(DOCKER_COMPOSE) build --pull --no-cache

down: ## Stop the docker hub
	$(DOCKER_COMPOSE) down --remove-orphans

sh: ## Log to the docker container
	@$(EXEC_APP) sh

pulumi: ## Pulumi enables you to safely and predictably create, change, and improve infrastructure.
	@$(EXEC_APP) ${PULUMI} "$1"