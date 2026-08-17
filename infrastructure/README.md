# BigBug Infrastructure Initialization

> OpenTofu/Terraform-based infrastructure initialization for BigBug development environment.

## Overview

This directory contains everything needed to spin up a complete BigBug development environment from scratch:

- **Docker Compose** — infrastructure services (Keycloak, GitLab, GitLab Runner)
- **OpenTofu modules** — declarative Keycloak, Harbor, and GitLab setup
- **Root OpenTofu config** — single `tofu apply` orchestrating all modules
- **Harbor in kind** — local OCI registry for testing
- **Automation scripts** — one-command environment initialization

## Prerequisites

| Tool | Version | Install Guide |
|------|---------|---------------|
| Docker | 24+ | [docker.com](https://docs.docker.com/engine/install/) |
| OpenTofu | 1.6+ | [opentofu.org](https://opentofu.org/docs/intro/install/) |
| _or_ Terraform | 1.5+ | [terraform.io](https://www.terraform.io/downloads) |
| curl | any | package manager |
| jq | 1.6+ | [jqlang.github.io](https://jqlang.github.io/jq/download/) |
| kind | 0.20+ (optional) | [kind.sigs.k8s.io](https://kind.sigs.k8s.io/) — for Harbor |

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

1. Check all dependencies
2. Start infrastructure services (Keycloak, GitLab, GitLab Runner) via `infrastructure/docker-compose.yml`
3. Wait for Keycloak and GitLab to be healthy
4. Deploy Harbor in kind (if kind is installed and cluster doesn't exist)
5. Initialize all infrastructure via a single `tofu apply` (Keycloak → Harbor → GitLab)
6. Update `.env` with generated tokens and secrets
7. Start application services (backend + frontend) via root `docker-compose.yml`

After completion, access:

| Service | URL | Credentials |
|---------|-----|-------------|
| Frontend UI | http://localhost:5173 | bigbug / bigbug |
| Backend API | http://localhost:8000 | — |
| Keycloak | http://localhost:8180 | admin / admin |
| GitLab | http://localhost:8080 | root / see container logs |

## Directory Structure

```
infrastructure/
├── terraform/           # Root OpenTofu module + sub-modules
├── harbor/              # Harbor deployment in kind
├── gitlab-components/   # GitLab CI/CD component templates
├── docker-compose.yml   # Infrastructure services (keycloak, gitlab, gitlab-runner)
├── init.sh              # Full initialization script
└── update-env.sh        # Update .env from OpenTofu outputs
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

### 2. Initialize Infrastructure via OpenTofu

```bash
cd infrastructure/terraform

# Copy and customize variables
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars:
#   - Set gitlab_token to your GitLab root PAT
#   - Customize other values as needed

# Apply all modules (Keycloak → Harbor → GitLab)
tofu init
tofu apply
```

### 3. Update Environment

```bash
cd ../..
./infrastructure/update-env.sh
```

### 4. Start Application

```bash
docker compose up -d
```

## Harbor (Optional)

Harbor runs as a separate kind cluster for local OCI registry testing.

### Deploy

```bash
./infrastructure/harbor/deploy.sh
```

The script automatically:
- Checks dependencies (kind, kubectl, helm, docker)
- Adds `harbor.local` to `/etc/hosts`
- Configures Docker insecure registry
- Creates a kind cluster with port mappings
- Installs Harbor via Helm

### Remove

```bash
# Remove cluster only
./infrastructure/harbor/teardown.sh

# Remove cluster + /etc/hosts entry
./infrastructure/harbor/teardown.sh --all
```

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
# Stop application
docker compose down

# Destroy OpenTofu-managed resources
cd infrastructure/terraform && tofu destroy

# Stop infrastructure and remove volumes
docker compose -f infrastructure/docker-compose.yml down -v
```

## Troubleshooting

### Keycloak not reachable

```bash
# Check container status
docker compose -f infrastructure/docker-compose.yml ps keycloak

# Check logs
docker compose -f infrastructure/docker-compose.yml logs keycloak

# Keycloak needs postgres-keycloak to be healthy first
docker compose -f infrastructure/docker-compose.yml restart postgres-keycloak keycloak
```

### GitLab takes too long to start

GitLab CE requires significant resources and can take 5+ minutes on first boot.

```bash
# Monitor GitLab startup
docker compose -f infrastructure/docker-compose.yml logs -f gitlab

# Check readiness endpoint
curl -v http://localhost:8080/users/sign_in
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
| 5432 | postgres-backend | root `docker-compose.yml` |
| 5433 | postgres-keycloak | `infrastructure/docker-compose.yml` |
| 6379 | redis | root `docker-compose.yml` |
| 8080 | gitlab | `infrastructure/docker-compose.yml` + `terraform.tfvars` |
| 8180 | keycloak | `infrastructure/docker-compose.yml` + `terraform.tfvars` |
| 8000 | backend | root `docker-compose.yml` |
| 5173 | frontend | root `docker-compose.yml` |

### Terraform state files

```bash
# State files are now centralized:
infrastructure/terraform/terraform.tfstate
infrastructure/terraform/terraform.tfstate.backup

# Backup
cp infrastructure/terraform/terraform.tfstate backups/terraform_$(date +%Y%m%d).tfstate
```
