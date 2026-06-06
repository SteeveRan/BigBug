# Harbor OpenTofu Configuration

> Declarative Harbor project and OIDC setup for BigBug using OpenTofu/Terraform.

## What Gets Created

This configuration provisions the following resources in Harbor:

| Resource | Name | Description |
|----------|------|-------------|
| **OIDC Auth** | Keycloak | OIDC authentication integration with Keycloak |
| **Project** | `gold-images` | Gold (base) images — private |
| **Project** | `app-images` | Application images — public |
| **Project** | `mirrors` | Mirrored images from external registries — public |
| **Robot Account** | `gold-images-ci` | CI/CD push/pull access to gold-images |
| **Robot Account** | `app-images-ci` | CI/CD push/pull access to app-images |
| **Robot Account** | `mirrors-ci` | CI/CD push/pull access to mirrors |
| **Registry** | `docker-hub` | Docker Hub endpoint for replication |
| **Registry** | `quay-io` | Quay.io endpoint for replication |
| **Replication** | `gold-images-mirror` | Pull alpine/ubuntu from Docker Hub → gold-images |
| **Replication** | `mirrors-sync` | Pull all images → mirrors project |
| **Webhook** | `bigbug-backend-webhook` | Notify backend on push/delete/scan events |

### Project Details

| Project | Public | Storage Quota | Vulnerability Scanning | Description |
|---------|--------|---------------|----------------------|-------------|
| `gold-images` | No | Unlimited | Disabled | Base OS/runtime images (sensitive) |
| `app-images` | Yes | Unlimited | Disabled | Built application images |
| `mirrors` | Yes | Unlimited | Disabled | Mirrored images from external registries |

### OIDC Configuration

| Setting | Value | Notes |
|---------|-------|-------|
| Auth Mode | `oidc_auth` | OIDC-based SSO |
| Provider | `Keycloak` | Display name in Harbor UI |
| Endpoint | `http://localhost:8180/realms/bigbug` | Keycloak realm (use host IP for kind) |
| Client ID | `harbor` | Keycloak OIDC client |
| Groups Claim | `groups` | Claim for role mapping |
| Scope | `openid,profile,email,groups` | Requested scopes |
| Verify Cert | No | Disabled for local dev |
| Auto Onboard | Yes | Create users on first login |
| User Claim | `preferred_username` | Used as Harbor username |

### Robot Account Permissions

Each CI robot account grants:
- `repository:push` — push container images
- `repository:pull` — pull container images
- `artifact:read` — read artifact metadata

## Environment Variables

### Harbor Connection

| Variable | Default | Description |
|----------|---------|-------------|
| `harbor_url` | `https://harbor.local:30443` | Harbor instance URL |
| `harbor_username` | `admin` | Harbor admin username |
| `harbor_password` | — | Harbor admin password (sensitive) |

### OIDC / Keycloak

| Variable | Default | Description |
|----------|---------|-------------|
| `auth_mode` | `oidc_auth` | Authentication mode |
| `oidc_provider_name` | `Keycloak` | OIDC provider display name |
| `oidc_endpoint` | `http://localhost:8180/realms/bigbug` | OIDC endpoint URL |
| `oidc_client_id` | `harbor` | OIDC client ID |
| `oidc_client_secret` | — | OIDC client secret (sensitive) |
| `oidc_groups_claim` | `groups` | Groups claim name |
| `oidc_scope` | `openid,profile,email,groups` | Requested scopes |
| `oidc_verify_cert` | `false` | Verify OIDC provider certificate |
| `oidc_auto_onboard` | `true` | Auto-create users on first login |
| `oidc_user_claim` | `preferred_username` | Username claim |

### Projects

| Variable | Default | Description |
|----------|---------|-------------|
| `gold_images_project_name` | `gold-images` | Gold images project name |
| `gold_images_storage_quota` | `-1` | Storage quota in GB (-1 = unlimited) |
| `app_images_project_name` | `app-images` | App images project name |
| `app_images_storage_quota` | `-1` | Storage quota in GB (-1 = unlimited) |
| `mirrors_project_name` | `mirrors` | Mirrors project name |
| `mirrors_storage_quota` | `-1` | Storage quota in GB (-1 = unlimited) |

### Replication

| Variable | Default | Description |
|----------|---------|-------------|
| `dockerhub_registry_name` | `docker-hub` | Docker Hub registry entry name |
| `dockerhub_endpoint_url` | `https://hub.docker.com` | Docker Hub endpoint |
| `quay_registry_name` | `quay-io` | Quay.io registry entry name |
| `quay_endpoint_url` | `https://quay.io` | Quay.io endpoint |
| `replication_schedule` | `""` | Cron schedule (empty = manual only) |

### Webhooks

| Variable | Default | Description |
|----------|---------|-------------|
| `webhook_backend_url` | `http://localhost:8000/api/webhooks/harbor` | Backend webhook URL |

## Usage

### Prerequisites

- Harbor deployed and healthy (see [`examples/harbor/deploy.sh`](../../examples/harbor/deploy.sh))
- Keycloak configured with OIDC client `harbor` (see [`examples/keycloak/`](../../examples/keycloak/))
- OpenTofu 1.6+ or Terraform 1.5+

### Quick Setup

```bash
cd infrastructure/terraform/harbor

# Copy example variables
cp terraform.tfvars.example terraform.tfvars

# Edit terraform.tfvars:
#   - Set harbor_password to your Harbor admin password
#   - Set oidc_client_secret from Keycloak → Clients → harbor → Credentials
#   - Set oidc_endpoint to http://<HOST_IP>:8180/realms/bigbug (for kind environment)

# Initialize providers
tofu init

# Plan changes (review before applying)
tofu plan

# Apply configuration
tofu apply
```

### Getting OIDC Client Secret

1. Deploy Keycloak via OpenTofu:
   ```bash
   cd ../../examples/keycloak
   tofu init && tofu apply
   ```

2. Create the `harbor` OIDC client manually in Keycloak Admin UI
   (or wait for automated client setup to be added).

3. Copy the client secret:
   - Keycloak Admin → Clients → `harbor` → Credentials → Client Secret

4. Paste into `infrastructure/terraform/harbor/terraform.tfvars`:
   ```hcl
   oidc_client_secret = "your-secret-here"
   ```

### Important for kind Environment

When Harbor runs inside a kind cluster, it cannot reach Keycloak on `localhost:8180`. Use the Docker bridge IP instead:

```bash
# Get Docker bridge gateway IP
docker network inspect bridge -f '{{(index .IPAM.Config 0).Gateway}}'
# → 172.17.0.1

# Update terraform.tfvars:
# oidc_endpoint = "http://172.17.0.1:8180/realms/bigbug"
```

### Verify in Harbor UI

1. Open https://harbor.local:30443
2. Login as `admin` / your admin password
3. Navigate to:
   - **Projects** → `gold-images` (private), `app-images` (public), `mirrors` (public)
   - **Administration** → **Configuration** → **Authentication** → OIDC should be configured
   - **Administration** → **Robot Accounts** → CI robot accounts listed
   - **Administration** → **Registries** → `docker-hub`, `quay-io` endpoints
   - **Administration** → **Replications** → replication policies

### Update Configuration

After modifying `.tf` files:

```bash
tofu plan    # Review what will change
tofu apply   # Apply changes
```

### Destroy Configuration

```bash
tofu destroy
```

**Note**: This will:
- Delete all BigBug projects (gold-images, app-images, mirrors)
- Revoke all robot accounts
- Remove replication policies and registry endpoints
- Delete webhook configurations
- OIDC configuration will be reset (admin can still login with db_auth)

## Outputs

| Output | Sensitive | Description |
|--------|-----------|-------------|
| `gold_images_project_id` | No | Gold images project numeric ID |
| `gold_images_project_name` | No | Gold images project name |
| `app_images_project_id` | No | App images project numeric ID |
| `app_images_project_name` | No | App images project name |
| `mirrors_project_id` | No | Mirrors project numeric ID |
| `mirrors_project_name` | No | Mirrors project name |
| `gold_images_ci_robot_name` | No | Gold images CI robot account name |
| `gold_images_ci_robot_secret` | **Yes** | Gold images CI robot secret |
| `app_images_ci_robot_name` | No | App images CI robot account name |
| `app_images_ci_robot_secret` | **Yes** | App images CI robot secret |
| `mirrors_ci_robot_name` | No | Mirrors CI robot account name |
| `mirrors_ci_robot_secret` | **Yes** | Mirrors CI robot secret |
| `dockerhub_registry_id` | No | Docker Hub registry endpoint ID |
| `quay_registry_id` | No | Quay.io registry endpoint ID |
| `webhook_id` | No | Backend webhook ID |
| `registry_url` | No | Harbor registry base URL |

Use `tofu output` to view all outputs. Sensitive outputs require `tofu output -json` or explicit reference by name:

```bash
# Get a robot account secret
tofu output -raw gold_images_ci_robot_secret

# Get all outputs in JSON format
tofu output -json
```

## Idempotency

This configuration is fully idempotent:

- Running `tofu apply` multiple times produces the same result
- Existing resources are not recreated
- `tofu plan` shows `No changes` when state matches reality

## Security Notes

- `terraform.tfvars` contains sensitive values and is **gitignored**
- Use `terraform.tfvars.example` as a template (safe to commit)
- Robot account secrets in outputs are marked as **sensitive** (hidden in logs)
- State files (`*.tfstate`) contain all secrets in plaintext — never commit them
- Rotate robot account secrets by tainting and reapplying:
  ```bash
  tofu taint harbor_robot_account.gold_images_ci
  tofu apply
  ```
- Consider using a remote backend (S3 + DynamoDB) for team environments
- OIDC client secret is stored in Harbor configuration and Terraform state

## Relationship to Legacy Scripts

This OpenTofu configuration **replaces** the following manual steps from [`examples/harbor/`](../../examples/harbor/):

| Manual Step | Terraform Equivalent |
|-------------|---------------------|
| `./init-harbor.sh` (create projects) | `harbor_project` resources |
| Manual OIDC setup via Harbor UI | `harbor_config_auth.oidc` |
| Manual robot account creation | `harbor_robot_account` resources |

The `deploy.sh` and `teardown.sh` scripts are still used for:
- Creating/destroying the kind cluster
- Installing Harbor via Helm
- Docker daemon configuration

**These are intentionally kept as legacy reference** and not replaced by Terraform.

## File Structure

```
infrastructure/terraform/harbor/
├── main.tf                   # Main configuration (provider, projects, OIDC, robots, registries, webhooks)
├── variables.tf              # Input variables with defaults
├── outputs.tf                # Output values (project IDs, robot secrets)
├── terraform.tfvars.example  # Example variable values (safe to commit)
├── .gitignore                # Prevents committing tfvars, state, and .terraform/
└── README.md                 # This file
```

## Troubleshooting

### Problem: Harbor API not reachable

```bash
# Check Harbor health
curl -k -u admin:Harbor12345 https://harbor.local:30443/api/v2.0/health

# Ensure deploy.sh ran successfully
kubectl get pods -n harbor
```

### Problem: OIDC endpoint unreachable from kind

Use Docker bridge IP instead of localhost (see section above).

### Problem: Provider initialization fails

```bash
# Clear provider cache and reinitialize
rm -rf .terraform .terraform.lock.hcl
tofu init
```

### Problem: Robot account secret not showing

Use `-raw` flag (not `-json`) for sensitive outputs:
```bash
tofu output -raw gold_images_ci_robot_secret
```

## References

- [Harbor Terraform Provider Documentation](https://registry.terraform.io/providers/goharbor/harbor)
- [Harbor OIDC Authentication](https://goharbor.io/docs/2.10.0/administration/configure-oidc-auth/)
- [Harbor API v2.0](https://goharbor.io/docs/2.10.0/build-customize-contribute/configure-swagger/)
- [Keycloak OIDC Client Configuration](https://www.keycloak.org/docs/latest/server_admin/#_oidc_clients)
- [Legacy Harbor Setup](examples/harbor/README.md)
