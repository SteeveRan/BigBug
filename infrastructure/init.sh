#!/usr/bin/env bash
#
# @file init.sh
# @description BigBug infrastructure initialization
#              Starts infrastructure services, optionally deploys Harbor,
#              applies OpenTofu (Keycloak → Harbor → GitLab),
#              and updates application .env with OpenTofu outputs.
#
# Usage:
#   ./infrastructure/init.sh
#
# Prerequisites:
#   - Docker 24+
#   - OpenTofu 1.6+ (or Terraform 1.5+)
#   - curl, jq
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# Compose files
INFRA_COMPOSE="${SCRIPT_DIR}/docker-compose.yml"

# .env file (infrastructure only — application .env is managed separately)
INFRA_ENV="${SCRIPT_DIR}/.env"
INFRA_ENV_EXAMPLE="${SCRIPT_DIR}/.env.example"

# Terraform
TF_DIR="${SCRIPT_DIR}/terraform"
TFVARS="${TF_DIR}/terraform.tfvars"
TFVARS_EXAMPLE="${TF_DIR}/terraform.tfvars.example"

# Harbor
HARBOR_DIR="${SCRIPT_DIR}/harbor"
HARBOR_CLUSTER="harbor"

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

    log "Waiting for ${service} at ${url} (timeout=${max_wait}s)..."

    local elapsed=0
    while (( elapsed < max_wait )); do
        if curl -fsS -o /dev/null --connect-timeout 5 "${url}" 2>/dev/null; then
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

for cmd in docker curl jq; do
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
# 2. Create infrastructure/.env from example if not exists
# ─────────────────────────────────────────────────────────────
log "### Checking infrastructure environment ###"

if [[ ! -f "${INFRA_ENV}" ]]; then
    if [[ -f "${INFRA_ENV_EXAMPLE}" ]]; then
        log "  Creating infrastructure/.env from infrastructure/.env.example..."
        cp "${INFRA_ENV_EXAMPLE}" "${INFRA_ENV}"
    else
        log_error "infrastructure/.env.example not found."
        exit 1
    fi
else
    log "  infrastructure/.env already exists."
fi

# Source infra .env to get GITLAB_TOKEN and GITLAB_ROOT_PASSWORD
# shellcheck disable=SC1090
source "${INFRA_ENV}"

# ─────────────────────────────────────────────────────────────
# 3. Start infrastructure services
# ─────────────────────────────────────────────────────────────
log "### Starting infrastructure services ###"
cd "${PROJECT_ROOT}"

compose_up_if_needed "${INFRA_COMPOSE}" 4 "infrastructure" "--env-file ${INFRA_ENV}"

# ─────────────────────────────────────────────────────────────
# 4. Wait for service readiness
# ─────────────────────────────────────────────────────────────
log "### Waiting for service readiness ###"

# Keycloak
wait_for_service "Keycloak" "http://localhost:8180/realms/master" 180

# GitLab — takes a while to boot
wait_for_service "GitLab" "http://localhost:8080/users/sign_in" 600

log "  All infrastructure services are ready."

# ─────────────────────────────────────────────────────────────
# 5. Deploy Harbor in kind (only if cluster doesn't exist)
# ─────────────────────────────────────────────────────────────
log "### Checking Harbor (kind) ###"

if command -v kind &>/dev/null; then
    if kind get clusters 2>/dev/null | grep -q "^${HARBOR_CLUSTER}$"; then
        log "  Harbor kind cluster '${HARBOR_CLUSTER}' already exists — skipping deploy."
    else
        log "  Harbor kind cluster not found. Running deploy.sh..."
        if [[ -f "${HARBOR_DIR}/deploy.sh" ]]; then
            (cd "${HARBOR_DIR}" && bash deploy.sh)
            log "  Harbor deployed in kind."
        else
            log_warn "  Harbor deploy.sh not found at ${HARBOR_DIR}/deploy.sh — skipping Harbor setup."
        fi
    fi
else
    log_warn "  kind is not installed — skipping Harbor deployment."
    log_warn "  Install kind: https://kind.sigs.k8s.io/docs/user/quick-start/"
fi

# ─────────────────────────────────────────────────────────────
# 6. Copy terraform.tfvars from example if not exists
# ─────────────────────────────────────────────────────────────
log "### Preparing OpenTofu variables ###"
cd "${TF_DIR}"

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
# 7. Verify / program GitLab PAT from infrastructure/.env
# ─────────────────────────────────────────────────────────────
log "### Checking GitLab PAT ###"

# GITLAB_TOKEN comes from infrastructure/.env (sourced in step 2)
GITLAB_PAT="${GITLAB_TOKEN:-}"

if [[ -z "${GITLAB_PAT}" ]]; then
    log_error "GITLAB_TOKEN is empty or not set in infrastructure/.env."
    log_error "Add GITLAB_TOKEN=<your-pat> to infrastructure/.env and re-run."
    exit 1
fi

log "  Token: ${GITLAB_PAT:0:8}..."

# Check if the token is already valid (non-403 means works)
log "  Checking if token is already valid..."
set +e
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" \
    --header "PRIVATE-TOKEN: ${GITLAB_PAT}" \
    "http://localhost:8080/api/v4/user" 2>/dev/null)
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
# 8. Run OpenTofu
# ─────────────────────────────────────────────────────────────
log "### Running OpenTofu ###"

log "  Initializing..."
if ! "${TF_CMD}" init -input=false; then
    log_error "OpenTofu init failed."
    exit 1
fi

log "  Applying..."
if ! "${TF_CMD}" apply -auto-approve -input=false; then
    log_error "OpenTofu apply failed. Check output above."
    exit 1
fi

log "  OpenTofu applied successfully."

# ─────────────────────────────────────────────────────────────
# 9. Update application .env with OpenTofu outputs
# ─────────────────────────────────────────────────────────────
log "### Updating .env from OpenTofu outputs ###"
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
log "    Keycloak:  http://localhost:8180  (admin / admin)"
log "    GitLab:    http://localhost:8080  (root / ${GITLAB_ROOT_PW_DISPLAY})"
if command -v kind &>/dev/null && kind get clusters 2>/dev/null | grep -q "^${HARBOR_CLUSTER}$"; then
log "    Harbor:    https://harbor.local:30443  (admin / Harbor12345)"
fi
log ""
log "  GitLab PAT: ${GITLAB_TOKEN_DISPLAY}"
log ""
log "  Next: start the application with: docker compose up -d"
log ""
