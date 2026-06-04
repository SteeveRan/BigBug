# DevOps Sync & Build Service — Architecture

## Overview

A fullstack DevOps service for:
- Mirroring GitHub repositories to GitLab (with CI/CD pipelines)
- Building base OS/runtime Docker images (Gold Images)
- Building application Docker images on top of Gold Images
- Tracking sync/build status, logs, schedules

## Tech Stack

### Backend
- **FastAPI** — REST API framework
- **SQLAlchemy 2.x** (async) — ORM
- **Alembic** — database migrations
- **PostgreSQL 17** — primary database
- **Redis 7** — cache / task queue
- **APScheduler** (AsyncIOScheduler) — scheduled jobs
- **python-gitlab** — GitLab API client
- **PyGithub** — GitHub API client
- **python-jose** + **passlib** — JWT auth
- **authlib** — OIDC/OAuth2 (Keycloak SSO)
- **pytest** + **pytest-asyncio** + **httpx** — testing

### Frontend
- **React 19** + **TypeScript**
- **Vite** — build tool
- **Yarn** — package manager
- **Redux Toolkit** + RTK Query — state management & API
- **Material UI v6** — component library
- **React Router v7** — routing
- **ESLint** + `@typescript-eslint` — linting
- **Vitest** + `@testing-library/react` — testing
- **keycloak-js** — SSO adapter

### Infrastructure (dev)
- **GitLab CE** — mirror target + CI/CD runner
- **GitLab Runner** — pipeline executor
- **Keycloak** — SSO / OIDC provider
- **PostgreSQL 17**
- **Redis 7**

---

## Docker Compose Services

| Service        | Image                        | Port(s)          |
|----------------|------------------------------|------------------|
| `gitlab`       | `gitlab/gitlab-ce:latest`    | 8080, 8443, 2222 |
| `gitlab-runner`| `gitlab/gitlab-runner:latest`| —                |
| `postgres`     | `postgres:17`                | 5432             |
| `redis`        | `redis:7`                    | 6379             |
| `keycloak`     | `quay.io/keycloak/keycloak`  | 8180             |
| `backend`      | `./backend`                  | 8000             |
| `frontend`     | `./frontend`                 | 5173             |

---

## Database Schema

### Status Flags (unified)
| Value | Meaning     |
|-------|-------------|
| 0     | OK / Success |
| 1     | Failed      |
| 2     | Warning / Stale |
| 3     | In Progress |
| 4     | Pending     |

### Models

#### Auth
- **User** — local users (username, email, hashed_password, keycloak_sub)
- **Role** — admin, operator, viewer
- **UserRole** — M2M join table

#### GitHub
- **GithubOrg** — GitHub organization or user account
- **GithubProject** — GitHub repository with metadata (description, README, license, stale tracking)
- **GithubRelease** — GitHub releases for delta tracking

#### GitLab Mirroring
- **GitlabMirror** — GitLab project mirror linked to GithubProject
- **SyncSchedule** — per-mirror cron schedule (is_enabled, use_default, cron_expression)
- **SyncLog** — sync run history (pipeline_id, status_flag, log_output)

#### Images
- **GoldImage** — base OS/runtime image definition (name, os_family, dockerfile, gitlab_project_id)
- **AppImage** — application image (linked to GithubProject + GoldImage, dockerfile)
- **ImageVersion** — unified version table for both gold and app images
  - `image_type`: `gold` | `app`
  - `gold_image_id` / `app_image_id` — one is set, other is NULL
  - `version_tag`, `arch` (amd64/arm64/arm/v7)
  - `sha256_digest`, `cosign_signature`, `is_signed`
  - `status_flag`, `status_text`
- **BuildSchedule** — per-image build schedule
  - `is_enabled` — false = manual only
  - `use_default_schedule` — use system default cron
  - `cron_expression` — custom cron if not default
- **BuildLog** — build run history linked to ImageVersion

---

## Authentication Flow

```
Local login:  POST /auth/login (username+password) → JWT access token
SSO login:    GET /auth/sso/redirect → Keycloak OIDC → callback → JWT
All requests: Authorization: Bearer <JWT>
RBAC:         FastAPI dependency checks role from JWT claims
```

### Roles
| Role     | Permissions                                      |
|----------|--------------------------------------------------|
| admin    | Full access + user/role management               |
| operator | Manage projects, mirrors, images, trigger syncs  |
| viewer   | Read-only access to all resources                |

---

## Mirror Sync Flow

```
Scheduler / Manual trigger
  → FastAPI: GET active mirrors
  → GitLab API: trigger pipeline via token
  → GitLab Runner: execute mirror pipeline
  → GitLab Runner: POST /webhooks/gitlab (pipeline status)
  → FastAPI: write SyncLog entry
  → Frontend: poll/display status
```

### Stale Detection
- `is_stale = (now - last_synced_at) > stale_threshold_days`
- Release delta = count of GithubRelease newer than `last_synced_release_tag`
- UI shows badge "Stale" + "N releases behind"

### Import Existing Mirror
- Operator provides GitHub URL + GitLab URL
- System fetches metadata from both APIs
- Creates GithubOrg (if missing), GithubProject, GitlabMirror with `is_imported=True`

---

## Image Build Flow

```
Scheduler / Manual trigger
  → FastAPI: create ImageVersion (status=Pending)
  → GitLab API: trigger build pipeline
  → GitLab Runner: docker build + push to registry
  → GitLab Runner: POST /webhooks/gitlab (pipeline done)
  → FastAPI: update ImageVersion (sha256, registry_url, status)
  → cosign sign (optional post-build step)
  → BuildLog updated
```

---

## Project Structure

```
BigBug/
├── docker-compose.yml
├── docker-compose.override.yml
├── .env.example
├── plans/
│   └── architecture.md
├── backend/
│   ├── Dockerfile
│   ├── pyproject.toml
│   ├── alembic.ini
│   ├── alembic/
│   │   ├── env.py
│   │   └── versions/
│   ├── tests/
│   │   ├── conftest.py
│   │   ├── test_auth.py
│   │   ├── test_mirrors.py
│   │   └── test_images.py
│   └── app/
│       ├── main.py
│       ├── config.py
│       ├── database.py
│       ├── models/
│       │   ├── __init__.py
│       │   ├── user.py
│       │   ├── role.py
│       │   ├── github_org.py
│       │   ├── github_project.py
│       │   ├── github_release.py
│       │   ├── gitlab_mirror.py
│       │   ├── sync_schedule.py
│       │   ├── sync_log.py
│       │   ├── gold_image.py
│       │   ├── app_image.py
│       │   ├── image_version.py
│       │   ├── build_schedule.py
│       │   └── build_log.py
│       ├── schemas/
│       ├── api/
│       │   ├── auth.py
│       │   ├── admin.py
│       │   ├── projects.py
│       │   ├── mirrors.py
│       │   ├── gold_images.py
│       │   ├── app_images.py
│       │   ├── schedules.py
│       │   └── webhooks.py
│       ├── services/
│       │   ├── auth.py
│       │   ├── github.py
│       │   ├── gitlab.py
│       │   ├── scheduler.py
│       │   └── build.py
│       └── core/
│           ├── security.py
│           ├── rbac.py
│           └── exceptions.py
├── frontend/
│   ├── Dockerfile
│   ├── package.json
│   ├── yarn.lock
│   ├── vite.config.ts
│   ├── tsconfig.json
│   ├── tsconfig.node.json
│   ├── .eslintrc.cjs
│   ├── vitest.config.ts
│   ├── index.html
│   └── src/
│       ├── main.tsx
│       ├── App.tsx
│       ├── store/
│       │   ├── index.ts
│       │   ├── authSlice.ts
│       │   └── api/
│       ├── router/
│       │   ├── index.tsx
│       │   └── ProtectedRoute.tsx
│       ├── pages/
│       │   ├── Login/
│       │   ├── Dashboard/
│       │   ├── Projects/
│       │   ├── Mirrors/
│       │   ├── GoldImages/
│       │   ├── AppImages/
│       │   └── Admin/
│       ├── components/
│       └── types/
└── gitlab-ci/
    ├── mirror-template.yml
    ├── gold-image-template.yml
    └── app-image-template.yml
```
