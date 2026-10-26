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

| # | Condition | Required behavior (system MUST...) | Required recovery (system MUST offer) | Severity | Closing test |
|---|-----------|-------------------|-----------------------|----------|--------------|
| 1 | Target GitLab project does not exist yet | System MUST store the mirror with `status: draft`; sync MUST report that the target project must be created first | System MUST show a message explaining the two-step flow, with a link to the GitLab Projects page | P1 | `gap -> ADR-0041` |
| 2 | Source and target identical | System MUST reject with a validation error | System MUST show an inline field error and MUST NOT store anything | P2 | test_mirroring.py::test_create_mirror_self_loop |

### Input validation

| # | Condition | Required behavior (system MUST...) | Severity | Closing test |
|---|-----------|-------------------|----------|--------------|
| 1 | Source URL not reachable by the provider | System MUST store the mirror; the first freshness check MUST report it unreachable | P1 | gap -> #142 |

## Sync mirror

| # | Condition | Required behavior (system MUST...) | Required recovery (system MUST offer) | Severity | Closing test |
|---|-----------|-------------------|-----------------------|----------|--------------|
| 1 | GitLab pipeline trigger fails | System MUST keep the mirror in its previous status; the sync run MUST be recorded as failed with the provider error | System MUST show an error toast with the provider reason and a Retry button | P1 | test_mirroring.py::test_sync_trigger_failure |
| 2 | Pipeline hangs (no webhook finalization) | System MUST keep the mirror `in progress` beyond SLA until requeued | Sync-runs admin page MUST offer a Requeue action | P1 | gap -> ADR-0042 |

## Error message copy

| Error state | User message | Additional action (button/link) |
|-------------|--------------|---------------------------------|
| No GitLab providers configured | "No GitLab provider configured. Add one to start mirroring." | "Configure provider" -> /settings/providers |
