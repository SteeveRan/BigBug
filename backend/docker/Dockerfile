# syntax=docker/dockerfile:1.23
#
# Multi-stage build for the BigBug backend (FastAPI + SQLAlchemy + Alembic).
#
# Layout rationale:
#   * `builder` stage compiles wheels and installs them into a self-contained
#     virtualenv at /opt/venv. Keeping deps outside /app means bind-mounting
#     the source tree at runtime (compose dev mode) does NOT shadow the
#     installed packages.
#   * `runtime` stage starts from a clean slim image, copies only the venv
#     plus app sources, runs as a non-root user and uses tini as PID 1 so
#     uvicorn receives signals correctly.
#
# Build:
#   docker build -t bigbug-backend:dev backend/
# Run:
#   docker run --rm -e DATABASE_URL=... bigbug-backend:dev app:init

ARG PYTHON_VERSION=3.14

############################################
# Stage 1: builder
############################################
FROM python:${PYTHON_VERSION}-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    VIRTUAL_ENV=/opt/venv \
    PATH="/opt/venv/bin:$PATH"

# WHY: build-essential is only needed for native wheels (bcrypt, asyncpg) and
# is dropped together with the entire builder stage from the final image.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        curl \
    && rm -rf /var/lib/apt/lists/*

# WHY: uv resolves & installs an order of magnitude faster than pip and we use
# it consistently across the project. The venv lives at a stable path so the
# runtime stage can copy it verbatim.
RUN pip install --no-cache-dir uv \
    && python -m venv /opt/venv

WORKDIR /build

# WHY: Copy only the manifest first so dependency installation is cached
# independently from source changes. The app/ source must also be present
# so that `uv pip install .` can discover the package defined in pyproject.toml
# (packages = ["app"]) and install it into /opt/venv.
COPY pyproject.toml ./
COPY app/ ./app/

RUN uv pip install --python /opt/venv/bin/python --no-cache .

############################################
# Stage 2: runtime
############################################
FROM python:${PYTHON_VERSION}-slim AS runtime

ARG APP_UID=1000
ARG APP_GID=1000

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    VIRTUAL_ENV=/opt/venv \
    PATH="/opt/venv/bin:$PATH" \
    PYTHONPATH=/app \
    ENVIRONMENT=production

LABEL org.opencontainers.image.title="bigbug-backend" \
      org.opencontainers.image.description="BigBug DevOps Sync & Build Service backend" \
      org.opencontainers.image.source="https://github.com/your-org/bigbug" \
      org.opencontainers.image.licenses="Apache-2.0"

# WHY: postgresql-client provides pg_isready used by entrypoint.sh to gate
# startup on DB readiness. tini guarantees correct signal propagation for
# uvicorn (esp. SIGTERM on `docker stop`). curl is used by HEALTHCHECK.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        postgresql-client \
        tini \
        curl \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system --gid "${APP_GID}" app \
    && useradd --system --uid "${APP_UID}" --gid app --home /app --shell /usr/sbin/nologin app

WORKDIR /app

# Copy the prebuilt virtualenv from the builder. Ownership stays root because
# the venv is read-only at runtime, which is desirable.
COPY --from=builder /opt/venv /opt/venv

# WHY: entrypoint.sh is copied separately (and outside /app) so a bind-mount
# of the source tree during development cannot override it.
COPY --chown=app:app docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

COPY --chown=app:app . /app

USER app

EXPOSE 8000

# WHY: /api/health is mounted under the FastAPI `/api` prefix (see app/main.py),
# so the healthcheck must hit the same path. start-period gives Alembic
# migrations a window to complete on cold starts before failures count.
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD curl -fsS http://localhost:8000/api/health || exit 1

ENTRYPOINT ["/usr/bin/tini", "--", "/entrypoint.sh"]
CMD ["app:start"]
