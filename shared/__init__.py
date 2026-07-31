"""Shared utilities for MkDocs plugins and CLI scripts.

Consumers must bootstrap the repo root onto ``sys.path`` before importing
(see internal/plans/plugins-scripts-shared-module.md, Open Questions #1):

    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
"""
