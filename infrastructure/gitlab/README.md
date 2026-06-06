# GitLab OpenTofu Configuration

> Declarative GitLab setup for BigBug using OpenTofu/Terraform.

## What Gets Created

This configuration provisions the following resources in GitLab:

| Resource | Name | Description |
|----------|------|-------------|
| **Group** | `bigbug-mirrors` | Group for mirror repositories (private, MR-only) |
| **PAT** | `bigbug-backend-token` | Personal Access Token with `api`, `read_repository`, `write_repository` scopes |

### Token Details

The Personal Access Token is created for the **root** user and grants the backend:
- `api` — full API access (create projects, manage CI/CD, webhooks)
- `read_repository` — clone/fetch mirrored repositories
- `write_repository` — push to mirrored repositories

**Expires**: `2027-12-31` by default (configurable via `backend_token_expires_at`)

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `gitlab_url` | `http://localhost:8080` | GitLab instance URL |
| `gitlab_token` | — | Root PAT for initial provider auth (sensitive) |
| `mirrors_group_name` | `bigbug-mirrors` | Group name for mirrors |
| `backend_token_name` | `bigbug-backend-token` | Name for the backend PAT |
| `backend_token_expires_at` | `2027-12-31` | PAT expiration date (ISO 8601) |
| `backend_token_scopes` | `["api", "read_repository", "write_repository"]` | PAT scopes |

## Usage

### Prerequisites

- GitLab CE running and healthy (see [`docker-compose.infra.yml`](../docker-compose.infra.yml))
- OpenTofu 1.6+ or Terraform 1.5+
- GitLab root Personal Access Token with `api` scope

### Getting the Root PAT

On a fresh GitLab instance:

```bash
# 1. Get the initial root password
docker compose -f docker-compose.infra.yml exec gitlab \
  cat /etc/gitlab/initial_root_password

# 2. Open GitLab in browser
open http://localhost:8080

# 3. Login as root with the password from step 1

# 4. Create a PAT:
#    Go to: http://localhost:8080/-/user_settings/personal_access_tokens
#    Name: bigbug-setup
#    Scopes: api
#    Click "Create personal access token"
#    Copy the generated token
```

### Quick Setup

```bash
cd infrastructure/gitlab

# Copy example variables
cp terraform.tfvars.example terraform.tfvars

# Edit terraform.tfvars — replace CHANGE-ME with your root PAT:
#   gitlab_token = "glpat-xxxxxxxxxxxxxxxxxxxx"

# Initialize providers
tofu init

# Plan changes (review before applying)
tofu plan

# Apply configuration
tofu apply
```

### Get the Backend Token

After applying, retrieve the generated token:

```bash
tofu output -raw backend_token
```

Or update `.env` automatically:

```bash
cd ..
./update-env.sh
```

### Verify in GitLab UI

1. Open http://localhost:8080
2. Login as root
3. Navigate to:
   - **Groups** → `bigbug-mirrors` (should exist, private)
   - **Settings → Access Tokens** → `bigbug-backend-token` (should be listed)

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
- Delete the `bigbug-mirrors` group (and all projects within it)
- Revoke the backend PAT
- Backend will lose access to GitLab until re-initialized

## Outputs

| Output | Sensitive | Description |
|--------|-----------|-------------|
| `mirrors_group_id` | No | Group numeric ID |
| `mirrors_group_path` | No | Group full path |
| `backend_token` | **Yes** | Backend PAT value |
| `backend_token_name` | No | Backend PAT name |
| `backend_token_expires_at` | No | Backend PAT expiration date |

Use `tofu output -raw backend_token` to retrieve the token for `.env`.

## Idempotency

This configuration is fully idempotent:

- Running `tofu apply` multiple times produces the same result
- Existing resources are not recreated
- `tofu plan` shows `No changes` when state matches reality

## Security Notes

- `terraform.tfvars` contains sensitive values and is **gitignored**
- Use `terraform.tfvars.example` as a template (safe to commit)
- The `backend_token` output is marked as **sensitive** (hidden in logs)
- State files (`*.tfstate`) contain the PAT in plaintext — never commit them
- Rotate the backend token before expiry by updating `backend_token_expires_at` and reapplying
- Consider using a remote backend (S3 + DynamoDB) for team environments
