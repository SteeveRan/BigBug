#!/usr/bin/env bash
#
# provision-gitlab.sh — Provision the BigBug GitLab CI/CD components project.
#
# Creates (idempotently) in GitLab:
#   * project  bigbug-mirrors/components  (private, default branch main)
#   * file     .gitlab-ci.yml              (consumer config, include local component)
#   * file     templates/docker-hub-to-harbor.yml  (CI/CD component source)
#   * git tag  v1.0.0                      (so `@1.0.0` resolves)
#   * instance docker runner `bigbug-docker-runner`
#
# Everything is done via GitLab REST API + `gitlab-runner register` inside the
# runner container — no git CLI and no OpenTofu required. Values come from
# infrastructure/.env (see infrastructure/.env.example).
#
# Usage:
#   ./provision-gitlab.sh              # provision + verify
#   ./provision-gitlab.sh --verify-only  # only run the verify checks
#
set -euo pipefail

readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly ENV_FILE="${SCRIPT_DIR}/.env"
readonly TEMPLATE_DIR="${SCRIPT_DIR}/gitlab-components"
readonly TEMPLATE_SRC="${TEMPLATE_DIR}/docker-hub-to-harbor-template.yml"

# ── Colour helpers (mirror infrastructure/harbor/deploy.sh style) ──────────
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'
# Logging goes to stderr so functions that return a value on stdout
# (ensure_group/ensure_project) don't pollute their captured output.
info()  { echo -e "${GREEN}[INFO]${NC}  $*" >&2; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $*" >&2; }
error() { echo -e "${RED}[ERROR]${NC} $*" >&2; }

# ── Env (sourced from infrastructure/.env with defaults) ───────────────────
if [[ -f "${ENV_FILE}" ]]; then
  # shellcheck disable=SC1090
  source "${ENV_FILE}"
fi

GITLAB_URL="${GITLAB_URL:-http://localhost:8080}"
GITLAB_TOKEN="${GITLAB_TOKEN:-}"
GITLAB_COMPONENTS_GROUP="${GITLAB_COMPONENTS_GROUP:-bigbug-mirrors}"
GITLAB_COMPONENTS_PROJECT="${GITLAB_COMPONENTS_PROJECT:-components}"
GITLAB_COMPONENTS_DEFAULT_BRANCH="${GITLAB_COMPONENTS_DEFAULT_BRANCH:-main}"
GITLAB_COMPONENTS_TAG="${GITLAB_COMPONENTS_TAG:-v1.0.0}"
GITLAB_RUNNER_CONTAINER="${GITLAB_RUNNER_CONTAINER:-bigbug-gitlab-runner}"
GITLAB_RUNNER_DESCRIPTION="${GITLAB_RUNNER_DESCRIPTION:-bigbug-docker-runner}"
GITLAB_RUNNER_TAG_LIST="${GITLAB_RUNNER_TAG_LIST:-bigbug,docker}"
GITLAB_RUNNER_AUTH_TOKEN="${GITLAB_RUNNER_AUTH_TOKEN:-}"
GITLAB_RUNNER_DOCKER_IMAGE="${GITLAB_RUNNER_DOCKER_IMAGE:-gcr.io/go-containerregistry/crane:debug}"
GITLAB_HARBOR_HOST="${GITLAB_HARBOR_HOST:-harbor.local}"

COMPONENTS_PATH="${GITLAB_COMPONENTS_GROUP}/${GITLAB_COMPONENTS_PROJECT}"

# ── Low-level helpers ───────────────────────────────────────────────────────
gitlab_api() {
  # gitlab_api <method> <api_path_without_prefix> <json_body_or_empty>
  local method="$1" path="$2" body="${3:-}"
  if [[ -n "${body}" ]]; then
    curl -sf -X "${method}" \
      -H "PRIVATE-TOKEN: ${GITLAB_TOKEN}" \
      -H "Content-Type: application/json" \
      -d "${body}" \
      "${GITLAB_URL}/api/v4${path}"
  else
    curl -sf -X "${method}" \
      -H "PRIVATE-TOKEN: ${GITLAB_TOKEN}" \
      "${GITLAB_URL}/api/v4${path}"
  fi
}

http_code() {
  # http_code <method> <full_api_path> <json_body_or_empty>
  local method="$1" path="$2" body="${3:-}"
  if [[ -n "${body}" ]]; then
    curl -s -o /dev/null -w '%{http_code}' -X "${method}" \
      -H "PRIVATE-TOKEN: ${GITLAB_TOKEN}" \
      -H "Content-Type: application/json" \
      -d "${body}" \
      "${GITLAB_URL}/api/v4${path}"
  else
    curl -s -o /dev/null -w '%{http_code}' -X "${method}" \
      -H "PRIVATE-TOKEN: ${GITLAB_TOKEN}" \
      "${GITLAB_URL}/api/v4${path}"
  fi
}

uri_encode() {
  jq -rn --arg v "$1" '$v|@uri'
}

check_dependencies() {
  info "Checking dependencies..."
  local missing=()
  for dep in curl jq docker; do
    if command -v "$dep" &>/dev/null; then
      info "  ✓ $dep"
    else
      error "  ✗ $dep not found"
      missing+=("$dep")
    fi
  done
  if [[ ${#missing[@]} -gt 0 ]]; then
    error "Missing dependencies: ${missing[*]}"
    exit 1
  fi
  if [[ -z "${GITLAB_TOKEN}" ]]; then
    error "GITLAB_TOKEN is empty. Add it to infrastructure/.env and re-run."
    exit 1
  fi
}

# ── Steps ───────────────────────────────────────────────────────────────────
ensure_group() {
  local code group_id
  code="$(http_code GET "/groups/${GITLAB_COMPONENTS_GROUP}")"
  if [[ "${code}" == "200" ]]; then
    group_id="$(gitlab_api GET "/groups/${GITLAB_COMPONENTS_GROUP}" | jq -r '.id')"
    info "Group '${GITLAB_COMPONENTS_GROUP}' exists (id=${group_id})"
    echo "${group_id}"
    return 0
  fi

  warn "Group '${GITLAB_COMPONENTS_GROUP}' not found — creating..."
  gitlab_api POST "/groups" \
    "{\"name\":\"${GITLAB_COMPONENTS_GROUP}\",\"path\":\"${GITLAB_COMPONENTS_GROUP}\",\"visibility\":\"private\"}" \
    >/dev/null
  group_id="$(gitlab_api GET "/groups/${GITLAB_COMPONENTS_GROUP}" | jq -r '.id')"
  info "Group '${GITLAB_COMPONENTS_GROUP}' created (id=${group_id})"
  echo "${group_id}"
}

unprotect_default_branch() {
  # unprotect_default_branch <project_id>
  #
  # The group `bigbug-mirrors` is created with default_branch_protection=2
  # (allowed_to_push = "no one"), so a freshly initialized project has its
  # `main` branch protected against any push. Without removing that protection
  # the Repository Files API returns `403 You are not allowed to push into
  # this branch` and the provision fails. This makes the script idempotent
  # against that group default.
  local project_id="$1" code
  code="$(http_code GET "/projects/${project_id}/protected_branches/${GITLAB_COMPONENTS_DEFAULT_BRANCH}")"
  if [[ "${code}" == "200" ]]; then
    warn "Branch '${GITLAB_COMPONENTS_DEFAULT_BRANCH}' is protected — unprotecting for provisioning"
    curl -s -o /dev/null -X DELETE \
      -H "PRIVATE-TOKEN: ${GITLAB_TOKEN}" \
      "${GITLAB_URL}/api/v4/projects/${project_id}/protected_branches/${GITLAB_COMPONENTS_DEFAULT_BRANCH}"
    info "Branch '${GITLAB_COMPONENTS_DEFAULT_BRANCH}' unprotected"
  else
    info "Branch '${GITLAB_COMPONENTS_DEFAULT_BRANCH}' is not protected — ok"
  fi
}

ensure_project() {
  local group_id="$1" enc_path code project_id
  enc_path="$(uri_encode "${COMPONENTS_PATH}")"
  code="$(http_code GET "/projects/${enc_path}")"
  if [[ "${code}" == "200" ]]; then
    project_id="$(gitlab_api GET "/projects/${enc_path}" | jq -r '.id')"
    info "Project '${COMPONENTS_PATH}' exists (id=${project_id})"
    echo "${project_id}"
    return 0
  fi

  warn "Project '${COMPONENTS_PATH}' not found — creating..."
  gitlab_api POST "/projects" \
    "{\"name\":\"${GITLAB_COMPONENTS_PROJECT}\",\"path\":\"${GITLAB_COMPONENTS_PROJECT}\",\"namespace_id\":${group_id},\"visibility\":\"private\",\"initialize_with_readme\":true,\"default_branch\":\"${GITLAB_COMPONENTS_DEFAULT_BRANCH}\"}" \
    >/dev/null
  project_id="$(gitlab_api GET "/projects/${enc_path}" | jq -r '.id')"
  info "Project '${COMPONENTS_PATH}' created (id=${project_id})"
  echo "${project_id}"
}

ensure_repository_file() {
  # ensure_repository_file <project_id> <file_path> <content>
  local project_id="$1" file_path="$2" content="$3"
  local enc_path code remote_content

  enc_path="$(uri_encode "${file_path}")"
  code="$(http_code GET "/projects/${project_id}/repository/files/${enc_path}?ref=${GITLAB_COMPONENTS_DEFAULT_BRANCH}")"

  local content_b64
  content_b64="$(printf '%s' "${content}" | base64 -w0)"

  if [[ "${code}" == "200" ]]; then
    remote_content="$(gitlab_api GET "/projects/${project_id}/repository/files/${enc_path}?ref=${GITLAB_COMPONENTS_DEFAULT_BRANCH}" | jq -r '.content' | base64 -d 2>/dev/null || true)"
    if [[ "${remote_content}" == "${content}" ]]; then
      info "File '${file_path}' is up to date — skip"
      return 0
    fi
    warn "File '${file_path}' differs — updating..."
    gitlab_api PUT "/projects/${project_id}/repository/files/${enc_path}" \
      "{\"branch\":\"${GITLAB_COMPONENTS_DEFAULT_BRANCH}\",\"content\":\"${content_b64}\",\"commit_message\":\"Update ${file_path} (provision-gitlab)\",\"encoding\":\"base64\"}" \
      >/dev/null
    info "File '${file_path}' updated"
    return 0
  fi

  warn "File '${file_path}' not found — creating..."
  gitlab_api POST "/projects/${project_id}/repository/files/${enc_path}" \
    "{\"branch\":\"${GITLAB_COMPONENTS_DEFAULT_BRANCH}\",\"content\":\"${content_b64}\",\"commit_message\":\"Add ${file_path} (provision-gitlab)\",\"encoding\":\"base64\"}" \
    >/dev/null
  info "File '${file_path}' created"
}

ensure_tag() {
  local project_id="$1" code
  code="$(http_code GET "/projects/${project_id}/repository/tags/${GITLAB_COMPONENTS_TAG}")"
  if [[ "${code}" == "200" ]]; then
    info "Tag '${GITLAB_COMPONENTS_TAG}' exists — skip"
    return 0
  fi

  warn "Tag '${GITLAB_COMPONENTS_TAG}' not found — creating on branch '${GITLAB_COMPONENTS_DEFAULT_BRANCH}'..."
  gitlab_api POST "/projects/${project_id}/repository/tags" \
    "{\"tag_name\":\"${GITLAB_COMPONENTS_TAG}\",\"ref\":\"${GITLAB_COMPONENTS_DEFAULT_BRANCH}\",\"message\":\"Components ${GITLAB_COMPONENTS_TAG}\"}" \
    >/dev/null
  info "Tag '${GITLAB_COMPONENTS_TAG}' created"
}

ensure_runner() {
  local desc="${GITLAB_RUNNER_DESCRIPTION}" existing_id locally_configured token
  local expected_host1 expected_host2

  # Idempotency key = runner description.
  existing_id="$(gitlab_api GET "/runners/all?per_page=100" | jq -r --arg d "${desc}" '.[]? | select(.description == $d) | .id' | head -1)"
  # `gitlab-runner list` prints ANSI colour codes that break grep — check the
  # persisted config.toml (the actual source of truth in the volume) directly.
  # A runner is only "configured" if BOTH host-gateway extra_hosts entries are
  # present as separate TOML array elements. The first revision passed a
  # comma-joined value, which stored `["a,b"]` (one element) and Docker
  # rejected it with "invalid IP address in add-host"; repeating the flag once
  # per host stores `["a", "b"]` correctly.
  expected_host1="gitlab.local:host-gateway"
  expected_host2="${GITLAB_HARBOR_HOST}:host-gateway"
  locally_configured="$(docker exec "${GITLAB_RUNNER_CONTAINER}" sh -c '
    cfg=/etc/gitlab-runner/config.toml
    [ -f "$cfg" ] || exit 0
    grep -q "name = \"'"${desc}"'\"" "$cfg" \
      && grep -q "extra_hosts = \[.*\"'"${expected_host1}"'\".*\]" "$cfg" \
      && grep -q "extra_hosts = \[.*\"'"${expected_host2}"'\".*\]" "$cfg" \
      && echo yes || true' 2>/dev/null)"

  if [[ -n "${existing_id}" ]]; then
    if [[ "${locally_configured}" == "yes" ]]; then
      info "Runner '${desc}' already registered (GitLab id=${existing_id}) — skip"
      return 0
    fi
    warn "Runner '${desc}' exists in GitLab (id=${existing_id}) but its local config is missing/stale — deleting orphan and re-registering"
    curl -s -X DELETE -H "PRIVATE-TOKEN: ${GITLAB_TOKEN}" \
      "${GITLAB_URL}/api/v4/runners/${existing_id}" >/dev/null || true
  fi

  # Modern auth-token flow (GitLab 16.0+). Registration-token endpoint is
  # deprecated in GitLab 19.x, so POST /api/v4/user/runners is the reliable path.
  if [[ -n "${GITLAB_RUNNER_AUTH_TOKEN}" ]]; then
    token="${GITLAB_RUNNER_AUTH_TOKEN}"
    info "Using GITLAB_RUNNER_AUTH_TOKEN from env"
  else
    info "Creating runner '${desc}' via /api/v4/user/runners..."
    token="$(gitlab_api POST "/user/runners" \
      "{\"runner_type\":\"instance_type\",\"description\":\"${desc}\",\"tag_list\":\"${GITLAB_RUNNER_TAG_LIST}\",\"run_untagged\":true,\"locked\":false}" \
      | jq -r '.token')"
  fi

  if [[ -z "${token}" || "${token}" == "null" ]]; then
    error "Failed to obtain runner authentication token"
    return 1
  fi

  info "Registering runner locally in '${GITLAB_RUNNER_CONTAINER}'..."
  # With the authentication-token flow (GitLab 16.0+), `--run-untagged`,
  # `--tag-list`, `--locked`, `--access-level`, `--paused`, `--maximum-timeout`
  # and `--maintenance-note` are reserved: they are set server-side via the
  # /user/runners API (already passed above), so they must NOT be repeated here.
  docker exec "${GITLAB_RUNNER_CONTAINER}" gitlab-runner register --non-interactive \
    --url "http://gitlab.local:8080" \
    --token "${token}" \
    --executor docker \
    --docker-image "${GITLAB_RUNNER_DOCKER_IMAGE}" \
    --docker-volumes /var/run/docker.sock:/var/run/docker.sock \
    --docker-extra-hosts "gitlab.local:host-gateway" \
    --docker-extra-hosts "${GITLAB_HARBOR_HOST}:host-gateway" \
    --docker-pull-policy if-not-present \
    --description "${desc}"

  docker exec "${GITLAB_RUNNER_CONTAINER}" gitlab-runner restart >/dev/null 2>&1 || true
  info "Runner '${desc}' registered"
}

ci_yml_content() {
  # Literal GitLab predefined variable; kept out of the heredoc so shell
  # expansion does not eat it. (Avoids backticks in comments too, which the
  # unquoted heredoc would treat as command substitution.)
  local ci_server_fqdn='$CI_SERVER_FQDN'
  cat <<EOF
# Provisioned by infrastructure/provision-gitlab.sh — do not edit manually.
#
# Consumer config: includes the locally published docker-hub-to-harbor
# component. Required inputs are passed here (with dev defaults) so the
# include lints; the runtime values (source_image, tags, target creds, …) are
# supplied by the backend as pipeline variables (see component contract).
#
# NOTE: the component host is the GitLab predefined variable CI_SERVER_FQDN
# (NOT a hardcoded FQDN). It resolves to gitlab.local:8080 for this instance —
# a hardcoded gitlab.local (no port) is treated by GitLab as an external host
# and rejected with "the component path is not supported". The version must
# match the git tag exactly, hence @${GITLAB_COMPONENTS_TAG}.
include:
  - component: ${ci_server_fqdn}/${COMPONENTS_PATH}/docker-hub-to-harbor@${GITLAB_COMPONENTS_TAG}
    inputs:
      target_registry: ${GITLAB_HARBOR_HOST}:443
      target_repo: bigbug/nginx

stages: [sync]
EOF
}

provision() {
  local group_id project_id
  group_id="$(ensure_group)"
  project_id="$(ensure_project "${group_id}")"

  unprotect_default_branch "${project_id}"
  ensure_repository_file "${project_id}" ".gitlab-ci.yml" "$(ci_yml_content)"
  ensure_repository_file "${project_id}" "templates/docker-hub-to-harbor.yml" "$(cat "${TEMPLATE_SRC}")"
  ensure_tag "${project_id}"
  ensure_runner
}

# ── Verify ──────────────────────────────────────────────────────────────────
verify() {
  local enc_path code fails=0

  enc_path="$(uri_encode "${COMPONENTS_PATH}")"
  code="$(http_code GET "/projects/${enc_path}")"
  if [[ "${code}" == "200" ]]; then
    info "✓ project ${COMPONENTS_PATH} exists (200)"
  else
    error "✗ project ${COMPONENTS_PATH} (HTTP ${code})"; fails=$((fails+1))
  fi

  local project_id
  project_id="$(gitlab_api GET "/projects/${enc_path}" | jq -r '.id')"

  local ci_content
  ci_content="$(gitlab_api GET "/projects/${project_id}/repository/files/$(uri_encode '.gitlab-ci.yml')?ref=${GITLAB_COMPONENTS_DEFAULT_BRANCH}" | jq -r '.content' | base64 -d 2>/dev/null || true)"
  if echo "${ci_content}" | grep -q "component:"; then
    info "✓ .gitlab-ci.yml contains component include"
  else
    error "✗ .gitlab-ci.yml missing component include"; fails=$((fails+1))
  fi

  code="$(http_code GET "/projects/${project_id}/repository/files/$(uri_encode 'templates/docker-hub-to-harbor.yml')?ref=${GITLAB_COMPONENTS_DEFAULT_BRANCH}")"
  if [[ "${code}" == "200" ]]; then
    info "✓ templates/docker-hub-to-harbor.yml exists (200)"
  else
    error "✗ templates/docker-hub-to-harbor.yml (HTTP ${code})"; fails=$((fails+1))
  fi

  code="$(http_code GET "/projects/${project_id}/repository/tags/${GITLAB_COMPONENTS_TAG}")"
  if [[ "${code}" == "200" ]]; then
    info "✓ tag ${GITLAB_COMPONENTS_TAG} exists (200)"
  else
    error "✗ tag ${GITLAB_COMPONENTS_TAG} (HTTP ${code})"; fails=$((fails+1))
  fi

  local runners
  runners="$(gitlab_api GET "/runners/all?per_page=100")"
  if echo "${runners}" | jq -e --arg d "${GITLAB_RUNNER_DESCRIPTION}" '.[]? | select(.description == $d)' >/dev/null 2>&1; then
    info "✓ runner '${GITLAB_RUNNER_DESCRIPTION}' exists in GitLab"
  else
    error "✗ runner '${GITLAB_RUNNER_DESCRIPTION}' not found in GitLab"; fails=$((fails+1))
  fi

  # `gitlab-runner list` emits ANSI colour codes that break grep, so verify the
  # persisted config.toml (the actual source of truth in the volume) directly.
  if docker exec "${GITLAB_RUNNER_CONTAINER}" sh -c 'grep -q "name = \"'"${GITLAB_RUNNER_DESCRIPTION}"'\"" /etc/gitlab-runner/config.toml' 2>/dev/null; then
    info "✓ runner '${GITLAB_RUNNER_DESCRIPTION}' present in local config"
  else
    error "✗ runner '${GITLAB_RUNNER_DESCRIPTION}' missing from local config"; fails=$((fails+1))
  fi

  echo ""
  if [[ "${fails}" -eq 0 ]]; then
    info "All verify checks passed."
  else
    error "${fails} verify check(s) failed."
  fi
  return "${fails}"
}

# ── Main ────────────────────────────────────────────────────────────────────
main() {
  local mode="${1:-}"
  check_dependencies

  if [[ "${mode}" == "--verify-only" ]]; then
    info "Verify-only mode."
    verify
    exit $?
  fi

  echo ""
  info "=== Provisioning GitLab components project + runner ==="
  echo ""
  provision
  echo ""
  info "=== Verify ==="
  verify
  exit $?
}

main "$@"
