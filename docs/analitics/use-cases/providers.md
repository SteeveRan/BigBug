---
artifact: use-case
version: "1.0"
---

# UC-prov-001: Register a provider

> Fully-dressed use case, adapted from A. Cockburn, "Writing Effective Use Cases" (2001).
> A use case describes WHAT the system does at its boundary, observable from the
> outside. It is an analysis artifact: no UI design, no implementation details.

## Header

| Field            | Value                                     |
| ---------------- | ----------------------------------------- |
| ID               | UC-prov-001                               |
| Name             | Register a provider                       |
| Goal level       | user-goal                                 |
| Scope            | Providers module                          |
| Primary actor    | operator                                  |
| Secondary actors | —                                         |
| Traces to        | US-prov-001; ADR-0007                     |

## Stakeholders and Interests

| Stakeholder | Interest                                                                    |
| ----------- | --------------------------------------------------------------------------- |
| operator    | Register an integration once, correctly shaped by the registry               |
| admin       | Secret-like keys never enter provider `config`; system providers stay out of user CRUD |
| viewer      | Registered providers appear in browse (public ones)                          |

## Preconditions

- Actor is authenticated and holds `providers:write`.

## Success Guarantee (Postconditions)

- The provider exists with status Pending, owned by the actor (private category), shaped strictly per the subtype registry.
- Minimal guarantee: on validation failure nothing is stored.

## Trigger

Actor submits the create-provider form (or an API payload).

## Main Success Scenario

| Step | Actor                                                     | System                                                                                              |
| ---- | --------------------------------------------------------- | --------------------------------------------------------------------------------------------------- |
| 1    | Actor chooses domain and subtype                          | System returns the subtype's registry metadata (allowed categories/directions, credential types, config schema) |
| 2    | Actor fills the subtype-driven fields and submits         |                                                                                                     |
| 3    |                                                           | System validates the payload against the registry (domain match, category/direction sets, required base URL, config schema + secret deny-list, visibility rules) |
| 4    |                                                           | System stores the provider with status Pending and reports it created                                |

## Extensions (Alternative Flows)

| At step | Condition                                            | Handling                                                                                 |
| ------- | ---------------------------------------------------- | ---------------------------------------------------------------------------------------- |
| 1       | Subtype's only category is `system`                  | Subtype is not offered for user creation (EC-prov-001)                                    |
| 3       | Duplicate live name                                  | Reject with conflict; nothing stored (EC-prov-002)                                        |
| 3       | Registry violation (domain/category/direction/base URL/unknown config key) | Reject with a field-specific error; nothing stored (EC-prov-003..006)         |
| 3       | Secret-like key in `config`                          | Reject naming the key; nothing stored (EC-prov-007)                                       |
| 3       | `category=system` requested                          | Reject: system providers cannot be created via the API, even with privileges (EC-prov-008) |
| 3       | Team visibility without team membership              | Reject with a field error (EC-prov-009)                                                   |

## Sub-variations

| At step | Variation                                              |
| ------- | ------------------------------------------------------ |
| 2       | Actor creates the provider anonymous (no credential)   |
| 2       | Actor creates a credential inline (see UC-prov-003)    |
| 2       | Actor binds a trust store (requires `trust_stores:read`) |

## Related Artifacts

- User stories: [US-prov-001](../stories/providers.md)
- Edge-case rows: docs/analitics/edge-cases/providers.md "Create provider"
- Open questions: none

---

# UC-prov-002: Test a provider connection

## Header

| Field            | Value                                     |
| ---------------- | ----------------------------------------- |
| ID               | UC-prov-002                               |
| Name             | Test a provider connection                |
| Goal level       | user-goal                                 |
| Scope            | Providers module                          |
| Primary actor    | operator                                  |
| Secondary actors | External system (Git/Docker/Helm API)     |
| Traces to        | US-prov-002; ADR-0007, ADR-0037           |

## Stakeholders and Interests

| Stakeholder | Interest                                                       |
| ----------- | -------------------------------------------------------------- |
| operator    | Know whether the integration works before consumers depend on it |
| consumer modules | Rely on a persisted, recent status instead of re-testing  |

## Preconditions

- Actor may read the provider and holds `providers:write` scoped to it.

## Success Guarantee (Postconditions)

- The provider carries the test outcome: status flag OK/Failed, a status text and `last_checked_at`.
- Minimal guarantee: a failed test never changes the provider's configuration; the previous status is replaced, not lost.

## Trigger

Actor triggers the connection test on a provider.

## Main Success Scenario

| Step | Actor                              | System                                                                                     |
| ---- | ---------------------------------- | ------------------------------------------------------------------------------------------ |
| 1    | Actor triggers the test            |                                                                                            |
| 2    |                                    | System decrypts the provider's credential (if any) and builds the TLS verification settings (verify flag × trust store, ADR-0037) |
| 3    |                                    | System calls the external system's health/read endpoint via the subtype client             |
| 4    |                                    | System stores status OK (or Failed with the reason) and reports the outcome to the actor   |

## Extensions (Alternative Flows)

| At step | Condition                                        | Handling                                                                                     |
| ------- | ------------------------------------------------ | --------------------------------------------------------------------------------------------- |
| 2       | No credential attached, external system demands auth | Status Failed with the anonymous-access explanation (EC-prov-021)                          |
| 3       | External system returns 401 with credential      | Status Failed: "authentication failed — check the credential" (EC-prov-022)                   |
| 3       | External system returns 403                      | Status Failed: "credential lacks permission" (EC-prov-023)                                     |
| 3       | External system returns 404                      | Status Failed: "resource not found" (EC-prov-024)                                              |
| 3       | Timeout / unreachable / TLS failure / 5xx        | Status Failed: "request failed" with the provider reason (EC-prov-025)                        |
| 3       | Trust store bound but endpoint presents an untrusted certificate | Status Failed with the TLS failure reason — verification is never silently disabled (EC-prov-026) |
| 3       | Client path ignores custom CAs (known gaps: PyGitHub, crane, cosign) | Behavior per ADR-0037 Known gaps; the test result reflects what that path can do (EC-prov-027) |

## Sub-variations

| At step | Variation                                             |
| ------- | ----------------------------------------------------- |
| 3       | Subtype test semantics differ (GitHub API rate, Helm index fetch, registry v2 ping) — all collapse to OK/Failed + reason |

## Related Artifacts

- User stories: [US-prov-002](../stories/providers.md)
- Edge-case rows: docs/analitics/edge-cases/providers.md "Test provider connection"
- Open questions: none

---

# UC-prov-003: Attach a credential to a provider

## Header

| Field            | Value                                     |
| ---------------- | ----------------------------------------- |
| ID               | UC-prov-003                               |
| Name             | Attach a credential to a provider         |
| Goal level       | user-goal                                 |
| Scope            | Providers module                          |
| Primary actor    | operator                                  |
| Secondary actors | —                                         |
| Traces to        | US-prov-003, US-prov-008; ADR-0010        |

## Stakeholders and Interests

| Stakeholder | Interest                                                       |
| ----------- | -------------------------------------------------------------- |
| operator    | Enter the secret once; never re-enter it on provider edits     |
| admin       | Secrets exist only encrypted in `credentials`, never in config or responses (ADR-0007 §3, ADR-0010) |

## Preconditions

- Actor holds `providers:write` on the provider; for inline creation `credentials:write` is exercised by the platform on the actor's behalf.

## Success Guarantee (Postconditions)

- The provider references a credential whose secret is stored Fernet-encrypted; no API response contains the secret.
- Minimal guarantee: on failure the previous credential binding is unchanged.

## Trigger

Actor submits the provider form with credential data (inline) or assigns an existing credential.

## Main Success Scenario

| Step | Actor                                          | System                                                                                    |
| ---- | ---------------------------------------------- | ----------------------------------------------------------------------------------------- |
| 1    | Actor picks the credential type offered by the subtype |                                                                                           |
| 2    | Actor enters username/secret and saves         |                                                                                           |
| 3    |                                                | System encrypts the secret and stores the credential, linking it to the provider          |
| 4    |                                                | System reports the provider saved with a "has credential" indicator, secret never echoed  |

## Extensions (Alternative Flows)

| At step | Condition                                       | Handling                                                                     |
| ------- | ----------------------------------------------- | ---------------------------------------------------------------------------- |
| 1       | Actor toggles anonymous access                  | Any existing credential binding is cleared; the provider is stored anonymous (EC-prov-020) |
| 2       | Secret empty where the type requires it         | Reject with a field error (EC-prov-030)                                       |
| 3       | Credential name already taken (hard-unique)     | Reject with a conflict; the generated name can be adjusted (EC-prov-033)      |

## Sub-variations

| At step | Variation                                             |
| ------- | ----------------------------------------------------- |
| 2       | Credential created in advance via admin credentials page (UC-prov-009) |

## Related Artifacts

- User stories: [US-prov-003](../stories/providers.md)
- Edge-case rows: docs/analitics/edge-cases/providers.md "Attach credential", "Manage credentials"
- Open questions: none

---

# UC-prov-004: Share a private provider with a team

## Header

| Field            | Value                                     |
| ---------------- | ----------------------------------------- |
| ID               | UC-prov-004                               |
| Name             | Share a private provider with a team      |
| Goal level       | user-goal                                 |
| Scope            | Providers module                          |
| Primary actor    | operator (owner)                          |
| Secondary actors | —                                         |
| Traces to        | US-prov-004; ADR-0007 §5                  |

## Stakeholders and Interests

| Stakeholder | Interest                                                   |
| ----------- | ---------------------------------------------------------- |
| operator    | Teammates can use the provider without making it public     |
| team member | Predictable access: visibility granted through membership   |
| other users | Remain unaware of the provider (no leakage)                 |

## Preconditions

- Actor owns the private provider and holds `providers:share` (or `providers:read_all`).
- The target team exists.

## Success Guarantee (Postconditions)

- The provider has visibility `team` bound to exactly one team; its category is unchanged.
- Minimal guarantee: on rejection the visibility is unchanged.

## Trigger

Actor submits share (or unshare) with a team.

## Main Success Scenario

| Step | Actor                          | System                                                              |
| ---- | ------------------------------ | -------------------------------------------------------------------- |
| 1    | Actor picks a team and shares  |                                                                      |
| 2    |                                | System verifies ownership, permission and team membership            |
| 3    |                                | System sets visibility=team with the team binding and reports success |
| 4    |                                | Team members see and may use the provider                            |

## Extensions (Alternative Flows)

| At step | Condition                                    | Handling                                            |
| ------- | -------------------------------------------- | ---------------------------------------------------- |
| 2       | Actor is not the owner (and lacks read_all)  | Reject with access-denied (EC-prov-010)              |
| 2       | Provider is not private                      | Reject: only private providers can be shared (EC-prov-011) |
| 2       | Provider already team-shared                 | Reject with conflict (EC-prov-012)                   |
| 2       | Actor is not a member of the target team     | Reject with a field error (EC-prov-013)              |
| 3       | Unshare requested while not shared           | Reject with conflict (EC-prov-014)                   |

## Sub-variations

| At step | Variation                                       |
| ------- | ----------------------------------------------- |
| 1       | Visibility changed via the provider form (same rules) |

## Related Artifacts

- User stories: [US-prov-004](../stories/providers.md)
- Edge-case rows: docs/analitics/edge-cases/providers.md "Share provider"
- Open questions: none

---

# UC-prov-005: Delete a provider

## Header

| Field            | Value                                     |
| ---------------- | ----------------------------------------- |
| ID               | UC-prov-005                               |
| Name             | Delete a provider                         |
| Goal level       | user-goal                                 |
| Scope            | Providers module                          |
| Primary actor    | operator                                  |
| Secondary actors | —                                         |
| Traces to        | US-prov-007; ADR-0007 §5                  |

## Stakeholders and Interests

| Stakeholder | Interest                                                          |
| ----------- | ----------------------------------------------------------------- |
| operator    | Know exactly what blocks deletion; clean up unused providers       |
| admin       | System providers are undeletable; consumers never dangle           |
| viewer      | Usage overview explains why a provider cannot go away              |

## Preconditions

- Actor may read the provider; deletion additionally requires `providers:delete` (non-system).

## Success Guarantee (Postconditions)

- The provider is soft-deleted (hidden, name reusable, no live consumer broken).
- Minimal guarantee: a gated deletion leaves the provider and all consumers untouched.

## Trigger

Actor requests deletion of a provider.

## Main Success Scenario

| Step | Actor                          | System                                                                         |
| ---- | ------------------------------ | ------------------------------------------------------------------------------- |
| 1    | Actor requests deletion        |                                                                                 |
| 2    |                                | System verifies mutation rights and absence of protection/usage                  |
| 3    |                                | System soft-deletes the provider and confirms                                    |

## Extensions (Alternative Flows)

| At step | Condition                                   | Handling                                                                        |
| ------- | ------------------------------------------- | -------------------------------------------------------------------------------- |
| 2       | Provider is protected (system category)     | Refuse with conflict (EC-prov-015)                                               |
| 2       | Live consumers exist                        | Refuse with conflict listing consumers per type; nothing deleted (EC-prov-016)   |
| 2       | Actor lacks `providers:delete`              | Refuse with permission error (EC-prov-017)                                       |

## Sub-variations

| At step | Variation                                                            |
| ------- | -------------------------------------------------------------------- |
| 1       | Actor first inspects the usage view, then retries after cleanup      |

## Related Artifacts

- User stories: [US-prov-007](../stories/providers.md)
- Edge-case rows: docs/analitics/edge-cases/providers.md "Delete provider"
- Open questions: none

---

# UC-prov-006: Bind a trust store to a provider

## Header

| Field            | Value                                     |
| ---------------- | ----------------------------------------- |
| ID               | UC-prov-006                               |
| Name             | Bind a trust store to a provider          |
| Goal level       | user-goal                                 |
| Scope            | Providers module                          |
| Primary actor    | operator                                  |
| Secondary actors | —                                         |
| Traces to        | US-prov-005, US-prov-009; ADR-0037        |

## Stakeholders and Interests

| Stakeholder | Interest                                                                  |
| ----------- | ------------------------------------------------------------------------- |
| operator    | Verified TLS against a self-signed endpoint without disabling the check   |
| admin       | Store contents are admin-managed; a store in use cannot silently disappear |

## Preconditions

- Actor holds `providers:write` on the provider and `trust_stores:read`.
- At least one trust store exists (otherwise see EC-prov-028).

## Success Guarantee (Postconditions)

- The provider references the store; outgoing TLS verifies against the store's CAs while verification stays on.
- Minimal guarantee: an unbind never disables verification — it reverts to system trust.

## Trigger

Actor selects (or clears) a trust store in the provider form and saves.

## Main Success Scenario

| Step | Actor                                   | System                                                                                     |
| ---- | --------------------------------------- | ------------------------------------------------------------------------------------------ |
| 1    | Actor picks a store from the list       |                                                                                            |
| 2    |                                         | System stores the binding; subsequent calls verify against the store's CAs                 |
| 3    | Actor clears the store binding later    | System unbinds; verification stays on with system trust (explicit null unbinds)            |

## Extensions (Alternative Flows)

| At step | Condition                                   | Handling                                                                        |
| ------- | ------------------------------------------- | -------------------------------------------------------------------------------- |
| 1       | No store exists yet                         | Show an actionable empty state pointing to admin trust stores (EC-prov-028)      |
| 2       | `verify_ssl` is false on the provider       | Verification is off; the store has no effect until verification is re-enabled (EC-prov-026) |

## Sub-variations

| At step | Variation                                        |
| ------- | ------------------------------------------------ |
| 1       | Binding set at creation time in the same form    |

## Related Artifacts

- User stories: [US-prov-005](../stories/providers.md)
- Edge-case rows: docs/analitics/edge-cases/providers.md "Bind trust store"
- Open questions: none

---

# UC-prov-007: Manage a trust store

## Header

| Field            | Value                                     |
| ---------------- | ----------------------------------------- |
| ID               | UC-prov-007                               |
| Name             | Manage a trust store                      |
| Goal level       | user-goal                                 |
| Scope            | Providers module (admin side)             |
| Primary actor    | admin                                     |
| Secondary actors | —                                         |
| Traces to        | US-prov-009; ADR-0037                     |

## Stakeholders and Interests

| Stakeholder | Interest                                                              |
| ----------- | --------------------------------------------------------------------- |
| admin       | Maintain correct CA sets; invalid PEM never enters a store            |
| operator    | Stores referenced by providers never vanish silently                  |

## Preconditions

- Actor holds `trust_stores:write` (read for inspection: `trust_stores:read`).

## Success Guarantee (Postconditions)

- The store exists with validated certificates (or is removed when unused).
- Minimal guarantee: a failed certificate upload leaves the store unchanged; a gated delete leaves it and its referrers untouched.

## Trigger

Actor creates/edits a store, uploads or removes certificates, or deletes a store.

## Main Success Scenario

| Step | Actor                                              | System                                                                        |
| ---- | -------------------------------------------------- | ------------------------------------------------------------------------------ |
| 1    | Actor creates a named store                        | System stores it with a globally unique name                                    |
| 2    | Actor pastes PEM (single cert or a chain)          | System parses and validates each block, splits chains into `-1, -2, …` entries, computes SHA-256 fingerprints and stores them |
| 3    | Actor views the store                              | System shows certificates with fingerprints; PEM is returned as-is (public material) |
| 4    | Actor deletes a certificate or an unused store     | System removes it; a store referenced by providers is refused with their names  |

## Extensions (Alternative Flows)

| At step | Condition                                       | Handling                                                        |
| ------- | ----------------------------------------------- | ---------------------------------------------------------------- |
| 1       | Duplicate store name                            | Reject with conflict (EC-prov-040)                               |
| 2       | Text contains no parseable certificate / garbage block | Reject with a validation error; nothing stored (EC-prov-041) |
| 2       | Nested certificate blocks                       | Reject with a validation error (EC-prov-042)                     |
| 2       | Duplicate certificate name in store or request  | Reject with conflict (EC-prov-043)                               |
| 4       | Store referenced by providers                   | Refuse with conflict listing the providers (EC-prov-044)         |
| 4       | Certificate not found                           | Refuse with not-found (EC-prov-045)                              |

## Sub-variations

| At step | Variation                                        |
| ------- | ------------------------------------------------ |
| 2       | Upload of several named certificates in one request |

## Related Artifacts

- User stories: [US-prov-009](../stories/providers.md)
- Edge-case rows: docs/analitics/edge-cases/providers.md "Manage trust store"
- Open questions: none

---

# UC-prov-008: List integration resources through a provider

## Header

| Field            | Value                                                       |
| ---------------- | ----------------------------------------------------------- |
| ID               | UC-prov-008                                                 |
| Name             | List integration resources through a provider               |
| Goal level       | user-goal                                                   |
| Scope            | Providers module (domain actions)                           |
| Primary actor    | operator                                                    |
| Secondary actors | External system (Git/Docker/Helm API)                       |
| Traces to        | US-prov-010; ADR-0007 §6                                    |

## Stakeholders and Interests

| Stakeholder      | Interest                                                              |
| ---------------- | --------------------------------------------------------------------- |
| operator         | One uniform way to discover groups/repos/projects/charts per provider |
| consumer modules | Reuse the dispatch instead of subtype-specific code                   |
| admin            | `trigger_pipeline` stays reserved for the platform's own GitLab       |

## Preconditions

- Actor may read the provider and holds `providers:use` scoped to it.

## Success Guarantee (Postconditions)

- The action result (action name + items) is returned; nothing in BigBug is mutated.
- Minimal guarantee: on failure no partial items are persisted anywhere by this use case.

## Trigger

Actor (or a consumer module on the actor's behalf) requests a domain action with parameters.

## Main Success Scenario

| Step | Actor                                       | System                                                                            |
| ---- | ------------------------------------------- | ---------------------------------------------------------------------------------- |
| 1    | Actor requests an action (e.g. list groups) |                                                                                    |
| 2    |                                             | System checks the capability against the registry for (subtype, category, direction) |
| 3    |                                             | System decrypts the credential, builds TLS settings and calls the external system   |
| 4    |                                             | System returns the action name and items in a uniform shape                         |

## Extensions (Alternative Flows)

| At step | Condition                                            | Handling                                                       |
| ------- | ---------------------------------------------------- | ---------------------------------------------------------------- |
| 2       | Capability not allowed for (category, direction)     | Refuse with 403 naming the action and combination (EC-prov-050)  |
| 3       | Client error 401/403/404/other                       | Same error semantics as UC-prov-002 (EC-prov-021..025)           |
| 3       | Anonymous provider calling an auth-required action   | Anonymous-access explanation (EC-prov-021)                       |

## Sub-variations

| At step | Variation                                                     |
| ------- | ------------------------------------------------------------- |
| 1       | `trigger_pipeline` requested on the system/internal GitLab (used by git mirroring) |

## Related Artifacts

- User stories: [US-prov-010](../stories/providers.md)
- Edge-case rows: docs/analitics/edge-cases/providers.md "Domain actions"
- Open questions: none

---

# UC-prov-009: Manage credentials centrally

## Header

| Field            | Value                                     |
| ---------------- | ----------------------------------------- |
| ID               | UC-prov-009                               |
| Name             | Manage credentials centrally              |
| Goal level       | user-goal                                 |
| Scope            | Providers module (admin side)             |
| Primary actor    | admin                                     |
| Secondary actors | —                                         |
| Traces to        | US-prov-008; ADR-0010, ADR-0026           |

## Stakeholders and Interests

| Stakeholder | Interest                                                            |
| ----------- | ------------------------------------------------------------------- |
| admin       | One controlled place for secrets; every mutation audited            |
| operator    | Credentials created here are attachable to own providers            |
| auditor     | Audit trail of who touched which credential and when                |

## Preconditions

- Actor holds `credentials:write` (read: `credentials:read`).

## Success Guarantee (Postconditions)

- The credential exists/changed/retired with an audit event per mutation; the secret is never present in any response.
- Minimal guarantee: a failed mutation leaves the credential unchanged.

## Trigger

Actor performs a credentials operation on the admin credentials page.

## Main Success Scenario

| Step | Actor                                       | System                                                       |
| ---- | ------------------------------------------- | -------------------------------------------------------------- |
| 1    | Actor creates a credential (type, name, username, secret) |                                                  |
| 2    |                                             | System encrypts the secret and stores the credential           |
| 3    | Actor updates fields or replaces the secret | System re-encrypts on secret change; other fields update in place |
| 4    | Actor retires (deletes) the credential      | System soft-deletes it and records the audit event             |

## Extensions (Alternative Flows)

| At step | Condition                                        | Handling                                              |
| ------- | ------------------------------------------------ | ------------------------------------------------------ |
| 1       | Secret empty where required                      | Reject with a field error (EC-prov-030)                 |
| 1       | Credential name already taken (hard-unique)      | Reject with conflict (EC-prov-033)                      |
| 3       | Credential is attached to providers and retired  | Provider bindings are detached (FK SET NULL); providers keep working anonymously (EC-prov-034) |
| 4       | Actor triggers "test"                            | Status is recorded and audited; current implementation records OK without contacting the target — see EC-prov-031 (gap) |

## Sub-variations

| At step | Variation                                        |
| ------- | ------------------------------------------------ |
| 1       | SSH key credential: public key stored alongside the secret |

## Related Artifacts

- User stories: [US-prov-008](../stories/providers.md)
- Edge-case rows: docs/analitics/edge-cases/providers.md "Manage credentials"
- Open questions: EC-prov-031 (credential test semantics)

---

# UC-prov-010: Inspect provider usage

## Header

| Field            | Value                                     |
| ---------------- | ----------------------------------------- |
| ID               | UC-prov-010                               |
| Name             | Inspect provider usage                    |
| Goal level       | user-goal                                 |
| Scope            | Providers module                          |
| Primary actor    | viewer                                    |
| Secondary actors | —                                         |
| Traces to        | US-prov-006; ADR-0007 §5                  |

## Stakeholders and Interests

| Stakeholder | Interest                                                         |
| ----------- | ---------------------------------------------------------------- |
| viewer      | Understand what depends on a provider                            |
| operator    | Know what to clean up before deletion (UC-prov-005)              |
| admin       | The same usage data gates deletion — one source of truth         |

## Preconditions

- Actor may read the provider and holds `providers:read`.

## Success Guarantee (Postconditions)

- The actor sees per-consumer-type counts of live references.
- Minimal guarantee: no consumer data is exposed beyond types and counts.

## Trigger

Actor opens the usage view of a provider.

## Main Success Scenario

| Step | Actor                              | System                                                          |
| ---- | ---------------------------------- | ----------------------------------------------------------------- |
| 1    | Actor opens usage for a provider   |                                                                    |
| 2    |                                    | System counts live references per consumer table and returns them  |
| 3    |                                    | System displays the counts grouped by consumer type                |

## Extensions (Alternative Flows)

| At step | Condition                                  | Handling                                    |
| ------- | ------------------------------------------ | --------------------------------------------- |
| 1       | Provider is hidden (system, not privileged) | Not-found, existence not leaked (EC-prov-018) |
| 1       | Provider unknown/deleted                   | Not-found (EC-prov-019)                       |

## Sub-variations

| At step | Variation                                                    |
| ------- | ------------------------------------------------------------- |
| 2       | Docker image sources count source and target sides separately |

## Related Artifacts

- User stories: [US-prov-006](../stories/providers.md)
- Edge-case rows: docs/analitics/edge-cases/providers.md "Browse providers", "Delete provider"
- Open questions: none
