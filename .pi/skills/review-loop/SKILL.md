---
name: review-loop
description: Run review → fix → re-review until clean (default max 3 rounds)
type: prompt
targets: [pi-agent]
---

# Review Loop

## Configuration

- `maxIterations`: 3 ← rendered by --max-iterations at install time (default 3)
- `freshContext`: true ← fresh eyes every round

## Protocol

1. Run ONE review pass over the current changes (git diff / worktree) and list each issue (location, cause, fix suggestion);
   **follow the code-review skill for review content** (if installed: `.pi/skills/code-review/SKILL.md` or `/skill:code-review`; otherwise use the fallback checklist below: correctness / performance / maintainability / project conventions / architecture consistency)
1. If there are must-fix issues → fix them → end with "Fixed [N] issue(s). Ready for another review."
1. Re-review the fix with fresh eyes (don't reuse the previous round's conclusions)
1. Stop and summarize (rounds run, fixes applied, validation, remaining items) when any of these holds:
   - review found no issues ("No issues found.")
   - the maxIterations cap is reached
   - the user interrupted / remaining suggestions are optional polish
1. If the same issue shows up two rounds in a row → stop and ask for human intervention (the worker cannot fix it)

## Serial execution (mandatory)

- Rounds are strictly SERIAL: round N+1 starts only after round N's fixes are applied and validated.
- Never launch multiple review rounds at once. The order is always: one review pass → fixes → next review pass.
- One round = one reviewer. Do not split a round into multiple parallel reviewers.
- Use `review_loop({ start: true, maxIterations: ... })` when the tool is available — it enforces this
  serial loop natively. Only fall back to manual looping when the tool is missing.

## Division of labor with the code-review skill

- This skill only handles **loop control** (rounds, cap, exit detection, fresh eyes)
- **Review content** (dimensions, checklist, output format) is delegated to the code-review skill
- Without code-review installed, use the fallback checklist above

> Install code-review alongside it: `--skill review-loop --skill code-review` (or `--all`)
> — Pi auto-discovers skills from `.pi/skills/` and registers `/skill:<name>` commands; no other config needed

## Driver (degrade by availability)

- If the `review_loop` tool is available (pi-review-loop installed):
  `review_loop({ start: true, maxIterations: 3 })`
  Use `/review-max 3` in-session to adjust the cap
- Otherwise: loop manually per the protocol, counting rounds yourself, never exceeding maxIterations

## Project grounding

Before reviewing, read (if present): ./CONVENTIONS.md, ./ARCHITECTURE.md, ./README.md
