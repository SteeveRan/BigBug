---
name: deliver-edge-cases
description: Documents edge cases, error states, boundary conditions, race conditions, and recovery paths for a feature - the systematic catalog of what can go wrong and the failure modes to design for. Use during specification to map the failure surface and ensure comprehensive coverage, or during QA planning to identify boundary and limit scenarios to test. Distinct from deliver-acceptance-criteria, which writes story-level Given/When/Then checks; this skill produces the whole-feature edge-case catalog.
license: Apache-2.0
disable-model-invocation: true
metadata:
  phase: deliver
  version: "2.1.1"
  updated: 2026-10-25
  category: specification
---
# Edge Cases

An edge cases document systematically catalogs the unusual, boundary, and error scenarios for a feature. While happy-path flows are typically well-specified, edge cases often get discovered in production - causing bugs, poor user experience, and support burden. Documenting edge cases upfront ensures engineering handles them intentionally and QA knows what to test.

## When to Use

- When you need to enumerate failure modes, race conditions, timeouts, and boundary or limit scenarios - everything that can go wrong - and define a recovery path for each
- During feature specification before engineering begins
- When preparing QA test plans
- After discovering production bugs to prevent similar issues
- When reviewing PRDs or user stories for completeness
- Before launch to ensure error states have been designed

## When NOT to Use

- You need story-scoped Given/When/Then checks for handoff -> use `deliver-acceptance-criteria`; this skill catalogs the whole feature's failure surface
- The feature is not specified enough to enumerate inputs, states, and limits -> run `/grill-me` first
- A production incident already happened and you want the learning banked -> write the post-mortem into the same catalog row (Found-in field), then close the loop with a test

## Instructions

When asked to document edge cases, follow these steps:

1. **Define the Feature Scope**
   Clearly describe what feature or flow you're analyzing. Edge cases are specific to context - the same input might be valid in one feature and invalid in another.

2. **Walk Through Input Validation**
   Consider every user input: What if it's empty? Too long? Wrong format? Contains special characters? What are the minimum and maximum valid values?

3. **Explore Boundary Conditions**
   Find the edges of acceptable ranges. If a field accepts 1-100, test 0, 1, 100, and 101. Consider pagination boundaries, timeout thresholds, and rate limits.

4. **Map Error States**
   Identify what can go wrong: network failures, permission denied, resource not found, concurrent modifications, expired sessions. Document both the scenario and expected behavior.

5. **Consider Concurrency Issues**
   What if two users act simultaneously? What if the user double-clicks? What if data changes between load and save? Race conditions often cause subtle bugs.

6. **Define Recovery Paths**
   For each error, specify how users recover. What message do they see? Can they retry? Is data preserved? Good error handling turns frustration into confidence.

7. **Prioritize by Likelihood and Impact**
   Not all edge cases need the same attention. High-likelihood + high-impact cases need robust handling; rare + low-impact cases might just need graceful failure.

## Output Format

Use the template in `references/TEMPLATE.md` to structure the output. A complete catalog covers every user-facing operation (one table set per operation: general, input validation, boundary conditions, error states & integration failures, concurrency), plus the error-message copy table.

## Process in this repo: format, location, update procedure

- **Format**: the catalog tables from `references/TEMPLATE.md`, one row per
  condition: Condition / Expected behavior / User-visible recovery / Severity /
  Closing test. Use the module's glossary terms (`GLOSSARY.md`) and never
  implementation file paths in the expected-behavior column (they rot; name the
  seam instead). Flow narratives for the operations are NOT part of the catalog
  - they live in use cases (`docs/analitics/use-cases/`, see the `deliver-use-cases`
  skill); the catalog rows and the use-case extensions must not contradict.
- **Location**: `docs/modules/<module>.md` - the module charter, a LIVING
  document committed to the repo. The edge-case catalog is its
  "Operations & Edge Cases" section (one sub-table per user-facing operation:
  create / edit / delete / sync ...). Create `docs/modules/<module>.md` lazily
  on first use; do not pre-create empty files.
- **Update procedure**:
  1. Adding or changing module behavior updates the same catalog row in the
     SAME PR as the code change - the charter and the code may not diverge.
  2. Every row whose expected behavior is implemented must name the test that
     pins it (integration test per ADR-0016/0017). A row without a test is
     marked "gap -> <ADR or issue>"; gaps are first-class state, not a shame.
  3. When a row changes meaning (not just content), that is a decision: surface
     it to an ADR (`/adr`) per the three-criteria rule of `domain-modeling`.

## Quality Checklist

Before finalizing, verify:

- [ ] All user inputs have validation edge cases documented
- [ ] Boundary conditions are explicitly listed
- [ ] Network/system failure scenarios are covered
- [ ] Each error state has a defined user-facing message
- [ ] Recovery paths are specified (not just error detection)
- [ ] Edge cases are prioritized by likelihood and impact

## Examples

See `references/EXAMPLE.md` for a completed example.