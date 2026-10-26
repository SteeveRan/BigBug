---
artifact: user-stories
version: "1.0"
created: 2026-10-26
status: complete
context: User stories for the Git Mirroring module (GitHub → GitLab). Motivating issue #159, part of the analytics wave #154. Architecture decisions: ADR-0008.
---

# User Stories: Git Mirroring

User stories for the Git Mirroring module: mirror GitHub repositories into GitLab, keep them fresh, verify their integrity, and recover from drift. Personas are the platform roles: admin, operator, viewer.

Flows live in [use cases](../use-cases/git-mirroring.md); the failure surface in [edge cases](../edge-cases/git-mirroring.md). Reports over mirrors are a separate module ([stories/reports](stories/reports.md) — issue #166): story US-gitmrr-009 covers only per-mirror log visibility, not the Reports pages.

---

## US-gitmrr-001: Import a source group from a Git provider

### Story Header

| Field        | Value                                     |
| ------------ | ----------------------------------------- |
| ID           | US-gitmrr-001                             |
| Title        | Import a source group from a Git provider |
| Persona      | operator                                  |
| Priority     | P1                                        |
| Epic/Feature | Git Mirroring — sources                   |
| Estimate     | 3 points                                  |

### User Story Statement

**As an** operator,

**I want** to import a GitHub group (organization) with all its repositories in one action,

**so that** I register a whole source group at once instead of entering repositories one by one.

### Context & Background

Mirroring starts from source inventory. A GitHub organization can hold dozens of repositories; typing them manually does not scale. The platform must resolve the group through a configured Resource Provider and register its repositories as source repositories (flow: UC-gitmrr-001).

### Acceptance Criteria

#### AC-1: Import by group identifier

**Given** a Git provider with valid credentials exists

**When** I submit an import with the provider and a group identifier

**Then** the system registers the group and all repositories visible to those credentials, and reports the registered count

#### AC-2: Discovery state visible

**Given** an import succeeded

**When** I open the Sources page

**Then** the imported group and its repositories are listed

#### AC-3: Refresh re-reads the source

**Given** an imported group exists

**When** I trigger a refresh

**Then** the system re-reads the repository list from the provider and reflects newly appeared or removed repositories

### Technical Notes

- Import requires `source_groups:write`; list/detail require `source_groups:read`; refresh requires `source_groups:refresh`.
- Repository metadata fetching happens in the background after registration; the list must not block on it.

### Dependencies

| Dependency                                | Type    | Status |
| ----------------------------------------- | ------- | ------ |
| Resource Provider with GitHub credentials | Feature | Ready  |

### Out of Scope

- Selecting a subset of repositories during import (import is all-or-report)
- Automatic re-import on a schedule

---

## US-gitmrr-002: Create a mirror for a source repository

### Story Header

| Field        | Value                                   |
| ------------ | --------------------------------------- |
| ID           | US-gitmrr-002                           |
| Title        | Create a mirror for a source repository |
| Persona      | operator                                |
| Priority     | P0                                      |
| Epic/Feature | Git Mirroring — mirrors                 |
| Estimate     | 3 points                                |

### User Story Statement

**As an** operator,

**I want** to create a mirror that binds a source repository to a target GitLab project,

**so that** the platform can keep the target in sync with the source.

### Context & Background

A mirror is the central record of the module. Creating it must produce a mirror that is ready to sync: the target GitLab project must exist and be bound to the mirror at creation time. A mirror that cannot sync because its target is unbound is a half-product — the system must either guide the operator through binding as part of creation (flow: UC-gitmrr-002) or clearly mark the mirror as not-ready-to-sync (edge cases EC-gitmrr-008..010).

### Acceptance Criteria

#### AC-1: Mirror bound to an existing target

**Given** a source repository and an existing GitLab project (created via the GitLab Projects module)

**When** I create a mirror selecting the source repository and the target project

**Then** the system stores the mirror with the target project bound and a Pending status

#### AC-2: Creation without a bound target is explicit

**Given** no target GitLab project is bound at creation

**When** I create the mirror

**Then** the system stores the mirror with a status that unambiguously means "target not bound yet" — not a generic Pending — and shows on the mirror what is missing before the first sync can succeed

#### AC-3: First sync of an unbound mirror explains the gap

**Given** a mirror with no bound target project

**When** a sync is attempted (manually or by schedule)

**Then** the system refuses the run with a message that names the missing prerequisite and links to where the target project can be created/bound

#### AC-4: Duplicate source is warned, not blocked

**Given** another active mirror already references the same source repository

**When** I create a mirror for it

**Then** the system shows a duplicate warning, records the warning in the audit log, and still creates the mirror on confirmation

### Technical Notes

- Creating a mirror requires `mirrors:write`.
- The sync engine performs no git operations itself; it triggers the CI pipeline of the target project (ADR-0008). A bound target project id is therefore a hard prerequisite of every sync.

### Dependencies

| Dependency                                       | Type   | Status |
| ------------------------------------------------ | ------ | ------ |
| US-gitmrr-001 / US-gitmrr-002 (source inventory) | Story  | Ready  |
| GitLab Projects module (target project creation) | Module | Ready  |

### Out of Scope

- Automatic creation of the GitLab project during mirror creation (decided in grill #142)

---

## US-gitmrr-003: Bulk create mirrors

### Story Header

| Field        | Value                   |
| ------------ | ----------------------- |
| ID           | US-gitmrr-003           |
| Title        | Bulk create mirrors     |
| Persona      | operator                |
| Priority     | P2                      |
| Epic/Feature | Git Mirroring — mirrors |
| Estimate     | 2 points                |

### User Story Statement

**As an** operator,

**I want** to create mirrors for many source repositories in one action,

**so that** onboarding a large source group does not mean repeating the create dialog dozens of times.

### Context & Background

Source groups regularly exceed 50 repositories. Bulk creation must validate the whole batch up front and report per-item outcomes (flow: UC-gitmrr-003).

### Acceptance Criteria

#### AC-1: Batch up to 500

**Given** up to 500 source repositories

**When** I submit a bulk creation

**Then** the system creates one mirror per item in the single request

#### AC-2: Over-limit batch rejected up front

**Given** a batch larger than 500

**When** I submit it

**Then** the system rejects the whole request with a message stating the limit, and creates nothing

#### AC-3: Missing sources reported

**Given** the batch references at least one unknown source repository

**When** I submit it

**Then** the system rejects the request listing the unknown identifiers, and creates nothing

### Technical Notes

- Requires `mirrors:write`. Same duplicate-warning semantics as single creation (US-gitmrr-002 AC-4).

### Dependencies

| Dependency    | Type  | Status |
| ------------- | ----- | ------ |
| US-gitmrr-002 | Story | Ready  |

### Out of Scope

- Partial success mode (all-or-nothing per request)

---

## US-gitmrr-004: Run a mirror sync on demand

### Story Header

| Field        | Value                       |
| ------------ | --------------------------- |
| ID           | US-gitmrr-004               |
| Title        | Run a mirror sync on demand |
| Persona      | operator                    |
| Priority     | P0                          |
| Epic/Feature | Git Mirroring — sync        |
| Estimate     | 2 points                    |

### User Story Statement

**As an** operator,

**I want** to trigger a sync of a mirror immediately,

**so that** I can bring a target up to date without waiting for the schedule (e.g. right after a release).

### Context & Background

The sync transfers code by triggering the CI pipeline of the target GitLab project (ADR-0008). The operator triggers; the pipeline runs; results come back asynchronously (US-gitmrr-008). Flow: UC-gitmrr-004.

### Acceptance Criteria

#### AC-1: Trigger accepted and run recorded

**Given** a mirror with a bound target project and a pipeline configured on its sync group

**When** I trigger sync

**Then** the system records a sync-run entry, marks the mirror In Progress, and returns success

#### AC-2: Misconfiguration is a named error

**Given** the mirror's sync group has no pipeline configured

**When** I trigger sync

**Then** the system records a skipped run with the reason "no pipeline configured" and shows it on the mirror

#### AC-3: Outcome visible

**Given** a triggered sync has finished on the GitLab side

**When** I view the mirror

**Then** I can see the sync outcome (completed/failed) and its timestamp

### Technical Notes

- Requires `mirrors:sync`. Freshness trigger uses the same permission.

### Dependencies

| Dependency                        | Type  | Status |
| --------------------------------- | ----- | ------ |
| US-gitmrr-002                     | Story | Ready  |
| US-gitmrr-005 (pipeline assigned) | Story | Ready  |

### Out of Scope

- Progress streaming while the pipeline runs (status is updated on completion events)

---

## US-gitmrr-005: Schedule automatic syncs via a sync group

### Story Header

| Field        | Value                                     |
| ------------ | ----------------------------------------- |
| ID           | US-gitmrr-005                             |
| Title        | Schedule automatic syncs via a sync group |
| Persona      | operator                                  |
| Priority     | P0                                        |
| Epic/Feature | Git Mirroring — sync groups               |
| Estimate     | 3 points                                  |

### User Story Statement

**As an** operator,

**I want** to configure a cron schedule and concurrency limit on a sync group,

**so that** all mirrors in the group are kept in sync automatically without per-mirror setup, and the source API is not hammered.

### Context & Background

The sync group is the unit of scheduling (ADR-0008): cron strings for sync and freshness, concurrency caps, enable/disable. A schedule change must take effect without redeploying or restarting the platform (flow: UC-gitmrr-005).

### Acceptance Criteria

#### AC-1: Cron schedule drives runs

**Given** a sync group with an enabled sync cron

**When** the cron fires

**Then** the system syncs the group's mirrors within the configured concurrency limit

#### AC-2: Schedule change applies without restart

**Given** a sync group whose cron or enabled flag I just changed

**When** the next cron time arrives

**Then** the runs follow the new configuration — no application restart in between

#### AC-3: Disabled group does not run

**Given** a disabled sync group

**When** its cron time passes

**Then** no sync runs are started for its mirrors

#### AC-4: Invalid cron rejected at save

**Given** I enter a malformed cron expression (or one longer than the 100-character limit)

**When** I save the sync group

**Then** the system rejects the change with a field error and keeps the previous schedule

#### AC-5: Mirrors can be assigned in bulk

**Given** up to 100 mirrors

**When** I bulk-assign them to a sync group

**Then** all listed mirrors belong to that group; mirrors from other groups are moved

### Technical Notes

- `sync_groups:read/write/delete`; bulk assign ≤ 100 per request; group deletion is prohibited for the default group and moves its mirrors to the default group.

### Dependencies

| Dependency                              | Type  | Status |
| --------------------------------------- | ----- | ------ |
| US-gitmrr-002                           | Story | Ready  |
| US-gitmrr-002 (pipeline bound to group) | Story | Ready  |

### Out of Scope

- Per-mirror cron overrides (scheduling unit is the group)

---

## US-gitmrr-006: Check mirror freshness

### Story Header

| Field        | Value                  |
| ------------ | ---------------------- |
| ID           | US-gitmrr-006          |
| Title        | Check mirror freshness |
| Persona      | operator               |
| Priority     | P1                     |
| Epic/Feature | Git Mirroring — health |
| Estimate     | 2 points               |

### User Story Statement

**As an** operator,

**I want** a cheap on-demand freshness comparison between source and target,

**so that** I can see whether a mirror lags behind its source without running a full sync.

### Context & Background

Freshness compares the last known source commit state with the recorded state (ADR-0008). It is safe to run often, on demand and by schedule. Flow: UC-gitmrr-006.

### Acceptance Criteria

#### AC-1: Verdict is one of three

**Given** a mirror with a linked source repository

**When** I trigger a freshness check

**Then** the system records a result of FRESH, STALE, or ERROR with a timestamp

#### AC-2: Stale is visible on the mirror

**Given** a freshness check returned STALE

**When** I view the mirror list or detail

**Then** the mirror carries a warning state, and diverged-commit accounting is updated

#### AC-3: Unverifiable source reported as error

**Given** the source provider is unreachable or has no valid credentials

**When** I trigger a freshness check

**Then** the system records an ERROR result with the provider's reason; the previous mirror state is not overwritten by a fake FRESH

### Technical Notes

- Requires `mirrors:sync` (same as manual sync).

### Dependencies

| Dependency    | Type  | Status |
| ------------- | ----- | ------ |
| US-gitmrr-002 | Story | Ready  |

### Out of Scope

- Automatic remediation on STALE (operator decides to re-sync)

---

## US-gitmrr-007: Verify mirror integrity

### Story Header

| Field        | Value                   |
| ------------ | ----------------------- |
| ID           | US-gitmrr-007           |
| Title        | Verify mirror integrity |
| Persona      | operator                |
| Priority     | P1                      |
| Epic/Feature | Git Mirroring — health  |
| Estimate     | 2 points                |

### User Story Statement

**As an** operator,

**I want** to compare the HEAD commits of source and target to detect manual changes to the target,

**so that** I can trust that a mirror is a faithful copy and notice target drift.

### Context & Background

A mirror exists to be trusted. Integrity check is the direct HEAD comparison (ADR-0008) with verdicts MATCH / MISMATCH / ERROR. The operation is a read of external state but a sensitive one — it is guarded by its own permission. Flow: UC-gitmrr-007.

### Acceptance Criteria

#### AC-1: Verdict is one of three

**Given** a mirror with a bound target project

**When** I run the integrity check

**Then** the system records MATCH, MISMATCH, or ERROR in the mirror's log and updates the mirror state accordingly

#### AC-2: Mismatch is visible and counted

**Given** an integrity check returned MISMATCH

**When** I view the mirror

**Then** the mirror shows a warning state with the diverged-commit count incremented

#### AC-3: Permission enforced

**Given** a user without the integrity-check permission

**When** they attempt the integrity-check operation

**Then** the system denies it with 403 — the endpoint is not open to any authenticated user

### Technical Notes

- Intended permission `mirrors:integrity_check` (seeded; admin+operator). Current code does not enforce it — divergence recorded in edge cases (EC-gitmrr-018) and grill #139 (C3).

### Dependencies

| Dependency    | Type  | Status |
| ------------- | ----- | ------ |
| US-gitmrr-002 | Story | Ready  |

### Out of Scope

- Automated integrity schedule (runs are user- or group-triggered)

---

## US-gitmrr-008: Track sync results of a mirror

### Story Header

| Field        | Value                          |
| ------------ | ------------------------------ |
| ID           | US-gitmrr-008                  |
| Title        | Track sync results of a mirror |
| Persona      | viewer                         |
| Priority     | P1                             |
| Epic/Feature | Git Mirroring — observability  |
| Estimate     | 2 points                       |

### User Story Statement

**As a** viewer,

**I want** to see the status and history of a mirror's sync runs,

**so that** I can answer "is this mirror up to date, and what happened in the last run" without asking an operator.

### Context & Background

Every sync, freshness, and integrity operation leaves a log entry (ADR-0008). The pipeline completion event must finalize the mirror state — a mirror must not stay In Progress after its pipeline has finished (flow: UC-gitmrr-008; gap analyzed in grill #142, H4).

### Acceptance Criteria

#### AC-1: Terminal states reachable

**Given** a sync run has finished (success or failure on the GitLab side)

**When** the completion event is processed

**Then** the mirror's status reflects the outcome — it never remains In Progress indefinitely

#### AC-2: History is browsable

**Given** a mirror with past operations

**When** I open its logs

**Then** I see the chronological list of runs with type, outcome, and timestamps

#### AC-3: Audit trail exists

**Given** a sync completed or failed

**When** I inspect the audit log

**Then** the corresponding audit event is recorded

### Technical Notes

- Reading requires `mirrors:read`.

### Dependencies

| Dependency    | Type  | Status |
| ------------- | ----- | ------ |
| US-gitmrr-004 | Story | Ready  |

### Out of Scope

- Reports pages (separate module, issue #166)

---

## US-gitmrr-009: Discover orphaned GitLab projects

### Story Header

| Field        | Value                             |
| ------------ | --------------------------------- |
| ID           | US-gitmrr-009                     |
| Title        | Discover orphaned GitLab projects |
| Persona      | admin                             |
| Priority     | P1                                |
| Epic/Feature | Git Mirroring — orphaned          |
| Estimate     | 2 points                          |

### User Story Statement

**As an** admin,

**I want** to discover GitLab projects on managed target instances that no mirror references,

**so that** I can detect drift between the platform's records and reality in GitLab.

### Context & Background

Orphaned discovery is an on-demand report over target GitLab instances: projects whose ids are not referenced by any active mirror (ADR-0008). Discovery only reports; remediation is a separate story (US-gitmrr-010). Flow: UC-gitmrr-009.

### Acceptance Criteria

#### AC-1: Orphans listed

**Given** a target GitLab instance with projects not referenced by mirrors

**When** I run discovery

**Then** each unreferenced project is listed with its path, web URL, and detection time

#### AC-2: Permission enforced

**Given** a user without the orphaned-management permission

**When** they attempt discovery

**Then** the system denies it with 403

#### AC-3: No providers is actionable, not a generic failure

**Given** no active GitLab providers are configured

**When** I open the orphaned page or run discovery

**Then** the system shows an actionable empty state ("configure a GitLab provider") with a link to provider settings — not a generic load failure

#### AC-4: One bad provider does not kill the scan

**Given** two GitLab providers, one unreachable

**When** I run discovery

**Then** the reachable provider is still scanned and its results returned; the failed provider is reported separately

### Technical Notes

- Intended permission `mirrors:manage_orphaned` (seeded; admin). Current code guards only by authentication — divergence recorded (EC-gitmrr-019) and grill #139 (C3) / #140 (H2).

### Dependencies

| Dependency                                  | Type    | Status |
| ------------------------------------------- | ------- | ------ |
| Resource Provider (GitLab, system/internal) | Feature | Ready  |

### Out of Scope

- Remediation actions (US-gitmrr-010)

---

## US-gitmrr-010: Relink or remove an orphaned mirror

### Story Header

| Field        | Value                               |
| ------------ | ----------------------------------- |
| ID           | US-gitmrr-010                       |
| Title        | Relink or remove an orphaned mirror |
| Persona      | admin                               |
| Priority     | P1                                  |
| Epic/Feature | Git Mirroring — orphaned            |
| Estimate     | 3 points                            |

### User Story Statement

**As an** admin,

**I want** to re-point a mirror's record at a different target path, or delete a stale orphan record,

**so that** orphaned entries can be resolved in the platform instead of hand-editing the database.

### Context & Background

The UI offers relink (reassign/move target) and delete actions for orphaned mirrors, but the backend endpoints do not exist — the flow dead-ends with guaranteed errors (audit C4, grill #140). This story states the required behavior: the remediation operations must exist at the platform boundary, be permission-guarded, and give explicit confirmation for destructive steps (flow: UC-gitmrr-009).

### Acceptance Criteria

#### AC-1: Relink operations exist end-to-end

**Given** an orphaned mirror entry

**When** I reassign it to another sync group or move its target path

**Then** the operation succeeds at the platform boundary and the mirror record reflects the change

#### AC-2: Delete is confirmed and reversible

**Given** an orphaned mirror entry

**When** I delete it with explicit confirmation

**Then** the mirror record is soft-deleted (recoverable within the retention window) and the GitLab project itself is never touched

#### AC-3: Permissions enforced on every remediation action

**Given** a user with read-only rights

**When** they attempt any relink/delete action

**Then** the system denies the action with 403

### Technical Notes

- Actions gated by `mirrors:write` (relink) and `mirrors:delete` (delete) — matching the frontend's existing PermissionGate usage. Implementation tracked in grill #140.

### Dependencies

| Dependency    | Type  | Status |
| ------------- | ----- | ------ |
| US-gitmrr-009 | Story | Ready  |

### Out of Scope

- Automatic (unattended) remediation of orphans — always a human action (ADR-0008 non-goal)

---

## US-gitmrr-011: Delete and restore a mirror safely

### Story Header

| Field        | Value                              |
| ------------ | ---------------------------------- |
| ID           | US-gitmrr-011                      |
| Title        | Delete and restore a mirror safely |
| Persona      | operator                           |
| Priority     | P1                                 |
| Epic/Feature | Git Mirroring — lifecycle          |
| Estimate     | 2 points                           |

### User Story Statement

**As an** operator,

**I want** mirror deletion to be a reversible soft delete with a retention window, and the target GitLab project to survive it,

**so that** an accidental deletion costs nothing, and cleanup never destroys data in GitLab.

### Context & Background

Deletion is soft with a 30-day retention; a daily cleanup physically removes expired records in FK order and never touches GitLab projects (ADR-0008). Flow: UC-gitmrr-010.

### Acceptance Criteria

#### AC-1: Soft delete is reversible

**Given** a deleted mirror within the retention window

**When** I restore it

**Then** the mirror and its cascade-deleted source repository are active again

#### AC-2: Target project survives

**Given** I delete a mirror (soft or via retention expiry)

**When** cleanup removes the record

**Then** the target GitLab project is not modified or deleted

#### AC-3: Retention enforced

**Given** a mirror soft-deleted longer than the retention period (30 days)

**When** the daily cleanup runs

**Then** the record is physically removed, and the removal is recorded in the audit log

### Technical Notes

- Delete/restore require `mirrors:delete`.

### Dependencies

| Dependency    | Type  | Status |
| ------------- | ----- | ------ |
| US-gitmrr-002 | Story | Ready  |

### Out of Scope

- Configuring the retention period per deployment (single platform setting)

---

## US-gitmrr-012: Adopt an existing GitLab project as a mirror

### Story Header

| Field        | Value                                        |
| ------------ | -------------------------------------------- |
| ID           | US-gitmrr-012                                |
| Title        | Adopt an existing GitLab project as a mirror |
| Persona      | operator                                     |
| Priority     | P2                                           |
| Epic/Feature | Git Mirroring — lifecycle                    |
| Estimate     | 2 points                                     |

### User Story Statement

**As an** operator,

**I want** to register a GitLab project that already receives code from elsewhere as a managed mirror,

**so that** pre-existing mirroring setups come under platform management without recreating them.

### Context & Background

Adoption registers the mirror with an OK initial state and records the last known source commit. Adoption must produce the same sync-ready binding as US-gitmrr-002 — including the target project binding (edge cases EC-gitmrr-010..012).

### Acceptance Criteria

#### AC-1: Adopted mirror is tracked

**Given** an existing GitLab project and its GitHub source

**When** I import it as a mirror

**Then** the mirror is registered with an OK state and the last known source commit recorded

#### AC-2: Adoption without a bound target is explicit

**Given** the adopted project cannot be bound to a target project record

**When** the import completes

**Then** the mirror is marked with the not-ready-to-sync status per US-gitmrr-002 AC-2 — not silently OK

### Technical Notes

- Requires `mirrors:import`.

### Dependencies

| Dependency    | Type  | Status |
| ------------- | ----- | ------ |
| US-gitmrr-002 | Story | Ready  |

### Out of Scope

- Automatic discovery of adoptable projects
