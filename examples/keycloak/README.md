# Keycloak OpenTofu Configuration

> Declarative Keycloak realm setup for BigBug using OpenTofu/Terraform.

## What Gets Created

This configuration provisions the following resources in Keycloak:

| Resource | Name | Description |
|----------|------|-------------|
| **Realm** | `bigbug` | BigBug application realm |
| **Client** | `bigbug-backend` | Confidential client for FastAPI backend (client secret auth) |
| **Client** | `bigbug-frontend` | Public client for React SPA (PKCE S256 enforced) |
| **Role** | `admin` | Full access + user/role management |
| **Role** | `operator` | Manage projects, mirrors, images, helm charts, docker images |
| **Role** | `viewer` | Read-only access to all resources |
| **User** | `bigbug` | Test user with role `admin` |

### Client Details

**Backend (confidential):**
- `client_id`: `bigbug-backend`
- `access_type`: confidential
- Standard flow + direct access grants enabled
- Uses client secret for authentication

**Frontend (public):**
- `client_id`: `bigbug-frontend`
- `access_type`: public
- Authorization Code flow with **PKCE S256** enforced
- Redirect URIs: `http://localhost:5173/*`, `http://localhost:5173/sso-callback`
- No implicit flow, no client secret

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `keycloak_url` | `http://localhost:8180` | Keycloak server URL |
| `keycloak_admin_username` | `admin` | Admin username |
| `keycloak_admin_password` | — | Admin password (sensitive) |
| `realm_name` | `bigbug` | Realm name |
| `backend_client_id` | `bigbug-backend` | Backend client ID |
| `backend_client_secret` | — | Backend client secret (sensitive) |
| `frontend_client_id` | `bigbug-frontend` | Frontend client ID |
| `frontend_redirect_uris` | `["http://localhost:5173/*", "http://localhost:5173/sso-callback"]` | Valid redirect URIs |
| `test_user_username` | `bigbug` | Test user username |
| `test_user_password` | — | Test user password (sensitive) |
| `test_user_email` | `bigbug@example.com` | Test user email |

## Usage

### Prerequisites

- Keycloak 24.0+ running and healthy (see [`docker-compose.infra.yml`](../docker-compose.infra.yml))
- OpenTofu 1.6+ or Terraform 1.5+

### Quick Setup

```bash
cd examples/keycloak

# Copy example variables
cp terraform.tfvars.example terraform.tfvars

# Review and edit terraform.tfvars (defaults work for local dev)

# Initialize providers
tofu init

# Plan changes (review before applying)
tofu plan

# Apply configuration
tofu apply
```

### Verify in Keycloak UI

1. Open http://localhost:8180
2. Login: `admin` / `admin`
3. Select realm "bigbug" (dropdown top-left)
4. Navigate to:
   - **Clients** → `bigbug-backend`, `bigbug-frontend`
   - **Realm roles** → admin, operator, viewer
   - **Users** → `bigbug` (with role admin)

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

**Note**: This will remove the entire realm and all its resources. Data cannot be recovered unless you have a backup.

## Outputs

| Output | Description |
|--------|-------------|
| `realm_id` | Realm UUID |
| `realm_name` | Realm name (`bigbug`) |
| `realm_url` | Full realm URL |
| `backend_client_id` | Backend client ID |
| `frontend_client_id` | Frontend client ID |
| `test_user_username` | Test user username |

Use `tofu output` to view all outputs.

## Idempotency

This configuration is fully idempotent:

- Running `tofu apply` multiple times produces the same result
- Existing resources are not recreated
- `tofu plan` shows `No changes` when state matches reality

## Security Notes

- `terraform.tfvars` contains sensitive values and is **gitignored**
- Use `terraform.tfvars.example` as a template (safe to commit)
- State files (`*.tfstate`) contain secrets — never commit them
- Consider using a remote backend (S3 + DynamoDB) for team environments
