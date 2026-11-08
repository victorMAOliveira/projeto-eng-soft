# EstágioHub — developer entry points.
# Recipes only call docker / docker compose, so they behave the same with GNU Make
# on Linux, macOS and Windows (cmd or sh). Everything else runs inside containers.

COMPOSE ?= docker compose
TOOLS   := $(COMPOSE) run --rm --no-deps tools
GEN_DIR := docs/relatorio/generated

.PHONY: help env up down clean logs ps seed test e2e eval screenshots report all

help:
	@echo "make env          - cria .env a partir de .env.example e gera segredos"
	@echo "make up           - constroi e sobe a stack (espera todos ficarem healthy)"
	@echo "make down         - para os containers (mantem os dados)"
	@echo "make clean        - remove containers, volumes e redes"
	@echo "make seed         - carrega dados de demonstracao via gateway"
	@echo "make test         - ruff + testes unitarios e de API"
	@echo "make e2e          - fluxo principal completo via gateway"
	@echo "make eval         - avaliacao offline do recomendador + metricas de reuso"
	@echo "make screenshots  - prints da interface (Playwright)"
	@echo "make report       - diagramas + relatorio .docx e .pdf"
	@echo "make all          - env, up, seed, test, e2e, eval, screenshots, report"

env:
	docker run --rm -v "$(CURDIR):/work" -w /work python:3.12-slim python scripts/make_env.py

up:
	$(COMPOSE) up -d --build --wait

down:
	$(COMPOSE) down

clean:
	$(COMPOSE) --profile tools down -v --remove-orphans

logs:
	$(COMPOSE) logs -f --tail=100

ps:
	$(COMPOSE) ps

seed:
	$(COMPOSE) run --rm --build tools python scripts/seed.py

test:
	$(COMPOSE) run --rm --no-deps --build tools python scripts/run_tests.py

e2e:
	$(COMPOSE) run --rm --build tools python scripts/e2e_demo.py

eval:
	$(TOOLS) python scripts/evaluate_recommender.py
	$(TOOLS) python scripts/reuse_metrics.py

screenshots:
	$(COMPOSE) run --rm screenshots
	$(COMPOSE) ps --format "table {{.Name}}\t{{.Image}}\t{{.Status}}" > $(GEN_DIR)/compose-ps.txt

report:
	$(TOOLS) python scripts/build_report.py prepare
	$(COMPOSE) run --rm mermaid
	$(COMPOSE) run --rm pandoc
	$(COMPOSE) run --rm screenshots python scripts/build_report.py pdf

all: env up seed test e2e eval screenshots report
