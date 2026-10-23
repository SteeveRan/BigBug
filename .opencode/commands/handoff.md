---
description: Compact the current conversation into a handoff document for another agent to pick up.
---
Invoke the `skill` tool with name `handoff` and follow its instructions exactly as written.
Do NOT read `.opencode/skills/handoff/SKILL.md` directly. Only if the `skill` tool is
unavailable or fails, fall back to reading `.opencode/skills/handoff/SKILL.md`.

The user passed arguments: $ARGUMENTS
If the arguments are empty, ask the user for them before starting.
