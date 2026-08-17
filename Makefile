# =============================================================================
# BigBug — единая точка входа для запуска всех скриптов проекта.
#
# Группы команд (подробнее: make help):
#   dev-*     — дев-сборка приложения (docker-compose.yml)
#   infra-*   — зависимости (keycloak, gitlab, harbor) + OpenTofu
#   test-*    — тесты по стеку и типу (unit / integrations / e2e / all)
#   lint-*    — линтинг
#   format-*  — форматирование
#   typecheck-* — проверка типов (mypy / tsc)
#   coverage-*  — покрытие кода и эндпоинтов
#   dead-code-* — поиск мёртвого кода (vulture / knip)
# =============================================================================

SHELL := /usr/bin/env bash
.DEFAULT_GOAL := help

# Compose-обёртки
COMPOSE_APP   := docker compose
COMPOSE_INFRA := docker compose -f infrastructure/docker-compose.yml --env-file infrastructure/.env

# Директории
TF_DIR := infrastructure/terraform

# =============================================================================
##@ Help
# =============================================================================

.PHONY: help
help: ## Показать все доступные команды
	@awk 'BEGIN {FS = ":.*##"; printf "\nКоманды Makefile (BigBug):\n"} \
		/^[a-zA-Z0-9_-]+:.*?##/ { printf "  \033[36m%-28s\033[0m %s\n", $$1, $$2 } \
		/^##@/ { printf "\n\033[1m%s\033[0m\n", substr($$0, 5) }' \
		$(MAKEFILE_LIST)

# =============================================================================
##@ dev — дев-сборка приложения (postgres, redis, backend, frontend)
# =============================================================================

.PHONY: dev-build
dev-build: ## Собрать образы приложения
	$(COMPOSE_APP) build

.PHONY: dev-up
dev-up: ## Запустить дев-стек (entrypoint сам ждёт БД и применяет миграции)
	$(COMPOSE_APP) up -d

.PHONY: dev-init
dev-init: ## Применить миграции Alembic (повторно, без перезапуска стека)
	$(COMPOSE_APP) run --rm backend app:init

.PHONY: dev-down
dev-down: ## Остановить дев-стек (контейнеры сохраняются)
	$(COMPOSE_APP) down

.PHONY: dev-clean
dev-clean: ## Остановить дев-стек и удалить вольюмы (postgres/redis)
	$(COMPOSE_APP) down -v --remove-orphans

# =============================================================================
##@ infra — зависимости (keycloak, gitlab, harbor)
# =============================================================================

.PHONY: infra-up
infra-up: ## Запустить инфраструктурные сервисы (keycloak + gitlab)
	$(COMPOSE_INFRA) up -d

.PHONY: infra-init
infra-init: ## Полная инициализация: compose → harbor (kind) → OpenTofu → .env
	./infrastructure/init.sh

.PHONY: infra-provision-gitlab
infra-provision-gitlab: ## Provision GitLab components project + runner (без OpenTofu)
	bash ./infrastructure/provision-gitlab.sh

.PHONY: infra-down
infra-down: ## Остановить инфраструктурные сервисы (контейнеры сохраняются)
	$(COMPOSE_INFRA) down

.PHONY: infra-clean
infra-clean: infra-clean-compose infra-clean-harbor infra-clean-tofu ## Полная чистка инфраструктуры (все сервисы)

.PHONY: infra-clean-compose
infra-clean-compose: ## Остановить keycloak/gitlab/postgres и удалить их вольюмы
	$(COMPOSE_INFRA) down -v --remove-orphans

.PHONY: infra-clean-harbor
infra-clean-harbor: ## Удалить kind-кластер Harbor и запись из /etc/hosts
	bash infrastructure/harbor/teardown.sh --all

.PHONY: infra-clean-tofu
infra-clean-tofu: ## Удалить все файлы OpenTofu (стейт, lock, .terraform, tfvars)
	rm -rf \
		$(TF_DIR)/.terraform \
		$(TF_DIR)/.terraform.lock.hcl \
		$(TF_DIR)/terraform.tfstate \
		$(TF_DIR)/terraform.tfstate.backup \
		$(TF_DIR)/terraform.tfvars \
		$(TF_DIR)/crash.log
	rm -f $(TF_DIR)/*.tfplan

# =============================================================================
##@ test — тесты по стеку и типу
# =============================================================================

# TEST_ARGS — проброс аргументов в тестовые скрипты для запуска конкретных
# тестов. Примеры:
#   make test-unit-backend TEST_ARGS="-k test_login"
#   make test-e2e-backend  TEST_ARGS="tests/e2e/test_auth.py -v"
#   make test-unit-frontend TEST_ARGS="-f Admin -t 'should render'"
TEST_ARGS ?=

.PHONY: test-unit-backend
test-unit-backend: ## Backend unit-тесты (tests/unit/)
	./backend/scripts/test-unit.sh $(TEST_ARGS)

.PHONY: test-e2e-backend
test-e2e-backend: ## Backend e2e-тесты (требует запущенного dev-стека)
	./backend/scripts/test-e2e.sh $(TEST_ARGS)

.PHONY: test-all-backend
test-all-backend: test-unit-backend test-e2e-backend ## Backend: unit + e2e

.PHONY: test-unit-frontend
test-unit-frontend: ## Frontend unit-тесты
	./frontend/scripts/test.sh --unit $(TEST_ARGS)

.PHONY: test-integrations-frontend
test-integrations-frontend: ## Frontend integration-тесты
	./frontend/scripts/test.sh --integrations $(TEST_ARGS)

.PHONY: test-e2e-frontend
test-e2e-frontend: ## Frontend e2e-тесты (Cypress — пока не настроены)
	./frontend/scripts/test.sh --e2e $(TEST_ARGS)

.PHONY: test-all-frontend
test-all-frontend: ## Frontend: unit + integrations
	./frontend/scripts/test.sh --all $(TEST_ARGS)

.PHONY: test-unit
test-unit: test-unit-backend test-unit-frontend ## Unit-тесты обоих стеков

.PHONY: test-integrations
test-integrations: test-integrations-frontend ## Integration-тесты (только frontend)

.PHONY: test-e2e
test-e2e: test-e2e-backend test-e2e-frontend ## E2E-тесты обоих стеков

.PHONY: test-all
test-all: test-all-backend test-all-frontend ## Все тесты (unit + integrations + e2e)

# =============================================================================
##@ lint / format / typecheck
# =============================================================================

.PHONY: lint-backend
lint-backend: ## Линтинг backend (ruff check)
	./backend/scripts/lint.sh

.PHONY: lint-frontend
lint-frontend: ## Линтинг frontend (eslint)
	./frontend/scripts/lint.sh

.PHONY: lint
lint: lint-backend lint-frontend ## Линтинг обоих стеков

.PHONY: format-backend
format-backend: ## Форматирование backend (ruff format + fix)
	./backend/scripts/format.sh

.PHONY: format-frontend
format-frontend: ## Форматирование frontend (prettier)
	./frontend/scripts/format.sh

.PHONY: format
format: format-backend format-frontend ## Форматирование обоих стеков

.PHONY: typecheck-backend
typecheck-backend: ## Проверка типов backend (mypy)
	./backend/scripts/type-check.sh

.PHONY: typecheck-frontend
typecheck-frontend: ## Проверка типов frontend (tsc --noEmit)
	./frontend/scripts/type-check.sh

.PHONY: typecheck
typecheck: typecheck-backend typecheck-frontend ## Проверка типов обоих стеков

# =============================================================================
##@ coverage — покрытие кода и эндпоинтов
# =============================================================================

.PHONY: coverage-backend-unit
coverage-backend-unit: ## Покрытие кода backend (unit, pytest-cov)
	./backend/scripts/test-unit.sh --cov=app --cov-report=term-missing

.PHONY: coverage-backend-e2e
coverage-backend-e2e: ## Покрытие кода e2e-прогоном + отчёт по эндпоинтам
	./backend/scripts/test-e2e-coverage.sh

.PHONY: coverage-frontend
coverage-frontend: ## Покрытие кода frontend (vitest --coverage)
	./frontend/scripts/test.sh --coverage

.PHONY: coverage-all
coverage-all: coverage-backend-unit coverage-backend-e2e coverage-frontend ## Покрытие обоих стеков

# =============================================================================
##@ dead-code — поиск мёртвого кода
# =============================================================================

.PHONY: dead-code-backend
dead-code-backend: ## Поиск мёртвого кода backend (vulture)
	./backend/scripts/vulture.sh

.PHONY: dead-code-frontend
dead-code-frontend: ## Поиск мёртвого кода frontend (knip)
	./frontend/scripts/dead-code.sh

.PHONY: dead-code
dead-code: dead-code-backend dead-code-frontend ## Поиск мёртвого кода обоих стеков
