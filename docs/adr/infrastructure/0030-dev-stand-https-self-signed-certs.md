---
status: proposed
date: 2026-10-23
decision-makers: SteeveRan
consulted: SteeveRan
informed: SteeveRan
---

# HTTPS на dev-стенде: self-signed сертификаты per-service, терминирование на ingress

## Context and Problem Statement

Dev-стенд переезжает в kind-кластер `bigbug-dev` ([ADR-0022](0022-dev-stand-on-kind.md)); адресация — хосты `keycloak.local`, `harbor.local`, `app.local`, `api.local` через haproxy-ingress. Ранние итерации стенда (#54–#57, уже в main) зафиксировали **plain HTTP** за ingress — «dev simplification». Однако:

- **Браузерный трафик** (SPA на `app.local`, OIDC-редиректы на `keycloak.local`, Harbor UI) в production будет HTTPS — dev на HTTP не репетирует реальную схему (mixed-content блокировки, secure-cookie поведение, redirect-логику OIDC-клиентов);
- **OIDC redirect URIs** уже разъехались: harbor-клиент в tofu ссылается на `https://harbor.local:30443/...` (эпоха отдельного harbor-кластера), frontend — на `http://localhost:5173/*` (compose-эра) — ни то, ни другое не соответствует целевой схеме;
- **Docker registry протокол** в реальном deploy — HTTPS (`harbor.local:443` в пресетах и тестах backend уже так думают);
- [ADR-0028](../common/0028-security-transport-cors-jwt-ttl.md) §1 фиксирует «TLS — задача периметра», но не отвечает, **каков периметр в dev-стенде** и откуда берутся сертификаты.

Вопрос: **как обеспечить HTTPS на dev-стенде** — кто генерирует сертификаты, как клиенты (хост, docker daemon, поды) начинают им доверять, и что происходит с сервисами за TLS-терминатором?

## Decision Drivers

* Сертификаты должны **переживать пересоздание кластера** — иначе каждый `infra-clean` инвалидирует доверие хоста/браузеров (перенастраивать после каждого цикла)
* Минимализм (ADR-0001): без CA-инфраструктуры (штатный cert-manager), без внешних зависимостей (Let's Encrypt невозможен на `.local`-хостах)
* Per-provider `verify_ssl` (ADR-0028 §2) не должен вырождаться в тотальный `verify_ssl=False` — self-signed стенд не повод отключать проверку везде
* Сервисы за TLS-терминатором должны корректно строить внешние URL (redirect'ы, HMR-вебсокеты) — им нужно видеть forwarded-заголовки
* Существующие issues #58–#62 (переезд Harbor, app chart, Makefile) — HTTPS-решение должно встраиваться в них, а не плодить отдельный параллельный поток

## Considered Options

* Per-service self-signed сертификаты, генерация императивным скриптом на хосте, терминирование на ingress
* Один локальный CA + wildcard `*.local`-сертификат
* cert-manager в кластере + self-signed ClusterIssuer
* Остаться на plain HTTP за ingress (статус-кво #54–#57)

## Decision Outcome

Chosen option: **per-service self-signed сертификаты** (по одному на хост: `keycloak.local`, `harbor.local`, `app.local`, `api.local` + GitLab), генерируемые **императивным скриптом на хосте до инициализации стенда**; TLS терминируется на haproxy-ingress, к подам — HTTP.

### Зафиксированные правила

**1. Скоуп: HTTPS — только на внешних reverse-proxy.** Все входящие соединения из «внешнего мира» (браузер, docker daemon хоста, OIDC-клиенты) — HTTPS на ingress (и на nginx omnibus GitLab: `external_url https://gitlab.local:8443`). **Pod-to-pod трафик остаётся HTTP** — нет жёсткого требования шифровать трафик внутри одной ноды dev-стенда; mTLS между сервисами — non-goal (согласован с ADR-0028 non-goals).

**2. Сертификаты: per-service self-signed, без CA.** У каждого внешнего хоста — свой self-signed сертификат (SAN: hostname). Нет CA/wildcard — если у сервиса появятся свои требования (например, настоящий CA-подписанный серт), он встраивается индивидуально, не ломая остальных.

**3. Генерация — императивно, на хосте, до стенда.** Скрипт `infrastructure/kind/certs.sh` (openssl, idempotent):
- создаёт `~/.local/state/bigbug/certs/<host>/{tls.crt,tls.key}` — **state-каталог рядом с tofu-стейтами** (`~/.local/state/bigbug/`, тот же жёсткий путь, что в `backend.tf`), общий для всех git-worktree машины: серты живут вне и кластера, и репозитория/ворктрия (выучено на практике: ворктрий, из которого делали bootstrap, удалили — серты пропали, доверие молча сломалось);
- **серты стабильны**: переживают `infra-clean`/`infra-init` и удаление ворктрия — доверие на хосте не перенастраивается после пересоздания кластера; удаляются только вручную или `certs.sh --reset` (осознанная ротация; после неё — повторный trust);
- `bootstrap.sh` **проверяет наличие сертов до создания кластера** и падает с внятной ошибкой («запустите certs.sh»), если их нет — порядок `certs → bootstrap` обязателен.

Обоснование императивности (та же граница, что кластер+hosts в [ADR-0029](0029-dev-stand-k8s-entities-via-opentofu-base-apps-split.md)): сертификаты нужны **до** кластера (bootstrap-чек, хост-доверие, docker daemon) и **вне его жизненного цикла**. Cert-manager + self-signed ClusterIssuer отклонён: он выдаёт сертификаты только внутри работающего кластера и пересоздаёт их вместе с кластером — доверие пришлось бы перенастраивать на каждом `infra-clean`.

**4. Доверие — двумя путями, по потребителю:**

| Потребитель | Механизм |
|---|---|
| Поды в кластере (backend → Keycloak OIDC/Harbor API) | **Secret/ConfigMap-инжект**: серты как k8s Secrets (см. §5) → маунт в под + `REQUESTS_CA_BUNDLE`/`SSL_CERT_FILE` env (`SSL_CERT_FILE` — httpx honors его; backend использует httpx, не requests) → per-provider `verify_ssl=True` работает со self-signed (ADR-0028 §2 сохраняет силу — проверку никто не отключает). Конкретный механизм зависит от чарта: Harbor берёт CA-бандл из **Secret** (`caBundleSecretName` — только Secret с ключом `ca.crt`, ConfigMap чарт не принимает — исключение к формулировке «ConfigMap-инжект») |
| Harbor core → Keycloak OIDC | маунт серта Keycloak в harbor-под + `oidc_verify_cert: true` (не выключать проверку) |
| Хост: браузер, curl, httpx e2e, tofu config root | **скрипты для пользователя**: `certs.sh` (генерация, без sudo) и `trust-host.sh` (добавление в system trust store, sudo — осознанное действие пользователя; `untrust-host.sh` в teardown-симметрию) |
| Docker daemon (push/pull harbor.local) | только через system trust store (после trust-host.sh + restart daemon). **`insecure-registries` убирается** — с HTTPS-сертификатами он больше не нужен, а его отсутствие гарантирует, что доверие реально работает |

**5. TLS-секреты в кластере — tofu (infra-apps/apps roots).** `kubernetes_secret` (type `kubernetes.io/tls`) из файлов state-каталога (`pathexpand("~/.local/state/bigbug/certs/<host>/...")`) в `infrastructure/terraform/infra-apps/` (keycloak/harbor) и `infrastructure/terraform/apps/` (api/app для приложения, #59) — паттерн [ADR-0024](../common/0024-k8s-secrets.md) (tofu управляет k8s-объектами); ingress'ы keycloakx/Harbor/app-chart ссылаются на секреты через values. **Base остаётся one-shot без внешних значений** (ADR-0029) — секреты из файлов нельзя помещать в base.

**6. Сервисы за прокси обязаны видеть forwarded-заголовки** (иначе строят внутренние URL):
- keycloakx: `proxy: forwarded` — уже настроено (#57);
- Harbor: `expose.tls.enabled: true` (cert из tofu-секрета), `externalURL: https://harbor.local`;
- app chart: Vite dev-сервер — `server.hmr.protocol: wss`, `clientPort: 443` (HMR-вебсокет через https-ingress), prod-values — nginx за ingress без спецнастроек;
- backend: FastAPI за proxy — uvicorn `--proxy-headers`, `FORWARDED_ALLOW_IPS` (trust proxy из pod-сети).

**7. CORS — env `CORS_ORIGINS`.** Kind-стенд = первый деплой с раздельными origin'ами (`app.local` ≠ `api.local`) — триггер из [ADR-0028](../common/0028-security-transport-cors-jwt-ttl.md) §3 сработал: hardcode выносится в env (ConfigMap chart'а, не Secret). Дефолт — текущие localhost'ы (compose-эра), values-dev добавляет `https://app.local`. ADR-0028 §3 обновляется.

**8. OIDC redirect URIs — точные https-URI**, снос наследия старых схем: frontend `["https://app.local/*"]`, harbor `["https://harbor.local/c/oidc/callback", "https://harbor.local/"]` (без `:30443`), backend client `valid_redirect_uris` `["*"]` → `["https://app.local/*"]` (ужесточение бесплатно к переезду).

**9. GitLab — HTTPS на его nginx.** Omnibus `external_url https://gitlab.local:8443` с сертом из certs.sh. GitLab остаётся compose-исключением (D3/ADR-0022 §4), но его внешний трафик тоже HTTPS.

**10. e2e** — `BIGBUG_E2E_BASE_URL=https://api.local`; httpx на хосте — через system trust store (после trust-host.sh).

### Consequences

* Good, because браузер/OIDC/docker-клиенты в dev работают по той же схеме, что в prod — mixed-content, secure-cookie и redirect-баги ловятся до прода
* Good, because серты вне кластера: пересоздание стенда не инвалидирует доверие — полный цикл `infra-clean && infra-init` не требует повторного trust
* Good, because `verify_ssl=True` по умолчанию работает везде (поды через Secret/ConfigMap-инжект, хост через system store) — ADR-0028 §2 не вырождается в тотальный `verify_ssl=False`
* Good, because per-service серты без CA — минимальная крипто-инфраструктура: нет единого CA, компромисс которого убил бы все хосты разом; каждый серт независим
* Bad, because 5 сертов вместо одного wildcard: новый хост = новый серт (правда, хост добавляется и в hosts, и в ingress — шаг не пустой)
* Bad, because доверие хоста — ручной шаг пользователя (`trust-host.sh` с sudo) — не автоматизирован намеренно: менять system trust store молча — плохо
* Bad, because **known limitation**: docker:dind CI-джобы (gold/app image builds, docker.sock executor) не наследуют host trust store — джобе нужен маунт серта (CI-переменная/маунт); до решения джобы работают с `--insecure`-паттернами или падают на self-signed — отложено, фикс в пресетах при первой необходимости
* Bad, because `certs/` в gitignored — на новой машине сначала `certs.sh` + `trust-host.sh`, потом `infra-init` (bootstrap чекает и подсказывает — mitigation)
* Neutral, because pod-to-pod HTTP — осознанный отказ от шифрования внутри одной ноды dev-стенда; в prod за ingress та же схема (TLS на периметре)

### Confirmation

1. Наличие и стабильность сертов:

```bash
./infrastructure/kind/certs.sh                  # генерация
ls ~/.local/state/bigbug/certs/keycloak.local/  # tls.crt tls.key
make infra-clean && make infra-init             # полный цикл
# серты не пересоздались (mtime прежний), доверие хоста не перенастраивалось
curl -fsS https://keycloak.local/realms/master  # → 200 без -k
```

2. Bootstrap-чек: `mv ~/.local/state/bigbug/certs /tmp/bigbug-certs.bak && ./infrastructure/kind/bootstrap.sh` → падает с сообщением «запустите certs.sh», кластер не создаётся; вернуть каталог обратно.

3. Поды доверяют сертам:

```bash
kubectl exec -n bigbug deploy/backend -- curl -fsS https://keycloak.local/realms/master  # → 200, без -k
kubectl get secret -n bigbug --context kind-bigbug-dev | grep tls-   # tls-секреты на месте
```

4. Docker через system trust (после trust-host.sh):

```bash
docker login harbor.local -u admin -p Harbor12345   # без insecure-registries в daemon.json
docker pull harbor.local/library/nginx:latest        # TLS-ошибок нет
```

5. Fitness-критерии ревью:
   - `grep -r "insecure-registries" infrastructure/` — пусто (механизм удалён);
   - `grep -rE "verify_ssl.*[Ff]alse|oidc_verify_cert.*false" infrastructure/terraform/apps/` — пусто (проверка не выключается);
   - в `charts/bigbug/values-dev.yaml` backend env содержит `REQUESTS_CA_BUNDLE` (secretKeyRef/ConfigMap), не plain-значение серта;
   - redirect URIs в `terraform.tfvars.example` — только https, без `:30443`.

## Pros and Cons of the Options

### Per-service self-signed + императивная генерация — chosen

* Good, because серты вне жизненного цикла кластера — стабильное доверие
* Good, because ноль новых зависимостей (openssl есть всюду)
* Bad, because per-service = N сертов, новый хост = новый серт
* Bad, because ручной trust-шаг на хосте

### Один CA + wildcard `*.local`

* Good, because один Secret для всех ingress-хостов, новый хост без нового серта
* Bad, because компромисс приватного ключа wildcard-серта или CA убивает все хосты разом; per-service ограничивает blast radius хостом
* Bad, потому что CA всё равно нужен вне кластера — сложность та же, плюс слой косвенности (CA → leaf)
* Вердикт: на dev-стенде с 4–5 хостами выгода wildcard мизерна против цены единого секретного материала

### cert-manager + self-signed ClusterIssuer

* Good, because декларативно, авто-ротация, «куберный» путь
* Bad, because серты живут и умирают с кластером — после каждого `infra-clean` все клиенты (браузер, docker, хост-trust) видят новый недоверенный серт; это ломает главный driver (стабильность доверия)
* Bad, because cert-manager — новый оператор в base ради задачи, решаемой openssl-ом за 10 строк
* Вердикт: пересмотр при появлении prod/preprod-кластера с реальными ACME/DNS-01 — но не для kind-стенда

### Остаться на plain HTTP (статус-кво)

* Good, because ноль работы
* Bad, because dev не репетирует prod-схему: mixed-content, secure-cookies, OIDC-redirect'ы, docker TLS — всё впервые встретится при первом HTTPS-деплое
* Bad, because OIDC redirect URIs уже разъехались по трём эпохам схем (localhost, :30443, bare) — рано или поздно сводить
* Вердикт: отклонено — цена разового переезда ниже цены «первого HTTPS-деплоя в проде»

## More Information

* [ADR-0022](0022-dev-stand-on-kind.md) — топология стенда (этот ADR уточняет §2 адресации: хосты те же, схема https; GitLab :8080 → :8443)
* [ADR-0028](../common/0028-security-transport-cors-jwt-ttl.md) — транспортная безопасность платформы (§1 «TLS на proxy» конкретизируется: периметр в dev = haproxy-ingress + nginx GitLab; §3 CORS-триггер сработал)
* [ADR-0029](0029-dev-stand-k8s-entities-via-opentofu-base-apps-split.md) — граница императивного (кластер, hosts, теперь серты) и tofu-слоёв (TLS-секреты — apps root)
* [ADR-0024](../common/0024-k8s-secrets.md) — tofu управляет k8s Secret'ами (TLS-секреты из файлов — тот же паттерн)
* [ADR-0023](0023-bigbug-helm-chart.md) — app chart (values-dev: REQUESTS_CA_BUNDLE, CORS_ORIGINS, Vite HMR)
* Issues: #58 (Harbor https), #59 (chart + TLS-секреты + CORS + HMR), #60 (e2e https), #61 (bootstrap-чек сертов, init-порядок, GitLab https), #62 (docs)
* Известный хвост для #59: backend-под зовёт `https://keycloak.local` — из пода DNS резолвится через external IP (extraPortMappings) — работает, но трафик выходит из кластера; альтернатива (internal service URL при внешнем issuer) — если всплывут проблемы, отдельное решение
* Условие пересмотра: prod/preprod-кластер с ACME (cert-manager вернётся); появление второго kind-кластера (общий CA/wildcard станет выгоднее per-service); требование mTLS внутри кластера
