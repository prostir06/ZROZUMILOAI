.PHONY: help lint test build security up down logs ps

VENV_BIN := backend/.venv/bin
PYTHON := $(if $(wildcard $(VENV_BIN)/python),$(CURDIR)/$(VENV_BIN)/python,python3)
RUFF := $(if $(wildcard $(VENV_BIN)/ruff),$(CURDIR)/$(VENV_BIN)/ruff,ruff)
BANDIT := $(if $(wildcard $(VENV_BIN)/bandit),$(CURDIR)/$(VENV_BIN)/bandit,bandit)

help:
	@echo "Доступні команди:"
	@echo "  make lint      - перевірка ruff (backend) та ESLint (frontend)"
	@echo "  make test      - запуск тестів backend (SQLite) та frontend (Vitest)"
	@echo "  make build     - збірка production bundle frontend"
	@echo "  make security  - сканування bandit (backend) та npm audit (frontend)"
	@echo "  make up        - збірка та запуск Docker Compose стеку"
	@echo "  make down      - зупинка Docker Compose стеку"
	@echo "  make ps        - статус контейнерів Docker Compose"
	@echo "  make logs      - логи Docker Compose"

lint:
	$(RUFF) check --config backend/pyproject.toml backend
	npm --prefix frontend run lint

test:
	cd backend && USE_SQLITE=True DJANGO_SECRET_KEY=dev-test-secret-key-at-least-32-chars CELERY_TASK_ALWAYS_EAGER=True ALLOW_REGISTRATION=True $(PYTHON) manage.py test --verbosity=1
	npm --prefix frontend test

build:
	npm --prefix frontend run build

security:
	$(BANDIT) -c backend/pyproject.toml -r backend -ll
	npm --prefix frontend audit --omit=dev --audit-level=high

up:
	docker compose up -d --build

down:
	docker compose down

ps:
	docker compose ps

logs:
	docker compose logs -f --tail=100
