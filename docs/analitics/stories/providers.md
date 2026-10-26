---
artifact: user-stories
version: "1.0"
created: 2026-10-26
status: complete
context: User stories for the Providers module (resource_providers registry, credentials, trust stores, test/usage lifecycle). Motivating issue #165, part of the analytics wave #154. Architecture decisions: ADR-0007 (Providers V3 registry), ADR-0037 (trust stores), ADR-0010 (Fernet secrets).
---

# User Stories: Providers

User stories for the Providers module: registering external integrations (Git, Docker/OCI, Helm) as Resource Providers, managing their Credentials and Trust Stores, verifying connectivity, sharing with teams, and safely removing them. Personas are the platform roles: admin, operator, viewer.

Flows live in [use cases](../use-cases/providers.md); the failure surface in [edge cases](../edge-cases/providers.md). Consumers of providers (git mirroring, image sync, chart sync, pipelines, GitLab projects) are separate modules; the providers module owns only the registry, credentials, trust stores and the test/usage lifecycle.

---

## US-prov-001: Register an external integration as a provider

### Story Header

| Field        | Value                                          |
| ------------ | ---------------------------------------------- |
| ID           | US-prov-001                                    |
| Title        | Register an external integration as a provider |
| Persona      | operator                                       |
| Priority     | P0                                             |
| Epic/Feature | Providers — registry                           |
| Estimate     | 3 points                                       |

### User Story Statement

**As an** operator,

**I want** to register an external system (GitHub, GitLab, Harbor, a Helm repository, …) as a provider by choosing its subtype and filling in the fields the platform asks for,

**so that** the platform can use this integration in mirrors, image sources, chart sources and pipelines.

### Context & Background

Providers are the single entry point for external integrations (ADR-0007). The set of fields, allowed categories/directions and credential types is defined by the subtype registry — the user must never have to know them in advance; the form is generated from the registry metadata (flow: UC-prov-001). A provider that is registered but not yet verified must be visibly marked as such, not silently assumed to work.

### Acceptance Criteria

#### AC-1: Subtype-driven form

**Given** I open the create-provider form

**When** I choose a domain and subtype

**Then** the form shows exactly the fields, categories, directions and credential types the registry declares for that subtype

#### AC-2: Created provider appears with Pending status

**Given** I submit a valid form

**When** the system creates the provider

**Then** the provider is listed with a Pending status until the first successful connection test

#### AC-3: Registry rules are enforced on the server

**Given** I submit a payload violating a subtype rule (wrong domain, disallowed category/direction, missing required base URL, unknown config key, secret-like config key)

**When** the system processes the request

**Then** it rejects the creation with a field-specific error and stores nothing

### Technical Notes

- Registry metadata is served by `GET /api/providers/types`; creation requires `providers:write` (system providers are not creatable via API at all, regardless of permissions — ADR-0007).
- Secret-like keys in `config` are rejected server-side (deny-list), not only in the UI.

### Dependencies

| Dependency                         | Type    | Status |
| ---------------------------------- | ------- | ------ |
| Credential (optional, see US-prov-003) | Feature | Ready  |

### Out of Scope

- Creating system providers via the API (they are seeded/admin-configured)
- Auto-discovery of integration instances on the network

---

## US-prov-002: Verify that a provider connection works

### Story Header

| Field        | Value                                  |
| ------------ | -------------------------------------- |
| ID           | US-prov-002                            |
| Title        | Verify that a provider connection works |
| Persona      | operator                               |
| Priority     | P0                                     |
| Epic/Feature | Providers — lifecycle                  |
| Estimate     | 2 points                               |

### User Story Statement

**As an** operator,

**I want** to test a provider's connection and see the stored result and reason,

**so that** I know the integration is usable before any module depends on it.

### Context & Background

The connection test is the module's health mechanism: it calls the external system with the provider's credentials and TLS settings, and records the outcome on the provider (flow: UC-prov-002). The result must survive page reloads and be visible to everyone who can see the provider — a green check someone else saw in a chat message is not a status.

### Acceptance Criteria

#### AC-1: Test result is reported immediately

**Given** a provider exists and I may read it

**When** I trigger the connection test

**Then** I see the outcome (success or the failure reason) immediately, whether or not the test passed

#### AC-2: Result is persisted on the provider

**Given** a connection test has run

**When** anyone views the provider afterwards

**Then** they see the last status (OK/Failed/Pending), the status text and when it was last checked

#### AC-3: Failure reason is actionable

**Given** the external system rejects the request (bad credential, insufficient permission, unknown resource, unreachable endpoint)

**When** the test finishes

**Then** the status text names the cause class (authentication failed / lacks permission / not found / request failed) rather than a bare HTTP code

### Technical Notes

- Test requires `providers:write` scoped to the provider (scope-providers, ADR-0004).
- Anonymous providers get a distinct 401 explanation ("requires authentication, only public resources") — EC-prov-021.

### Out of Scope

- Scheduled/automatic re-testing of all providers (health checks of consumers are the consumers' concern)

---

## US-prov-003: Attach credentials to a provider without exposing the secret

### Story Header

| Field        | Value                                                   |
| ------------ | ------------------------------------------------------- |
| ID           | US-prov-003                                             |
| Title        | Attach credentials to a provider without exposing the secret |
| Persona      | operator                                                |
| Priority     | P0                                                      |
| Epic/Feature | Providers — credentials                                 |
| Estimate     | 3 points                                                |

### User Story Statement

**As an** operator,

**I want** to attach a credential (token, basic auth, SSH key) to my provider once and have every use of the provider reuse it,

**so that** the secret is entered a single time, stored encrypted, and never shown to anyone again.

### Context & Background

Credentials are stored Fernet-encrypted (ADR-0010) in a separate `credentials` entity referenced by the provider. Once saved, the secret must never appear in any API response, list, or form — only metadata and a "has credential" indicator (flow: UC-prov-003). A provider without a credential is anonymous and must degrade explicitly (public resources only), not fail mysteriously.

### Acceptance Criteria

#### AC-1: Secret is write-only

**Given** a credential is created or updated with a secret

**When** any provider or credential API response is returned afterwards

**Then** the secret (or an encrypted form of it) is not present in the payload

#### AC-2: Anonymous access is explicit

**Given** I create or edit a provider without a credential

**When** I save it

**Then** the provider is stored as anonymous and its tests/uses distinguish "anonymous" from "wrong credential" in failure messages

#### AC-3: Credential survives provider edits

**Given** a provider has a credential and I edit the provider without touching the secret

**When** the update is saved

**Then** the previously attached credential remains attached

### Technical Notes

- Credential entity has its own admin CRUD (`/api/credentials`, `credentials:read`/`credentials:write`); the provider form may create a credential inline.
- Divergence (requirements gap): see EC-prov-031 — the credential "test" currently records OK without validating the secret; the normative requirement is that a credential test verifies the secret against the target system.

### Out of Scope

- Credential rotation automation (ADR-0010 non-goal)
- Per-user scoping of credentials (credentials are platform-level entities)

---

## US-prov-004: Share a private provider with my team

### Story Header

| Field        | Value                                    |
| ------------ | ---------------------------------------- |
| ID           | US-prov-004                              |
| Title        | Share a private provider with my team    |
| Persona      | operator                                 |
| Priority     | P1                                       |
| Epic/Feature | Providers — visibility                   |
| Estimate     | 2 points                                 |

### User Story Statement

**As an** operator,

**I want** to share my private provider with exactly one team I belong to,

**so that** my teammates can use it in their sources and mirrors without me making it public.

### Context & Background

Visibility is owner/team/public on private-category providers; sharing is bounded to one team (ADR-0007 — multi-sharing is a recorded non-goal). Sharing changes who can see and use the provider; it never changes its category (flow: UC-prov-004).

### Acceptance Criteria

#### AC-1: Team members can see and use the shared provider

**Given** a provider shared with a team I am a member of

**When** I list providers or pick one in a consumer module

**Then** the shared provider is available to me

#### AC-2: Non-members do not see it

**Given** a provider shared with a team I do not belong to

**When** I list providers

**Then** the shared provider is not in my list and direct access is denied

#### AC-3: Unshare reverts to owner-only

**Given** a team-shared provider

**When** the owner unshares it

**Then** visibility returns to owner-only and the team binding is cleared

### Technical Notes

- Share/unshare require the owner (or `providers:read_all`) plus `providers:share`; team membership is verified server-side.
- Only private providers can be shared; already-shared → 409; not shared → 409 on unshare.

### Out of Scope

- Sharing with multiple teams (ceiling recorded in ADR-0007)

---

## US-prov-005: Trust a self-signed endpoint without disabling verification

### Story Header

| Field        | Value                                                    |
| ------------ | -------------------------------------------------------- |
| ID           | US-prov-005                                              |
| Title        | Trust a self-signed endpoint without disabling verification |
| Persona      | operator                                                 |
| Priority     | P1                                                       |
| Epic/Feature | Providers — trust stores                                 |
| Estimate     | 3 points                                                 |

### User Story Statement

**As an** operator,

**I want** to bind a named set of CA certificates (a trust store) to my provider,

**so that** connections to its self-signed HTTPS endpoint are verified against that CA instead of being verified not at all.

### Context & Background

`verify_ssl=false` is a MITM vector (ADR-0028 → ADR-0037); the trust store adds the missing axis "which CAs to trust" while verification stays on (flow: UC-prov-006). The store itself is administered by an admin (US-prov-009); the operator only binds or unbinds it.

### Acceptance Criteria

#### AC-1: Binding switches the trust source, not the check

**Given** a provider with `verify_ssl=true` and a bound trust store containing the endpoint's CA

**When** the platform calls the endpoint

**Then** the certificate is verified against the store's CAs and succeeds without disabling verification

#### AC-2: Explicit unbinding

**Given** a provider with a bound trust store

**When** I clear the store in the provider form and save

**Then** the provider reverts to system trust, and verification remains on

#### AC-3: Disabling verification remains a deliberate act

**Given** any trust store configuration

**When** `verify_ssl` is set to false

**Then** verification is off for that provider regardless of the store (the store never re-enables it)

### Technical Notes

- Requires `trust_stores:read` to see stores in the picker; binding itself is a provider update (`providers:write`).
- Known limitations (PyGitHub, crane, cosign paths ignore custom CAs) are recorded in ADR-0037 "Known gaps" and EC-prov-027.

### Out of Scope

- Editing trust store contents from the provider form (store management is admin-only, US-prov-009)
- mTLS client certificates (ADR-0037 non-goal)

---

## US-prov-006: Browse providers and see where they are used

### Story Header

| Field        | Value                                             |
| ------------ | ------------------------------------------------- |
| ID           | US-prov-006                                       |
| Title        | Browse providers and see where they are used      |
| Persona      | viewer                                            |
| Priority     | P1                                                |
| Epic/Feature | Providers — visibility                            |
| Estimate     | 2 points                                          |

### User Story Statement

**As a** viewer,

**I want** to browse the providers I am allowed to see, filter them by domain/subtype/category/direction, and check where a provider is used,

**so that** I understand the platform's integrations before proposing changes.

### Context & Background

The list is visibility-filtered server-side: public + own + team-shared for regular users; system providers only for privileged roles (ADR-0007 §5). The usage view lists live consumers (pipelines, source repositories, docker image sources, helm chart sources, gitlab projects) — it is the same data the delete gate uses (flow: UC-prov-010).

### Acceptance Criteria

#### AC-1: Filtered browsing

**Given** providers of several domains exist

**When** I filter by domain/subtype/category/direction or open "My providers"

**Then** only matching providers I may see are listed

#### AC-2: System providers are invisible to me

**Given** system providers exist (platform's own GitLab/Harbor)

**When** I browse as a viewer/operator without system privileges

**Then** system providers appear neither in the list nor by direct reference

#### AC-3: Usage is inspectable

**Given** a provider I can read

**When** I open its usage view

**Then** I see the count of live consumers per consumer type

### Technical Notes

- Requires `providers:read`; usage endpoint returns `{resource, count}` rows.
- Hidden system providers respond to direct GET with 404 (existence not leaked), not 403.

### Out of Scope

- Cross-module navigation from usage rows to the consumers' pages (nice-to-have, not required)

---

## US-prov-007: Remove a provider safely

### Story Header

| Field        | Value                              |
| ------------ | ---------------------------------- |
| ID           | US-prov-007                        |
| Title        | Remove a provider safely           |
| Persona      | operator                           |
| Priority     | P1                                 |
| Epic/Feature | Providers — lifecycle              |
| Estimate     | 2 points                           |

### User Story Statement

**As an** operator,

**I want** to delete a provider only when nothing depends on it, and be told exactly what blocks the deletion otherwise,

**so that** I cannot silently break mirrors or pipelines that reference it.

### Context & Background

Deletion is soft, gated twice: protected (system) providers cannot be deleted at all, and any live consumer blocks deletion with the usage list returned to the user (ADR-0007 §5; flow: UC-prov-005). A soft-deleted provider's name becomes reusable.

### Acceptance Criteria

#### AC-1: Deletion is refused while in use

**Given** a provider referenced by at least one live consumer

**When** I request deletion

**Then** the system refuses with 409 and lists the consumers per type, and nothing is deleted

#### AC-2: Protected providers are not deletable

**Given** a system (protected) provider

**When** I request deletion

**Then** the system refuses with 409 regardless of my permissions

#### AC-3: Name is reusable after deletion

**Given** a deleted provider

**When** I create a new provider with the same name

**Then** creation succeeds

### Technical Notes

- Requires `providers:delete` (non-system); consumers counted exclude soft-deleted rows.
- Deletion is soft (`is_deleted`), recoverable at the DB level; no UI restore is required.

### Out of Scope

- Restoring soft-deleted providers from the UI

---

## US-prov-008: Manage credentials centrally

### Story Header

| Field        | Value                              |
| ------------ | ---------------------------------- |
| ID           | US-prov-008                        |
| Title        | Manage credentials centrally       |
| Persona      | admin                              |
| Priority     | P1                                 |
| Epic/Feature | Providers — credentials            |
| Estimate     | 2 points                           |

### User Story Statement

**As an** admin,

**I want** to create, update and retire platform credentials in one place, with every mutation audited,

**so that** secrets are managed under control and their history is traceable.

### Context & Background

Credentials are a first-class entity (types: GitHub token, GitLab token, HTTPS basic, SSH key) encrypted at rest (ADR-0010); all mutations write audit events (ADR-0026). Retirement is a soft delete (flow: UC-prov-009).

### Acceptance Criteria

#### AC-1: CRUD with audit

**Given** I hold `credentials:write`

**When** I create, update, delete or test a credential

**Then** the change is applied and an audit event records who did what and when

#### AC-2: Secrets are never readable

**Given** credentials exist

**When** any credential is listed or fetched

**Then** the response contains metadata and, for SSH keys, the public key — never the secret

#### AC-3: A tested credential shows its state

**Given** a credential was tested

**When** I view it

**Then** I see the test status and when it was last tested

### Technical Notes

- Divergence: the current credential test writes OK without contacting the target system — normative requirement is verification (EC-prov-031, gap).
- Soft-deleted credentials keep a hard-unique name — reusing a retired name is currently impossible (EC-prov-033, gap).

### Out of Scope

- Automatic rotation (ADR-0010 non-goal)

---

## US-prov-009: Manage trust stores centrally

### Story Header

| Field        | Value                              |
| ------------ | ---------------------------------- |
| ID           | US-prov-009                        |
| Title        | Manage trust stores centrally      |
| Persona      | admin                              |
| Priority     | P1                                 |
| Epic/Feature | Providers — trust stores           |
| Estimate     | 2 points                           |

### User Story Statement

**As an** admin,

**I want** to maintain named trust stores — create a store, paste PEM certificates (a chain in one paste is acceptable), inspect fingerprints, and delete a store only when no provider uses it,

**so that** operators can bind a maintained set of CAs instead of disabling verification.

### Context & Background

Trust stores are the ADR-0037 entity: store + certificates, PEM validated server-side, SHA-256 fingerprints for identification, deletion gated by provider usage with the referring providers named (flow: UC-prov-007). PEM contents are public material and are returned as-is — this is deliberate (do not "fix" by encrypting, ADR-0037).

### Acceptance Criteria

#### AC-1: Certificates are validated on entry

**Given** I paste PEM text into a store

**When** I save it

**Then** every certificate block is parsed and validated, invalid input is rejected with a validation error, and each block becomes its own certificate entry (chains are split, suffixed `-1`, `-2`, …)

#### AC-2: Fingerprints identify certificates

**Given** certificates in a store

**When** I view the store

**Then** each certificate shows its SHA-256 fingerprint

#### AC-3: Deletion in use is refused with names

**Given** a store referenced by providers

**When** I request deletion

**Then** the system refuses with 409 listing the providers, and the store is untouched

### Technical Notes

- `trust_stores:read` for admin+operator (operator needs the list to bind), `trust_stores:write` admin-only (ADR-0037 RBAC).

### Out of Scope

- CRL/OCSP, expiry validation in UI, CA rotation automation (ADR-0037 non-goals)

---

## US-prov-010: Pick integration resources through a provider in other modules

### Story Header

| Field        | Value                                                   |
| ------------ | ------------------------------------------------------- |
| ID           | US-prov-010                                             |
| Title        | Pick integration resources through a provider in other modules |
| Persona      | operator                                                |
| Priority     | P1                                                      |
| Epic/Feature | Providers — domain actions                              |
| Estimate     | 3 points                                                |

### User Story Statement

**As an** operator,

**I want** consumer modules (source import, image sources, chart sources) to list groups, repositories, projects or charts through a provider via one uniform action interface,

**so that** every module works the same way against any supported integration.

### Context & Background

Domain actions (`list_groups`, `list_repositories`, `list_projects`, `list_charts`, `get_commit`, `trigger_pipeline`) are dispatched through the registry: a subtype offers a capability only for allowed (category, direction) combinations — `trigger_pipeline` is reserved for the platform's own system/internal GitLab (ADR-0007 §6; flow: UC-prov-008). Client failures are translated to meaningful errors, not raw HTTP dumps.

### Acceptance Criteria

#### AC-1: Capability rules are enforced

**Given** a subtype that does not offer an action for the provider's (category, direction)

**When** the action is requested

**Then** the system refuses with 403 naming the action and the provider combination

#### AC-2: Uniform result shape

**Given** any successful action

**When** the response is returned

**Then** it carries the action name and a list of items, regardless of the subtype

#### AC-3: Client failures are meaningful

**Given** the external system returns 401/403/404 or fails

**When** the action is dispatched

**Then** the error names the cause class and the provider subtype, consistent with the connection-test error semantics

### Technical Notes

- Requires `providers:use` scoped to the provider.
- Consumers call this via the same `/api/providers/{id}/actions/{action}` endpoint the UI uses.

### Out of Scope

- Caching of action results (consumers own their persistence)

---

## US-prov-011: Designate the default provider per scope

### Story Header

| Field        | Value                                    |
| ------------ | ---------------------------------------- |
| ID           | US-prov-011                              |
| Title        | Designate the default provider per scope |
| Persona      | admin                                    |
| Priority     | P2                                       |
| Epic/Feature | Providers — registry                     |
| Estimate     | 1 point                                  |

### User Story Statement

**As an** admin,

**I want** to mark one provider as the default within its (domain, subtype, category, direction) scope,

**so that** consumer modules can preselect a sensible integration without asking me each time.

### Context & Background

Default is a per-scope singleton: setting a new default automatically clears the previous one in the same scope (ADR-0007; enforced additionally by a partial unique index). Only admins may change defaults.

### Acceptance Criteria

#### AC-1: One default per scope

**Given** a scope already has a default provider

**When** an admin sets another provider as default in that scope

**Then** the previous default is cleared and the new one is stored — exactly one default remains

#### AC-2: Non-admins cannot change defaults

**Given** an operator without admin rights

**When** they attempt to set a default

**Then** the system refuses with 403 naming the required rights

### Technical Notes

- Requires `providers_system:write` (or `admin:panel:access`).

### Out of Scope

- Multiple defaults per scope; per-team defaults
