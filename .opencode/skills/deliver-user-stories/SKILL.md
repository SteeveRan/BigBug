---
name: deliver-user-stories
description: Generates user stories in the standard persona, action, benefit story format from product requirements or feature descriptions. Use when breaking a feature into stories for sprint planning, writing tickets, or communicating scope to engineering. For testable Given/When/Then acceptance criteria on a story, use deliver-acceptance-criteria; for boundary and failure scenarios, use deliver-edge-cases.
license: Apache-2.0
disable-model-invocation: true
metadata:
  phase: deliver
  version: "2.1.0"
  updated: 2026-10-25
  category: specification
---
# User Stories

User stories are concise descriptions of functionality from the user's perspective. They capture who needs something, what they need, and why - without prescribing how to build it. Good user stories enable teams to break large features into estimable, deliverable increments while maintaining focus on user value.

## When to Use

- After PRD approval, when breaking down features for implementation
- During sprint planning to create actionable work items
- When writing tickets for engineering teams
- When communicating requirements to stakeholders in accessible terms
- When prioritizing a backlog based on user value

## When NOT to Use

- You need deeper, QA-ready Given/When/Then coverage for a single story or slice -> use `deliver-acceptance-criteria`
- You need the feature-wide catalog of boundary conditions and failure scenarios -> use `deliver-edge-cases`
- The feature itself is not yet specified -> run `/grill-me` (or `/grill-with-docs`) first; stories should trace back to documented requirements
- You want refinement-session outcomes (estimates, scope decisions, open questions) -> not vendored in this repo; capture them in the same tracking issue instead

## Instructions

When asked to create user stories, follow these steps:

1. **Understand the Feature Context**
   Review the PRD or feature description. Understand the overall goal, target users, and scope boundaries. User stories should trace back to documented requirements.

2. **Identify User Personas**
   Determine which users interact with this feature. Each story should be written for a specific persona, not generic "users." Different personas may need different stories for the same feature.

3. **Break Down by User Goal**
   Decompose the feature into distinct user goals. Each story should deliver a complete, valuable capability - something the user can actually do when the story is done.

4. **Write Story Statements**
   Use the format: "As a [persona], I want [action] so that [benefit]." The benefit clause is critical - it explains why this matters and helps prioritize.

5. **Define Acceptance Criteria**
   Write specific, testable criteria using Given/When/Then format. Acceptance criteria define "done" - if all criteria pass, the story is complete.

6. **Apply INVEST Criteria**
   Validate each story against INVEST: Independent, Negotiable, Valuable, Estimable, Small, Testable. Revise stories that don't meet these criteria.

7. **Add Context and Notes**
   Include relevant design references, technical considerations, and dependencies. These help implementers understand the full picture.

## Output Format

Use the template in `references/TEMPLATE.md` to structure the output. A complete output carries, per story: Story Header; User Story Statement; Context & Background; Acceptance Criteria; Design Notes; Technical Notes; Dependencies; Out of Scope; and Open Questions where any remain. Multi-story documents nest these sections under one heading per story, as the example shows.

## Process in this repo: format, location, update procedure

- **Format**: a user story is a REPO document, not an issue. One story = one
  section, exactly the shape in `references/TEMPLATE.md` (Story Header with ID;
  User Story Statement; Acceptance Criteria in Given/When/Then; Design Notes;
  Technical Notes; Dependencies; Out of Scope; Open Questions). Personas must be
  the platform's built-in roles: admin, operator, viewer.
- **Location**: `docs/analitics/stories/<module>.md` - one living file per module
  (e.g. `docs/analitics/stories/providers.md`), H2 per feature, stories under it with
  stable IDs (`US-<module>-NNN`). Committed to the repo and versioned with the
  code. The issue tracker only ever receives TICKETS derived from stories
  (`/to-tickets`); the story text itself never lives in an issue.
- **Direction of truth**: a story is NORMATIVE - the user's request, the
  requirement the code must satisfy. A PR that contradicts a story is an
  INCORRECT PR and is returned; the story never bends to match written code.
- **Update procedure**: a story changes ONLY when the user's request changes
  (explicit, reviewed decision - not as a side effect of a code PR).
  Implementation may add clarifying detail or new acceptance criteria for a
  requirements gap additively, with explicit reviewer acceptance in the same
  PR. Renaming or renumbering story IDs is forbidden once tickets reference
  them; retire a story with a `status: retired` header line instead of
  deleting it.
  Durable behavioral obligations that outlive the feature (module-level
  contracts, edge cases, recovery paths) do NOT live in the story - they go to
  `docs/analitics/edge-cases/<module>.md` (see the `deliver-edge-cases` skill).
  Detailed actor-system interaction flows are NOT stories either - they go to
  use cases (see the `deliver-use-cases` skill).

## Quality Checklist

Before finalizing, verify:

- [ ] Each story follows "As a... I want... so that..." format
- [ ] Stories are independent (can be built in any order)
- [ ] Acceptance criteria use Given/When/Then format
- [ ] Each criterion is testable (someone can verify pass/fail)
- [ ] Stories are small enough to complete in one sprint
- [ ] No implementation details in the story statement
- [ ] Benefit clause explains why this matters to the user

## Examples

See `references/EXAMPLE.md` for a completed example.