#!/usr/bin/env bash
#
# @file init.sh
# @description Full environment initialization for BigBug
#              Starts infrastructure, applies OpenTofu configurations,
#              updates .env, and starts application services.
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

# ─────────────────────────────────────────────────────────────
# Logging
# ─────────────────────────────────────────────────────────────
log() {
    printf '[%s] %s\n' "$(date +'%Y-%m-%d %H:%M:%S')" "$*" >&2
}

log_error() {
    printf '[%s] ERROR: %s\n' "$(date +'%Y-%m-%d %H:%M:%S')" "$*" >&2
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
    # Warn if using Terraform instead of OpenTofu (still works, just FYI)
    if [[ "${TF_VERSION}" != "unknown" ]]; then
        log "  NOTE: Using HashiCorp Terraform. OpenTofu is recommended but not required."
    fi
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
# 2. Check .env
# ─────────────────────────────────────────────────────────────
log "### Checking .env ###"

if [[ ! -f "${PROJECT_ROOT}/.env" ]]; then
    if [[ -f "${PROJECT_ROOT}/.env.example" ]]; then
        log "  .env not found, copying from .env.example..."
        cp "${PROJECT_ROOT}/.env.example" "${PROJECT_ROOT}/.env"
        log "  Created .env from .env.example. Please review and customize if needed."
    else
        log_error ".env not found and .env.example not available. Please create .env manually."
        exit 1
    fi
fi

# ─────────────────────────────────────────────────────────────
# 3. Start infrastructure
# ─────────────────────────────────────────────────────────────
log "### Starting infrastructure services ###"
cd "${PROJECT_ROOT}"
docker compose -f docker-compose.infra.yml up -d

# ─────────────────────────────────────────────────────────────
# 4. Wait for service readiness
# ─────────────────────────────────────────────────────────────
log "### Waiting for service readiness ###"

# Keycloak — check health endpoint
wait_for_service "Keycloak" "http://localhost:8180/realms/master" 180

# GitLab — takes a while to boot
wait_for_service "GitLab" "http://localhost:8080/-/health" 600

log "  All infrastructure services are ready."

# ─────────────────────────────────────────────────────────────
# 5. Initialize Keycloak with OpenTofu
# ─────────────────────────────────────────────────────────────
log "### Initializing Keycloak ###"
cd "${SCRIPT_DIR}/keycloak"

if [[ ! -f terraform.tfvars ]]; then
    log "  Creating terraform.tfvars from defaults..."
    cat > terraform.tfvars <<'TFVARS'
keycloak_url             = "http://localhost:8180"
keycloak_admin_username  = "admin"
keycloak_admin_password  = "admin"
realm_name               = "bigbug"
backend_client_id        = "bigbug-backend"
backend_client_secret    = "bigbug-backend-secret"
frontend_client_id       = "bigbug-frontend"
test_user_username       = "bigbug"
test_user_password       = "bigbug"
test_user_email          = "bigbug@example.com"
TFVARS
    log "  Created terraform.tfvars with default development values."
fi

"${TF_CMD}" init -input=false
"${TF_CMD}" apply -auto-approve -input=false

# ─────────────────────────────────────────────────────────────
# 6. Initialize GitLab with OpenTofu
# ─────────────────────────────────────────────────────────────
log "### Initializing GitLab ###"
cd "${SCRIPT_DIR}/gitlab"

if [[ ! -f terraform.tfvars ]]; then
    log "  WARNING: gitlab/terraform.tfvars not found."
    log "  You need a GitLab root PAT to continue."

    # Try to extract the initial root password
    ROOT_PASSWORD=""
    if docker compose -f "${PROJECT_ROOT}/docker-compose.infra.yml" exec -T gitlab cat /etc/gitlab/initial_root_password 2>/dev/null; then
        ROOT_PASSWORD="$(docker compose -f "${PROJECT_ROOT}/docker-compose.infra.yml" exec -T gitlab cat /etc/gitlab/initial_root_password 2>/dev/null | grep 'Password:' | awk '{print $2}')"
    fi

    if [[ -n "${ROOT_PASSWORD}" ]]; then
        log "  Initial root password: ${ROOT_PASSWORD}"
        log "  Please create a root PAT at http://localhost:8080/-/user_settings/personal_access_tokens"
        log "  (scope: api) and add it to infrastructure/gitlab/terraform.tfvars:"
        echo ""
        echo "    gitlab_url   = \"http://localhost:8080\""
        echo "    gitlab_token = \"YOUR-ROOT-PAT\""
        echo ""
    else
        log "  Copy terraform.tfvars.example to terraform.tfvars and set gitlab_token."
        log "  Initial root password can be found in the GitLab container logs:"
        log "    docker compose -f docker-compose.infra.yml exec gitlab cat /etc/gitlab/initial_root_password"
    fi

    log_error "GitLab initialization skipped — terraform.tfvars required."
    log "  To complete GitLab setup later, run:"
    log "    cd infrastructure/gitlab && ${TF_CMD} init && ${TF_CMD} apply -auto-approve"
    log "    cd ../.. && ./infrastructure/update-env.sh"
elif ! grep -qE 'gitlab_token\s*=\s*"CHANGE-ME' terraform.tfvars 2>/dev/null; then
    "${TF_CMD}" init -input=false
    "${TF_CMD}" apply -auto-approve -input=false
else
    log_error "gitlab/terraform.tfvars still has placeholder token."
    log "  Update gitlab_token in infrastructure/gitlab/terraform.tfvars with a real root PAT."
    log "  Then run: cd infrastructure/gitlab && ${TF_CMD} apply -auto-approve"
fi

# ─────────────────────────────────────────────────────────────
# 7. Update .env with OpenTofu outputs
# ─────────────────────────────────────────────────────────────
log "### Updating .env ###"
"${SCRIPT_DIR}/update-env.sh"

# ─────────────────────────────────────────────────────────────
# 8. Start application services
# ─────────────────────────────────────────────────────────────
log "### Starting application services ###"
cd "${PROJECT_ROOT}"
docker compose -f docker-compose.app.yml up -d

# ─────────────────────────────────────────────────────────────
# Done
# ─────────────────────────────────────────────────────────────
log ""
log "==========================================="
log "  ✅ BigBug initialization complete!"
log "==========================================="
log ""
log "  Services:"
log "    Frontend:  http://localhost:5173"
log "    Backend:   http://localhost:8000"
log "    Keycloak:  http://localhost:8180  (admin / admin)"
log "    GitLab:    http://localhost:8080  (root / see container logs)"
log ""
log "  Login:  bigbug / bigbug"
log ""
