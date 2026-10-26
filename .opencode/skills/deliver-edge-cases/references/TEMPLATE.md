---
artifact: edge-case-catalog
version: "1.1"
---

# Module Charter: <Module Name> — Operations & Edge Cases

> Living document: `docs/modules/<module>.md`. One catalog table per
> user-facing operation. Vocabulary: `GLOSSARY.md`. No implementation file
> paths in "Expected behavior" - name the seam, not the code.

## Overview

| Field | Value |
|-------|-------|
| Module | [name as in GLOSSARY] |
| Purpose | [one paragraph - why this module exists] |
| User-facing operations | [list: create / edit / delete / sync / import ...] |
| Permissions | [permission strings guarding the operations] |
| Bound ADRs | [ADR-NNNN ...] |

## <Operation 1: e.g. "Create provider">

| # | Condition | Expected behavior | User-visible recovery | Severity | Closing test |
|---|-----------|-------------------|-----------------------|----------|--------------|
| 1 | [duplicate label] | [system behavior] | [what the user sees and can do] | P1 | [test file/case or `gap -> <ADR/issue>`] |
| 2 | [input exceeds max length] | | | P2 | |

### Input validation

| # | Condition | Expected behavior | Severity | Closing test |
|---|-----------|-------------------|----------|--------------|
| 1 | [field empty] | | P1 | |
| 2 | [field wrong format / special chars] | | P2 | |

### Boundary conditions

| # | Condition | Expected behavior | Severity | Closing test |
|---|-----------|-------------------|----------|--------------|
| 1 | [value at min / max / beyond] | | P2 | |

### Error states & integration failures

| # | Condition | Expected behavior | User-visible recovery | Severity | Closing test |
|---|-----------|-------------------|-----------------------|----------|--------------|
| 1 | [provider API timeout] | | [retry/link to retry] | P1 | |
| 2 | [permission denied] | | | P1 | |

### Concurrency

| # | Condition | Expected behavior | Severity | Closing test |
|---|-----------|-------------------|----------|--------------|
| 1 | [double submit / concurrent edit] | | P2 | |

## <Operation 2: ...>

[Same table set per operation]

## Error message copy

| Error state | User message | Additional action (button/link) |
|-------------|--------------|---------------------------------|
| [condition #] | "[exact copy]" | [e.g. "Configure provider" -> /settings/providers] |

## Rules

1. Every row needs a Closing test: an existing test case name, or an explicit
   `gap -> <ADR or issue>`. A row without either is invalid.
2. Same-PR rule: a PR changing module behavior updates the affected rows in
   the same PR.
3. A row whose expected behavior encodes a real trade-off (hard to reverse,
   surprising, deliberate choice) must be surfaced to an ADR (`/adr`).
4. Flow narratives for operations live in use cases (`docs/use-cases/`),
   which reference these rows; the two must not contradict.
