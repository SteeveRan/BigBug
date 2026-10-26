# BigBug Design Contract (design.md)

> This file is the visual source of truth for ALL UI work in this repository
> (agents AND humans). Read it completely before planning, generating,
> reviewing, or modifying any user-facing UI. Normative: "MUST" is enforced by
> CI gates and code review; violations block the PR.

## Canonical tokens (code owns the truth)

The product's visual identity is defined in code, nowhere else:

| Source | Covers | Location |
|---|---|---|
| Ant Design 6 defaults + `darkAlgorithm` (default) / `lightAlgorithm` | all AntD component tokens | `frontend/src/theme.ts` |
| Brand palette (primary `#7C3AED` + derived), radius (6/8/4), Inter, font size 14 | AntD token overrides | `frontend/src/theme.ts` (`sharedToken`, `darkTheme`, `lightTheme`) |
| Custom components outside AntD | CSS variables `--bigbug-*` (bg, border, text, brand) | `frontend/src/colors.css` (switched via `data-theme` on `<html>`) |

Rules:

1. Components MUST NOT contain raw colors, hex literals, ad-hoc px sizes,
   radii, shadows, or `!important` overrides. Reference AntD tokens
   (`theme.useToken()` / `token.*`) or `--bigbug-*` variables instead.
2. New visual constants MUST be added to `theme.ts` / `colors.css` first
   (PR that touches only those files is preferred), then consumed from there.
3. Dark theme is the default. Every screen MUST work in both themes.
4. Use existing AntD components as-is (Table, Form, Tree, Select...). Do not
   rebuild what AntD provides; do not restyle AntD components beyond documented
   token overrides.
5. Typography: Inter, base size 14, line-height 1.5715 (from `sharedToken`).
   No other font families or one-off sizes.

## Penpot (design mirror & sketch surface)

Self-hosted Penpot runs on the dev stand (`https://penpot.local`, TLS via the
shared BigBug Dev CA). Its role is NOT a second source of truth:

- The Penpot **library mirrors the canon**: AntD default components with
  brand overrides from `theme.ts`. Build/refresh it with the
  `penpot-generate-library` skill (extracts tokens from the codebase).
- **Screens/frames are sketches for approval**, built ONLY from library
  components bound to tokens (`penpot-generate-design` skill). Never invent
  new tokens, colors, or components inside Penpot.
- Pipeline for a UI feature: analytics (US/UC) → docs-PR if visual language
  changes → sketch frame in Penpot (design-phase issue) → owner approval →
  implementation issue (MUST link the Penpot frame) → code → review compares
  the implementation against `export_shape` screenshots from Penpot.
- If code and a Penpot frame disagree, the CODE is right (it is the canon):
  update the frame, and report the discrepancy in the issue — do not silently
  reconcile either way.

## Agent skills

- `.opencode/skills/penpot-*` — Penpot MCP workflows (tokens → library →
  screens, a11y audit, Figma import). Order matters: tokens/library FIRST,
  screens SECOND.
- MCP endpoint for agents: `https://penpot.local/mcp/stream?userToken=<token>`
  (streamable HTTP; token from the Penpot UI — Your account → Integrations →
  MCP Server; regenerate when the session expires).
- `execute_code` / `export_shape` require the **Penpot MCP plugin** running in
  the browser on the focused file. MCP operates on the currently focused page.

## Verification (planned gates)

- `design-tokens` CI gate: lint forbids raw hex/px in `frontend/src/{components,pages}` outside `theme.ts`/`colors.css`.
- `make check-tokens`: drift diff between the code canon and the Penpot library token export.
- `make check-adr-order`: design docs go in a docs-PR BEFORE implementation (existing gate).
