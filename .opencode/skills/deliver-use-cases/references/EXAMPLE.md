---
artifact: use-case
version: "1.0"
---

# UC-GM-001: Import a source group from a Git provider

## Header

| Field | Value |
|-------|-------|
| ID | UC-GM-001 |
| Name | Import a source group from a Git provider |
| Goal level | user-goal |
| Scope | Git Mirroring module |
| Primary actor | operator |
| Secondary actors | Git provider API (GitHub / GitLab / Generic Git) |
| Traces to | US-GM-003, US-GM-005 |

## Stakeholders and Interests

| Stakeholder | Interest |
|-------------|----------|
| operator | Get all repositories of a group registered without manual one-by-one entry |
| viewer | See discovered repositories in the Sources tab |

## Preconditions

- Operator is authenticated and holds `source_groups:write`.
- At least one Git provider with credentials exists (status OK).

## Success Guarantee (Postconditions)

- The group and all discovered repositories exist in BigBug with `status: imported`.
- Minimal guarantee: on partial failure, already-imported repositories are kept
  and the group record carries the failure reason.

## Trigger

Operator picks "Import group" on the Sources tab.

## Main Success Scenario

| Step | Actor | System |
|------|-------|--------|
| 1 | Operator selects provider and enters group identifier | |
| 2 | | System resolves the group via the provider API and lists its repositories |
| 3 | Operator confirms the repository list | |
| 4 | | System stores the group, creates source-repository records, reports count |

## Extensions (Alternative Flows)

| At step | Condition | Handling |
|---------|-----------|----------|
| 2 | Group not found or not visible to credentials | System reports "group not found", nothing stored |
| 2 | Provider API timeout / rate limit | System retries once, then reports failure with the provider error; nothing stored |
| 2 | No credentials configured for any Git provider | System shows actionable state: "Add a Git provider" link to /settings/providers |
| 4 | Some repositories fail to register | System stores the successful ones, reports the failed list with reasons |

## Sub-variations

| At step | Variation |
|---------|-----------|
| 1 | Operator enters multiple group identifiers (bulk import) |

## Related Artifacts

- User stories: docs/analitics/stories/git-mirroring/US-gitmrr-003.md, US-gitmrr-005.md
- Edge-case rows: docs/analitics/edge-cases/git-mirroring.md "Create mirror" table
- Open questions: none
