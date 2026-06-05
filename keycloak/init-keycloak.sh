#!/usr/bin/env bash
#
# @file init-keycloak.sh
# @description Idempotent bootstrapper for the BigBug realm in Keycloak.
#              Creates (or leaves intact) the realm, the backend confidential
#              client, the frontend public client (PKCE), the realm roles
#              consumed by app/core/rbac.py (admin/operator/viewer) and a
#              default test user mapped to the requested role.
# @dependencies kcadm.sh (ships with the keycloak image), curl, bash 4+
#
# Designed to be re-runnable: every create_* helper checks for an existing
# entity by ID/name and exits 0 if it already exists, so re-running the
# script after, e.g., adding new roles never wipes existing state.
#
# Required environment:
#   KEYCLOAK_URL                 (default http://keycloak:8180)
#   KEYCLOAK_ADMIN               (default admin)
#   KEYCLOAK_ADMIN_PASSWORD      (default admin)
#   KEYCLOAK_REALM               (default bigbug)
#   KEYCLOAK_CLIENT_ID           (default bigbug-backend)
#   KEYCLOAK_CLIENT_SECRET       (required, secret used by backend OIDC)
#   KEYCLOAK_FRONTEND_CLIENT_ID  (default bigbug-frontend)
#   KEYCLOAK_FRONTEND_REDIRECT_URIS  comma-separated list (default http://localhost:5173/*)
#   KEYCLOAK_FRONTEND_WEB_ORIGINS    comma-separated list (default +)
#   KC_TEST_USER / KC_TEST_PASSWORD / KC_TEST_EMAIL / KC_TEST_ROLE
#

set -euo pipefail

# ─────────────────────────────────────────────────────────────
# Logging & defaults
# ─────────────────────────────────────────────────────────────
log() {
    local level="${1:-INFO}"
    shift || true
    printf '%s [%s] [keycloak-init] %s\n' \
        "$(date -u +'%Y-%m-%dT%H:%M:%SZ')" "${level}" "$*" >&2
}

: "${KEYCLOAK_URL:=http://keycloak:8180}"
: "${KEYCLOAK_ADMIN:=admin}"
: "${KEYCLOAK_ADMIN_PASSWORD:=admin}"
: "${KEYCLOAK_REALM:=bigbug}"
: "${KEYCLOAK_CLIENT_ID:=bigbug-backend}"
: "${KEYCLOAK_CLIENT_SECRET:=bigbug-backend-secret}"
: "${KEYCLOAK_FRONTEND_CLIENT_ID:=bigbug-frontend}"
: "${KEYCLOAK_FRONTEND_REDIRECT_URIS:=http://localhost:5173/*}"
: "${KEYCLOAK_FRONTEND_WEB_ORIGINS:=+}"
: "${KC_TEST_USER:=bigbug}"
: "${KC_TEST_PASSWORD:=bigbug}"
: "${KC_TEST_EMAIL:=bigbug@example.com}"
: "${KC_TEST_ROLE:=admin}"
: "${KC_WAIT_TIMEOUT:=120}"

# WHY: All realm roles consumed by backend/app/core/rbac.py (RoleName enum).
# Keep this list in sync with the Python enum or RBAC checks will silently
# deny access.
REALM_ROLES=(admin operator viewer)

KCADM="/opt/keycloak/bin/kcadm.sh"

# ─────────────────────────────────────────────────────────────
# Wait for Keycloak readiness
# ─────────────────────────────────────────────────────────────
wait_for_keycloak() {
    log INFO "Waiting for Keycloak at ${KEYCLOAK_URL} (timeout=${KC_WAIT_TIMEOUT}s)"
    local elapsed=0
    local interval=3
    while (( elapsed < KC_WAIT_TIMEOUT )); do
        if curl -fsS -o /dev/null "${KEYCLOAK_URL}/realms/master"; then
            log INFO "Keycloak is reachable after ${elapsed}s"
            return 0
        fi
        sleep "${interval}"
        elapsed=$(( elapsed + interval ))
    done
    log ERROR "Keycloak not reachable within ${KC_WAIT_TIMEOUT}s"
    return 1
}

# ─────────────────────────────────────────────────────────────
# kcadm helpers
# ─────────────────────────────────────────────────────────────
kc_login() {
    log INFO "Authenticating against master realm as ${KEYCLOAK_ADMIN}"
    "${KCADM}" config credentials \
        --server "${KEYCLOAK_URL}" \
        --realm master \
        --user "${KEYCLOAK_ADMIN}" \
        --password "${KEYCLOAK_ADMIN_PASSWORD}" >/dev/null
}

# Return non-empty (and exit 0) if a realm with the given name exists.
realm_exists() {
    local realm="$1"
    "${KCADM}" get "realms/${realm}" --fields id 2>/dev/null | grep -q '"id"'
}

# Resolve the UUID of a client inside a realm by its clientId, empty if absent.
client_uuid() {
    local realm="$1" client_id="$2"
    "${KCADM}" get clients -r "${realm}" -q "clientId=${client_id}" --fields id 2>/dev/null \
        | grep -oE '"id" *: *"[^"]+"' | head -n1 | cut -d'"' -f4
}

# Resolve the UUID of a user inside a realm by username, empty if absent.
user_uuid() {
    local realm="$1" username="$2"
    "${KCADM}" get users -r "${realm}" -q "username=${username}" --fields id 2>/dev/null \
        | grep -oE '"id" *: *"[^"]+"' | head -n1 | cut -d'"' -f4
}

role_exists() {
    local realm="$1" role="$2"
    "${KCADM}" get "roles/${role}" -r "${realm}" --fields name 2>/dev/null | grep -q '"name"'
}

# ─────────────────────────────────────────────────────────────
# Provisioning steps
# ─────────────────────────────────────────────────────────────
create_realm() {
    if realm_exists "${KEYCLOAK_REALM}"; then
        log INFO "Realm '${KEYCLOAK_REALM}' already exists, leaving as is"
        return 0
    fi
    log INFO "Creating realm '${KEYCLOAK_REALM}'"
    "${KCADM}" create realms \
        -s "realm=${KEYCLOAK_REALM}" \
        -s enabled=true \
        -s "displayName=BigBug" \
        -s sslRequired=external >/dev/null
}

create_realm_roles() {
    for role in "${REALM_ROLES[@]}"; do
        if role_exists "${KEYCLOAK_REALM}" "${role}"; then
            log INFO "Realm role '${role}' already exists"
            continue
        fi
        log INFO "Creating realm role '${role}'"
        "${KCADM}" create "roles" -r "${KEYCLOAK_REALM}" \
            -s "name=${role}" \
            -s "description=BigBug RBAC role: ${role}" >/dev/null
    done
}

create_backend_client() {
    local uuid
    uuid="$(client_uuid "${KEYCLOAK_REALM}" "${KEYCLOAK_CLIENT_ID}")"
    if [[ -n "${uuid}" ]]; then
        log INFO "Backend client '${KEYCLOAK_CLIENT_ID}' already exists (${uuid}), refreshing secret"
        # WHY: Rotating the secret on every run would invalidate active backend
        # sessions; we only enforce it matches the expected value.
        "${KCADM}" update "clients/${uuid}" -r "${KEYCLOAK_REALM}" \
            -s "secret=${KEYCLOAK_CLIENT_SECRET}" >/dev/null
        return 0
    fi

    log INFO "Creating confidential client '${KEYCLOAK_CLIENT_ID}'"
    "${KCADM}" create clients -r "${KEYCLOAK_REALM}" \
        -s "clientId=${KEYCLOAK_CLIENT_ID}" \
        -s enabled=true \
        -s publicClient=false \
        -s "secret=${KEYCLOAK_CLIENT_SECRET}" \
        -s standardFlowEnabled=true \
        -s directAccessGrantsEnabled=true \
        -s serviceAccountsEnabled=true \
        -s 'redirectUris=["*"]' \
        -s 'webOrigins=["*"]' \
        -s 'attributes={"access.token.lifespan":"900"}' >/dev/null
}

# WHY: Frontend uses Authorization Code + PKCE (S256). Public clients must not
# carry a secret and require explicit pkce.code.challenge.method to refuse
# non-PKCE flows.
create_frontend_client() {
    local uuid
    uuid="$(client_uuid "${KEYCLOAK_REALM}" "${KEYCLOAK_FRONTEND_CLIENT_ID}")"

    # Convert comma-separated env vars to JSON arrays expected by kcadm.
    local redirect_json origin_json
    redirect_json="$(python3 -c 'import json,os,sys; print(json.dumps([s.strip() for s in os.environ["KEYCLOAK_FRONTEND_REDIRECT_URIS"].split(",") if s.strip()]))')"
    origin_json="$(python3 -c 'import json,os,sys; print(json.dumps([s.strip() for s in os.environ["KEYCLOAK_FRONTEND_WEB_ORIGINS"].split(",") if s.strip()]))')"

    if [[ -n "${uuid}" ]]; then
        log INFO "Frontend client '${KEYCLOAK_FRONTEND_CLIENT_ID}' already exists (${uuid}), updating redirect/web-origins"
        "${KCADM}" update "clients/${uuid}" -r "${KEYCLOAK_REALM}" \
            -s "redirectUris=${redirect_json}" \
            -s "webOrigins=${origin_json}" \
            -s 'attributes={"pkce.code.challenge.method":"S256"}' >/dev/null
        return 0
    fi

    log INFO "Creating public client '${KEYCLOAK_FRONTEND_CLIENT_ID}' with PKCE enforced"
    "${KCADM}" create clients -r "${KEYCLOAK_REALM}" \
        -s "clientId=${KEYCLOAK_FRONTEND_CLIENT_ID}" \
        -s enabled=true \
        -s publicClient=true \
        -s standardFlowEnabled=true \
        -s directAccessGrantsEnabled=false \
        -s implicitFlowEnabled=false \
        -s "redirectUris=${redirect_json}" \
        -s "webOrigins=${origin_json}" \
        -s 'attributes={"pkce.code.challenge.method":"S256"}' >/dev/null
}

create_test_user() {
    local uuid
    uuid="$(user_uuid "${KEYCLOAK_REALM}" "${KC_TEST_USER}")"

    if [[ -z "${uuid}" ]]; then
        log INFO "Creating test user '${KC_TEST_USER}'"
        "${KCADM}" create users -r "${KEYCLOAK_REALM}" \
            -s "username=${KC_TEST_USER}" \
            -s "email=${KC_TEST_EMAIL}" \
            -s emailVerified=true \
            -s enabled=true >/dev/null
        uuid="$(user_uuid "${KEYCLOAK_REALM}" "${KC_TEST_USER}")"
    else
        log INFO "Test user '${KC_TEST_USER}' already exists (${uuid})"
    fi

    log INFO "Resetting password for '${KC_TEST_USER}' (non-temporary)"
    "${KCADM}" set-password -r "${KEYCLOAK_REALM}" \
        --username "${KC_TEST_USER}" \
        --new-password "${KC_TEST_PASSWORD}" >/dev/null || true

    # WHY: We add the role unconditionally — kcadm is a no-op if the mapping
    # already exists. This is cheaper than fetching current mappings.
    log INFO "Granting role '${KC_TEST_ROLE}' to '${KC_TEST_USER}'"
    "${KCADM}" add-roles -r "${KEYCLOAK_REALM}" \
        --uusername "${KC_TEST_USER}" \
        --rolename "${KC_TEST_ROLE}" >/dev/null
}

main() {
    log INFO "Bootstrapping realm '${KEYCLOAK_REALM}' on ${KEYCLOAK_URL}"
    wait_for_keycloak
    kc_login
    create_realm
    create_realm_roles
    create_backend_client
    create_frontend_client
    create_test_user
    log INFO "Realm '${KEYCLOAK_REALM}' bootstrap complete"
}

main "$@"
