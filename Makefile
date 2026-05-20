# Makefile for a2a_local (Agent Community Protocol)

.PHONY: help install-skill install-skill-cli install-deps discover docker-up docker-down

help:
	@echo "Available targets:"
	@echo "  install-skill       Install a2a-consult skill (Grok)"
	@echo "  install-skill-cli   Install skill + make 'a2a-consult' available as CLI command"
	@echo "  install-deps        Install Python dependencies (nats-py + synadia-ai-agents)"
	@echo "  discover            Discover currently running A2A agents"
	@echo "  docker-up           Start Docker Compose (with build)"
	@echo "  docker-down         Stop Docker Compose"

install-skill:
	@./scripts/install-a2a-consult.sh

install-skill-cli:
	@./scripts/install-a2a-consult.sh --cli

install-deps:
	@./scripts/install-a2a-consult.sh --install-deps

discover:
	@python3 scripts/discover_agents.py --owner $${OWNER:-$$(whoami)} --session $${SESSION:-collab}

docker-up:
	@cd docker && docker compose up --build

docker-down:
	@cd docker && docker compose down