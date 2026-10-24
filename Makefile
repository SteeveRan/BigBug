# =============================================================================
# BigBug — единая точка входа для запуска всех скриптов проекта.
#
# Группы команд (подробнее: make help):
#   dev-*     — приложение в kind-кластере bigbug-dev (helm chart bigbug)
#   infra-*   — kind-стенд (tofu base/infra-apps/apps) + GitLab compose-зона
#   test-*    — тесты по стеку и типу (unit / integrations / e2e / all)
#   lint-*    — линтинг
#   format-*  — форматирование
#   typecheck-* — проверка типов (mypy / tsc)
#   coverage-*  — покрытие кода и эндпоинтов
#   dead-code-* — поиск мёртвого кода (vulture / knip)
# =============================================================================

SHELL := /usr/bin/env bash
.DEFAULT_GOAL := help

# Compose-обёртка (GitLab compose-зона — ADR-0033; приложение живёт в kind/helm)
COMPOSE_INFRA := docker compose -f infrastructure/gitlab/docker-compose.yml --env-file infrastructure/gitlab/.env

# Директории
TF_DIR    := infrastructure/terraform
TF_ROOTS  := $(TF_DIR)/apps/.terraform $(TF_DIR)/infra-apps/.terraform $(TF_DIR)/base/.terraform
STATE_DIR := $(HOME)/.local/state/bigbug

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
##@ dev — приложение в kind-кластере bigbug-dev (helm chart bigbug)
# =============================================================================

# kind-стенд (ADR-0022): кластер, ns, релиз, dev-теги образов (values-dev, #59)
KIND_CLUSTER   := bigbug-dev
KUBE_CONTEXT   := kind-$(KIND_CLUSTER)
APP_NAMESPACE  := bigbug
APP_RELEASE    := bigbug
# CNPG Cluster CR name (tofu apps root) — не совпадает с release name
DB_CLUSTER     := bigbug-dev
BACKEND_IMAGE  := bigbug-backend:dev
FRONTEND_IMAGE := bigbug-frontend:dev

.PHONY: dev-migrate-check
dev-migrate-check: ## Чек миграций ветки на чистой копии БД (multi-agent pre-merge)
	./backend/scripts/migrate-check.sh $(DB)

.PHONY: dev-build
dev-build: ## Собрать dev-образы (bigbug-{backend,frontend}:dev) и залить в kind
	docker build -f backend/docker/Dockerfile -t $(BACKEND_IMAGE) backend
	docker build -f frontend/docker/Dockerfile -t $(FRONTEND_IMAGE) frontend
	kind load docker-image $(BACKEND_IMAGE) $(FRONTEND_IMAGE) --name $(KIND_CLUSTER)

.PHONY: dev-up
dev-up: ## Задеплоить приложение в kind (helm upgrade; миграции — pre-upgrade hook job, повтор = повторный dev-up)
	helm upgrade --install $(APP_RELEASE) charts/bigbug -n $(APP_NAMESPACE) \
		--kube-context $(KUBE_CONTEXT) -f charts/bigbug/values-dev.yaml --wait --timeout 10m

.PHONY: dev-down
dev-down: ## Удалить релиз bigbug из kind (данные CNPG/Redis сохраняются)
	@helm uninstall $(APP_RELEASE) -n $(APP_NAMESPACE) --kube-context $(KUBE_CONTEXT) --wait 2>&1 \
		| grep -v 'release: not found' || echo "Релиз $(APP_RELEASE) уже удалён — ок."

.PHONY: dev-clean
dev-clean: dev-down ## dev-down + сброс app-данных (DROP SCHEMA в CNPG + flush Redis); только владелец инфры
	@if [ "$(CONFIRM)" != "yes" ]; then \
		echo "ОШИБКА: dev-clean удаляет данные приложения (CNPG + Redis) общего стенда."; \
		echo "Разрешено только владельцу инфры (см. AGENTS.md: Multi-agent discipline)."; \
		echo "Запускайте: make dev-clean CONFIRM=yes"; \
		exit 1; \
	fi
	PGPOD=$$(kubectl --context $(KUBE_CONTEXT) -n $(APP_NAMESPACE) get pod -l cnpg.io/cluster=$(DB_CLUSTER) -o jsonpath='{.items[0].metadata.name}'); \
	PGPW=$$(kubectl --context $(KUBE_CONTEXT) -n $(APP_NAMESPACE) get secret $(DB_CLUSTER)-app -o jsonpath='{.data.password}' | base64 -d); \
	kubectl --context $(KUBE_CONTEXT) -n $(APP_NAMESPACE) exec "$$PGPOD" -c postgres -- env PGPASSWORD="$$PGPW" \
		psql -h localhost -U bigbug -d bigbug -c 'DROP SCHEMA public CASCADE; CREATE SCHEMA public;'
	kubectl --context $(KUBE_CONTEXT) -n $(APP_NAMESPACE) exec $(APP_RELEASE)-cache-0 -- redis-cli flushall

.PHONY: dev-db-create
dev-db-create: ## Создать БД на ворктрий в CNPG (DB=feat_<branch>)
	@if [ -z "$(DB)" ]; then echo "Использование: make dev-db-create DB=feat_<branch>"; exit 1; fi
	$(MAKE) dev-db-psql ARGS="CREATE DATABASE $(DB)"

.PHONY: dev-db-drop
dev-db-drop: ## Удалить БД ворктрия (DB=feat_<branch>)
	@if [ -z "$(DB)" ]; then echo "Использование: make dev-db-drop DB=feat_<branch>"; exit 1; fi
	@if [ "$(DB)" = "bigbug" ]; then echo "ОШИБКА: нельзя удалять каноническую БД bigbug."; exit 1; fi
	$(MAKE) dev-db-psql ARGS="DROP DATABASE IF EXISTS $(DB)"

.PHONY: dev-db-psql
dev-db-psql: ## Выполнить SQL в CNPG bigbug (ARGS="SQL") — kubectl exec в pod
	@if [ -z "$(ARGS)" ]; then echo "Использование: make dev-db-psql ARGS='SELECT 1'"; exit 1; fi
	@PGPOD=$$(kubectl --context $(KUBE_CONTEXT) -n $(APP_NAMESPACE) get pod -l cnpg.io/cluster=$(DB_CLUSTER) -o jsonpath='{.items[0].metadata.name}'); \
	PGPW=$$(kubectl --context $(KUBE_CONTEXT) -n $(APP_NAMESPACE) get secret $(DB_CLUSTER)-app -o jsonpath='{.data.password}' | base64 -d); \
	kubectl --context $(KUBE_CONTEXT) -n $(APP_NAMESPACE) exec "$$PGPOD" -c postgres -- env PGPASSWORD="$$PGPW" \
		psql -h localhost -U bigbug -d bigbug -c "$(ARGS)"

# =============================================================================
##@ infra — kind-стенд (tofu: base/infra-apps/apps) + GitLab compose-зона
# =============================================================================

.PHONY: infra-up
infra-up: ## Запустить GitLab compose-зону (kind-стенд не «останавливается»; полный стенд — infra-init)
	bash infrastructure/kind/certs.sh
	$(COMPOSE_INFRA) up -d

.PHONY: infra-init
infra-init: ## Полная инициализация: certs → gitlab compose → kind bootstrap → tofu base/infra-apps/apps → .env
	./infrastructure/init.sh

.PHONY: infra-trust
infra-trust: ## Доверие хоста сертам dev-стенда (sudo; https-хосты без -k — ADR-0030; idempotent)
	sudo ./infrastructure/kind/trust-host.sh

.PHONY: fresh-up
fresh-up: ## Полный цикл с нуля: infra-init (certs+trust → gitlab → kind → tofu) → dev-build → dev-up
	$(MAKE) infra-init
	$(MAKE) dev-build
	$(MAKE) dev-up

.PHONY: infra-down
infra-down: ## Остановить GitLab compose-зону (вольюмы живы; kind/tofu-стенд продолжает работать)
	$(COMPOSE_INFRA) down

.PHONY: infra-clean
infra-clean: ## Полная чистка: tofu destroy (apps→infra-apps→base) + kind teardown + state-каталоги; GitLab-вольюмы и certs/ не трогаются
	@if [ "$(CONFIRM)" != "yes" ]; then \
		echo "ОШИБКА: infra-clean уничтожает kind-кластер и tofu-стейт (GitLab-вольюмы и серты не трогаются)."; \
		echo "Разрешено только владельцу инфры (см. AGENTS.md: Multi-agent discipline)."; \
		echo "Запускайте: make infra-clean CONFIRM=yes"; \
		exit 1; \
	fi
	$(MAKE) infra-clean-tofu infra-clean-kind

.PHONY: infra-clean-tofu
infra-clean-tofu: ## tofu destroy трёх root'ов (порядок apps → infra-apps → base, кластер ещё жив); infra-apps скипается, если GitLab не запущен (gitlab_* ресурсы недостижимы, in-cluster часть умрёт с kind)
	@set -e; for root in apps infra-apps base; do \
		if [ "$$root" = "infra-apps" ] && \
		   [ "$$(curl -sk -o /dev/null -w '%{http_code}' https://gitlab.local:8443/-/health 2>/dev/null || true)" != "200" ]; then \
			echo ">>> GitLab (https://gitlab.local:8443) не запущен — destroy infra-apps пропущен:"; \
			echo ">>> gitlab_* ресурсы недостижимы, in-cluster часть (keycloak/harbor/CNPG) умрёт с kind-кластером."; \
			continue; \
		fi; \
		echo ">>> tofu destroy: $$root"; \
		(cd infrastructure/terraform/$$root && tofu init -input=false && tofu destroy -auto-approve -input=false); \
	done

.PHONY: infra-clean-kind
infra-clean-kind: ## Удалить kind-кластер + hosts и стейт-каталоги (~/.local/state/bigbug/{apps,infra-apps,base}); certs/ не трогается
	bash infrastructure/kind/teardown.sh --all
	rm -rf $(STATE_DIR)/apps $(STATE_DIR)/infra-apps $(STATE_DIR)/base
	rm -rf $(TF_ROOTS)

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
test-e2e-backend: ## Backend e2e-тесты (требует запущенного dev-стенда kind; seed учёток входит)
	@bash -c 'source backend/scripts/e2e-env.sh && ./backend/scripts/test-e2e.sh $(TEST_ARGS)'

.PHONY: test-e2e-seed
test-e2e-seed: ## Идемпотентный сид e2e-учёток в БД (ADR-0024 §3)
	@bash -c 'source backend/scripts/e2e-env.sh && ./backend/scripts/seed-e2e.sh'

.PHONY: coverage-backend-e2e
coverage-backend-e2e: ## Покрытие кода e2e-прогоном + отчёт по эндпоинтам
	@bash -c 'source backend/scripts/e2e-env.sh && ./backend/scripts/test-e2e-coverage.sh'

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

.PHONY: coverage-frontend
coverage-frontend: ## Покрытие кода frontend (vitest --coverage)
	./frontend/scripts/test.sh --coverage

.PHONY: coverage-all
coverage-all: coverage-backend-unit coverage-backend-e2e coverage-frontend ## Покрытие обоих стеков

# =============================================================================
##@ security — сканирование секретов
# =============================================================================

.PHONY: secrets-scan
secrets-scan: ## Поиск секретов в полной git-истории (gitleaks, exit != 0 при находках)
	./scripts/secrets-scan.sh

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
