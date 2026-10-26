---
artifact: edge-case-catalog
version: "1.1"
---

# Edge-Case Catalog: Git Mirroring

## Overview

| Field | Value |
|-------|-------|
| Module | Git Mirroring |
| Purpose | Mirror Git repositories from external providers into GitLab, keep them fresh, and report on their health. |
| User-facing operations | import group, create mirror, bulk create mirrors, sync mirror, freshness check, integrity check, orphaned discovery |
| Permissions | mirrors:read/write/delete/sync/import/integrity_check/manage_orphaned, source_groups:read/write, sync_groups:read/write |
| Bound ADRs | ADR-0008 (git mirroring GitHub→GitLab) |

## Create mirror

| # | Condition | Expected behavior | User-visible recovery | Severity | Closing test |
|---|-----------|-------------------|-----------------------|----------|--------------|
| 1 | Target GitLab project does not exist yet | Mirror record stored with `status: draft`; sync explicitly reports that the target project must be created first | Message explains the two-step flow with a link to the GitLab Projects page | P1 | `gap -> ADR-0041` |
| 2 | Source and target identical | Rejected with validation error | Inline field error, nothing stored | P2 | test_mirroring.py::test_create_mirror_self_loop |

### Input validation

| # | Condition | Expected behavior | Severity | Closing test |
|---|-----------|-------------------|----------|--------------|
| 1 | Source URL not reachable by the provider | Mirror stored; first freshness check reports unreachable | P1 | gap -> #142 |

## Sync mirror

| # | Condition | Expected behavior | User-visible recovery | Severity | Closing test |
|---|-----------|-------------------|-----------------------|----------|--------------|
| 1 | GitLab pipeline trigger fails | Mirror stays in previous status; sync run recorded as failed with provider error | Error toast with the provider reason + Retry button | P1 | test_mirroring.py::test_sync_trigger_failure |
| 2 | Pipeline hangs (no webhook finalization) | Mirror remains `in progress` beyond SLA | Sync-runs admin page offers Requeue | P1 | gap -> ADR-0042 |

## Error message copy

| Error state | User message | Additional action (button/link) |
|-------------|--------------|---------------------------------|
| No GitLab providers configured | "No GitLab provider configured. Add one to start mirroring." | "Configure provider" -> /settings/providers |
