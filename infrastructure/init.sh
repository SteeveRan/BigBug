#!/usr/bin/env bash
#
# @file init.sh
# @description BigBug infrastructure initialization (ADR-0022/0029/0033).
#              Ensures TLS certs (ADR-0030), starts the GitLab compose zone,
#              bootstraps the kind cluster, applies OpenTofu
#              (base → apps → config/GitLab), updates application .env.
#
# Usage:
#   ./infrastructure/init.sh
#
# Prerequisites:
#   - Docker 24+
#   - kind, kubectl
#   - OpenTofu 1.6+ (or Terraform 1.5+)
#   - curl, jq, openssl
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# Compose files (GitLab compose zone — ADR-0033)
GITLAB_DIR="${SCRIPT_DIR}/gitlab"
INFRA_COMPOSE="${GITLAB_DIR}/docker-compose.yml"

# .env file (gitlab compose zone only — application .env is managed separately)
INFRA_ENV="${GITLAB_DIR}/.env"
INFRA_ENV_EXAMPLE="${GITLAB_DIR}/.env.example"

# Terraform roots (ADR-0029: base/infra-apps/apps; GitLab config in infra-apps)
TF_BASE_DIR="${SCRIPT_DIR}/terraform/base"
TF_INFRA_APPS_DIR="${SCRIPT_DIR}/terraform/infra-apps"
TF_APPS_DIR="${SCRIPT_DIR}/terraform/apps"
TFVARS="${TF_INFRA_APPS_DIR}/terraform.tfvars"
TFVARS_EXAMPLE="${TF_INFRA_APPS_DIR}/terraform.tfvars.example"

# kind (ADR-0022: единый кластер bigbug-dev; harbor-кластер снесён — #62)
KIND_DIR="${SCRIPT_DIR}/kind"
KIND_CLUSTER="bigbug-dev"

# ─────────────────────────────────────────────────────────────
# Logging
# ─────────────────────────────────────────────────────────────
log() {
    printf '[%s] %s\n' "$(date +'%Y-%m-%d %H:%M:%S')" "$*" >&2
}

log_error() {
    printf '[%s] ERROR: %s\n' "$(date +'%Y-%m-%d %H:%M:%S')" "$*" >&2
}

log_warn() {
    printf '[%s] WARN:  %s\n' "$(date +'%Y-%m-%d %H:%M:%S')" "$*" >&2
}

# ─────────────────────────────────────────────────────────────
# Helper: check if Docker containers for a compose file are running
# ─────────────────────────────────────────────────────────────
compose_services_running() {
    local compose_file="$1"
    local expected="$2"
    local extra_args="${3:-}"

    local running
    running="$(docker compose -f "${compose_file}" ${extra_args} ps --status running --format '{{.Service}}' 2>/dev/null)"
    local count
    count="$(echo "${running}" | grep -c . || true)"

    if (( count >= expected )); then
        return 0
    fi
    return 1
}

# ─────────────────────────────────────────────────────────────
# Helper: start compose services only if not already running
# ─────────────────────────────────────────────────────────────
compose_up_if_needed() {
    local compose_file="$1"
    local min_services="${2:-1}"
    local label="$3"
    local extra_args="${4:-}"

    if compose_services_running "${compose_file}" "${min_services}" "${extra_args}"; then
        log "  ${label} containers already running — skipping docker compose up"
    else
        log "  Starting ${label} containers..."
        docker compose -f "${compose_file}" ${extra_args} up -d
    fi
}

# ─────────────────────────────────────────────────────────────
# Helper: wait for a service to respond via HTTP
# ─────────────────────────────────────────────────────────────
wait_for_service() {
    local service="$1"
    local url="$2"
    local max_wait="${3:-120}"
    local curl_extra="${4:-}"

    log "Waiting for ${service} at ${url} (timeout=${max_wait}s)..."

    local elapsed=0
    while (( elapsed < max_wait )); do
        if curl -fsS ${curl_extra} -o /dev/null --connect-timeout 5 "${url}" 2>/dev/null; then
            log "  ${service} is ready (${elapsed}s)"
            return 0
        fi
        sleep 3
        elapsed=$((elapsed + 3))
    done

    log_error "${service} not ready after ${max_wait}s"
    return 1
}

# ─────────────────────────────────────────────────────────────
# 1. Check dependencies
# ─────────────────────────────────────────────────────────────
log "### Checking dependencies ###"

MISSING_DEPS=()

for cmd in docker curl jq openssl; do
    if ! command -v "${cmd}" &>/dev/null; then
        MISSING_DEPS+=("${cmd}")
    fi
done

# Check for tofu or terraform
if command -v tofu &>/dev/null; then
    TF_CMD="tofu"
    log "  Found: tofu ($(tofu version -json 2>/dev/null | jq -r '.terraform_version' 2>/dev/null || echo 'unknown'))"
elif command -v terraform &>/dev/null; then
    TF_CMD="terraform"
    TF_VERSION="$(terraform version -json 2>/dev/null | jq -r '.terraform_version' 2>/dev/null || echo 'unknown')"
    log "  Found: terraform ${TF_VERSION}"
    log "  NOTE: Using HashiCorp Terraform. OpenTofu is recommended but not required."
else
    MISSING_DEPS+=("tofu (or terraform)")
fi

if (( ${#MISSING_DEPS[@]} > 0 )); then
    log_error "Missing dependencies: ${MISSING_DEPS[*]}"
    log_error "Please install them and try again."
    echo ""
    echo "Installation guides:"
    echo "  OpenTofu: https://opentofu.org/docs/intro/install/"
    echo "  Terraform: https://www.terraform.io/downloads"
    echo "  Docker: https://docs.docker.com/engine/install/"
    echo "  jq: https://jqlang.github.io/jq/download/"
    exit 1
fi

# ─────────────────────────────────────────────────────────────
# 2. Create infrastructure/gitlab/.env from example if not exists
# ─────────────────────────────────────────────────────────────
log "### Checking gitlab compose environment ###"

if [[ ! -f "${INFRA_ENV}" ]]; then
    if [[ -f "${INFRA_ENV_EXAMPLE}" ]]; then
        log "  Creating infrastructure/gitlab/.env from .env.example..."
        cp "${INFRA_ENV_EXAMPLE}" "${INFRA_ENV}"
    else
        log_error "infrastructure/gitlab/.env.example not found."
        exit 1
    fi
else
    log "  infrastructure/gitlab/.env already exists."
fi

# Source infra .env to get GITLAB_TOKEN and GITLAB_ROOT_PASSWORD
# shellcheck disable=SC1090
source "${INFRA_ENV}"

# ─────────────────────────────────────────────────────────────
# 3. Ensure TLS certificates (ADR-0030) — GitLab omnibus mounts them
# ─────────────────────────────────────────────────────────────
log "### Ensuring TLS certificates ###"

bash "${KIND_DIR}/certs.sh"   # idempotent: existing certs are kept

# ─────────────────────────────────────────────────────────────
# 4. Start infrastructure services
# ─────────────────────────────────────────────────────────────
log "### Starting infrastructure services ###"
cd "${PROJECT_ROOT}"

# Compose = GitLab zone only (gitlab + gitlab-runner — ADR-0033)
compose_up_if_needed "${INFRA_COMPOSE}" 2 "gitlab compose zone" "--env-file ${INFRA_ENV}"

# ─────────────────────────────────────────────────────────────
# 5. Wait for service readiness
# ─────────────────────────────────────────────────────────────
log "### Waiting for service readiness ###"

# GitLab — https omnibus (ADR-0030 §9), self-signed: -k in scripts, host
# trust via trust-host.sh; takes a while to boot
wait_for_service "GitLab" "https://gitlab.local:8443/users/sign_in" 600 "-k"

log "  All infrastructure services are ready."

# ─────────────────────────────────────────────────────────────
# 6. kind cluster bigbug-dev (bootstrap) — ADR-0022/0030
# ─────────────────────────────────────────────────────────────
log "### Checking kind cluster '${KIND_CLUSTER}' ###"

if command -v kind &>/dev/null; then
    if kind get clusters 2>/dev/null | grep -q "^${KIND_CLUSTER}$"; then
        log "  Cluster '${KIND_CLUSTER}' already exists — skipping bootstrap."
    else
        log "  Cluster not found. Running bootstrap.sh (certs already ensured in step 3)..."
        if [[ -f "${KIND_DIR}/bootstrap.sh" ]]; then
            (cd "${KIND_DIR}" && bash bootstrap.sh)
            log "  Cluster ready."
        else
            log_error "  bootstrap.sh not found at ${KIND_DIR}/bootstrap.sh"
            exit 1
        fi
    fi
else
    log_error "  kind is not installed — cannot set up the cluster."
    log_error "  Install kind: https://kind.sigs.k8s.io/docs/user/quick-start/"
    exit 1
fi

# ─────────────────────────────────────────────────────────────
# 7. Copy terraform.tfvars from example if not exists
# ─────────────────────────────────────────────────────────────
log "### Preparing OpenTofu variables ###"

if [[ ! -f "${TFVARS}" ]]; then
    if [[ -f "${TFVARS_EXAMPLE}" ]]; then
        log "  Creating terraform.tfvars from terraform.tfvars.example..."
        cp "${TFVARS_EXAMPLE}" "${TFVARS}"
    else
        log_error "terraform.tfvars.example not found at ${TFVARS_EXAMPLE}"
        exit 1
    fi
else
    log "  terraform.tfvars already exists."
fi

# ─────────────────────────────────────────────────────────────
# 8. Verify / program GitLab PAT from infrastructure/gitlab/.env
#    (documented imperative exception from IaC — ADR-0033)
# ─────────────────────────────────────────────────────────────
log "### Checking GitLab PAT ###"

# GITLAB_TOKEN comes from infrastructure/gitlab/.env (sourced in step 2)
GITLAB_PAT="${GITLAB_TOKEN:-}"

if [[ -z "${GITLAB_PAT}" ]]; then
    log_error "GITLAB_TOKEN is empty or not set in infrastructure/gitlab/.env."
    log_error "Add GITLAB_TOKEN=<your-pat> to infrastructure/gitlab/.env and re-run."
    exit 1
fi

log "  Token: ${GITLAB_PAT:0:8}..."

# Check if the token is already valid (non-403 means works)
log "  Checking if token is already valid..."
GITLAB_CACERT="$HOME/.local/state/bigbug/certs/gitlab.local/tls.crt"
set +e
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" \
    --cacert "${GITLAB_CACERT}" \
    --header "PRIVATE-TOKEN: ${GITLAB_PAT}" \
    "https://gitlab.local:8443/api/v4/user" 2>/dev/null)
set -e

if [[ "${HTTP_CODE}" != "403" ]]; then
    log "  Token is already valid (HTTP ${HTTP_CODE}) — skipping programming."
else
    log "  Token returned 403 — programming into GitLab..."

    # Program the token into GitLab root user (expires 90 days from now)
    set +e
    docker compose -f "${INFRA_COMPOSE}" --env-file "${INFRA_ENV}" exec -T gitlab \
        gitlab-rails runner "u=User.find_by_username('root'); t=u.personal_access_tokens.create!(name:'bigbug-backend-token',scopes:['api','read_repository','write_repository'],expires_at:90.days.from_now); t.set_token('${GITLAB_PAT}'); t.save!" 2>/dev/null
    PAT_RC=$?
    set -e

    if [[ ${PAT_RC} -ne 0 ]]; then
        log_error "Failed to program GitLab PAT."
        log_error "Check GitLab logs: docker compose -f ${INFRA_COMPOSE} --env-file ${INFRA_ENV} logs gitlab"
        exit 1
    fi

    log "  PAT programmed successfully."
fi

# Write token to terraform.tfvars so tofu can use it (expires_at is computed by terraform)
sed -i "s|gitlab_token\s*=\s*\"[^\"]*\"|gitlab_token = \"${GITLAB_PAT}\"|" "${TFVARS}"
log "  gitlab_token written to terraform.tfvars."

# ─────────────────────────────────────────────────────────────
# 9. Run OpenTofu — base → apps → config (ADR-0029/0033; общий state
#    backend ~/.local/state/bigbug для base/infra-apps/apps). keycloak-провайдер
#    логинится при plan, поэтому infra-apps идёт в 2 фазы: инсталляции, затем конфиг.
#    Приложение (ns bigbug) — отдельный apps root, после infra-apps.
# ─────────────────────────────────────────────────────────────
log "### Running OpenTofu ###"

log "  Applying base layer (platform: ingress, operators)..."
(cd "${TF_BASE_DIR}" && "${TF_CMD}" init -input=false && "${TF_CMD}" apply -auto-approve -input=false) || {
    log_error "base layer apply failed."
    exit 1
}

log "  Applying apps layer — phase 1: installations (keycloak_init, harbor_init)..."
(cd "${TF_INFRA_APPS_DIR}" && "${TF_CMD}" init -input=false \
    && "${TF_CMD}" apply -auto-approve -input=false \
        -target=module.keycloak_init -target=module.harbor_init) || {
    log_error "apps layer (installations) failed."
    exit 1
}

log "  Waiting for Keycloak to answer (https)..."
wait_for_service "Keycloak" "https://keycloak.local/realms/master" 180

log "  Applying apps layer — full (realm, clients, harbor config)..."
(cd "${TF_INFRA_APPS_DIR}" && "${TF_CMD}" apply -auto-approve -input=false) || {
    log_error "apps layer (full) failed."
    exit 1
}

log "  Applying app-infra root (ns bigbug: CNPG, Redis, app secrets)..."
(cd "${TF_APPS_DIR}" && "${TF_CMD}" init -input=false \
    && "${TF_CMD}" apply -auto-approve -input=false) || {
    log_error "app-infra root apply failed."
    exit 1
}

log "  OpenTofu applied successfully."

# ─────────────────────────────────────────────────────────────
# 10. Update host-tool .env vars (e2e base URL, GitLab PAT)
# ─────────────────────────────────────────────────────────────
"${SCRIPT_DIR}/update-env.sh"

# ─────────────────────────────────────────────────────────────
# Done
# ─────────────────────────────────────────────────────────────

GITLAB_TOKEN_DISPLAY="$(grep -oP 'gitlab_token\s*=\s*"\K[^"]+' "${TFVARS}" 2>/dev/null || echo "UNKNOWN")"
GITLAB_ROOT_PW_DISPLAY="${GITLAB_ROOT_PASSWORD:-UNKNOWN}"

log ""
log "==========================================="
log "  ✅ Infrastructure initialization complete!"
log "==========================================="
log ""
log "  Infrastructure services:"
log "    Keycloak:  https://keycloak.local  (admin / admin)"
log "    GitLab:    https://gitlab.local:8443  (root / ${GITLAB_ROOT_PW_DISPLAY})"
log "    Harbor:    https://harbor.local  (admin / Harbor12345)"
log ""
log "  GitLab PAT: ${GITLAB_TOKEN_DISPLAY}"
log ""
log "  Next: make dev-build && make dev-up"
log ""
