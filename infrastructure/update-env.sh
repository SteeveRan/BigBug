#!/usr/bin/env bash
#
# @file update-env.sh
# @description Updates the .env file with host-tool variables only.
#
# Since issue #56 (ADR-0024) all application secrets (DB credentials,
# ENCRYPTION_KEY, Keycloak OIDC) are delivered into the cluster as k8s Secrets
# by the OpenTofu apps layer — NOT via .env. GitLab PAT is app configuration
# (resource_providers, set in UI at app deploy time) — tofu does not mint it.
# This script keeps only the variables needed by tools running on the host,
# outside the cluster:
#   - BIGBUG_E2E_BASE_URL — e2e tests hit the ingress (http://api.local)
#
# Usage:
#   ./infrastructure/update-env.sh
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
ENV_FILE="${PROJECT_ROOT}/.env"

# ─────────────────────────────────────────────────────────────
# Logging
# ─────────────────────────────────────────────────────────────
log() {
    printf '[%s] %s\n' "$(date +'%Y-%m-%d %H:%M:%S')" "$*" >&2
}

# ─────────────────────────────────────────────────────────────
# Helper: update or add a key=value in .env
# ─────────────────────────────────────────────────────────────
update_env_var() {
    local key="$1"
    local value="$2"
    local file="${3:-$ENV_FILE}"

    if [[ ! -f "${file}" ]]; then
        log "  WARNING: ${file} does not exist. Creating..."
        touch "${file}"
    fi

    if grep -q "^${key}=" "${file}"; then
        # Update existing key
        sed -i "s|^${key}=.*|${key}=${value}|" "${file}"
        log "  Updated ${key}"
    else
        # Append new key
        echo "${key}=${value}" >> "${file}"
        log "  Added ${key}"
    fi
}

log "### Updating .env with host-tool variables ###"

# App secrets (DB/Fernet/Keycloak) are k8s Secrets managed by the apps layer
# (ADR-0024) — this script must not write them into .env. GitLab PAT is set
# in the app UI (resource_providers) at app deploy time — not here either.

# e2e tests run on the host and reach the backend through the ingress host
update_env_var "BIGBUG_E2E_BASE_URL" "http://api.local"

log "### .env update complete ###"
