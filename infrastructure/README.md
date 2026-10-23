# BigBug Infrastructure Initialization

> OpenTofu/Terraform-based infrastructure initialization for BigBug development environment.

## Overview

This directory contains everything needed to spin up a complete BigBug development environment from scratch:

- **Docker Compose** — GitLab zone only: GitLab CE omnibus + GitLab Runner ([ADR-0033](../docs/adr/infrastructure/0033-gitlab-dev-stand-compose-omnibus.md)); Keycloak/Harbor/app — в kind-кластере `bigbug-dev` ([ADR-0022](../docs/adr/infrastructure/0022-dev-stand-on-kind.md))
- **OpenTofu roots** ([ADR-0029](../docs/adr/infrastructure/0029-dev-stand-k8s-entities-via-opentofu-base-apps-split.md)): `terraform/base` (платформа кластера), `terraform/apps` (keycloakx + CNPG, Harbor chart + их API-конфиг), `terraform/` config root (GitLab base setup — [ADR-0033](../docs/adr/infrastructure/0033-gitlab-dev-stand-compose-omnibus.md))
- **kind scripts** — cluster bootstrap, self-signed certs ([ADR-0030](../docs/adr/infrastructure/0030-dev-stand-https-self-signed-certs.md)), host trust
- **Automation scripts** — one-command environment initialization

> **Provisioning GitLab CI/CD Components и пайплайнов теперь делает само приложение**
> через API (`/api/gitlab-projects`, `/api/components/presets`, `/api/pipelines/configs/*/push-ci`),
> а не bash/Terraform. Terraform остаётся только для **базовой настройки** GitLab
> (groups, users, projects, tokens, memberships) + Harbor + Keycloak. Реальные пресеты
> компонентов вшиты в [`backend/app/services/gitlab_projects/presets.py`](../../backend/app/services/gitlab_projects/presets.py),
> а YAML-примеры лежат в [`infrastructure/gitlab-components/examples/`](gitlab-components/examples/).

## Prerequisites

| Tool | Version | Install Guide |
|------|---------|---------------|
| Docker | 24+ | [docker.com](https://docs.docker.com/engine/install/) |
| OpenTofu | 1.6+ | [opentofu.org](https://opentofu.org/docs/intro/install/) |
| _or_ Terraform | 1.5+ | [terraform.io](https://www.terraform.io/downloads) |
| curl | any | package manager |
| jq | 1.6+ | [jqlang.github.io](https://jqlang.github.io/jq/download/) |
| kind | 0.20+ | [kind.sigs.k8s.io](https://kind.sigs.k8s.io/) |
| kubectl, helm, openssl | any | package manager |

## Quick Start

The fastest way to get everything running:

```bash
# From the project root
make infra-init       # equivalent to ./infrastructure/init.sh
```

> Все infra-команды доступны через корневой [`Makefile`](../Makefile): `make infra-up`, `make infra-init`, `make infra-down`, `make infra-clean`. Справка: `make help`.

Direct invocation:

```bash
# From the project root
./infrastructure/init.sh
```

This single command will:

1. Check all dependencies (docker, kind, kubectl, tofu/terraform, curl, jq, openssl)
2. Ensure self-signed TLS certs (`kind/certs.sh` → `~/.local/state/bigbug/certs` — shared per machine, [ADR-0030](../docs/adr/infrastructure/0030-dev-stand-https-self-signed-certs.md))
3. Start the GitLab compose zone (gitlab + gitlab-runner)
4. Wait for GitLab (`https://gitlab.local:8443`) and bootstrap the kind cluster `bigbug-dev`
5. `tofu apply`: base (platform) → apps (Keycloak/Harbor, two-phase) → config root (GitLab)
6. Verify / program the GitLab root PAT (`gitlab-rails runner` — ADR-0033 exception)
7. Update `.env` with host-tool variables

After completion, access:

| Service | URL | Credentials |
|---------|-----|-------------|
| Keycloak | https://keycloak.local | admin / admin |
| Harbor | https://harbor.local | admin / Harbor12345 |
| GitLab | https://gitlab.local:8443 | root / see `infrastructure/.env` |
| Frontend UI / Backend API | https://app.local / https://api.local | bigbug / bigbug |

## Directory Structure

```
infrastructure/
├── terraform/             # Config root: GitLab base setup (ADR-0033)
│   ├── base/              # Root: platform (ingress, operators) — ADR-0029
│   ├── apps/              # Root: keycloakx+CNPG, Harbor chart + API config — ADR-0029
│   └── modules/gitlab/    # GitLab module (group, service-account, membership)
├── kind/                  # kind cluster scripts: bootstrap, certs, trust
├── harbor/                # LEGACY (cluster эпоха) — подлежит сносу (#62)
├── gitlab-components/
│   └── examples/          # GitLab CI/CD component templates (examples only — not used by the app)
├── docker-compose.yml     # GitLab zone (gitlab + gitlab-runner) — ADR-0033
├── init.sh                # Full initialization script
└── update-env.sh          # Update .env with host-tool variables
```

## Manual Step-by-Step

If you prefer to run each step manually:

### 1. Start Infrastructure

```bash
docker compose -f infrastructure/docker-compose.yml up -d
```

Wait for all services to be healthy:

```bash
docker compose -f infrastructure/docker-compose.yml ps
```

### 2. Apply OpenTofu (base → apps → config)

```bash
cd infrastructure/terraform/base && tofu init && tofu apply && cd ../..

cd infrastructure/terraform/apps
cp ../terraform.tfvars.example apps/terraform.tfvars 2>/dev/null || true
tofu init
tofu apply -target=module.keycloak_init -target=module.harbor_init   # phase 1: installs
tofu apply                                                           # phase 2: config

cd ..   # config root (GitLab)
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars: set gitlab_token (GitLab root PAT)
tofu init && tofu apply
```

### 3. Update Environment

```bash
cd ../..
./infrastructure/update-env.sh
```

## Harbor (in kind, apps root)

Harbor runs in the `bigbug-dev` kind cluster behind the TLS ingress. Install/config live in `infrastructure/terraform/apps/modules/harbor_init|harbor_conf` — no separate deploy script. See [ADR-0035](../docs/adr/infrastructure/0035-harbor-dev-stand-chart.md) and `terraform/apps/README.md`. Legacy `infrastructure/harbor/` (separate-cluster era) is pending removal — #62.

## Updating Configuration

After changing any `.tf` files:

```bash
cd infrastructure/terraform

tofu plan    # Review changes
tofu apply   # Apply changes

cd ../..
./infrastructure/update-env.sh   # Refresh .env with new outputs
```

## Destroying Environment

```bash
# Stop GitLab compose zone (volumes preserved)
docker compose -f infrastructure/docker-compose.yml down

# Destroy OpenTofu-managed resources (per root)
cd infrastructure/terraform/base && tofu destroy && cd ../apps && tofu destroy && cd .. && tofu destroy && cd ../..

# Full cleanup (CONFIRM-guarded, owner only): make infra-clean
```

## Troubleshooting

### GitLab not reachable / TLS errors

```bash
# Certs must exist before compose up (init.sh runs certs.sh first)
ls ~/.local/state/bigbug/certs/gitlab.local/     # tls.crt tls.key

# Logs
docker compose -f infrastructure/docker-compose.yml logs -f gitlab

# Readiness (self-signed: -k in scripts, host trust via kind/trust-host.sh)
curl -k https://gitlab.local:8443/users/sign_in
```

### GitLab takes too long to start

GitLab CE requires significant resources and can take 5+ minutes on first boot.

```bash
# Monitor GitLab startup
docker compose -f infrastructure/docker-compose.yml logs -f gitlab

# Check readiness endpoint
curl -vk https://gitlab.local:8443/users/sign_in
```

### OpenTofu state issues

```bash
# Force unlock state (if a previous run was interrupted)
cd infrastructure/terraform
tofu force-unlock <LOCK_ID>

# Refresh state without making changes
tofu refresh

# See what would change
tofu plan
```

### Port conflicts

Default ports can conflict with local services:

| Port | Service | Change via |
|------|---------|------------|
| 5432 | postgres-backend (CNPG CR in kind) | terraform/apps |
| 6379 | redis (CR in kind) | terraform/apps |
| 8443 | gitlab (https, ADR-0033) | `infrastructure/docker-compose.yml` |
| 2222 | gitlab ssh | `infrastructure/docker-compose.yml` |
| 80/443 | ingress (keycloak.local, harbor.local, app.local, api.local) | kind extraPortMappings |
| 8000/5173 | backend/frontend (app chart in kind) | charts/bigbug |

### Terraform state files

```bash
# State lives in the shared local backend (ADR-0029 update #58):
~/.local/state/bigbug/{base,apps,}/terraform.tfstate

# Backup
cp ~/.local/state/bigbug/apps/terraform.tfstate backups/terraform_apps_$(date +%Y%m%d).tfstate
```
