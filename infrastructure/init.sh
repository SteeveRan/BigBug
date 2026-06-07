#!/usr/bin/env bash
#
# @file init.sh
# @description Full environment initialization for BigBug
#              Starts infrastructure, deploys Harbor in kind (if needed),
#              applies OpenTofu (Keycloak → Harbor → GitLab),
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

# Compose files
INFRA_COMPOSE="${SCRIPT_DIR}/docker-compose.yml"
APP_COMPOSE="${PROJECT_ROOT}/docker-compose.yml"

# Terraform root module
TF_DIR="${SCRIPT_DIR}/terraform"

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

    local running
    running="$(docker compose -f "${compose_file}" ps --status running --format '{{.Service}}' 2>/dev/null)"
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

    if compose_services_running "${compose_file}" "${min_services}"; then
        log "  ${label} containers already running — skipping docker compose up"
    else
        log "  Starting ${label} containers..."
        docker compose -f "${compose_file}" up -d
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
# 3. Start infrastructure services
# ─────────────────────────────────────────────────────────────
log "### Starting infrastructure services ###"
cd "${PROJECT_ROOT}"

# infrastructure/docker-compose.yml: postgres-keycloak, keycloak, gitlab, gitlab-runner
compose_up_if_needed "${INFRA_COMPOSE}" 4 "infrastructure"

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
# 6. Initialize infrastructure with OpenTofu (single apply)
#    Order: Keycloak → Harbor → GitLab (resolved by dependency graph)
# ─────────────────────────────────────────────────────────────
log "### Initializing infrastructure with OpenTofu ###"
cd "${TF_DIR}"

if [[ ! -f terraform.tfvars ]]; then
    log "  Creating terraform.tfvars from defaults..."

    # Generate a random backend user password if not set
    BACKEND_PASSWORD="$(openssl rand -base64 24 | tr -d '/+=' | head -c 20)"

    cat > terraform.tfvars <<TFVARS_EOF
# Auto-generated by init.sh — edit as needed
keycloak_url            = "http://localhost:8180"
keycloak_admin_username = "admin"
keycloak_admin_password = "admin"
realm_name              = "bigbug"

backend_client_id     = "bigbug-backend"
backend_client_secret = "bigbug-backend-secret"

frontend_client_id    = "bigbug-frontend"
frontend_redirect_uris = ["http://localhost:5173/*", "http://localhost:3000/*"]

harbor_client_id                = "harbor"
harbor_client_secret            = "harbor-oidc-secret"
harbor_redirect_uris            = ["https://harbor.local:30443/c/oidc/callback", "https://harbor.local:30443/*"]
harbor_post_logout_redirect_uris = ["https://harbor.local:30443/c/oidc/logout", "https://harbor.local:30443/"]
harbor_root_url                 = "https://harbor.local:30443"

test_user_username = "bigbug"
test_user_password = "bigbug"
test_user_email    = "bigbug@example.com"

harbor_url      = "https://harbor.local"
harbor_username = "admin"
harbor_password = "Harbor12345"

harbor_auth_mode          = "oidc_auth"
harbor_oidc_provider_name = "Keycloak"
harbor_oidc_endpoint      = "http://localhost:8180/realms/bigbug"
harbor_oidc_groups_claim  = "groups"
harbor_oidc_scope         = "openid,profile,email,groups"
harbor_oidc_verify_cert   = false
harbor_oidc_auto_onboard  = true
harbor_oidc_user_claim    = "preferred_username"

gold_images_project_name  = "gold-images"
gold_images_storage_quota = -1

app_images_project_name  = "app-images"
app_images_storage_quota = -1

mirrors_project_name  = "mirrors"
mirrors_storage_quota = -1

replication_schedule    = "0 0 2 * * *"
dockerhub_registry_name = "docker-hub"
dockerhub_endpoint_url  = "https://hub.docker.com"
quay_registry_name      = "quay-io"
quay_endpoint_url       = "https://quay.io"

webhook_backend_url = "http://localhost:8000/api/webhooks/harbor"

gitlab_url   = "http://localhost:8080"
gitlab_token = "CHANGE-ME-root-personal-access-token"

mirrors_group_name = "bigbug-mirrors"

backend_user_name     = "BigBug Backend"
backend_user_username = "bigbug-backend"
backend_user_email    = "bigbug-backend@localhost.localdomain"
backend_user_password = "${BACKEND_PASSWORD}"

backend_token_name       = "bigbug-backend-token"
backend_token_expires_at = "2027-12-31"
backend_token_scopes     = ["api", "read_repository", "write_repository"]
TFVARS_EOF
    log "  Created terraform.tfvars with default development values."
fi

# Check if gitlab_token is still a placeholder
if grep -qE 'gitlab_token\s*=\s*"CHANGE-ME' terraform.tfvars 2>/dev/null; then
    log_warn "  GitLab token is still a placeholder in terraform.tfvars."
    log_warn "  Attempting to extract GitLab initial root password..."

    ROOT_PASSWORD=""
    if ROOT_PASSWORD="$(docker compose -f "${INFRA_COMPOSE}" exec -T gitlab cat /etc/gitlab/initial_root_password 2>/dev/null | grep 'Password:' | awk '{print $2}')" && [[ -n "${ROOT_PASSWORD}" ]]; then
        log "  Initial root password: ${ROOT_PASSWORD}"
        log "  Please create a root PAT at http://localhost:8080/-/user_settings/personal_access_tokens"
        log "  (scope: api) and update gitlab_token in ${TF_DIR}/terraform.tfvars"
        echo ""
        echo "    gitlab_token = \"YOUR-ROOT-PAT\""
        echo ""
        log_error "Skipping GitLab module — terraform will apply only Keycloak + Harbor."
        log "  After setting gitlab_token, run:"
        log "    cd ${TF_DIR} && ${TF_CMD} init && ${TF_CMD} apply -auto-approve"
        log "    cd ${PROJECT_ROOT} && ./infrastructure/update-env.sh"

        # Apply only Keycloak + Harbor by targeting them
        "${TF_CMD}" init -input=false
        "${TF_CMD}" apply -auto-approve -input=false -target='module.keycloak' -target='module.harbor'
    else
        log_error "  Could not extract GitLab root password."
        log "  Copy terraform.tfvars.example to terraform.tfvars and set gitlab_token."
        log_error "Skipping all terraform — gitlab_token required."
        log "  To complete setup later:"
        log "    cd ${TF_DIR}"
        log "    # Edit terraform.tfvars -> set gitlab_token"
        log "    ${TF_CMD} init && ${TF_CMD} apply -auto-approve"
        log "    cd ${PROJECT_ROOT} && ./infrastructure/update-env.sh"
    fi
else
    # All tokens set — full apply
    "${TF_CMD}" init -input=false
    "${TF_CMD}" apply -auto-approve -input=false
    log "  OpenTofu applied successfully."
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

# root docker-compose.yml: postgres-backend, redis, backend, frontend
compose_up_if_needed "${APP_COMPOSE}" 2 "application"

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
if command -v kind &>/dev/null && kind get clusters 2>/dev/null | grep -q "^${HARBOR_CLUSTER}$"; then
log "    Harbor:    https://harbor.local:30443  (admin / Harbor12345)"
fi
log ""
log "  Login:  bigbug / bigbug"
log ""
