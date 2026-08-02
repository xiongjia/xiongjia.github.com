---
description: Strict project-level code review (used by the review loop)
argument-hint: "[focus]"
---

You are reviewing this project's code. Review strictly with fresh eyes, at most 3 rounds.

## Read before reviewing

- ./README.md, ./CONVENTIONS.md, ./ARCHITECTURE.md (read if present)

## Review dimensions

1. Correctness: logic errors, null pointers, races, edge cases
2. Performance: needless loops, memory, repeated computation
3. Maintainability: naming, comments, complexity
4. Project conventions: compliance with ./CONVENTIONS.md
5. Architecture consistency: patterns conflicting with the existing architecture

## Output rules

- Issues found → fix them → end with "Fixed [N] issue(s). Ready for another review."
- No issues → output only "No issues found."
