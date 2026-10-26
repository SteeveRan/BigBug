---
artifact: use-case
version: "1.0"
---

# UC-<module>-NNN: [Verb phrase naming the actor's goal]

> Fully-dressed use case, adapted from A. Cockburn, "Writing Effective Use Cases" (2001).
> A use case describes WHAT the system does at its boundary, observable from the
> outside. It is an analysis artifact: no UI design, no implementation details.

## Header

| Field | Value |
|-------|-------|
| ID | UC-<module>-NNN |
| Name | [Verb phrase: "Import a source group", not "Group import"] |
| Goal level | [user-goal / subfunction] |
| Scope | [the module / subsystem under design] |
| Primary actor | [admin / operator / viewer / external system] |
| Secondary actors | [e.g. GitLab API, Harbor, Keycloak] |
| Traces to | [US-<module>-NNN story IDs; ADR-NNNN] |

## Stakeholders and Interests

| Stakeholder | Interest |
|-------------|----------|
| [actor/stakeholder] | [what they need from this use case] |

## Preconditions

- [State that must hold before the scenario starts]

## Success Guarantee (Postconditions)

- [State of the world after the main success scenario completes]
- Minimal guarantee (holds even on failure): [what is true no matter what]

## Trigger

[The event that starts this use case]

## Main Success Scenario

| Step | Actor | System |
|------|-------|--------|
| 1 | [actor action] | |
| 2 | | [system response/validate] |
| 3 | [actor action] | |
| 4 | | [system response] |

## Extensions (Alternative Flows)

> Format: `<step>: <condition> -> <handling>`. Reference the step number of the
> main scenario where the divergence happens. Anything that can fail, MUST have
> an extension here - cross-check with the module's edge-case catalog.

| At step | Condition | Handling |
|---------|-----------|----------|
| 2 | [e.g. provider credentials invalid] | [system behavior + user-visible outcome] |

## Sub-variations

| At step | Variation |
|---------|-----------|
| 3 | [e.g. bulk import of N groups instead of one] |

## Related Artifacts

- User stories: [US-...]
- Edge-case rows: [docs/analitics/edge-cases/<module>.md rows]
- Open questions: [links or "none"]
