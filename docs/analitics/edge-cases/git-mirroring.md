---
artifact: edge-case-catalog
version: "1.1"
---

# Edge-Case Catalog: Git Mirroring

> Living document: `docs/analitics/edge-cases/git-mirroring.md`. One catalog table per
> user-facing operation. Vocabulary: `GLOSSARY.md`. No implementation file
> paths in "Expected behavior" — name the seam, not the code.
> Row IDs (EC-gitmrr-NNN) are stable; adding rows is allowed, renumbering is not.

## Overview

| Field                  | Value                                                                                                                                                                                                             |
| ---------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Module                 | Git Mirroring                                                                                                                                                                                                     |
| Purpose                | Mirror Git repositories from GitHub into GitLab, keep them fresh, verify their integrity, and recover from drift — with BigBug as orchestrator and GitLab CI pipelines as the transfer mechanism (ADR-0008).      |
| User-facing operations | import source group, create mirror, bulk create mirrors, sync mirror, sync result intake, configure sync group, freshness check, integrity check, orphaned discovery, orphaned remediation, delete/restore mirror |
| Permissions            | `mirrors:read/write/delete/sync/import/integrity_check/manage_orphaned`, `source_groups:read/write/refresh`, `sync_groups:read/write/delete`                                                                      |
| Bound ADRs             | ADR-0008 (git mirroring GitHub→GitLab), ADR-0007 (providers), ADR-0025 (webhook verification), ADR-0004 (RBAC), ADR-0039 (task queue)                                                                             |

## Import source group

| #   | ID            | Condition                                       | Required behavior (system MUST...)                               | Required recovery (system MUST offer)                | Severity | Closing test |
| --- | ------------- | ----------------------------------------------- | ---------------------------------------------------------------- | ---------------------------------------------------- | -------- | ------------ |
| 1   | EC-gitmrr-001 | Group not found at the provider                 | reject the import with "group not found" and store nothing       | show the error with the entered identifier editable  | P2       | gap -> #159  |
| 2   | EC-gitmrr-002 | Provider API timeout / rate limit / TLS failure | reject the import with the provider's reason and store nothing   | show the provider reason with a Retry button         | P1       | gap -> #159  |
| 3   | EC-gitmrr-003 | No Git provider configured                      | show an actionable empty state, not a generic failure            | "Configure provider" link -> /settings/providers     | P1       | gap -> #159  |
| 4   | EC-gitmrr-004 | Group already imported                          | report the conflict and leave existing records unchanged         | offer to open the existing group                     | P2       | gap -> #159  |
| 5   | EC-gitmrr-005 | Some repositories fail to register              | keep the successful ones and report the failed list with reasons | show per-item failures with a Retry for failed items | P2       | gap -> #159  |

### Input validation

| #   | ID            | Condition              | Required behavior (system MUST...) | Severity | Closing test |
| --- | ------------- | ---------------------- | ---------------------------------- | -------- | ------------ |
| 6   | EC-gitmrr-040 | Empty group identifier | reject with a field error          | P3       | gap -> #159  |
| 7   | EC-gitmrr-041 | Unknown provider id    | reject with a field error          | P3       | gap -> #159  |

## Create mirror

| #   | ID            | Condition                                         | Required behavior (system MUST...)                                                                                                                                | Required recovery (system MUST offer)                                                    | Severity | Closing test           |
| --- | ------------- | ------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------- | -------- | ---------------------- |
| 1   | EC-gitmrr-006 | Source repository unknown                         | reject with a validation error and store nothing                                                                                                                  | inline field error                                                                       | P2       | gap -> #159            |
| 2   | EC-gitmrr-007 | Active mirror with the same source exists         | warn and record an audit warning, but create on confirmation                                                                                                      | duplicate warning with a link to the existing mirror                                     | P2       | gap -> #159            |
| 3   | EC-gitmrr-008 | Target GitLab project not bound                   | store the mirror in a not-ready-to-sync state that names the missing prerequisite; every sync attempt MUST refuse with the same explanation (never a generic 400) | message explaining the two-step flow + link to GitLab Projects to create/bind the target | P1       | gap -> grill #142 (H1) |
| 4   | EC-gitmrr-009 | Target namespace/name empty or over length limits | reject with field errors and store nothing                                                                                                                        | inline field errors                                                                      | P2       | gap -> #159            |
| 5   | EC-gitmrr-010 | Automatic first sync after creation fails         | keep the created mirror and show the sync failure reason                                                                                                          | mirror page with the failure and a Sync button                                           | P2       | gap -> #159            |

### Input validation

| #   | ID            | Condition                     | Required behavior (system MUST...) | Severity | Closing test |
| --- | ------------- | ----------------------------- | ---------------------------------- | -------- | ------------ |
| 6   | EC-gitmrr-042 | Missing sync group in request | reject with a field error          | P3       | gap -> #159  |

## Bulk create mirrors

| #   | ID            | Condition                                    | Required behavior (system MUST...)                                  | Required recovery (system MUST offer) | Severity | Closing test |
| --- | ------------- | -------------------------------------------- | ------------------------------------------------------------------- | ------------------------------------- | -------- | ------------ |
| 1   | EC-gitmrr-011 | Batch larger than 500                        | reject the whole request stating the limit and create nothing       | message with the limit                | P2       | gap -> #159  |
| 2   | EC-gitmrr-012 | Batch references unknown source repositories | reject the whole request listing the unknown ids and create nothing | list of bad items editable            | P2       | gap -> #159  |
| 3   | EC-gitmrr-013 | Empty batch                                  | reject with a validation error                                      | —                                     | P3       | gap -> #159  |

## Sync mirror

| #   | ID            | Condition                                                   | Required behavior (system MUST...)                                                                                      | Required recovery (system MUST offer)                                     | Severity | Closing test      |
| --- | ------------- | ----------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------- | -------- | ----------------- |
| 1   | EC-gitmrr-014 | Mirror has no sync group                                    | refuse the run with a message naming the prerequisite                                                                   | assignment UI for sync groups                                             | P2       | gap -> #159       |
| 2   | EC-gitmrr-015 | Group has no pipeline configured                            | record a skipped run with reason "no pipeline configured"; no exception raised                                          | mirror shows the skip reason with a link to the group's pipeline settings | P2       | gap -> #159       |
| 3   | EC-gitmrr-016 | Pipeline has no GitLab provider                             | refuse with a message naming the pipeline                                                                               | link to the pipeline's provider settings                                  | P2       | gap -> #159       |
| 4   | EC-gitmrr-017 | GitLab rejects the pipeline creation / timeout              | record the failed run with the provider reason; mirror returns to its previous state                                    | error toast with the provider reason and Retry                            | P1       | gap -> #159       |
| 5   | EC-gitmrr-045 | Sync pipeline variables do not match the CI preset contract | trigger and preset MUST agree on the variable names (single contract); a mismatch MUST be a defect, not silent behavior | —                                                                         | P1       | gap -> grill #142 |

## Sync result intake (webhook)

| #   | ID            | Condition                                                       | Required behavior (system MUST...)                                                                               | Required recovery (system MUST offer) | Severity | Closing test           |
| --- | ------------- | --------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------- | ------------------------------------- | -------- | ---------------------- |
| 1   | EC-gitmrr-020 | Webhook without valid authentication                            | reject the event without processing (per ADR-0025)                                                               | —                                     | P1       | gap -> grill #139 (C1) |
| 2   | EC-gitmrr-021 | Event matches no run record                                     | ignore the event, report "ignored", corrupt nothing                                                              | —                                     | P3       | gap -> #159            |
| 3   | EC-gitmrr-022 | Terminal event lost (GitLab unreachable, webhook not delivered) | expiry handling for runs stuck In Progress beyond SLA (mechanism per grill #142)                                 | requeue/finalize path                 | P1       | gap -> grill #142 (H4) |
| 4   | EC-gitmrr-046 | Terminal event processed                                        | mirror status MUST be finalized (completed/failed) — a mirror MUST NOT remain In Progress after a terminal event | —                                     | P1       | gap -> grill #142 (H4) |

## Configure sync group

| #   | ID            | Condition                               | Required behavior (system MUST...)                         | Required recovery (system MUST offer)     | Severity | Closing test      |
| --- | ------------- | --------------------------------------- | ---------------------------------------------------------- | ----------------------------------------- | -------- | ----------------- |
| 1   | EC-gitmrr-023 | Malformed cron or string over 100 chars | reject with a field error; previous schedule keeps working | inline field error                        | P2       | gap -> #159       |
| 2   | EC-gitmrr-024 | Duplicate group name on create          | reject with "name exists"                                  | rename prompt                             | P3       | gap -> #159       |
| 3   | EC-gitmrr-025 | Group disabled                          | start no runs; keep the schedule                           | —                                         | P2       | gap -> #159       |
| 4   | EC-gitmrr-026 | Non-default group deleted               | migrate its mirrors to the default group; record in audit  | confirmation dialog stating the migration | P2       | gap -> #159       |
| 5   | EC-gitmrr-027 | Default group delete attempted          | refuse: the default group cannot be deleted                | —                                         | P2       | gap -> #159       |
| 6   | EC-gitmrr-047 | Schedule settings changed               | new schedule MUST apply without an application restart     | —                                         | P1       | gap -> grill #142 |

## Freshness check

| #   | ID            | Condition                                | Required behavior (system MUST...)                                | Required recovery (system MUST offer) | Severity | Closing test |
| --- | ------------- | ---------------------------------------- | ----------------------------------------------------------------- | ------------------------------------- | -------- | ------------ |
| 1   | EC-gitmrr-028 | Source unreachable / credentials invalid | record ERROR with the provider reason; last-known state unchanged | Retry with the provider reason shown  | P1       | gap -> #159  |
| 2   | EC-gitmrr-029 | Mirror has no linked source repository   | refuse with a message naming the prerequisite                     | link to source registration           | P2       | gap -> #159  |

## Integrity check

| #   | ID            | Condition                                 | Required behavior (system MUST...)                                         | Required recovery (system MUST offer) | Severity | Closing test           |
| --- | ------------- | ----------------------------------------- | -------------------------------------------------------------------------- | ------------------------------------- | -------- | ---------------------- |
| 1   | EC-gitmrr-030 | Source HEAD unreadable                    | record ERROR with the provider reason; never a fake MATCH                  | Retry                                 | P1       | gap -> #159            |
| 2   | EC-gitmrr-031 | Target unreachable or not bound           | record ERROR / refuse with the not-ready explanation respectively          | Retry / link to remediation           | P1       | gap -> #159            |
| 3   | EC-gitmrr-018 | User lacks the integrity-check permission | deny with 403 — the operation MUST NOT be open to every authenticated user | —                                     | P1       | gap -> grill #139 (C3) |

## Orphaned discovery

| #   | ID            | Condition                          | Required behavior (system MUST...)                                                                | Required recovery (system MUST offer)            | Severity | Closing test           |
| --- | ------------- | ---------------------------------- | ------------------------------------------------------------------------------------------------- | ------------------------------------------------ | -------- | ---------------------- |
| 1   | EC-gitmrr-032 | No GitLab providers configured     | show an actionable state, not a generic failure (semantics: configuration state, not error)       | "Configure provider" link -> /settings/providers | P1       | gap -> grill #140 (H2) |
| 2   | EC-gitmrr-033 | One provider unreachable           | return results from reachable providers; report the failed one separately                         | per-provider failure row with Retry              | P2       | gap -> #159            |
| 3   | EC-gitmrr-019 | User lacks the orphaned permission | deny with 403                                                                                     | —                                                | P1       | gap -> grill #139 (C3) |
| 4   | EC-gitmrr-048 | Large result set / search          | support pagination and search at the platform boundary (list contract consistent for all clients) | —                                                | P2       | gap -> grill #140      |

## Orphaned remediation

> **status: moved to #160** — remediation осиротевших зеркал — отдельный модуль
> (issue #160, grill #140). Таблица остаётся как отправная точка; финальный
> контракт и закрытие гэпов — в комплекте #160.

| #   | ID            | Condition                                                      | Required behavior (system MUST...)                                                                     | Required recovery (system MUST offer)       | Severity | Closing test              |
| --- | ------------- | -------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------ | ------------------------------------------- | -------- | ------------------------- |
| 1   | EC-gitmrr-034 | Orphan deleted                                                 | soft-delete the mirror record (recoverable within retention); NEVER modify/delete the GitLab project   | confirmation dialog naming the consequences | P1       | gap -> grill #140 (C4)    |
| 2   | EC-gitmrr-035 | Remediation target invalid (unknown group/path)                | reject with a validation error; change nothing                                                         | inline field error                          | P2       | gap -> grill #140 (C4)    |
| 3   | EC-gitmrr-036 | Relink/delete endpoints called without write/delete permission | deny with 403                                                                                          | —                                           | P1       | gap -> grill #140 (C4)    |
| 4   | EC-gitmrr-037 | Remediation operation executed                                 | record in audit; reason model for orphans MUST be consistent between list and detail (single contract) | —                                           | P2       | gap -> grill #140 (C4/M6) |

## Delete/restore mirror

| #   | ID            | Condition                                                          | Required behavior (system MUST...)                                                                             | Required recovery (system MUST offer) | Severity | Closing test |
| --- | ------------- | ------------------------------------------------------------------ | -------------------------------------------------------------------------------------------------------------- | ------------------------------------- | -------- | ------------ |
| 1   | EC-gitmrr-038 | Retention window expired (configured `soft_delete_retention_days`) | physically remove the record in FK order during daily cleanup; record in audit; NEVER touch the GitLab project | —                                     | P1       | gap -> #159  |
| 2   | EC-gitmrr-039 | Restore of a never-deleted mirror                                  | report the state without changing it                                                                           | —                                     | P3       | gap -> #159  |
| 3   | EC-gitmrr-043 | Repository delete attempted while active mirrors reference it      | refuse with 409 listing the referencing mirror ids                                                             | list of blockers with links           | P2       | gap -> #159  |
| 4   | EC-gitmrr-044 | Mirror restored after cascade source-repository deletion           | restore the mirror AND its cascade-deleted source repository                                                   | —                                     | P2       | gap -> #159  |

## Error message copy

| Error state                               | User message                                                                                                  | Additional action (button/link)             |
| ----------------------------------------- | ------------------------------------------------------------------------------------------------------------- | ------------------------------------------- |
| No GitLab providers configured (orphaned) | "No GitLab provider configured. Add one to start discovery."                                                  | "Configure provider" -> /settings/providers |
| Target project not bound (sync refused)   | "Target GitLab project is not bound to this mirror. Create and bind it first."                                | "GitLab Projects" -> /gitlab-projects       |
| Group has no pipeline (sync skipped)      | "Sync skipped: no pipeline configured on the sync group."                                                     | "Configure pipeline" -> sync group detail   |
| Provider API failure (import/freshness)   | "Provider request failed: {reason}"                                                                           | "Retry"                                     |
| Webhook rejected (auth)                   | — (external caller; no UI copy)                                                                               | —                                           |
| Orphan delete confirmation                | "Delete this orphan record? The GitLab project itself will not be touched. Recoverable for {retention} days." | "Delete" / "Cancel"                         |
