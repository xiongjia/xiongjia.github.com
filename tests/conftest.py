"""Shared pytest fixtures: make scripts/ and health macros importable.

The macros live under docs/notes/health/macros/ (loaded by the mkdocs macros
plugin at build time) and the CLI scripts under scripts/; tests import them
directly, so both directories are added to sys.path once here instead of in
every test file.
"""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))
sys.path.insert(0, str(REPO_ROOT / "docs" / "notes" / "health" / "macros"))
