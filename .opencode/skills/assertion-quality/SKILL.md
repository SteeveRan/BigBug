---
name: assertion-quality
description: "Analyze assertion quality, depth, variety, and false confidence in existing tests (pytest and Jest/Vitest). ALWAYS USE when asked about weak, shallow, trivial, always-true, self-referential, assertion-free, presence/truthiness-only, or insufficiently diverse assertions. DO NOT USE for direct fixes or for writing new test cases. Use test-anti-patterns for general severity-ranked audits beyond assertions."
---

# Assertion Diversity Analysis

Analyze test code (pytest and Jest/Vitest) to measure how varied and meaningful the assertions are. Produce a metrics report that reveals whether tests verify different facets of correctness — not just "output equals X" but also structure, exceptions, state transitions, side effects, and invariants.

> **Framework-specific guidance**: Use the framework-specific assertion APIs of the target language — pytest's bare `assert`, `pytest.raises`, and `unittest.mock` verifiers, or Jest/Vitest's `expect()` matchers. The API catalogs differ significantly between the two, so classify assertions against the API surface of the framework actually under analysis before assigning categories.

## Why Assertion Diversity Matters

Low assertion diversity signals shallow testing. Tests may pass while bugs hide in unasserted logic. Common symptoms:

| Problem | Symptom | Consequence |
|---------|---------|-------------|
| Trivial assertions | Test contains only `assert result is not None` / `expect(x).toBeDefined()` | Test passes but doesn't verify correctness |
| Single-value obsession | Always check one field or return value | Bugs in unasserted logic slip through |
| No negative assertions | Never check what shouldn't happen | Regressions sneak in through false positives |
| No state checks | Don't verify object state changes | Missed side-effects or lifecycle issues |
| No structural checks | Only assert top-level value | Bugs in nested objects go unnoticed |
| Assertion-free tests | Tests that call but don't verify | Code coverage lies; false security |

## When to Use

- User asks to evaluate assertion quality or depth
- User asks "are my tests actually testing anything meaningful?"
- User wants to know if test assertions are too shallow or trivial
- User asks for assertion coverage metrics or diversity analysis
- User suspects tests give false confidence despite passing
- Any test-generation workflow may call this skill as a pre-completion self-review step on freshly generated tests, before declaring the run finished

## When Not to Use

- User wants to write new tests (help them directly, using the project's test-writing conventions)
- User wants to detect anti-patterns beyond assertions (use `test-anti-patterns`)
- User wants to fix or rewrite assertions (help them directly)
- User asks about code coverage percentages (out of scope — this analyzes assertion quality, not line coverage)

## Inputs

| Input | Required | Description |
|-------|----------|-------------|
| Test code | Yes | One or more test files or a test directory to analyze |
| Production code | No | The code under test, to evaluate whether assertions cover the important behaviors |

## Workflow

### Step 1: Detect language and test framework

Identify whether the target codebase uses pytest (Python) or Jest/Vitest (TypeScript/JavaScript). The framework determines the assertion APIs you will classify in Step 3:

- **pytest**: bare `assert` statements, `pytest.raises`, `unittest.mock` call verifiers (`assert_called_with`), plugins such as `pytest-asyncio` and snapshot plugins (`syrupy`)
- **Jest/Vitest**: `expect()` matchers (`toBe`, `toEqual`, `toStrictEqual`, `toContain`, `toThrow`, `resolves`/`rejects`), mock matchers (`toHaveBeenCalledWith`), snapshot matchers (`toMatchSnapshot`)

### Step 2: Gather the test code

Read all test files the user provides. If the user points to a directory or project, scan for all test files using the framework markers:

- pytest: files named `test_*.py` or `*_test.py`, test functions `def test_*`
- Jest/Vitest: `*.test.ts(x)` / `*.spec.ts(x)` files, `it()` / `test()` blocks (often grouped in `describe()`)

### Step 3: Classify every assertion

For each test, identify all assertions and classify them into these framework-neutral categories:

| Category | What it verifies | Examples |
|----------|------------------|----------|
| **Equality** | Return value matches expected | `assert x == y` (pytest), `expect(x).toBe(y)` / `expect(x).toEqual(y)` (Jest/Vitest) |
| **Boolean** | Condition holds | `assert flag` (pytest), `expect(x).toBe(true)` / `expect(x).toBeTruthy()` (Jest/Vitest) |
| **Null / None** | Presence/absence of value | `assert x is None` (pytest), `expect(x).toBeNull()` / `expect(x).toBeUndefined()` (Jest/Vitest) |
| **Exception / Error** | Error handling behavior | `with pytest.raises(E): ...` (pytest), `expect(fn).toThrow(E)` (Jest/Vitest) |
| **Type checks** | Runtime type correctness | `assert isinstance(x, T)` (pytest), `expect(x).toBeInstanceOf(T)` (Jest/Vitest) |
| **String** | Text content and format | `assert sub in s` (pytest), `expect(s).toMatch(/x/)` / `expect(s).toContain(sub)` (Jest/Vitest) |
| **Collection** | Collection contents and structure | `assert item in collection` / `assert set(a) == set(b)` (pytest), `expect(arr).toContain(x)` / `expect(arr).toEqual([...])` (Jest/Vitest) |
| **Comparison** | Ordering and magnitude | `assert x > y` (pytest), `expect(x).toBeGreaterThan(y)` (Jest/Vitest) |
| **Approximate** | Floating-point or tolerance-based | `assert x == pytest.approx(y)` (pytest), `expect(x).toBeCloseTo(y)` (Jest/Vitest) |
| **Negative** | What should NOT happen | `assert x != y` (pytest), `expect(x).not.toBe(y)` (Jest/Vitest) |
| **State / Side-effect** | State transitions and side effects | Assertions on object properties after mutation; mock-call verifications: `mock_method.assert_called_with(...)` (Python `unittest.mock`), `expect(mock).toHaveBeenCalledWith(...)` (Jest/Vitest) |
| **Structural / Deep** | Deep object correctness | `.toEqual({...})` (Jest/Vitest deep equality), snapshot tests (`.toMatchSnapshot()` for Jest/Vitest, `syrupy` for pytest) |

A single assertion can belong to multiple categories (e.g., `assert x != y` is both Equality and Negative; `expect(mock).toHaveBeenCalledWith(...)` is both State/Side-effect and a specific-call assertion).

### Step 4: Compute metrics

Calculate these metrics for the test suite:

#### Per-test metrics
- **Assertion count**: Number of assertions in each test
- **Assertion categories**: Which categories each test uses

#### Suite-wide metrics
- **Average assertions per test**: Total assertions / total tests
- **Assertion type spread**: Number of distinct assertion categories used across the suite (out of 12)
- **Tests with zero assertions**: Count and percentage of tests with no assertions at all
- **Tests with only trivial assertions**: Count and percentage of tests where every assertion is only a null check or always-true (`assert True`, `expect(true).toBe(true)`) — trivial means no meaningful value verification
- **Tests with self-referential assertions**: Count and percentage of tests whose assertions compare an input to a round-tripped or identity-transformed version of itself (e.g., `assert parse(str(x)) == x` or `expect(parse(String(input))).toBe(input)`) or assert a field against itself (`assert dto.name == dto.name`). These are tautological — they verify the plumbing, not the behavior.
- **Tests with negative assertions**: Count and percentage (target: at least 10% of tests should verify what should NOT happen)
- **Tests with exception assertions**: Count and percentage
- **Tests with state/side-effect assertions**: Count and percentage
- **Tests with structural/deep assertions**: Count and percentage
- **Single-category tests**: Count and percentage of tests that use only one assertion category

### Step 5: Apply calibration rules

Before reporting, calibrate findings:

- **Evaluate the matcher predicate before describing its weakness.** For every weak assertion, name one realistic defective value or behavior that would still satisfy that exact predicate. For every assertion credited as meaningful, name the behavior it pins. If you cannot give such a counterexample from the test and available production contract, do not speculate that the assertion is weak.
- **Trivial means truly trivial.** A null/None/undefined check alone is trivial (`assert result is not None`, `expect(x).toBeDefined()`). But a null check followed by a meaningful value assertion is not trivial — the null check is a guard before the real assertion. Only flag a test as "trivial" if it has no meaningful value assertions.
- **Use exact Jest semantics.** `toBeDefined()` rejects only `undefined`; `null` does satisfy it, but mention that only when `null` is a realistic contract-breaking result. `toMatchObject(expected)` verifies the expected subset structurally; it neither proves object identity nor full-object equality. Never claim that it does.
- **Boolean assertions checking meaningful conditions are not trivial.** `assert result.is_valid` / `expect(result.isValid).toBe(true)` check a specific property — these are Boolean assertions, not trivial ones. Always-true assertions (`assert True`, `expect(true).toBe(true)`) are trivial.
- **Exact construction and mapping checks are meaningful.** A test that constructs an object and pins each requested property to an independent expected literal can catch swapped, dropped, or incorrectly assigned values. Do not downgrade it merely because the implementation is a constructor, dataclass, property mapping, or in-memory store.
- **Consider the test's intent.** A test for a void function that verifies state change on a dependency is legitimate even if it only uses one Boolean assertion.
- **Exception tests are inherently low-assertion-count.** `with pytest.raises(E): ...` / `expect(fn).toThrow(E)` may be the only assertion — that's fine for exception-focused tests. Don't penalize them for low assertion count.
- **Mock-call verifications and bare assertion forms count.** Treat `expect(mock).toHaveBeenCalledWith(...)` (Jest/Vitest) and bare `assert` (pytest) as real assertions of the appropriate category. Do not treat them as missing-framework-API smells.
- **Snapshot assertions** (`.toMatchSnapshot()`, `syrupy`) count as Structural/Deep assertions. Flag stale or never-updated snapshots separately.
- **Property-based tests** (Hypothesis `@given` for pytest) generate assertions implicitly through generated cases — count the inner assertion logic, not the outer scaffold.
- **Don't conflate diversity with volume.** A test with 20 equality assertions has high volume but low diversity. A test with one equality, one null check, and one exception assertion has low volume but good diversity.
- **Self-referential assertions are not meaningful equality checks.** Asserting that an output equals an input round-trip looks like a real equality assertion but is tautological when the operation under test is expected to be identity. Flag these separately from normal equality assertions. If the test's *purpose* is to verify a round-trip (serialize/deserialize, encode/decode), the assertion is valid — but it should be accompanied by assertions on non-trivial inputs that exercise the transformation.
- **Match recommendations to the named behavior.** Formatting tests should pin the exact formatted representation, validation tests need rejected inputs, and round-trip tests need inputs that exercise escaping, null/empty handling, or another transformation boundary. For each assertion-free create/update/delete operation, recommend its specific returned value or observable post-condition rather than one generic "check state" remedy.
- **If assertions are well-diversified, say so.** A report concluding the suite has good diversity is perfectly valid.

### Step 6: Report findings

**Scale the report depth to the size and complexity of the suite.** The structure below is the full template for a substantial suite (roughly 15+ tests or a multi-file project). For a small or simple input (a single file with only a handful of tests), do not emit every section — a padded multi-section dashboard on a trivial input reads as noise and buries the answer. Instead, answer the user's question directly and concisely: which tests are assertion-free or trivial-only, the overall assertion-quality verdict, and concrete recommendations (still distinguishing intentional smoke tests from tests masquerading as real verification). Use only the sections that carry real signal for the input at hand; a short metric summary plus the assertion-free list and recommendations is often enough. Never omit the rubric-relevant substance (assertion-free/trivial identification, the quality verdict, and concrete recommendations) — only trim structural overhead that adds no information.

For a five-to-eight-test file, default to one verdict plus one compact per-test table. Omit category-spread dashboards and hypothetical failure modes unless the caller asks for metrics. State only counterexamples supported by the assertion predicate and available production behavior.

Present the analysis in this structure:

1. **Summary Dashboard** — A quick-reference table of key metrics:
   ```
   | Metric                        | Value  | Assessment |
   |-------------------------------|--------|------------|
   | Total tests                   | 25     | —          |
   | Average assertions per test   | 2.4    | Moderate   |
   | Assertion type spread         | 5/12   | Low        |
   | Tests with zero assertions    | 3 (12%)| Concerning |
   | Tests with only trivial asserts | 4 (16%)| Acceptable |
   | Tests with negative assertions | 2 (8%) | Below target |
   | Single-category tests         | 15 (60%)| High       |
   ```

2. **Category Breakdown** — For each assertion category, show:
   - How many tests use it
   - Representative examples from the code
   - Whether it's overused or underused relative to the code under test

3. **Gap Analysis** — Based on the production code (if available), identify:
   - Behaviors that are tested but only with equality checks
   - Error paths with no exception assertions
   - State-changing operations with no state verification
   - Collections returned but never checked for contents

4. **Recommendations** — Prioritized list of improvements:
   - Which tests would benefit most from additional assertion types
   - Which assertion categories are missing and why they matter
   - Concrete examples of assertions that could be added

5. **Assertion-free tests** — If any exist, list each one with its test name and what it appears to be testing, so the user can decide whether to add assertions or mark them as intentional smoke tests.

## Validation

- [ ] Every assertion in the test suite was classified into at least one category
- [ ] Metrics are computed correctly (counts add up)
- [ ] Trivial-assertion tests are correctly identified (not over-flagged)
- [ ] Exception tests are not penalized for low assertion count
- [ ] Boolean assertions on meaningful properties are not classified as trivial
- [ ] Every weak-assertion claim includes a realistic counterexample that the exact matcher would accept
- [ ] Jest matcher semantics are precise (`toBeDefined` versus `undefined`; `toMatchObject` subset matching versus identity/full equality)
- [ ] Recommendations are concrete (name specific tests and suggest specific assertion types)
- [ ] If the suite has good diversity, the report acknowledges this

## Common Pitfalls

| Pitfall | Solution |
|---------|----------|
| Penalizing exception tests for low assertion count | Exception assertions are complete on their own — skip count warnings for these |
| Flagging null/None/undefined checks before value checks as trivial | Only flag tests where the null/None/undefined check is the ONLY assertion |
| Counting any Boolean assertion as trivial | Only always-true assertions (`assert True`, `expect(true).toBe(true)`) are trivial |
| Ignoring framework differences | pytest's bare `assert ==`, Jest's `expect().toBe()`, and Jest's `toEqual()` deep equality all map to the **Equality** category, but each framework has distinct APIs for the other categories — classify against the framework actually under analysis |
| Treating bare assertion forms as missing-framework | Bare `assert` (pytest) is canonical — count it in the right category |
| Treating mock-call verifications as assertion-free | `expect(mock).toHaveBeenCalledWith(...)` and `mock.assert_called_with(...)` are State/Side-effect assertions |
| Recommending diversity for diversity's sake | Only suggest adding assertion types that would catch real bugs in the code under test |
| Missing implicit assertions | Exception assertions are both Exception and Negative; snapshot/property-based tests are real assertions with implicit structure |
| Async tests with unawaited assertions | Jest with `.resolves`/`.rejects` and pytest-asyncio can silently pass tests where assertions are not awaited — treat as assertion-free even when assertion calls are present |
