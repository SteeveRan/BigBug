---
name: test-anti-patterns
description: >
  Audit a test file or suite (pytest, Jest/Vitest, or any framework); produce a
  severity-ranked diagnostic report. ALWAYS USE for tests that verify nothing,
  missing/tautological assertions, swallowed/broad exceptions,
  flaky/order-dependent tests, duplication, or magic values. DO NOT USE for
  writing new tests, running tests, migrating between test frameworks, coverage
  collection/metrics, or behavioral gap analysis — those are out of scope for
  this audit skill.
---

# Test Anti-Pattern Detection

Quick, pragmatic analysis of test code (primarily pytest and Jest/Vitest in this repository) for anti-patterns and quality issues that undermine test reliability, maintainability, and diagnostic value.

## When to Use

- User asks to review test quality or find test smells
- User wants to know why tests are flaky or unreliable
- User asks "are my tests good?" or "what's wrong with my tests?"
- User requests a test audit or test code review
- User wants diagnostic findings before deciding what to improve

## When Not to Use

- User wants to write new tests from scratch (this skill audits; it does not author)
- User wants direct implementation fixes rather than a diagnostic review (use the relevant write/edit skill)
- User wants to run or execute tests (use the project's pytest / Jest / Vitest commands directly)
- User wants to migrate between test frameworks or versions (report that the migration workflow is out of scope for this audit)
- User wants coverage collection or coverage/CRAP metrics (use native tooling: `pytest --cov`, `vitest --coverage`)
- User asks whether tests would catch a bug or wants behavioral/pseudo-mutation gap analysis (note the adjacent gaps in your report; do not attempt exhaustive mutation analysis)
- User wants a deep formal test smell audit with academic taxonomy and extended catalog (use `test-smell-detection` instead of a pragmatic audit)

## Inputs

| Input | Required | Description |
|-------|----------|-------------|
| Test scope | No | Test files, classes, directory, or project to analyze. Discover from the current workspace when omitted. |
| Production code | No | The code under test, for context on what tests should verify |
| Specific concern | No | A focused area like "flakiness" or "naming" to narrow the review |

## Workflow

### Step 1: Detect language and framework

Resolve the named test path from the current workspace before asking for input.
When no path is supplied, discover test files under the current directory using
the repository manifests and conventional test markers. Never resolve target
files relative to documentation or skill storage locations; always relative to
the user's workspace.

If one reader says a path is missing but a workspace glob/search finds it,
normalize that exact path and retry. Use a shell text reader (`sed`/`cat` on
Unix, `Get-Content` on PowerShell) only for a confirmed reader availability,
transport, or path-normalization failure and only after verifying the canonical
path remains inside the current workspace. Stop on content-exclusion,
permission/policy, workspace-boundary, or unknown failures. Audit any discovered
file that a permitted reader can access; never ask the user to paste it. If
every permitted reader fails, report the exact blocker without bypassing
security boundaries.

Identify the language and framework: pytest for the FastAPI backend
(`backend/tests/`), Jest/Vitest for the React/TS frontend (`frontend/src/**/*.test.*`
and `*.spec.*`).

### Step 2: Gather the test code

Inventory the resolved scope before reading bodies. For one file or class, read
that scope directly. For a project or suite, discover test files once, batch
independent reads where tools allow, and stop when every discovered test and
class-level fixture has a ledger disposition.

Use the built-in discovery markers in this skill: files matching
`test_*.py` / `*_test.py` (pytest), `*.test.*` / `*.spec.*` (Jest/Vitest), and
in-file markers such as `def test_*` (pytest), `describe`/`it`/`test` blocks
(Jest/Vitest).

Do not read unrelated production code wholesale. Open the production symbol
corresponding to every suspicious test needed to decide whether an assertion,
transformation, identity contract, or adjacent gap is real. For a systematic
facade/surface-area pattern, every invoked member is relevant: read the entire
small production type or inspect each invoked member, then map each weak test to
the exact observable result, exception, state change, or boundary it should
verify.

### Step 3: Scan for anti-patterns

Check each test file against the anti-pattern catalog below. Report findings
grouped by severity. Use the cross-framework examples in the catalog.

Before drafting the report, make a private completeness ledger with one row for
every test and every class-level fixture/resource. Record its oracle (or
absence), exception handling, state/time dependencies, concurrency safety,
precondition/assertion order, and disposition. Do not publish until every row is
either attached to a finding or explicitly judged sound. In particular:

- `actual != oldValue` is a weak mutation oracle: it accepts every wrong new
  value. Require the exact expected value.
- Include unused or undisposed class-level resources; function-only scans miss
  module-level objects such as a shared `httpx.Client` or a module-scoped DB fixture.
- Treat an unsynchronized shared/global collection as both order-coupled and
  parallel-unsafe when tests read and write it. Also flag dereferencing a
  nullable result before the assertion intended to prove it non-null.
- When production code is supplied, note obvious untested contracts adjacent to
  a finding, but do not perform exhaustive branch or mutation analysis. List
  those gaps in the report's adjacent-coverage section.

#### Critical -- Tests that give false confidence

| Anti-Pattern | What to Look For |
|---|---|
| **No assertions** | Tests that execute code but never assert anything. A passing test without assertions proves nothing. In pytest a function with no `assert` and no `pytest.raises`; in Jest/Vitest no `expect(...)` inside the test body. Mock-call verifications (`assert mock.called`, `expect(mock).toHaveBeenCalled(...)`, `vi.expect(mock).toHaveBeenCalled()`) are real assertions. |
| **Missing await on async assertions (JS/TS, Python)** | `expect(promise).resolves.toBe(x)` without `await`/`return`, `expect(...).rejects.toThrow()` without `await`, `async` test function returning a coroutine without `await` under pytest-asyncio, Vitest `await expect(...)` forgotten on a rejected-promise check. These tests silently pass even when the underlying assertion would have failed. |
| **Coverage touching** | Test class/module that methodically calls every public member on a type — often in alphabetical or declaration order — without asserting meaningful outcomes. Each test typically does `result = sut.method_name(...)` or `const result = sut.methodName()` with no assertion, or only a trivial `is not None` / `toBeTruthy()` check. The intent is to inflate code-coverage metrics rather than verify behavior. Distinct from a single assertion-free test: the pattern is *systematic* coverage of the surface area with no real verification. |
| **Self-referential assertion** | The expected value is computed from the same actual value, such as `assert result == result` or `expect(result).toBe(result)`. Do not apply this label merely because a valid identity, clone, serialization, or round-trip contract compares output with input: those assertions can fail. Instead check whether the input exercises a transformation and whether independently known representation, field, reference-identity, or invalid-input assertions are missing. |
| **Swallowed exceptions** | Bare `except:` or `except Exception:` with `pass` (Python) and no assertion; `try { ... } catch (e) {}` (JS/TS); catching in a fixture and re-raising as a generic `Error` that hides the original cause. |
| **Assert in catch block only** | `try: act() except Exception as e: assert False, str(e)` (and JS equivalents) — use `pytest.raises` / `expect(fn).toThrow` / `await expect(...).rejects.toThrow` instead. The test passes when no exception is thrown even if the result is wrong. |
| **Always-true assertions** | `assert True`, `expect(true).toBe(true)`, `assert result == result`, or conditions that can never fail. |
| **Commented-out assertions** | Assertions that were disabled but the test still runs, giving the illusion of coverage. |

#### High -- Tests likely to cause pain

| Anti-Pattern | What to Look For |
|---|---|
| **Flakiness indicators** | Wall-clock sleeps/waits used for synchronization: `time.sleep(...)` (Python), `setTimeout` / `await new Promise(r => setTimeout(...))` (JS/TS), sleep-based waits in Playwright/Cypress tests. Wall-clock reads without abstraction: `datetime.now()`/`datetime.utcnow()`, `Date.now()` / `new Date()`. Unseeded randomness: `random.random()`/`random.randint()`, `Math.random()`, `faker` values that are not pinned. Environment-dependent paths (hard-coded `/tmp/...`, network hosts, absolute home paths). |
| **Test ordering dependency** | Shared/global mutable state modified across tests; setup that doesn't fully reset state (`setUp`/`setUpClass`, `beforeEach`/`beforeAll`, module-level `let` in a test file); tests that fail when run individually but pass in suite (or vice versa). Examples: module-level globals (Python), top-level `let`/`const` in test file (JS/TS), `beforeAll` mutations not undone, class/module-scoped fixtures that accumulate state. |
| **Over-mocking** | More mock setup lines than actual test logic. Verifying exact call sequences on mocks rather than outcomes. Mocking types the test owns. Per framework: `unittest.mock` / `pytest-mock` (Python), Jest auto-mocks / `vi.mock` / Sinon (JS/TS). Mocking the exact function under test is a special case — it turns the test into a tautology. |
| **Implementation coupling** | Testing private functions/attributes via `getattr` or reaching into underscore-prefixed names (Python), `(thing as any)`-style casts to reach internals (TS). Asserting on internal state instead of observable behavior. Verifying exact method call counts on collaborators instead of business outcomes. |
| **Broad exception assertions** | `pytest.raises(Exception)` without checking the message or a more specific type; `expect(fn).toThrow()` / `.toThrow(Error)` without a message matcher; `assertRaises(Exception)` with no kind check. A test that accepts any failure accepts the wrong failure. |
| **Weak transformation oracle** | A normalization, casing, trimming, mapping, or conversion test supplies an input already in the expected form, so a no-op implementation passes even though the assertion may catch other defects. Use an input that must change and assert an independently derived expected value. A producer/consumer round trip is useful but does not replace an independent format assertion when both sides could share the same defect. |

#### Medium -- Maintainability and clarity issues

| Anti-Pattern | What to Look For |
|---|---|
| **Poor naming** | Test names like `test_1`, `test_foo`, or `it works` that don't describe the scenario or outcome. Follow the existing naming convention in the same suite. |
| **Magic values** | Unexplained numbers or strings in arrange/assert: `assert result == 42` / `expect(result).toBe(42)` — what does 42 mean? |
| **Duplicate tests** | Three or more tests with near-identical bodies that differ only in a single input value. Should be parametrized: `@pytest.mark.parametrize` (pytest), `test.each` / `it.each` (Jest/Vitest). Note: Two tests covering distinct boundary conditions (e.g., zero vs. negative) are NOT duplicates -- separate tests for different edge cases provide clearer failure diagnostics and are a valid practice. |
| **Giant tests** | Tests exceeding ~30 lines or testing multiple behaviors at once. Hard to diagnose when they fail. |
| **Assertion messages that repeat the assertion** | `assert x == y, "x is not equal to y"` / `expect(result).toBe(expected)` inside a message that re-quotes the comparison add no information. Messages should describe the business meaning. |
| **Missing AAA / Given-When-Then separation** | Arrange/Act/Assert phases are interleaved or indistinguishable. |

#### Low -- Style and hygiene

| Anti-Pattern | What to Look For |
|---|---|
| **Unused test infrastructure** | Setup/teardown hooks that do nothing — `setUp`/`teardown`, `beforeEach`/`afterEach`, `beforeAll`/`afterAll` — and test helper functions that are never called. |
| **Unmanaged resources** | Test creates disposable resources without cleanup: file/connection without a `with` block or `try/finally` (Python), missing `afterEach` teardown for temp files/DBs, unclosed clients/sockets in any language. |
| **Print debugging** | Leftover `print()` / `console.log` / `console.debug` statements used during test development. |
| **Inconsistent naming convention** | Mix of naming styles in the same test file/module (e.g., some use `test_method_scenario_expected`, others use `test_should_do_something`). |

### Step 4: Calibrate severity honestly

Before reporting, re-check each finding against these severity rules:

- **Critical/High**: Only for issues that cause tests to give false confidence or be unreliable. A test that always passes regardless of correctness is Critical. Shared mutable state is High when it is a latent isolation risk, but **Critical when the user reports actual order-dependent failures or the code proves one test requires another to run first**. Missing-await on async assertions is Critical (silent pass).
- **Medium**: Only for issues that actively harm maintainability -- 5+ nearly-identical tests, truly meaningless names like `test_1` / `test` / `it1`.
- **Low**: Cosmetic naming mismatches, minor style preferences, assertion messages that could be better. When in doubt, rate Low.
- **Use the caller's severity vocabulary consistently.** If the caller asks for
  Critical / Warning / Info, map latent reliability risks to Warning and
  maintenance/cosmetic concerns to Info. Keep a demonstrated false-confidence
  or current order-dependency root cause Critical; do not downgrade it merely to
  make every requested tier non-empty. Severity describes the demonstrated
  failure mode, not how much prose a finding receives.
- **Separate a systemic finding from its instances.** Coverage touching across a
  facade is one Critical systemic finding whose evidence lists every affected
  test. All assertion-free instances, including the last facade method, retain
  the same false-confidence severity. Report `1 finding / 6 affected tests`, not
  six findings plus a seventh summary finding, and do not downgrade one instance
  merely to manufacture multiple tiers.
- **Do not severity-rank ordinary missing cases as anti-patterns.** Adjacent
  untested branches, exception paths, and boundaries may be useful coverage
  opportunities, but list them separately from the anti-pattern counts unless a
  weak existing test specifically creates the gap. They are not Critical merely
  because the suite has a systemic Critical issue.
- **Not an issue** (per-framework nuance):
  - pytest **bare `assert`** is the canonical assertion form, not a missing assertion library. Do NOT flag.
  - Separate tests for distinct boundary conditions (zero vs. negative vs. null). Do NOT flag as duplicates.
  - Explicit per-test setup instead of `beforeEach` / a shared fixture (this *improves* isolation).
  - Tests that are short and clear but could theoretically be consolidated.
  - Round-trip or serialization equality with non-trivial input. It is valid
    metamorphic evidence, not a self-comparison; still recommend one independent
    representation when producer and consumer could share a defect.
  - A transformation tested only with an already-transformed input. Keep it out
    of the tautology count, but report the weak oracle when removing the
    transformation would still pass. Use an input that must change and pin its
    independently expected output.
  - Clone value equality. Keep it, and add distinct-reference or mutation-
    independence evidence when the contract promises a deep copy.
  - A validator or accessor returning the original value when pass-through is the
    production contract. Missing invalid-input cases are a coverage gap, not proof
    that the existing assertion is tautological.

IMPORTANT: If the tests are well-written, say so clearly up front. Do not inflate severity to justify the review. A review that finds zero Critical/High issues and only minor Low suggestions is a valid and valuable outcome. Lead with what the tests do well.

### Step 5: Report findings

**Depth bar — a tidy report that is shallower than an unassisted review is a failure.** Before writing, satisfy all five:

1. **Account for every test in scope.** Build the complete test/fixture inventory
   before summarizing. For a systematic pattern such as coverage touching,
   enumerate every affected test at least once rather than giving representative
   examples. A finding table that silently skips tests (or fixtures like an
   unused module-level HTTP client) is incomplete. State the number reviewed.
2. **Verify the production contract before judging the oracle.** Inspect the
   actual transformation, DTO/serializer fields, and promised identity/clone semantics.
   Never invent fields or require lossless round-tripping when production is
   intentionally lossy.
   For every suspicious equality, write down the independently known oracle
   before assigning a finding. If the assertion compares a transformed output
   with non-trivial input, clone state, snapshot, mock verification, or a
   framework-native assertion context, explain why it can fail before calling it
   tautological or assertion-free. Conversely, when a transformation test uses
   an already-normalized input, call out that the input cannot distinguish the
   real transformation from a no-op and provide a changing input plus exact
   expected output. For paired producer/consumer APIs, retain the round-trip test
   and add one independent representation oracle rather than replacing valid
   metamorphic evidence.
3. **Make every Critical/High fix complete and specific.** Give the replacement assertion with the *exact expected value* (the computed discount, the exact JSON field, the full expected object), not a `// assert something here` placeholder.
4. **Name obvious adjacent gaps without widening into mutation analysis** —
   when production code is supplied, note directly related untested throws,
   null results, boundary values, and round-trip/culture-sensitivity risks in an
   **Adjacent coverage gaps** section of the report itself.
5. **Keep the report internally consistent.** Summary counts must equal the enumerated findings. Publish a settled conclusion: do all reconsidering before you write, and never leave "wait, that's wrong" / "this should fail but doesn't" reasoning in the output.
6. **Make non-findings decisive.** For a clean or mostly clean small suite, name
   the suspicious constructs you cleared and the framework rule that makes each
   valid. Do not bury a clean verdict under a generic checklist or speculative
   improvements.

Present findings in this structure:

1. **Summary** -- Total issues found, broken down by severity (Critical / High / Medium / Low). If tests are well-written, lead with that assessment.
2. **Critical and High findings** -- List each with:
   - The anti-pattern name
   - The specific location (file, test name, line)
   - A brief explanation of why it's a problem
   - A concrete fix (show before/after code when helpful)
3. **Medium and Low findings** -- Summarize in a table unless the user wants full detail
4. **Positive observations** -- Call out things the tests do well (specific exception types, data-driven tests, clear AAA structure, proper use of fakes, good naming). Don't only report negatives.

Before publishing, assign each finding a stable identity. A grouped row counts
as one finding regardless of how many tests it lists; separate rows count
separately. Recompute the summary from those rows. Keep `affected tests` as a
different number so a bundled finding cannot create a hidden count mismatch.

### Step 6: Prioritize recommendations

If there are many findings, recommend which to fix first:

1. **Critical** -- Fix immediately, these tests may be giving false confidence
2. **High** -- Fix soon, these cause flakiness or maintenance burden
3. **Medium/Low** -- Fix opportunistically during related edits

## Validation

- [ ] Every test in scope is accounted for (reviewed count stated; none silently skipped)
- [ ] Identity and round-trip findings match the production contract and use only real fields
- [ ] Every finding includes a specific location (not just a general warning)
- [ ] Every Critical/High finding includes a concrete fix with exact expected values
- [ ] Adjacent untested error paths and boundary values are called out
- [ ] Summary counts match the enumerated findings
- [ ] Grouped findings distinguish finding count from affected-test count
- [ ] Adjacent coverage opportunities are not inflated into Critical anti-pattern findings
- [ ] Report covers all categories (assertions, isolation, naming, structure)
- [ ] Positive observations are included alongside problems
- [ ] Recommendations are prioritized by severity

## Common Pitfalls

| Pitfall | Solution |
|---------|----------|
| Reporting style issues as critical | Naming and formatting are Medium/Low, never Critical |
| Suggesting rewrites instead of targeted fixes | Show minimal diffs -- change the assertion, not the whole test |
| Flagging intentional design choices | If `time.sleep` / a delay is in an integration test testing actual timing, that's not an anti-pattern. Consider context. |
| Inventing false positives on clean code | If tests follow best practices, say so. A review finding "0 Critical, 0 High, 1 Low" is perfectly valid. Don't inflate findings to justify the review. |
| Flagging separate boundary tests as duplicates | Two tests for zero and negative inputs test different edge cases. Only flag as duplicates when 3+ tests have truly identical bodies differing by a single value. |
| Rating cosmetic issues as Medium | Naming mismatches (e.g., test name says `ValueError` but asserts `ValidationError`) are Low, not Medium -- the test still works correctly. |
| Ignoring the test framework | Use the terminology of the actual framework; don't describe a pytest suite in Jest terms or vice versa. |
| Missing the forest for the trees | If 80% of tests have no assertions, lead with that systemic issue rather than listing every instance |
| Trading depth for tidiness | A severity table and positive observations do not substitute for coverage of every test, exact expected values in fixes, and the adjacent error-path/boundary gaps |
| Contradicting yourself in the report | Reason first, then write one settled verdict per finding — never emit "wait, that's wrong" / "should fail but doesn't" reconsiderations |
| Counts that don't add up | The summary's per-severity totals must match the findings you listed |
