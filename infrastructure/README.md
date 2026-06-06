# BigBug Infrastructure Initialization

> OpenTofu/Terraform-based infrastructure initialization for BigBug development environment.

## Overview

This directory contains everything needed to spin up a complete BigBug development environment from scratch:

- **Docker Compose files** — infrastructure and application services
- **OpenTofu configurations** — declarative Keycloak and GitLab setup
- **Automation scripts** — one-command environment initialization

## Prerequisites

| Tool | Version | Install Guide |
|------|---------|---------------|
| Docker | 24+ | [docker.com](https://docs.docker.com/engine/install/) |
| OpenTofu | 1.6+ | [opentofu.org](https://opentofu.org/docs/intro/install/) |
| _or_ Terraform | 1.5+ | [terraform.io](https://www.terraform.io/downloads) |
| curl | any | package manager |
| jq | 1.6+ | [jqlang.github.io](https://jqlang.github.io/jq/download/) |

## Quick Start

The fastest way to get everything running:

```bash
# From the project root
./infrastructure/init.sh
```

This single command will:

1. Check all dependencies
2. Start infrastructure (PostgreSQL, Redis, Keycloak, GitLab)
3. Wait for all services to be healthy
4. Initialize Keycloak realm, clients, roles, and test user via OpenTofu
5. Initialize GitLab groups and tokens via OpenTofu
6. Update `.env` with generated tokens
7. Start application services (backend + frontend)

After completion, access:

| Service | URL | Credentials |
|---------|-----|-------------|
| Frontend UI | http://localhost:5173 | bigbug / bigbug |
| Backend API | http://localhost:8000 | — |
| Keycloak | http://localhost:8180 | admin / admin |
| GitLab | http://localhost:8080 | root / see container logs |

## Manual Step-by-Step

If you prefer to run each step manually:

### 1. Start Infrastructure

```bash
docker compose -f docker-compose.infra.yml up -d
```

Wait for all services to be healthy:

```bash
docker compose -f docker-compose.infra.yml ps
```

### 2. Initialize Keycloak

```bash
cd infrastructure/keycloak

# Copy and customize variables
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars if needed

# Apply configuration
tofu init
tofu apply

# Verify in UI: http://localhost:8180 (admin / admin)
```

### 3. Initialize GitLab

```bash
cd infrastructure/gitlab

# Get the initial root password
docker compose -f ../../docker-compose.infra.yml exec gitlab \
  cat /etc/gitlab/initial_root_password

# Create a root Personal Access Token at:
# http://localhost:8080/-/user_settings/personal_access_tokens
# Scope: "api"

# Copy and customize variables
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars — set gitlab_token to your root PAT

# Apply configuration
tofu init
tofu apply
```

### 4. Update Environment

```bash
cd ..
./update-env.sh
```

### 5. Start Application

```bash
docker compose -f docker-compose.app.yml up -d
```

## Directory Structure

```
infrastructure/
├── README.md                    # This file
├── init.sh                      # Full initialization script
├── update-env.sh                # Update .env from OpenTofu outputs
│
├── harbor/                      # Harbor deployment in kind cluster
│   ├── setup/                   # Shell scripts and configs
│   │   ├── deploy.sh
│   │   ├── teardown.sh
│   │   ├── test-push.sh
│   │   ├── init-harbor.sh
│   │   ├── kind-config.yaml
│   │   ├── harbor-values.yaml
│   │   ├── keycloak-integration.md
│   │   └── README.md
│   └── terraform/               # OpenTofu: Harbor configuration
│       ├── main.tf
│       ├── variables.tf
│       ├── outputs.tf
│       ├── terraform.tfvars.example
│       └── README.md
│
├── keycloak/                    # OpenTofu: Keycloak configuration
│   ├── main.tf                  # Provider configuration
│   ├── realm.tf                 # Realm "bigbug"
│   ├── clients.tf               # Backend + Frontend OIDC clients
│   ├── roles.tf                 # RBAC roles (admin, operator, viewer)
│   ├── users.tf                 # Test user
│   ├── variables.tf             # Input variables
│   ├── outputs.tf               # Exported values
│   ├── terraform.tfvars.example # Example variables
│   ├── .gitignore               # Ignore state and secrets
│   └── README.md                # Keycloak-specific docs
│
├── gitlab/                      # OpenTofu: GitLab configuration
│   ├── main.tf                  # Provider configuration
│   ├── groups.tf                # Mirrors group
│   ├── tokens.tf                # Personal Access Tokens
│   ├── variables.tf             # Input variables
│   ├── outputs.tf               # Exported tokens (sensitive)
│   ├── terraform.tfvars.example # Example variables
│   ├── .gitignore               # Ignore state and secrets
│   └── README.md                # GitLab-specific docs
│
└── gitlab-components/           # GitLab CI/CD component templates
    ├── app-image-template.yml
    ├── docker-sync-template.yml
    ├── gold-image-template.yml
    ├── helm-sync-template.yml
    └── mirror-template.yml
```

## Updating Configuration

### Keycloak

After changing `.tf` files:

```bash
cd infrastructure/keycloak
tofu plan    # Review changes
tofu apply   # Apply changes
```

### GitLab

After changing `.tf` files:

```bash
cd infrastructure/gitlab
tofu plan    # Review changes
tofu apply   # Apply changes
```

Run `./infrastructure/update-env.sh` after any changes that modify outputs.

## Destroying Environments

```bash
# Stop application
docker compose -f docker-compose.app.yml down

# Destroy OpenTofu-managed resources
cd infrastructure/keycloak && tofu destroy
cd infrastructure/gitlab && tofu destroy

# Stop infrastructure and remove volumes
docker compose -f docker-compose.infra.yml down -v
```

## Troubleshooting

### Keycloak not reachable

```bash
# Check container status
docker compose -f docker-compose.infra.yml ps keycloak

# Check logs
docker compose -f docker-compose.infra.yml logs keycloak

# Keycloak needs postgres-keycloak to be healthy first
docker compose -f docker-compose.infra.yml restart postgres-keycloak keycloak
```

### GitLab takes too long to start

GitLab CE requires significant resources and can take 5+ minutes on first boot.

```bash
# Monitor GitLab startup
docker compose -f docker-compose.infra.yml logs -f gitlab

# Check health endpoint
curl -v http://localhost:8080/-/health
```

### OpenTofu state issues

```bash
# Force unlock state (if a previous run was interrupted)
cd infrastructure/keycloak  # or infrastructure/gitlab
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
| 5432 | postgres-backend | `docker-compose.infra.yml` |
| 5433 | postgres-keycloak | `docker-compose.infra.yml` |
| 6379 | redis | `docker-compose.infra.yml` |
| 8080 | gitlab | `docker-compose.infra.yml` + `terraform.tfvars` |
| 8180 | keycloak | `docker-compose.infra.yml` + `terraform.tfvars` |
| 8000 | backend | `docker-compose.app.yml` |
| 5173 | frontend | `docker-compose.app.yml` |
