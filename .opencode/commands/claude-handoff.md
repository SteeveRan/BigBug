---
description: Hand the current conversation off to a fresh background agent that picks up the work immediately.
---
Invoke the `skill` tool with name `claude-handoff` and follow its instructions exactly as written.
Do NOT read `.opencode/skills/claude-handoff/SKILL.md` directly. Only if the `skill` tool is
unavailable or fails, fall back to reading `.opencode/skills/claude-handoff/SKILL.md`.

The user passed arguments: $ARGUMENTS
If the arguments are empty, ask the user for them before starting.
