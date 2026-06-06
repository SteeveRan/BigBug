#!/usr/bin/env bash
#
# @file update-env.sh
# @description Updates the .env file with outputs from OpenTofu/Terraform state.
#              Reads Keycloak and GitLab outputs and writes them to .env.
#
# Usage:
#   ./infrastructure/update-env.sh
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
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

# ── Keycloak outputs ──────────────────────────────────────────
KC_DIR="${SCRIPT_DIR}/keycloak"
if [[ -d "${KC_DIR}/.terraform" ]]; then
    log "  Reading Keycloak outputs..."
    cd "${KC_DIR}"

    KC_REALM="$("${TF_CMD}" output -raw realm_name 2>/dev/null || echo "")"
    KC_BACKEND_ID="$("${TF_CMD}" output -raw backend_client_id 2>/dev/null || echo "")"
    KC_FRONTEND_ID="$("${TF_CMD}" output -raw frontend_client_id 2>/dev/null || echo "")"

    if [[ -n "${KC_REALM}" ]]; then
        update_env_var "KEYCLOAK_REALM" "${KC_REALM}"
    fi
    if [[ -n "${KC_BACKEND_ID}" ]]; then
        update_env_var "KEYCLOAK_CLIENT_ID" "${KC_BACKEND_ID}"
    fi
    if [[ -n "${KC_FRONTEND_ID}" ]]; then
        update_env_var "KEYCLOAK_CLIENT_ID_FRONTEND" "${KC_FRONTEND_ID}"
    fi
else
    log "  Keycloak state not found — skipping. Run 'cd infrastructure/keycloak && ${TF_CMD} apply' first."
fi

# ── GitLab outputs ────────────────────────────────────────────
GL_DIR="${SCRIPT_DIR}/gitlab"
if [[ -d "${GL_DIR}/.terraform" ]]; then
    log "  Reading GitLab outputs..."
    cd "${GL_DIR}"

    GL_TOKEN="$("${TF_CMD}" output -raw backend_token 2>/dev/null || echo "")"

    if [[ -n "${GL_TOKEN}" ]]; then
        update_env_var "GITLAB_TOKEN" "${GL_TOKEN}"
    else
        log "  WARNING: Could not extract GITLAB_TOKEN from GitLab outputs."
    fi
else
    log "  GitLab state not found — skipping. Run 'cd infrastructure/gitlab && ${TF_CMD} apply' first."
fi

log "### .env update complete ###"
