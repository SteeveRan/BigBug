#!/usr/bin/env bash
#
# @file update-env.sh
# @description Updates the .env file with host-tool variables only.
#
# Since issue #56 (ADR-0024) all application secrets (DB credentials,
# ENCRYPTION_KEY, GitLab PAT) are delivered into the cluster as k8s Secrets
# by the OpenTofu base layer — NOT via .env. This script keeps only the
# variables needed by tools running on the host, outside the cluster:
#   - BIGBUG_E2E_BASE_URL — e2e tests hit the ingress (http://api.local)
#   - GITLAB_TOKEN        — tofu/CLI access to GitLab from the host
#
# Usage:
#   ./infrastructure/update-env.sh
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
TF_DIR="${SCRIPT_DIR}/terraform"
ENV_FILE="${PROJECT_ROOT}/.env"

# Detect tofu or terraform
if command -v tofu &>/dev/null; then
    TF_CMD="tofu"
elif command -v terraform &>/dev/null; then
    TF_CMD="terraform"
else
    echo "ERROR: Neither 'tofu' nor 'terraform' found. Please install one of them." >&2
    exit 1
fi

# ─────────────────────────────────────────────────────────────
# Logging
# ─────────────────────────────────────────────────────────────
log() {
    printf '[%s] %s\n' "$(date +'%Y-%m-%d %H:%M:%S')" "$*" >&2
}

log_warn() {
    printf '[%s] WARN:  %s\n' "$(date +'%Y-%m-%d %H:%M:%S')" "$*" >&2
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

# App DB / Fernet / Keycloak secrets are now k8s Secrets managed by OpenTofu
# (base layer, ADR-0024) — this script must not write them into .env.

# e2e tests run on the host and reach the backend through the ingress host
update_env_var "BIGBUG_E2E_BASE_URL" "http://api.local"

# ─────────────────────────────────────────────────────────────
# GitLab PAT for host CLI tools (from the config root module outputs)
# ─────────────────────────────────────────────────────────────
if [[ -f "${TF_DIR}/terraform.tfstate" ]]; then
    cd "${TF_DIR}"

    log "  Reading GitLab outputs..."
    GL_TOKEN="$("${TF_CMD}" output -raw gitlab_backend_token 2>/dev/null || echo "")"

    if [[ -n "${GL_TOKEN}" ]]; then
        update_env_var "GITLAB_TOKEN" "${GL_TOKEN}"
    else
        log_warn "  Could not extract GITLAB_TOKEN from terraform outputs (GitLab module may not have been applied)."
    fi
else
    log_warn "  Root terraform state not found at ${TF_DIR}/terraform.tfstate"
    log_warn "  Run 'cd ${TF_DIR} && ${TF_CMD} apply' first — skipping GITLAB_TOKEN."
fi

log "### .env update complete ###"
