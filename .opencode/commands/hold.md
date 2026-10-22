---
description: Freeze the agent — stop all actions, report state and reasoning, wait for explicit approval
agent: build
---

The user has signaled a deviation: something in your behavior feels wrong to them.
Enter FREEZE mode immediately and follow it exactly.

## 1. Stop everything

- Do not run any command, do not edit any file, do not spawn any sub-agent or
  background task. If a started action can be aborted — abort it.
- Do NOT fix anything. No "quick patches", no "let me just clean this up".
  Explanations first; fixes only after explicit human approval.
- The only allowed commands are read-only state checks: `git status`,
  `git diff --stat`, `git diff` (unstaged changes only). Run them once to know
  what state you left the workspace in. Nothing else.

## 2. Report in this exact structure

1. **What I did** — the last actions in order, files touched, commands run.
   Grounded in the git output from step 1, not in memory.
2. **Why I did it** — the reasoning at the time and what you actually verified
   before acting. If you did not verify anything before acting, say so plainly.
3. **Current state** — workspace clean / list of modified files / processes or
   background jobs still running.
4. **Suggestion** — one short proposal of what to do next. Do not execute it.

## 3. Wait

End your turn after the report. Do not take any action until the user replies.

If the user then says "ok" / "continue" / "fix it", resume work under these
constraints: fix only what was agreed, announce each step before doing it, and
return to FREEZE mode on the next deviation signal.
