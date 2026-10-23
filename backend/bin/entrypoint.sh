#!/usr/bin/env bash
#
# @file bin/entrypoint.sh
# @description Container entrypoint for the BigBug backend. Dispatches between
#              `app:start` (wait for DB, seed, launch uvicorn),
#              `app:init` (wait for DB, run migrations, seed, exit — used by
#              the helm migrate hook Job, ADR-0023 §4) and arbitrary commands
#              (e.g. bash, pytest) that are exec'd as-is.
#              In k8s migrations run as a pre-install/pre-upgrade hook Job;
#              `app:start` only waits for DB readiness.
# @dependencies pg_isready (postgresql-client), python3 (stdlib only), alembic
#
# Exit codes:
#   0  – success / command finished
#   1  – DB unreachable within DB_WAIT_TIMEOUT
#   2  – alembic migrations failed
#

set -euo pipefail

# WHY: Single timestamped logger keeps container output greppable by `docker logs`
# and lets us avoid mixing `echo` calls with different formats throughout the file.
log() {
    local level="${1:-INFO}"
    shift || true
    printf '%s [%s] [entrypoint] %s\n' \
        "$(date -u +'%Y-%m-%dT%H:%M:%SZ')" "${level}" "$*" >&2
}

# WHY: DATABASE_URL uses the async SQLAlchemy scheme (postgresql+asyncpg://),
# which pg_isready cannot consume directly. We parse it once in pure stdlib
# Python (no extra deps in the image) and export the discrete fields we need.
parse_database_url() {
    if [[ -z "${DATABASE_URL:-}" ]]; then
        log ERROR "DATABASE_URL is not set"
        return 1
    fi

    # WHY: a Python parse (bin/parse_db_url.py) is robust against URL-encoded
    # credentials and unusual hostnames (e.g. IPv6), where shell regexes fail.
    local parsed
    parsed="$(python3 /app/bin/parse_db_url.py "${DATABASE_URL}")"

    DB_HOST="$(echo "${parsed}" | cut -f1)"
    DB_PORT="$(echo "${parsed}" | cut -f2)"
    DB_USER="$(echo "${parsed}" | cut -f3)"
    DB_NAME="$(echo "${parsed}" | cut -f4)"
    export DB_HOST DB_PORT DB_USER DB_NAME
}

# WHY: We poll pg_isready instead of relying on docker-compose `depends_on`
# alone because Compose's `service_healthy` is not honored by all
# orchestrators we target (e.g. plain `docker run`, Kubernetes jobs).
wait_for_db() {
    local timeout="${DB_WAIT_TIMEOUT:-60}"
    local interval=2
    local elapsed=0

    parse_database_url

    log INFO "Waiting for PostgreSQL at ${DB_HOST}:${DB_PORT} (timeout=${timeout}s)"

    while (( elapsed < timeout )); do
        if pg_isready -h "${DB_HOST}" -p "${DB_PORT}" -U "${DB_USER}" -d "${DB_NAME}" -q; then
            log INFO "PostgreSQL is accepting connections after ${elapsed}s"
            return 0
        fi
        sleep "${interval}"
        elapsed=$(( elapsed + interval ))
    done

    log ERROR "PostgreSQL not reachable within ${timeout}s"
    return 1
}

# WHY: `alembic upgrade head` is idempotent, so it is safe to run on every
# container start. We split it from `wait_for_db` to allow callers to retry
# only the failed phase if needed.
run_migrations() {
    log INFO "Applying Alembic migrations (upgrade head)"
    if ! alembic upgrade head; then
        log ERROR "Alembic migrations failed"
        return 2
    fi
    log INFO "Migrations applied"
}

# WHY: Seeding the admin user after migrations guarantees the first
# administrator exists for bootstrapping. The Python script is idempotent —
# it exits cleanly when an admin already exists.
seed_admin() {
    log INFO "Seeding admin user (idempotent)"
    if ! python3 /app/bin/seed_admin.py; then
        log WARN "Admin seeding returned non-zero (see above) — continuing"
    fi
}

# WHY: Seeding the default public providers after migrations keeps the platform
# usable out-of-the-box (GitHub/GitLab/Docker Hub anonymous sources). The script
# is idempotent (upsert by name) and only touches seeded fields.
seed_providers() {
    log INFO "Seeding default providers (idempotent)"
    if ! python3 /app/bin/seed_providers.py; then
        log WARN "Provider seeding returned non-zero (see above) — continuing"
    fi
}

# WHY: `--reload` is only safe and useful in development, where the source tree
# is bind-mounted into the container. In production the watcher wastes CPU and
# can lead to inconsistent worker state on partial writes. Extra flags after
# `app:start --` (e.g. --proxy-headers from helm values-dev) are appended so
# the chart can tune uvicorn without editing the image.
start_app() {
    local -a uvicorn_args=(
        app.main:app
        --host 0.0.0.0
        --port 8000
    )
    if [[ "${ENVIRONMENT:-development}" == "development" ]]; then
        uvicorn_args+=(--reload)
        log INFO "Starting uvicorn in development mode (auto-reload enabled)"
    else
        log INFO "Starting uvicorn in ${ENVIRONMENT} mode"
    fi
    if [[ "${1:-}" == "--" ]]; then
        shift
        uvicorn_args+=("$@")
    fi
    exec uvicorn "${uvicorn_args[@]}"
}

# WHY: Compose dev mounts no CA bundle; k8s mounts the stand bundle
# (ConfigMap bigbug-ca-bundle) at EXTRA_CA_DIR. SSL_CERT_FILE/REQUESTS_CA_BUNDLE
# REPLACE the trust store entirely, so the exported bundle must be complete:
# system roots (public CAs: api.github.com, …) + stand certs (self-signed
# keycloak.local / harbor.local / gitlab.local). Merged into a writable
# emptyDir (/run/bigbug-ca) at every container start; exported for both httpx
# (app) and requests (transitive deps). No bundle mounted → no export, system
# store used as-is (compose parity). Never verify=False (ADR-0030 §4).
build_ca_bundle() {
    local extra_dir="/etc/bigbug-certs"
    local out="/run/bigbug-ca/ca-bundle.crt"
    shopt -s nullglob
    local extras=("${extra_dir}"/*.crt)
    shopt -u nullglob
    if (( ${#extras[@]} == 0 )); then
        log INFO "No stand CA bundle mounted at ${extra_dir} — using system trust store"
        return 0
    fi
    mkdir -p "$(dirname "$out")"
    cat /etc/ssl/certs/ca-certificates.crt "${extras[@]}" > "$out"
    export SSL_CERT_FILE="$out" REQUESTS_CA_BUNDLE="$out"
    log INFO "CA bundle built: system roots + ${#extras[@]} stand cert(s) → $out"
}

main() {
    # WHY: When the container is invoked without arguments docker-compose passes
    # an empty argv. Treat that as the default production-style start.
    local cmd="${1:-app:start}"

    build_ca_bundle

    case "${cmd}" in
        app:start)
            wait_for_db
            seed_admin
            seed_providers
            shift
            start_app "$@"
            ;;
        app:init)
            # helm hook Job only (ADR-0023 §4): migrations + seeds, then exit
            wait_for_db
            run_migrations
            seed_admin
            seed_providers
            log INFO "Initialization complete, exiting (app:init)"
            ;;
        *)
            # WHY: Forwarding the raw argv lets operators run ad-hoc commands
            # (bash, pytest, alembic ...) without bypassing the entrypoint —
            # which keeps the image's `USER`/`WORKDIR`/env consistent.
            log INFO "Executing custom command: $*"
            exec "$@"
            ;;
    esac
}

main "$@"
