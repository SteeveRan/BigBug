#!/usr/bin/env bash
#
# @file entrypoint.sh
# @description Container entrypoint for the BigBug backend. Dispatches between
#              `app:start` (wait for DB, run migrations, launch uvicorn),
#              `app:init` (wait for DB, run migrations, exit) and arbitrary
#              commands (e.g. bash, pytest) that are exec'd as-is.
#              The two `app:*` commands are intended for production / CI flows
#              where deterministic DB readiness and schema upgrades must
#              precede the application start.
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

    # WHY: A here-doc into python3 is more robust than awk/sed regexes against
    # URL-encoded credentials or unusual hostnames (e.g. IPv6).
    local parsed
    parsed="$(python3 - <<'PY' "${DATABASE_URL}"
import sys
from urllib.parse import urlparse, unquote

raw = sys.argv[1]
# Strip SQLAlchemy dialect (e.g. "postgresql+asyncpg") so urlparse sees a
# scheme it can reason about.
scheme, _, rest = raw.partition("://")
base_scheme = scheme.split("+", 1)[0]
url = urlparse(f"{base_scheme}://{rest}")

host = url.hostname or ""
port = url.port or 5432
user = unquote(url.username or "")
db = (url.path or "/").lstrip("/")

if not host:
    sys.stderr.write("DATABASE_URL is missing host component\n")
    sys.exit(1)

print(f"{host}\t{port}\t{user}\t{db}")
PY
)"

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
    if ! python3 /app/docker/seed_admin.py; then
        log WARN "Admin seeding returned non-zero (see above) — continuing"
    fi
}

# WHY: `--reload` is only safe and useful in development, where the source tree
# is bind-mounted into the container. In production the watcher wastes CPU and
# can lead to inconsistent worker state on partial writes.
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
    exec uvicorn "${uvicorn_args[@]}"
}

main() {
    # WHY: When the container is invoked without arguments docker-compose passes
    # an empty argv. Treat that as the default production-style start.
    local cmd="${1:-app:start}"

    case "${cmd}" in
        app:start)
            wait_for_db
            run_migrations
            seed_admin
            start_app
            ;;
        app:init)
            wait_for_db
            run_migrations
            seed_admin
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
