"""Local CI-equivalent checks for the bot — keep in sync with ci.yml.

``scripts/git_bot.py`` runs these in the worktree before pushing (and again
on ``submit`` after manual tweaks). ``fmt`` mutates (auto-formats changed
md/py); the rest verify. See ``internal/bot-auto-pr-design.md`` → §2.
"""

from __future__ import annotations

CHECKS: list[list[str]] = [
    ["uv", "run", "poe", "fmt"],
    ["uv", "run", "poe", "check-fmt"],
    ["uv", "run", "poe", "lint-py"],
    ["uv", "run", "poe", "test"],
    ["uv", "run", "mkdocs", "build"],
]
