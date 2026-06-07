#!/usr/bin/env bash
#
# @file update-env.sh
# @description Updates the .env file with outputs from the root OpenTofu module.
#              Reads all infrastructure outputs from infrastructure/terraform/
#              and writes them to the project .env.
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

log "### Updating .env from OpenTofu outputs ###"

# ─────────────────────────────────────────────────────────────
# Read all outputs from the root terraform module
# ─────────────────────────────────────────────────────────────
if [[ ! -f "${TF_DIR}/terraform.tfstate" ]]; then
    log_warn "  Root terraform state not found at ${TF_DIR}/terraform.tfstate"
    log_warn "  Run 'cd ${TF_DIR} && ${TF_CMD} apply' first."
    exit 0
fi

cd "${TF_DIR}"

log "  Reading Keycloak outputs..."

KC_REALM="$("${TF_CMD}" output -raw keycloak_realm_name 2>/dev/null || echo "")"
KC_BACKEND_ID="$("${TF_CMD}" output -raw keycloak_backend_client_id 2>/dev/null || echo "")"
KC_BACKEND_SECRET="$("${TF_CMD}" output -raw keycloak_backend_client_secret 2>/dev/null || echo "")"
KC_FRONTEND_ID="$("${TF_CMD}" output -raw keycloak_frontend_client_id 2>/dev/null || echo "")"

if [[ -n "${KC_REALM}" ]]; then
    update_env_var "KEYCLOAK_REALM" "${KC_REALM}"
fi
if [[ -n "${KC_BACKEND_ID}" ]]; then
    update_env_var "KEYCLOAK_CLIENT_ID" "${KC_BACKEND_ID}"
fi
if [[ -n "${KC_BACKEND_SECRET}" ]]; then
    update_env_var "KEYCLOAK_CLIENT_SECRET" "${KC_BACKEND_SECRET}"
fi
if [[ -n "${KC_FRONTEND_ID}" ]]; then
    update_env_var "KEYCLOAK_FRONTEND_CLIENT_ID" "${KC_FRONTEND_ID}"
fi

log "  Reading GitLab outputs..."

GL_TOKEN="$("${TF_CMD}" output -raw gitlab_backend_token 2>/dev/null || echo "")"

if [[ -n "${GL_TOKEN}" ]]; then
    update_env_var "GITLAB_TOKEN" "${GL_TOKEN}"
else
    log_warn "  Could not extract GITLAB_TOKEN from terraform outputs (GitLab module may not have been applied)."
fi

log "### .env update complete ###"
