# Domain Docs

How the engineering skills should consume this repo's domain documentation when exploring the codebase.

## Before exploring, read these

- **`GLOSSARY.md`** at the repo root, or
- **`GLOSSARY-MAP.md`** at the repo root if it exists: it points at one `GLOSSARY.md` per context. Read each one relevant to the topic.
- **`docs/adr/README.md`**: the ADR registry — the single entry point for architecture decisions. Read ADRs that touch the area you're about to work in (they are grouped into `backend/`, `frontend/`, `common/`, `infrastructure/` subfolders).
- **`docs/modules/<module>.md`** (if it exists): the module's living charter — its user-facing operations, edge-case catalog, and closing tests. Update it in the same PR as any behavior change (see the `deliver-edge-cases` skill).

If any of these files don't exist, **proceed silently**. Don't flag their absence; don't suggest creating them upfront. The `/domain-modeling` skill (reached via `/grill-with-docs` and `/improve-codebase-architecture`) creates them lazily when terms or decisions actually get resolved.

## File structure

Single-context repo (this repo):

```
/
├── GLOSSARY.md
├── docs/adr/
│   ├── README.md                  ← ADR registry (single entry point)
│   ├── backend/                   ← service-scoped decisions
│   ├── frontend/
│   ├── common/                    ← decisions binding across services
│   └── infrastructure/
├── backend/
└── frontend/
```

A new service gets its own subfolder `docs/adr/<service>/` in the shared ADR registry; `common/` holds decisions binding across services. Switch to multi-context (root `GLOSSARY-MAP.md` + per-context glossaries, e.g. `backend/GLOSSARY.md`, `frontend/GLOSSARY.md`) only when services develop conflicting domain vocabularies.

Multi-context repo (presence of `GLOSSARY-MAP.md` at the root):

```
/
├── GLOSSARY-MAP.md
├── docs/adr/                          ← system-wide decisions
└── src/
    ├── ordering/
    │   ├── GLOSSARY.md
    │   └── docs/adr/                  ← context-specific decisions
    └── billing/
        ├── GLOSSARY.md
        └── docs/adr/
```

## Use the glossary's vocabulary

When your output names a domain concept (in an issue title, a refactor proposal, a hypothesis, a test name), use the term as defined in `GLOSSARY.md`. Don't drift to synonyms the glossary explicitly avoids.

If the concept you need isn't in the glossary yet, that's a signal: either you're inventing language the project doesn't use (reconsider) or there's a real gap (note it for `/domain-modeling`).

## Flag ADR conflicts

If your output contradicts an existing ADR, surface it explicitly rather than silently overriding:

> _Contradicts ADR-0007 (event-sourced orders), but worth reopening because…_
