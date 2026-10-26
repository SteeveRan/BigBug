---
name: deliver-use-cases
description: Writes fully-dressed use cases (Cockburn style) - actor-system interaction flows with preconditions, main success scenario, extensions, and sub-variations - as repo documents. Use when a user story needs detailed behavior specification, when flows have many alternative/error branches, or when specifying what a module does at its boundary before designing it. Distinct from deliver-user-stories (one-line need + acceptance criteria, no flows) and deliver-edge-cases (failure-surface catalog without a flow narrative).
license: Apache-2.0
disable-model-invocation: true
metadata:
  phase: deliver
  version: "1.0.0"
  updated: 2026-10-25
  category: specification
---

# Use Cases

A use case captures an actor-system interaction sequence that delivers a
measurable value to the actor. It describes WHAT the system does, observable
from the outside - never HOW. Use cases and user stories are different
artifacts and BOTH exist in this repo: a story states the need (who/what/why +
acceptance criteria); a use case specifies the interaction flow (steps,
alternatives, guarantees). A story may be covered by zero or several use cases.

## When to Use

- A story's behavior has branching flows (errors, alternative paths) that
  acceptance criteria alone cannot hold
- Specifying a module's boundary behavior before design/ADR work
- Deriving test scenarios for multi-step flows
- Onboarding: a new contributor needs to understand what a module does

## When NOT to Use

- The need fits in one sentence plus acceptance criteria -> use `deliver-user-stories`
- You need a failure-surface catalog (inputs, boundaries, races) without flow
  narrative -> use `deliver-edge-cases`
- The criterion is a design decision (hard to reverse, surprising, real
  trade-off) -> that is an ADR (`/adr`), not a use case

## Instructions

1. **Name it with a verb phrase** capturing the actor's goal ("Import a source
   group", never "Group import"). Use `GLOSSARY.md` vocabulary; avoid acronyms
   and generic verbs ("manage", "process").
2. **Identify the actors.** Primary actor initiates; secondary actors are
   consulted systems (GitLab API, Harbor, Keycloak). Personas are the
   platform's built-in roles: admin, operator, viewer.
3. **Pick the goal level** (Cockburn): user-goal for anything a user would
   call a task; subfunction only for steps reused across several use cases.
4. **Write the main success scenario** as numbered actor/system steps in the
   two-column table. Keep it the simplest path to the goal - no branches here.
5. **Write extensions for every divergence**: reference the step number where
   it happens, state the condition, and the handling. Anything that can fail
   MUST have an extension - cross-check the module's edge-case catalog so both
   artifacts agree.
6. **State the guarantees**: success postconditions and the minimal guarantee
   (what holds even when the flow fails - e.g. "no partial import is left").
7. **Trace**: link the story IDs this use case covers and the edge-case rows.

## Process in this repo: format, location, update procedure

- **Format**: fully-dressed use case per `references/TEMPLATE.md` (Header,
  Stakeholders, Preconditions, Success Guarantee, Trigger, Main Success
  Scenario as actor/system table, Extensions, Sub-variations, Related
  Artifacts). See `references/EXAMPLE.md` for a completed example.
- **Location**: `docs/analitics/use-cases/<module>.md` - one living file per module
  holding its use-case model. When a module grows past ~10 use cases, split to
  `docs/analitics/use-cases/<module>/UC-<module>-NNN-<slug>.md` (one file per use case)
  and keep `docs/analitics/use-cases/<module>.md` as an index (ID, name, one-line goal,
  trace). Committed to the repo, versioned with the code.
- **Update procedure**:
  1. Same-PR rule: a PR that changes module behavior updates the affected use
     case in the same PR.
  2. IDs are stable: never renumber `UC-<module>-NNN` once stories, tickets, or
     tests reference them; retire with `status: retired` in the header.
  3. Extensions mirror edge-case rows: when a flow failure mode changes,
     update the module charter (`docs/modules/<module>.md`) row and the use
     case extension together.
  4. A use case contradicts an existing ADR -> surface the conflict explicitly
     per `docs/agents/domain.md`, never silently override.

## Quality Checklist

Before finalizing, verify:

- [ ] Name is a verb phrase in glossary vocabulary
- [ ] Goal level stated; steps describe WHAT, no UI or implementation design
- [ ] Main scenario is branch-free; all branches live in Extensions
- [ ] Every failure-capable step has an extension, consistent with the
      module's edge-case catalog
- [ ] Minimal guarantee stated (what holds on failure)
- [ ] Traces to story IDs and edge-case rows exist
- [ ] No technology choices leaked into the flow (that is ADR territory)

## Examples

See `references/EXAMPLE.md` for a completed use case.
