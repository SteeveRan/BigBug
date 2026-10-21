# Runbook: External Provider API Notes

> Reference for debugging external integrations (GitLab, Harbor, GitHub, Docker registries, Helm repos). **Upstream vendor docs are authoritative** — this file only captures non-obvious facts and quirks we hit in practice. App-side API contract is OpenAPI: `http://localhost:8000/docs` / `backend/openapi.json` (guarded by `backend/tests/unit/test_openapi_contract.py`, regenerated via `backend/scripts/export-openapi.sh`).

## GitLab

- Auth header: `PRIVATE-TOKEN: <token>` (PAT / group / project access tokens).
- PAT scopes: `api` (full), `read_api` (read-only), `read_repository` / `write_repository` for repo ops.
- Rate limit (default): 2000 req/min authenticated, 500 req/min per-IP unauthenticated. Headers: `RateLimit-Limit`, `RateLimit-Remaining`, `RateLimit-Reset`. On 429 — exponential backoff.
- Pagination: `page`/`per_page` params; totals in headers `X-Total`, `X-Total-Pages`, `X-Page`, `X-Per-Page`, `X-Next-Page`, `X-Prev-Page`.
- Health check used by the app: `GET {url}/api/v4/version`.
- Webhook secret arrives in header `X-Gitlab-Token` — verify with constant-time compare (`hmac.compare_digest`).

## Harbor

- API base: `https://harbor.example.com/api/v2.0`.
- Prefer **robot accounts** over user credentials. Robot permissions: `push`, `pull`, `delete`, `read`. Auth: `Authorization: Bearer <robot-token>` (or HTTP Basic for admin).
- Vulnerability scanning: trigger `POST .../artifacts/:reference/scan`, fetch report via `GET .../artifacts/:reference/additions/vulnerabilities`; scan overview also embeds in artifact `scan_overview` when queried with `with_scan_overview=true`.
- Pagination: `page`/`page_size`; total in `X-Total-Count` header, next/prev in `Link` header.
- Health check used by the app: `GET {url}/api/v2.0/ping`.
- No hard API rate limits; keep connection pooling and reasonable concurrency (<100 req/s).

## GitHub

- Auth header: `Authorization: token <token>` (PAT) or `Authorization: Bearer <jwt>` (GitHub App).
- Classic PAT scopes: `repo`, `read:org`, `read:user`.
- API version header: `X-GitHub-Api-Version: 2022-11-28`, `Accept: application/vnd.github+json`.
- Rate limit: 5000 req/hour authenticated, 60 req/hour unauthenticated. Headers: `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset`.
- Pagination via `Link` response header (`rel="next"`, `rel="last"`), `per_page` up to 100.
- Webhook signature: `X-Hub-Signature-256` = HMAC-SHA256 of raw body with the webhook secret — verify with constant-time compare.
- Use ETags for conditional requests to save rate budget.

## Docker Registries (OCI Distribution API v2)

- Bearer-token challenge flow:
  1. `GET /v2/` → 401 with `WWW-Authenticate: Bearer realm="...",service="...",scope="..."`.
  2. `GET <realm>/token?service=...&scope=...` (optionally with Basic auth) → `{"token": "..."}`.
  3. Retry with `Authorization: Bearer <token>`.
  - Cache the token until expiry; don't re-fetch per request.
- Registry quirks:
  - **Docker Hub**: registry URL `https://registry-1.docker.io`, token endpoint `https://auth.docker.io/token`.
  - **GCR**: HTTP Basic with literal username `_json_key`, password = full service-account JSON.
  - **ECR**: Basic with username `AWS`, password = output of `aws ecr get-login-password`. **Token TTL is 12 hours** — rotate/refresh automatically.
  - **ACR**: Basic with username / service-principal password.
- Digest: take `Docker-Content-Digest` response header, not the body field.

## Helm Repositories

- A Helm repo is a plain HTTP server: `index.yaml` + `<chart>-<version>.tgz` files. Anonymous or HTTP Basic auth (Bearer on some ChartMuseum installs).
- `index.yaml` is the source of list data: `entries.<chart>[].version / digest / urls[]`. Chart download URLs may be relative — resolve against the repo base URL.
- ChartMuseum (optional extra API, when available): `GET /api/charts` (list), `GET /api/charts/<name>/<version>`, `POST /api/charts` (upload, multipart). Faster than parsing `index.yaml` for large repos.
- Harbor can act as a Helm repo: `https://harbor.example.com/chartrepo/<project>` with Harbor Basic auth.
- Verify chart `digest`/checksum on download; set HTTP timeouts.
