---
status: proposed
date: 2026-10-22
decision-makers: SteeveRan
---

# Secrets в k8s: OpenTofu (kubernetes provider) управляет Secret'ами dev-стенда

## Context and Problem Statement

После переезда dev-стенда в kind ([ADR-0022](../infrastructure/0022-dev-stand-on-kind.md)) конфигурация и секреты приложения должны доставляться в поды по-куберному — через Secret/ConfigMap, а не через `.env` docker compose. При этом OpenTofu уже управляет конфигурацией инфраструктурных сервисов ([ADR-0013](../infrastructure/0013-opentofu-iac-keycloak-gitlab-harbor.md)) и генерирует часть секретов (Keycloak client secret, GitLab PAT, пароли).

Вопрос: **кто и каким способом создаёт k8s Secret'ы** для приложения и инфраструктурных сервисов dev-стенда — OpenTofu напрямую, скрипт-обвязка поверх `tofu output`, или ручной `kubectl`?

Отдельно в этом ADR: политика e2e-учёток — чем тестируется живой стенд ([ADR-0018](0018-e2e-testing-strategy.md)), теперь, когда стенд живёт в кластере.

## Decision Drivers

- Единый источник секрета: tofu уже генерирует/знает большинство кредов — дублирование в bash-скриптах = рассинхрон
- Декларативность: Secret'ы должны пересоздаваться `make infra-init` с нуля, как и всё остальное
- Граница: tofu управляет **инфраструктурными** секретами; бизнес-секреты (stored credentials в БД) шифруются приложением ([ADR-0010](../backend/0010-fernet-secrets-encryption.md)) — эту схему не трогаем
- E2E-тесты ходят на живой стенд — им нужны предсказуемые тестовые учётки, а не реальные пароли

## Considered Options

* tofu + kubernetes provider: Secret'ы как ресурсы в tofu-конфиге
* Bash-обвязка: `tofu output -json` → `kubectl create secret` в init.sh
* External Secrets Operator + Vault (dev-версия prod-подхода)
* Ручной kubectl / скрипт с хардкодом паролей

## Decision Outcome

Chosen option: **tofu + kubernetes provider** — Secret'ы объявлены как ресурсы в tofu-конфиге (модуль `k8s-secrets`), провайдер `hashicorp/kubernetes` указывает на контекст `kind-bigbug-dev`. Модуль подключается в **apps root** ([ADR-0029](../infrastructure/0029-dev-stand-k8s-entities-via-opentofu-base-apps-split.md)): секреты зависят от Postgres Cluster (CNPG) и токена из config-root — оба появляются после base, поэтому base секретов не создаёт. Один `tofu apply` по каждому root'у создаёт и конфигурацию Keycloak/GitLab/Harbor, и все k8s Secret'ы.

### Зафиксированные правила

**1. Какие Secret'ы создаёт tofu** (namespace `bigbug`, **apps-слой** — уточнение
из #56: apps применяются после base и config-root, поэтому в момент их apply
существуют и CNPG-кластер, и `gitlab_backend_token`; base не создаёт секретов —
он one-shot бутстрап без внешних значений):

| Secret | Содержимое | Потребители |
|---|---|---|
| `bigbug-db-credentials` | `DATABASE_URL` + `username`/`password`/`database`/`host`/`port` — проекция секрета `bigbug-dev-app`, генерируемого CNPG-оператором (не ручная копия) | backend (DATABASE_URL), hook Job миграций |
| `bigbug-keycloak-oidc` | `client_id`, `client_secret` (генерируются модулем keycloak) | backend |
| `bigbug-fernet-key` | `ENCRYPTION_KEY` (Fernet: 32 байта, urlsafe base64; генерация детерминирована state'ом — no drift на повторных apply) | backend |
| `bigbug-gitlab-token` | `GITLAB_TOKEN` (= `gitlab_backend_token` из config-root, **не** admin/root PAT из tfvars) | backend |

Граница: `app/core/secrets.py` (шифрование stored credentials) **не меняется** — `ENCRYPTION_KEY` просто доставляется из k8s Secret вместо `.env`.

**2. `.env` сжимается**: [`infrastructure/update-env.sh`](../../../infrastructure/update-env.sh) остаётся только для хостовых инструментов, которым нужен доступ извне кластера: e2e-скрипты (`BIGBUG_E2E_BASE_URL=http://api.local`), `tofu`/CLI с GitLab PAT. Конфигурация приложения — целиком через k8s Secret/values ([ADR-0023](../infrastructure/0023-bigbug-helm-chart.md)).

**3. E2E-учётки** ([ADR-0018](0018-e2e-testing-strategy.md)): отдельный seed-скрипт (`backend/scripts/seed-e2e.sh`, make-цель), вызывается из `test-e2e.sh` **до прогона** и создаёт тестовых пользователей:
- в БД BigBug (локальный email/password auth — через API или seed-функцию);
- в realm `bigbug` Keycloak (SSO-сценарии — приоритет: они самые сложные и легко ломаются; realm-пользователи добавляются в tofu-модуль keycloak `users.tf`, чтобы пересоздавались вместе со стендом).

Политика: **никаких реальных кредов в e2e** — только seeded-учётки с известными паролями из фикстур скрипта.

**4. Провайдер и контекст**: `hashicorp/kubernetes` — не новая внешняя зависимость (поставляется с tofu), но новый паттерн «tofu управляет k8s-объектами»; это расширение границы IaC из ADR-0013 (раньше — «управление ресурсами внутри kind-кластера через tofu» было non-goal).

### Consequences

* Good, because один `tofu apply` воспроизводит весь набор секретов с нуля — no manual `kubectl create secret`
* Good, because Secret'ы версионируются в tofu-конфиге (значения — из generated-ресурсов, в git попадают только ссылки)
* Good, because связь «CNPG Cluster ↔ Secret приложения» декларативна: tofu ссылается на атрибуты обоих модулей
* Bad, because tofu state теперь содержит чувствительные значения в plaintext (как и раньше для client_secret/PAT — local state, gitignored; приемлемо для dev, для prod — remote state + шифрование)
* Bad, because порядок apply усложняется: k8s-модуль требует живого кластера и namespace — init.sh должен гарантировать создание кластера до `tofu apply`
* Neutral, because External Secrets Operator/Vault — целевой prod-подход, но в dev это лишний оператор; переоценка при prod-ADR

### Confirmation

1. Проверка воспроизводимости:

```bash
make infra-clean && make infra-init
kubectl get secrets -n bigbug --context kind-bigbug-dev
# ожидается: bigbug-db-credentials, bigbug-keycloak-oidc, bigbug-fernet-key, bigbug-gitlab-token
```

2. E2E-политика: `grep -rE 'password' backend/tests/e2e/` показывает только ссылки на seeded-учётки (константы из seed-скрипта/фикстур), никаких личных или admin-паролей стенда. Прогон `make test-e2e-backend` начинается с вызова seed-скрипта (видно в логе).

3. Fitness-критерии ревью:
   - Новый инфраструктурный секрет появляется как resource в модуле `k8s-secrets` (подключённом в apps root), а не `kubectl create` в bash
   - Base-слой не содержит ресурсов приложений и секретов (граница [ADR-0029](../infrastructure/0029-dev-stand-k8s-entities-via-opentofu-base-apps-split.md))
   - Приложение в k8s не получает секреты через plain env в Deployment-манифесте — только `secretKeyRef`

## Pros and Cons of the Options

### tofu + kubernetes provider (chosen)

* Good, because декларативно, идемпотентно, с графом зависимостей (Keycloak client secret → Secret → Deployment)
* Good, because ноль новых инструментов в цепочке
* Bad, because tofu state — plaintext-хранилище секретов (dev-приемлемо, gitignored)
* Bad, because init.sh обязан создать кластер до apply — новый порядок зависимости

### Bash-обвязка (`tofu output` → `kubectl create secret`)

* Good, because не трогает tofu-конфиг
* Bad, because императивный парсинг outputs в bash — рассинхрон и хрупкость (не идемпотентен, не виден в plan/diff)
* Bad, because именно от такой склейки уходим (драйвер ADR-0013)

### External Secrets Operator + Vault

* Good, потому что prod-grade: секреты вне state, ротация, аудит
* Bad, because Vault в dev — тяжёлая зависимость ради нескольких Secret'ов; переоценка в prod-ADR

### Ручной kubectl

* Good, потому что ноль кода
* Bad, because невоспроизводимо и не версонируется — противоречит ADR-0013

## More Information

- [ADR-0022](../infrastructure/0022-dev-stand-on-kind.md) — кластер `bigbug-dev`, операторы CNPG/redis-operator
- [ADR-0023](../infrastructure/0023-bigbug-helm-chart.md) — как приложение потребляет Secret'ы (env из `secretKeyRef`)
- [ADR-0013](../infrastructure/0013-opentofu-iac-keycloak-gitlab-harbor.md) — граница IaC расширяется: k8s-объекты теперь тоже tofu (non-goal из этого ADR снят)
- [ADR-0010](../backend/0010-fernet-secrets-encryption.md) — Fernet-шифрование stored credentials (не меняется)
- [ADR-0018](0018-e2e-testing-strategy.md) — e2e против живого стенда; seed-скрипт — новый обязательный шаг прогона
- Условие пересмотра: prod (Vault/ESO, remote state) — отдельный ADR
