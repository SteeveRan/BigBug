---
artifact: edge-case-catalog
version: "1.1"
---

# Edge-Case Catalog: Providers

> Living document: `docs/analitics/edge-cases/providers.md`. One catalog table per
> user-facing operation. Vocabulary: `GLOSSARY.md`. No implementation file
> paths in "Expected behavior" — name the seam, not the code.
> Row IDs (EC-prov-NNN) are stable; adding rows is allowed, renumbering is not.

## Overview

| Field                  | Value                                                                                                                                                                         |
| ---------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Module                 | Providers                                                                                                                                                                      |
| Purpose                | Register and manage external integrations (Git, Docker/OCI, Helm) as Resource Providers with typed Credentials and Trust Stores; verify connectivity and expose usage to consumers safely (ADR-0007, ADR-0037, ADR-0010). |
| User-facing operations | create provider, edit provider, test connection, attach credential, share/unshare, delete, browse/list, usage, domain actions, manage credentials, manage trust stores, set default |
| Permissions            | `providers:read`, `providers:write`, `providers:delete`, `providers:use`, `providers:read_all`, `providers_system:write`, `providers:share`, `credentials:read`, `credentials:write`, `trust_stores:read`, `trust_stores:write` |
| Bound ADRs             | ADR-0007 (Providers V3 registry), ADR-0037 (trust stores), ADR-0010 (Fernet secrets), ADR-0004 (RBAC scope-providers), ADR-0026 (audit), ADR-0028 (transport/verify_ssl)        |

## Create provider

| #   | ID            | Condition                                            | Required behavior (system MUST...)                                                                 | Required recovery (system MUST offer)                        | Severity | Closing test                                                        |
| --- | ------------- | ---------------------------------------------------- | --------------------------------------------------------------------------------------------------- | ------------------------------------------------------------- | -------- | -------------------------------------------------------------------- |
| 1   | EC-prov-001   | Subtype offered only in the `system` category        | not offer the subtype for user creation; system providers are never API-creatable                    | —                                                              | P2       | unit `test_system_creation_forbidden_even_with_permission`; e2e `test_create_system_provider_forbidden` |
| 2   | EC-prov-002   | Duplicate live provider name                         | reject with 409 conflict and store nothing                                                          | show "name exists" with the name editable                      | P2       | unit `test_duplicate_name_conflict`; e2e `test_create_duplicate_name_409`                   |
| 3   | EC-prov-003   | Subtype does not belong to the selected domain       | reject with a field error naming the correct domain                                                  | domain picker correction                                        | P3       | unit `test_domain_mismatch_rejected` (test_provider_schema.py)               |
| 4   | EC-prov-004   | Category/direction not allowed for the subtype       | reject with a field error (422)                                                                      | inline field error                                             | P2       | e2e `test_create_invalid_category_422`                                      |
| 5   | EC-prov-005   | Required `base_url` missing (subtype requires it)    | reject with a field error and store nothing                                                          | inline field error on base URL                                 | P2       | unit `test_requires_base_url_for_generic_git`; `test_base_url_satisfies_generic_git` |
| 6   | EC-prov-006   | Unknown key in `config` (not in subtype schema)      | reject naming the unknown key(s); nothing stored (schema is closed — `additionalProperties: false`)  | inline field error listing the keys                            | P2       | unit `test_unknown_config_key_rejected`; `test_provider_registry.py::test_specs_have_config_schema` |
| 7   | EC-prov-007   | Secret-like key in `config` (deny-list: exact names and `*_token/_password/_secret/_key/_credentials` suffixes) | reject naming the key; nothing stored — the secret belongs in a credential | message directing to the credential field | P1 | unit `test_exact_keys_rejected`, `test_suffix_keys_rejected` (test_provider_security.py); frontend `ProviderFormModal` mirror check |
| 8   | EC-prov-008   | `category=system` in an API create                   | reject with 403 regardless of the caller's permissions (even admin)                                  | —                                                              | P1       | unit `test_system_create_forbidden_for_admin` (test_rbac_providers.py)       |
| 9   | EC-prov-009   | Team visibility requested without team membership    | reject with a field error; nothing stored                                                            | team picker limited to own teams                               | P2       | unit `test_create_team_membership_required` (test_providers_create_team.py)  |
| 10  | EC-prov-035   | `name` or `label` over 255 chars / `base_url` over 500 | reject with a field error and store nothing                                                        | inline field errors                                            | P3       | gap -> #165                                                                  |

## Edit provider

| #   | ID            | Condition                                   | Required behavior (system MUST...)                                       | Required recovery (system MUST offer)      | Severity | Closing test                                                    |
| --- | ------------- | -------------------------------------------- | ------------------------------------------------------------------------- | ------------------------------------------- | -------- | ---------------------------------------------------------------- |
| 1   | EC-prov-010a  | Category change attempted via PATCH          | reject with 400: "changing category is not supported" (category is ownership axis, immutable) | recreate-with-new-category guidance | P2 | unit `test_provider_service_crud.py` (category change) — `gap -> #165` for a named case |
| 2   | EC-prov-012a  | Default flag set by non-admin                | reject with 403 naming the required rights (`providers_system:write` or `admin:panel:access`) | —             | P2       | unit `test_operator_cannot_set_default`; e2e `test_operator_cannot_set_default` |
| 3   | EC-prov-013a  | New default set in a scope with an existing default | clear the previous default in the same (domain, subtype, category, direction) scope atomically; exactly one default remains | — | P2 | unit `test_switch_default_unsets_previous`; constraints `test_resource_provider_constraints.py` (uq_default_per_scope) |
| 4   | EC-prov-014a  | Trust store field absent in PATCH            | keep the current binding (absent ≠ null); explicit `null` unbinds         | —                                            | P1       | unit `test_provider_patch_trust_store_id` / `test_provider_patch_trust_store_null_unbinds` (test_trust_store_api.py) |
| 5   | EC-prov-015a  | Edit without touching the credential         | keep the previously attached credential                                   | —                                            | P2       | AC-3 of US-prov-003; frontend integration `ProviderFormModal.test.tsx` — `gap -> #165` for backend case |
| 6   | EC-prov-016a  | Private provider mutated by non-owner        | reject with 403 "not the owner" (unless `providers:read_all`)             | —                                            | P1       | unit `test_private_hidden_from_other_user` (test_provider_service_crud.py) |

## Test provider connection

| #   | ID            | Condition                                              | Required behavior (system MUST...)                                                                          | Required recovery (system MUST offer)              | Severity | Closing test                                                        |
| --- | ------------- | ------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------- | -------- | ---------------------------------------------------------------------- |
| 1   | EC-prov-021   | No credential attached; the endpoint demands auth (HTTP 401) | record Failed and explain the anonymous case: "requires authentication … only public resources. Attach a credential." | open the credential form / assign credential     | P1       | unit `test_401_anonymous_requires_auth` (test_provider_service_crud.py) |
| 2   | EC-prov-022   | HTTP 401 with a credential attached                     | record Failed: "authentication failed (HTTP 401). Check that the provider credential is valid."                | re-enter the credential (link to credential assign)  | P1       | unit `test_401_with_credential_is_auth_failure`                          |
| 3   | EC-prov-023   | HTTP 403 from the external system                       | record Failed: "credential lacks permission for this resource"                                                  | show the reason; suggest checking the account scopes | P1       | gap -> #165 (mapping covered by `_client_error`; no named test)          |
| 4   | EC-prov-024   | HTTP 404 from the external system                       | record Failed: "resource not found (HTTP 404)"                                                                  | check base URL / resource id                         | P2       | gap -> #165                                                              |
| 5   | EC-prov-025   | Timeout / unreachable / TLS failure / other HTTP error  | record Failed: "request failed" with the provider reason (client errors map to 502-class); status text truncated to 500 chars | show the reason with a Retry                     | P1       | gap -> #165                                                              |
| 6   | EC-prov-026   | Trust store bound but certificate untrusted (or `verify_ssl=false` overrides the store) | never silently disable verification: a bound store changes only the trust source; `verify_ssl=false` wins and is a deliberate act | fix the store contents or consciously set verify_ssl=false | P1 | unit `test_verify_ssl_false_wins`, `test_verify_ssl_false_ignores_store` (test_trust_store_tls.py) |
| 7   | EC-prov-027   | Client path ignores custom CAs (known gaps: PyGitHub, crane, cosign — ADR-0037) | behave per the ADR-0037 known-gap contract (system trust or no verification on that path); not regress to silent store assumption | — | P2 | gap -> grill #139 (C2 cosign fail-open) |
| 8   | EC-prov-028   | Test of a hidden system provider by a non-privileged user | behave as not-found (existence not leaked)                                                                   | —                                                    | P2       | unit `test_system_hidden_from_regular` (test_providers_visibility.py)    |

## Attach credential / assign

| #   | ID            | Condition                                        | Required behavior (system MUST...)                                     | Required recovery (system MUST offer)        | Severity | Closing test                                                     |
| --- | ------------- | ------------------------------------------------- | ------------------------------------------------------------------------- | ----------------------------------------------- | -------- | ------------------------------------------------------------------- |
| 1   | EC-prov-020   | Anonymous access toggled on                       | clear the credential binding (null) and store the provider anonymous; failure messages must distinguish anonymous from bad-credential | re-attach a credential later | P2 | frontend `ProviderFormModal.test.tsx` (anonymous switch); e2e `test_create_get_update_delete` — `gap -> #165` for the backend null-binding case |
| 2   | EC-prov-030   | Secret empty where the credential type requires it | reject with a field error; nothing stored                               | inline field error                              | P1       | unit `test_create_requires_secret` (test_credential_schema.py)        |
| 3   | EC-prov-031   | Credential "test" triggered                       | verify the secret against the target system and record the real outcome  | show the failure reason with a Retry            | P1       | **gap** — current implementation records OK without any network validation; divergence reported in #165, owner: credentials lifecycle |
| 4   | EC-prov-032   | Credential attached to a provider is soft-deleted | detach the provider (FK SET NULL); the provider continues anonymous; its next test reports the anonymous explanation (EC-prov-021) | re-attach a credential | P2 | model FK `credential_id ON DELETE SET NULL`; e2e `test_credentials_crud.py` — `gap -> #165` for provider-side detachment |
| 5   | EC-prov-033   | Credential name already taken (hard DB unique — retired names are NOT reusable) | reject with conflict naming the existing credential | rename prompt | P2 | **gap** — divergence between credential (hard unique) and provider/trust-store (partial unique, name reusable); reported in #165 |

## Share provider

| #   | ID            | Condition                                    | Required behavior (system MUST...)                    | Required recovery (system MUST offer) | Severity | Closing test                                              |
| --- | ------------- | --------------------------------------------- | -------------------------------------------------------- | ---------------------------------------- | -------- | ------------------------------------------------------------ |
| 1   | EC-prov-010   | Non-owner shares (without `providers:read_all`) | reject with 403 "not the owner"                        | —                                         | P1       | unit `test_share_non_owner_403` (test_providers_share.py)     |
| 2   | EC-prov-011   | Provider is not private (public/system)       | reject with 400: only private providers can be shared   | —                                         | P2       | unit `test_share_success` matrix + service rule — `gap -> #165` for a named test |
| 3   | EC-prov-012   | Provider already team-shared                  | reject with 409                                         | offer unshare first                        | P2       | unit `test_share_already_team_409`                            |
| 4   | EC-prov-013   | Actor not a member of the target team         | reject with 422 (unless `providers:read_all`)           | team picker limited to own teams           | P2       | unit `test_share_non_member_422`                              |
| 5   | EC-prov-014   | Unshare while not shared                      | reject with 409                                         | —                                          | P3       | unit `test_unshare_not_team_409`                              |
| 6   | EC-prov-018a  | Share without `providers:share`               | reject with 403 naming the permission                   | —                                          | P1       | unit `test_share_without_permission_403`                      |

## Delete provider

| #   | ID            | Condition                                    | Required behavior (system MUST...)                                              | Required recovery (system MUST offer)                  | Severity | Closing test                                                              |
| --- | ------------- | --------------------------------------------- | ----------------------------------------------------------------------------------- | ---------------------------------------------------------- | -------- | ---------------------------------------------------------------------------- |
| 1   | EC-prov-015   | Provider is protected (system category)       | refuse with 409: "Protected provider cannot be deleted"                             | —                                                           | P1       | unit `test_protected_delete_conflict`                                         |
| 2   | EC-prov-016   | Live consumers exist (pipelines, source_repositories, docker_image_sources source+target, helm_chart_sources, gitlab_projects) | refuse with 409 listing consumers per type and delete nothing; soft-deleted consumers are not counted | usage view listing what blocks deletion | P1 | unit `test_provider_service_crud.py` + e2e `test_providers_usage.py` — `gap -> #165` for a named 409-usage case |
| 3   | EC-prov-017   | Actor lacks `providers:delete` (non-system)   | refuse with 403                                                                     | —                                                           | P1       | e2e `test_viewer_without_write_403`; RBAC matrix unit `test_viewer_read_only`  |
| 4   | EC-prov-019a  | Deletion of a provider that is the scope default | allowed; the scope is left without a default until an admin designates a new one | show a hint that the scope default was removed             | P3       | gap -> #165                                                                  |

## Browse providers

| #   | ID            | Condition                                        | Required behavior (system MUST...)                                       | Required recovery (system MUST offer) | Severity | Closing test                                                                 |
| --- | ------------- | ------------------------------------------------- | ---------------------------------------------------------------------------- | ---------------------------------------- | -------- | -------------------------------------------------------------------------------- |
| 1   | EC-prov-018   | System provider requested by a non-privileged user | respond as not-found (404), never 403 — existence of hidden providers is not leaked | —                          | P1       | unit `test_system_provider_visible_without_read_all`; api `_is_system_visible` → 404 |
| 2   | EC-prov-019   | Provider id unknown or already deleted            | respond 404                                                                   | —                                         | P3       | unit `test_get_missing_404` (trust-store analog); providers analog `gap -> #165` |
| 3   | EC-prov-022a  | Filters combined (domain+subtype+category+direction+owner=me) | apply all filters AND-wise to the visibility-filtered base list    | reset-filters control                    | P3       | e2e `test_owner_me_filter` — `gap -> #165` for combined filters               |
| 4   | EC-prov-023a  | Caller without `providers:read`                   | refuse with 403                                                              | —                                         | P1       | e2e `test_viewer_without_write_403` (read allowed) / RBAC matrix              |

## Domain actions (list groups / repositories / projects / charts, get commit, trigger pipeline)

| #   | ID            | Condition                                              | Required behavior (system MUST...)                                                | Required recovery (system MUST offer) | Severity | Closing test                                                        |
| --- | ------------- | ------------------------------------------------------- | -------------------------------------------------------------------------------------- | ---------------------------------------- | -------- | ------------------------------------------------------------------------ |
| 1   | EC-prov-050   | Action not allowed for the (subtype, category, direction) combination — e.g. `trigger_pipeline` off the system/internal GitLab | refuse with 403 naming the action and the combination; never dispatch | —             | P1       | unit `test_trigger_pipeline_only_gitlab_system_internal`, `test_no_other_subtype_has_trigger_pipeline` (test_provider_registry.py) |
| 2   | EC-prov-051   | Consumer error 401/403/404/other during the action      | map to the same error semantics as the connection test (EC-prov-021..025), naming the subtype | Retry / fix credential      | P1       | unit `test_401_anonymous_requires_auth` / `test_401_with_credential_is_auth_failure` (shared `_client_error`) |
| 3   | EC-prov-052   | Action params missing/empty (e.g. group id)             | reject or return a meaningful provider-side error; never a silent empty success | inline param error                  | P2       | gap -> #165                                                              |
| 4   | EC-prov-053   | Caller without scoped `providers:use` on the provider   | refuse with 403 before any external call                                                | —                                         | P1       | unit `test_provider_scope_denies_without_link` (test_rbac_providers.py)   |

## Manage credentials

| #   | ID            | Condition                                       | Required behavior (system MUST...)                                        | Required recovery (system MUST offer) | Severity | Closing test                                             |
| --- | ------------- | -------------------------------------------------- | ------------------------------------------------------------------------------ | ---------------------------------------- | -------- | ------------------------------------------------------------- |
| 1   | EC-prov-055   | Any credentials mutation (create/update/delete/test) | write an audit event recording actor, action, credential (ADR-0026)       | —                                         | P1       | e2e `test_credentials_crud.py`; audit asserted — `gap -> #165` for explicit audit assertions |
| 2   | EC-prov-056   | Credential listed/fetched                           | never include the secret or its ciphertext in the response                | —                                         | P1       | unit `test_out_has_no_secret_or_encrypted_secret` (test_credential_schema.py); `test_provider_security.py` |
| 3   | EC-prov-031   | (see "Attach credential") Credential test must actually verify | —                                                              | —                                         | P1       | gap -> #165                                                   |
| 4   | EC-prov-057   | Caller without `credentials:read`                   | refuse with 403                                                           | —                                         | P2       | RBAC matrix `test_credentials_read_is_kept` — `gap -> #165` for API-level case |

## Manage trust store

| #   | ID            | Condition                                       | Required behavior (system MUST...)                                                              | Required recovery (system MUST offer)            | Severity | Closing test                                                          |
| --- | ------------- | -------------------------------------------------- | ---------------------------------------------------------------------------------------------------- | ----------------------------------------------------- | -------- | -------------------------------------------------------------------------- |
| 1   | EC-prov-040   | Duplicate store name                               | reject with 409 conflict                                                                             | rename prompt                                          | P2       | unit `test_duplicate_name_409` (test_trust_store_service.py)                |
| 2   | EC-prov-041   | PEM text contains no parseable certificate / garbage block | reject with 422 validation error; store nothing                                              | inline error pointing at the PEM field                 | P1       | unit `test_invalid_pem_422`, `test_garbage_block_422`                        |
| 3   | EC-prov-042   | Nested certificate blocks in one PEM text          | reject with 422 ("nested certificate blocks")                                                        | split the chain before pasting                          | P3       | unit `_parse_pem_blocks` path — `gap -> #165` for a named test               |
| 4   | EC-prov-043   | Duplicate certificate name in store or request     | reject with 409 before any insert                                                                   | rename prompt                                           | P2       | unit `test_duplicate_cert_name_409`                                          |
| 5   | EC-prov-044   | Store referenced by providers is deleted           | refuse with 409 listing the referring providers by name (FK RESTRICT, usage gate)                    | usage view of the store                                 | P1       | unit `test_delete_store_with_provider_409_with_names`; `test_delete_in_use_409` (test_trust_store_api.py) |
| 6   | EC-prov-045   | Certificate id not found in the store              | refuse with 404                                                                                       | —                                                       | P3       | unit `test_delete_missing_certificate_404`                                   |
| 7   | EC-prov-046   | Chain paste (multiple PEM blocks in one text)      | split into separate entries named `<name>-1`, `<name>-2`, …; validate each block; compute fingerprints | re-paste with explicit names if the suffixing is unwanted | P2   | unit `test_chain_of_three_pem_blocks_creates_three_rows`                     |
| 8   | EC-prov-047   | Store deleted while a stale bundle file remains on a pod | never serve stale trust: bundle content is re-checked against the DB on every resolve; orphan files are garbage only | —                              | P1       | unit `test_bundle_file_written_and_regenerated` (test_trust_store_tls.py)    |
| 9   | EC-prov-048   | Operator (no `trust_stores:write`) mutates a store | refuse with 403 (write is admin-only; read allowed for binding pickers)                         | —                                        | P1       | unit `test_operator_write_403`, `test_operator_delete_403` (test_trust_store_api.py) |

## Concurrency

| #   | ID            | Condition                                                       | Required behavior (system MUST...)                                                                | Severity | Closing test                                                                 |
| --- | ------------- | ------------------------------------------------------------------ | -------------------------------------------------------------------------------------------------------- | -------- | --------------------------------------------------------------------------------- |
| 1   | EC-prov-060   | Two providers created with the same name simultaneously            | partial unique index holds: one creation succeeds, the other fails with a conflict (name unique among live rows) | P2 | constraints `test_resource_provider_constraints.py` (uq_resource_providers_name) |
| 2   | EC-prov-061   | Two admins set different defaults in one scope simultaneously      | exactly one default survives (partial unique `uq_default_per_scope`); the loser fails or is auto-cleared  | P2       | constraints `test_resource_provider_constraints.py` — `gap -> #165` for the API-level case |
| 3   | EC-prov-062   | Provider deleted while a consumer registers it                     | consumer-side FK/usage gate refuses (registering against a deleted provider MUST fail); no dangling registration | P2 | gap -> #165 (cross-module: consumer seam)                                         |
| 4   | EC-prov-063   | Double-submit of the provider form                                 | second submission hits the duplicate-name conflict (409), not a silent second provider                     | P3       | gap -> #165 (frontend dedupe)                                                     |

## Error message copy

| Error state                    | User message                                                                                                                              | Additional action (button/link)                     |
| ------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------ | ----------------------------------------------------- |
| EC-prov-021 (anonymous 401)    | "<subtype> requires authentication for this operation; this provider is anonymous and can only access public resources. Attach a credential to access private resources." | "Assign credential" → credential assign modal         |
| EC-prov-022 (401 with credential) | "<subtype> authentication failed (HTTP 401). Check that the provider credential is valid."                                              | "Edit credential"                                     |
| EC-prov-023 (403)              | "<subtype> access forbidden (HTTP 403). The credential lacks permission for this resource."                                                 | "Check credential scopes"                             |
| EC-prov-024 (404)              | "<subtype> resource not found (HTTP 404)."                                                                                                  | "Edit base URL"                                       |
| EC-prov-025 (other/timeout)    | "<subtype> request failed: <reason>"                                                                                                        | "Retry"                                               |
| EC-prov-016 (delete in use)    | "Provider is in use: <consumers with counts>"                                                                                               | "View usage" → usage view                             |
| EC-prov-015 (protected delete) | "Protected provider cannot be deleted"                                                                                                      | —                                                     |
| EC-prov-044 (trust store in use) | "Trust store is in use by providers: <names>"                                                                                             | —                                                     |
| EC-prov-007 (secret-like key)  | "Секретные ключи (<key>) не допускаются в config — используйте credential" (frontend mirror of the server deny-list)                        | "Use credential field"                                |

## Rules

1. Every row needs a Closing test: an existing test case name, or an explicit
   `gap -> <ADR or issue>`. A row without either is invalid.
2. The catalog is the requirement, code complies with it. A PR whose behavior
   contradicts a row is incorrect and is returned. The catalog itself changes
   only through an explicit requirements change.
3. A row whose expected behavior encodes a real trade-off (hard to reverse,
   surprising, deliberate choice) must be surfaced to an ADR (`/adr`).
4. Flow narratives for operations live in use cases (`docs/analitics/use-cases/providers.md`),
   which reference these rows; the two must not contradict.
