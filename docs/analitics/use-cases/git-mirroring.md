---
artifact: use-case
version: "1.0"
---

# UC-gitmrr-001: Import a source group from a Git provider

> Fully-dressed use case, adapted from A. Cockburn, "Writing Effective Use Cases" (2001).
> A use case describes WHAT the system does at its boundary, observable from the
> outside. It is an analysis artifact: no UI design, no implementation details.

## Header

| Field            | Value                                            |
| ---------------- | ------------------------------------------------ |
| ID               | UC-gitmrr-001                                    |
| Name             | Import a source group from a Git provider        |
| Goal level       | user-goal                                        |
| Scope            | Git Mirroring module                             |
| Primary actor    | operator                                         |
| Secondary actors | Git provider API (GitHub / GitLab / Generic Git) |
| Traces to        | US-gitmrr-001                                    |

## Stakeholders and Interests

| Stakeholder | Interest                                                             |
| ----------- | -------------------------------------------------------------------- |
| operator    | Register all repositories of a group without manual one-by-one entry |
| viewer      | See discovered repositories in the Sources tab                       |

## Preconditions

- Operator is authenticated and holds `source_groups:write`.
- At least one Git provider with credentials exists (status OK).

## Success Guarantee (Postconditions)

- The group and all discovered repositories exist in BigBug as source records.
- Minimal guarantee: on partial failure, already-registered repositories are kept
  and the failure reason is visible to the operator.

## Trigger

Operator submits a group import (provider + group identifier).

## Main Success Scenario

| Step | Actor                                                       | System                                                                                                                       |
| ---- | ----------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------- |
| 1    | Operator selects a provider and enters the group identifier |                                                                                                                              |
| 2    |                                                             | System resolves the group via the provider API and lists its repositories                                                    |
| 3    | Operator confirms the import                                |                                                                                                                              |
| 4    |                                                             | System stores the group, creates source-repository records, and reports the count; metadata fetch proceeds in the background |

## Extensions (Alternative Flows)

| At step | Condition                                         | Handling                                                                                  |
| ------- | ------------------------------------------------- | ----------------------------------------------------------------------------------------- |
| 2       | Group not found or not visible to the credentials | System reports "group not found"; nothing is stored (EC-gitmrr-001)                       |
| 2       | Provider API timeout / rate limit / TLS failure   | System reports failure with the provider reason; nothing is stored (EC-gitmrr-002)        |
| 2       | No Git provider configured                        | System shows an actionable state with a link to provider settings (EC-gitmrr-003)         |
| 2       | Group already imported                            | System reports the conflict; existing records are left unchanged (EC-gitmrr-004)          |
| 4       | Some repositories fail to register                | System keeps the successful ones and reports the failed list with reasons (EC-gitmrr-005) |

## Sub-variations

| At step | Variation                                              |
| ------- | ------------------------------------------------------ |
| 1       | Operator imports a single repository without its group |

## Related Artifacts

- User stories: [US-gitmrr-001](../stories/git-mirroring.md)
- Edge-case rows: docs/analitics/edge-cases/git-mirroring.md "Import source group"
- Open questions: none

---

# UC-gitmrr-002: Create a mirror

## Header

| Field            | Value                |
| ---------------- | -------------------- |
| ID               | UC-gitmrr-002        |
| Name             | Create a mirror      |
| Goal level       | user-goal            |
| Scope            | Git Mirroring module |
| Primary actor    | operator             |
| Secondary actors | —                    |
| Traces to        | US-gitmrr-002        |

## Stakeholders and Interests

| Stakeholder | Interest                                               |
| ----------- | ------------------------------------------------------ |
| operator    | A mirror record that is ready to sync                  |
| admin       | Duplicate sources are visible, not silently duplicated |

## Preconditions

- Operator holds `mirrors:write`.
- The source repository exists (registered via UC-gitmrr-001 or manually).

## Success Guarantee (Postconditions)

- The mirror exists with the target GitLab project bound and Pending status; the first sync can be triggered.
- Minimal guarantee: on validation failure, no mirror record is left behind.

## Trigger

Operator submits the mirror creation form (source, target namespace/name, sync group).

## Main Success Scenario

| Step | Actor                                                                         | System                                                                                              |
| ---- | ----------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------- |
| 1    | Operator selects the source repository, target namespace/name, and sync group |                                                                                                     |
| 2    |                                                                               | System validates the source and the sync group exist                                                |
| 3    |                                                                               | System checks for an active mirror with the same source; none found                                 |
| 4    |                                                                               | System stores the mirror with the target project bound and Pending status                           |
| 5    |                                                                               | System reports the created mirror; if the group has a pipeline, the first sync starts automatically |

## Extensions (Alternative Flows)

| At step | Condition                                  | Handling                                                                                                                                                  |
| ------- | ------------------------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 2       | Source repository unknown                  | System rejects with a validation error; nothing stored (EC-gitmrr-006)                                                                                    |
| 3       | Duplicate source exists                    | System warns (and writes an audit warning), proceeds on confirmation (EC-gitmrr-007)                                                                      |
| 4       | Target GitLab project not bound            | System stores the mirror in a not-ready-to-sync state that names the missing prerequisite; a later sync refuses with the same explanation (EC-gitmrr-008) |
| 4       | Target namespace/name empty or over limits | System rejects with field errors (EC-gitmrr-009)                                                                                                          |
| 5       | Automatic first sync fails                 | System keeps the created mirror and shows the sync failure reason — creation itself succeeds (EC-gitmrr-010)                                              |

## Sub-variations

| At step | Variation                                                                              |
| ------- | -------------------------------------------------------------------------------------- |
| 1       | Operator pre-checks duplicates via the check-duplicates action before filling the form |

## Related Artifacts

- User stories: [US-gitmrr-002](../stories/git-mirroring.md)
- Edge-case rows: docs/analitics/edge-cases/git-mirroring.md "Create mirror"
- Open questions: auto-creation of the GitLab project at mirror creation — grill #142

---

# UC-gitmrr-003: Bulk create mirrors

## Header

| Field            | Value                |
| ---------------- | -------------------- |
| ID               | UC-gitmrr-003        |
| Name             | Bulk create mirrors  |
| Goal level       | user-goal            |
| Scope            | Git Mirroring module |
| Primary actor    | operator             |
| Secondary actors | —                    |
| Traces to        | US-gitmrr-003        |

## Preconditions

- Operator holds `mirrors:write`.
- Source repositories for the batch exist.

## Success Guarantee (Postconditions)

- One mirror per item of a valid batch exists.
- Minimal guarantee: on rejection, nothing is created (all-or-nothing per request).

## Trigger

Operator submits a batch creation (up to 500 items).

## Main Success Scenario

| Step | Actor                                                                     | System                                                                                              |
| ---- | ------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------- |
| 1    | Operator selects up to 500 source repositories and common target settings |                                                                                                     |
| 2    |                                                                           | System validates the batch size and that all listed sources exist                                   |
| 3    |                                                                           | System creates the mirrors with Pending status and reports per-item results with duplicate warnings |

## Extensions (Alternative Flows)

| At step | Condition                        | Handling                                                                                  |
| ------- | -------------------------------- | ----------------------------------------------------------------------------------------- |
| 2       | Batch larger than 500            | System rejects the whole request stating the limit; nothing created (EC-gitmrr-011)       |
| 2       | Some source repositories unknown | System rejects the whole request listing the unknown ids; nothing created (EC-gitmrr-012) |
| 2       | Empty batch                      | System rejects with a validation error (EC-gitmrr-013)                                    |

## Related Artifacts

- User stories: [US-gitmrr-003](../stories/git-mirroring.md)
- Edge-case rows: docs/analitics/edge-cases/git-mirroring.md "Bulk create mirrors"

---

# UC-gitmrr-004: Run a mirror sync on demand

## Header

| Field            | Value                              |
| ---------------- | ---------------------------------- |
| ID               | UC-gitmrr-004                      |
| Name             | Run a mirror sync on demand        |
| Goal level       | user-goal                          |
| Scope            | Git Mirroring module               |
| Primary actor    | operator                           |
| Secondary actors | GitLab API (target), GitLab Runner |
| Traces to        | US-gitmrr-004                      |

## Preconditions

- Operator holds `mirrors:sync`.
- The mirror has a sync group; target project bound (per US-gitmrr-002 AC-2 the not-ready state is named explicitly otherwise).

## Success Guarantee (Postconditions)

- A sync-run record exists; the mirror is marked In Progress; the result will arrive as a completion event (UC-gitmrr-005).
- Minimal guarantee: a failed trigger leaves the mirror in its previous state with the failure recorded.

## Trigger

Operator presses "Sync" on a mirror (or a schedule fires — UC-gitmrr-006).

## Main Success Scenario

| Step | Actor                  | System                                                                                |
| ---- | ---------------------- | ------------------------------------------------------------------------------------- |
| 1    | Operator triggers sync |                                                                                       |
| 2    |                        | System resolves the group's pipeline and validates prerequisites                      |
| 3    |                        | System creates the pipeline run on the target GitLab with the mirror's variables      |
| 4    |                        | System records the run, marks the mirror In Progress, reports success to the operator |

## Extensions (Alternative Flows)

| At step | Condition                        | Handling                                                                                                     |
| ------- | -------------------------------- | ------------------------------------------------------------------------------------------------------------ |
| 2       | Mirror has no sync group         | System refuses with a message naming the prerequisite (EC-gitmrr-014)                                        |
| 2       | Group has no pipeline configured | System records a skipped run with reason "no pipeline configured"; no error is raised (EC-gitmrr-015)        |
| 2       | Pipeline has no GitLab provider  | System refuses with a message naming the pipeline (EC-gitmrr-016)                                            |
| 2       | Target project not bound         | System refuses with the not-ready explanation and a link to remediation (EC-gitmrr-008)                      |
| 3       | GitLab API rejects or times out  | System records the failed run with the provider reason; mirror returns to its previous state (EC-gitmrr-017) |

## Related Artifacts

- User stories: [US-gitmrr-004](../stories/git-mirroring.md)
- Edge-case rows: docs/analitics/edge-cases/git-mirroring.md "Sync mirror"

---

# UC-gitmrr-005: Record a sync completion event

## Header

| Field            | Value                                 |
| ---------------- | ------------------------------------- |
| ID               | UC-gitmrr-005                         |
| Name             | Record a sync completion event        |
| Goal level       | user-goal                             |
| Scope            | Git Mirroring module                  |
| Primary actor    | GitLab (external system, via Webhook) |
| Secondary actors | —                                     |
| Traces to        | US-gitmrr-008                         |

## Stakeholders and Interests

| Stakeholder | Interest                                                   |
| ----------- | ---------------------------------------------------------- |
| operator    | Mirror status reflects reality after the pipeline finishes |
| admin       | Fake completion events cannot corrupt the state            |

## Preconditions

- A sync run was triggered by the platform (a run record exists).

## Success Guarantee (Postconditions)

- The run record carries the final status; the mirror's status reflects the outcome and never remains In Progress after a terminal event.
- Minimal guarantee: an unmatchable event is ignored without corrupting any record.

## Trigger

GitLab sends a pipeline event webhook.

## Main Success Scenario

| Step | Actor                              | System                                                                                                   |
| ---- | ---------------------------------- | -------------------------------------------------------------------------------------------------------- |
| 1    | GitLab delivers the pipeline event |                                                                                                          |
| 2    |                                    | System verifies the webhook authenticity                                                                 |
| 3    |                                    | System matches the event to the run record                                                               |
| 4    |                                    | System updates the run status, finalizes the mirror state (completed/failed), and writes the audit event |

## Extensions (Alternative Flows)

| At step | Condition                                                   | Handling                                                                           |
| ------- | ----------------------------------------------------------- | ---------------------------------------------------------------------------------- |
| 2       | Webhook lacks valid authentication                          | System rejects the event without processing (EC-gitmrr-020)                        |
| 3       | No run record matches the event                             | System ignores the event and reports it as ignored (EC-gitmrr-021)                 |
| 4       | Event lost / GitLab unreachable (no terminal event arrives) | The run stays In Progress; expiry handling per grill #142 decision (EC-gitmrr-022) |

## Related Artifacts

- User stories: [US-gitmrr-008](../stories/git-mirroring.md)
- Edge-case rows: docs/analitics/edge-cases/git-mirroring.md "Sync result intake"
- Open questions: finalization mechanism (webhook-direct vs task-queue) — grill #142

---

# UC-gitmrr-006: Schedule syncs for a sync group

## Header

| Field            | Value                           |
| ---------------- | ------------------------------- |
| ID               | UC-gitmrr-006                   |
| Name             | Schedule syncs for a sync group |
| Goal level       | user-goal                       |
| Scope            | Git Mirroring module            |
| Primary actor    | operator                        |
| Secondary actors | —                               |
| Traces to        | US-gitmrr-005                   |

## Preconditions

- Operator holds `sync_groups:write`.
- The sync group exists (the default group exists always).

## Success Guarantee (Postconditions)

- The group's schedule is stored and drives automatic runs without an application restart.
- Minimal guarantee: an invalid schedule change is rejected and the previous schedule keeps working.

## Trigger

Operator edits the group's cron/enabled/concurrency settings.

## Main Success Scenario

| Step | Actor                                  | System                                                           |
| ---- | -------------------------------------- | ---------------------------------------------------------------- |
| 1    | Operator submits new schedule settings |                                                                  |
| 2    |                                        | System validates cron syntax and limits                          |
| 3    |                                        | System stores the settings and applies them to the live schedule |
| 4    |                                        | System reports the next run according to the new settings        |

## Extensions (Alternative Flows)

| At step | Condition                            | Handling                                                                         |
| ------- | ------------------------------------ | -------------------------------------------------------------------------------- |
| 2       | Malformed cron or over-limit string  | System rejects with a field error; previous schedule unchanged (EC-gitmrr-023)   |
| 2       | Name conflict on create              | System reports that a group with the name exists (EC-gitmrr-024)                 |
| 3       | Group disabled                       | No runs start; schedule kept for later (EC-gitmrr-025)                           |
| 3       | Operator deletes a non-default group | Mirrors migrate to the default group; deletion recorded in audit (EC-gitmrr-026) |
| 3       | Operator deletes the default group   | System refuses: the default group cannot be deleted (EC-gitmrr-027)              |

## Related Artifacts

- User stories: [US-gitmrr-005](../stories/git-mirroring.md)
- Edge-case rows: docs/analitics/edge-cases/git-mirroring.md "Configure sync group"

---

# UC-gitmrr-007: Check mirror freshness

## Header

| Field            | Value                     |
| ---------------- | ------------------------- |
| ID               | UC-gitmrr-007             |
| Name             | Check mirror freshness    |
| Goal level       | user-goal                 |
| Scope            | Git Mirroring module      |
| Primary actor    | operator                  |
| Secondary actors | Git provider API (source) |
| Traces to        | US-gitmrr-006             |

## Preconditions

- Operator holds `mirrors:sync` (or the group's freshness schedule fires).
- The mirror has a linked source repository with a provider.

## Success Guarantee (Postconditions)

- A freshness result (FRESH / STALE / ERROR) is recorded with a timestamp.
- Minimal guarantee: an errored check does not overwrite the last known-good state.

## Trigger

Operator triggers freshness, or the group's freshness cron fires.

## Main Success Scenario

| Step | Actor                                 | System                                                                                                           |
| ---- | ------------------------------------- | ---------------------------------------------------------------------------------------------------------------- |
| 1    | Operator triggers the freshness check |                                                                                                                  |
| 2    |                                       | System reads the source's latest commit state via the provider                                                   |
| 3    |                                       | System compares it with the recorded last-known state                                                            |
| 4    |                                       | System records FRESH or STALE (updating the last-known state and divergence count) and reflects it on the mirror |

## Extensions (Alternative Flows)

| At step | Condition                                | Handling                                                                                  |
| ------- | ---------------------------------------- | ----------------------------------------------------------------------------------------- |
| 2       | Source unreachable / credentials invalid | System records ERROR with the provider reason; last-known state unchanged (EC-gitmrr-028) |
| 2       | Mirror has no linked source repository   | System refuses with a message naming the prerequisite (EC-gitmrr-029)                     |

## Related Artifacts

- User stories: [US-gitmrr-006](../stories/git-mirroring.md)
- Edge-case rows: docs/analitics/edge-cases/git-mirroring.md "Freshness check"

---

# UC-gitmrr-008: Verify mirror integrity

## Header

| Field            | Value                                          |
| ---------------- | ---------------------------------------------- |
| ID               | UC-gitmrr-008                                  |
| Name             | Verify mirror integrity                        |
| Goal level       | user-goal                                      |
| Scope            | Git Mirroring module                           |
| Primary actor    | operator                                       |
| Secondary actors | Git provider API (source), GitLab API (target) |
| Traces to        | US-gitmrr-007                                  |

## Preconditions

- Operator holds the integrity-check permission.
- The mirror has a bound target project.

## Success Guarantee (Postconditions)

- An integrity verdict (MATCH / MISMATCH / ERROR) is recorded; the mirror state reflects it.
- Minimal guarantee: an errored check does not fake a MATCH.

## Trigger

Operator triggers the integrity check.

## Main Success Scenario

| Step | Actor                                 | System                                                                                                                  |
| ---- | ------------------------------------- | ----------------------------------------------------------------------------------------------------------------------- |
| 1    | Operator triggers the integrity check |                                                                                                                         |
| 2    |                                       | System reads the HEAD commit of the source default branch via the source provider                                       |
| 3    |                                       | System reads the HEAD commit of the target project via the GitLab API                                                   |
| 4    |                                       | System records MATCH or MISMATCH (incrementing the divergence count), updates the mirror state, and reports the verdict |

## Extensions (Alternative Flows)

| At step | Condition                             | Handling                                                                                   |
| ------- | ------------------------------------- | ------------------------------------------------------------------------------------------ |
| 2       | Source unreadable                     | System records ERROR with the provider reason (EC-gitmrr-030)                              |
| 3       | Target project unreachable or unbound | System records ERROR / refuses with the not-ready explanation respectively (EC-gitmrr-031) |
| 1       | User lacks the permission             | System denies with 403 (EC-gitmrr-018)                                                     |

## Related Artifacts

- User stories: [US-gitmrr-007](../stories/git-mirroring.md)
- Edge-case rows: docs/analitics/edge-cases/git-mirroring.md "Integrity check"

---

# UC-gitmrr-009: Discover and remediate orphaned mirrors

> **status: discovery-owned-here, remediation moved to #160.** Шаги 1–2 (discovery) —
> норматив этого модуля; шаги 3–4 (reassign/move-target/delete) — отправная точка
> для #160 (grill #140, отдельный ADR-кандидат), финальный контракт там.

## Header

| Field            | Value                                   |
| ---------------- | --------------------------------------- |
| ID               | UC-gitmrr-009                           |
| Name             | Discover and remediate orphaned mirrors |
| Goal level       | user-goal                               |
| Scope            | Git Mirroring module                    |
| Primary actor    | admin                                   |
| Secondary actors | GitLab API (target instances)           |
| Traces to        | US-gitmrr-009, US-gitmrr-010            |

## Preconditions

- Admin holds the orphaned-management permission (discovery) and `mirrors:write`/`mirrors:delete` (remediation).
- At least one active GitLab provider exists.

## Success Guarantee (Postconditions)

- Orphaned projects are listed; any remediation leaves an auditable, reversible record.
- Minimal guarantee: discovery failures never modify anything; remediation never touches the GitLab project itself.

## Trigger

Admin opens the orphaned page and runs discovery; then optionally remediates an entry.

## Main Success Scenario

| Step | Actor                                                             | System                                                                                     |
| ---- | ----------------------------------------------------------------- | ------------------------------------------------------------------------------------------ |
| 1    | Admin starts discovery                                            |                                                                                            |
| 2    |                                                                   | System scans each active GitLab provider and lists projects whose ids no mirror references |
| 3    | Admin picks an orphan and chooses reassign / move-target / delete |                                                                                            |
| 4    |                                                                   | System applies the remediation to the mirror record, records it in audit, and confirms     |

## Extensions (Alternative Flows)

| At step | Condition                                       | Handling                                                                                                              |
| ------- | ----------------------------------------------- | --------------------------------------------------------------------------------------------------------------------- |
| 1       | No GitLab providers configured                  | System shows an actionable empty state with a link to provider settings (EC-gitmrr-032)                               |
| 2       | One provider unreachable                        | System returns results from reachable providers and reports the failed one separately (EC-gitmrr-033)                 |
| 1       | User lacks the permission                       | System denies with 403 (EC-gitmrr-019)                                                                                |
| 4       | Delete chosen                                   | System soft-deletes the mirror record (recoverable within retention); the GitLab project is untouched (EC-gitmrr-034) |
| 4       | Remediation target invalid (e.g. unknown group) | System rejects with a validation error; nothing changed (EC-gitmrr-035)                                               |

## Related Artifacts

- User stories: [US-gitmrr-009](../stories/git-mirroring.md), [US-gitmrr-010](../stories/git-mirroring.md)
- Edge-case rows: docs/analitics/edge-cases/git-mirroring.md "Orphaned discovery", "Orphaned remediation"
- Open questions: remediation endpoint design / error semantics — grill #140

---

# UC-gitmrr-010: Delete and restore a mirror

## Header

| Field            | Value                       |
| ---------------- | --------------------------- |
| ID               | UC-gitmrr-010               |
| Name             | Delete and restore a mirror |
| Goal level       | user-goal                   |
| Scope            | Git Mirroring module        |
| Primary actor    | operator                    |
| Secondary actors | —                           |
| Traces to        | US-gitmrr-011               |

## Preconditions

- Operator holds `mirrors:delete`.
- The mirror exists and is active.

## Success Guarantee (Postconditions)

- The mirror is soft-deleted (recoverable within the retention window) or restored; the target GitLab project is never touched by either.
- Minimal guarantee: cleanup expiry removes only the record, never GitLab data.

## Trigger

Operator deletes a mirror (with confirmation); later, an operator/admin restores it — or the retention expires.

## Main Success Scenario

| Step | Actor                                         | System                                                                                                           |
| ---- | --------------------------------------------- | ---------------------------------------------------------------------------------------------------------------- |
| 1    | Operator triggers delete with confirmation    |                                                                                                                  |
| 2    |                                               | System soft-deletes the mirror (and cascade soft-deletes its source repository if no other mirror references it) |
| 3    | Operator restores within the retention window |                                                                                                                  |
| 4    |                                               | System restores the mirror and its cascade-deleted source repository                                             |

## Extensions (Alternative Flows)

| At step | Condition                                                               | Handling                                                                                                              |
| ------- | ----------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------- |
| 2       | Mirrors still reference the source repository at repository-delete time | System refuses with 409 listing the referencing mirror ids (EC-gitmrr-036)                                            |
| 3       | Mirror already deleted / not deleted                                    | System reports the state without changing it (EC-gitmrr-037)                                                          |
| 4       | Retention window expired (configured `soft_delete_retention_days`)      | Daily cleanup physically removes the record in FK order with an audit event; GitLab project untouched (EC-gitmrr-038) |

## Related Artifacts

- User stories: [US-gitmrr-011](../stories/git-mirroring.md)
- Edge-case rows: docs/analitics/edge-cases/git-mirroring.md "Delete/restore mirror"
