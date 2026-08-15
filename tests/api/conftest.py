"""API test fixtures: keep history writes out of the developer's .bot-api/.

Unit tests that call ``_finalize`` (api/executor.py) or drive the router
write finished runs into the JSONL history. Without isolation they pollute
the real ``.bot-api/history.jsonl`` (test fixtures showed up as fake
\"weight\" runs in the console history). This autouse fixture redirects the
history file to a per-test tmp dir so no test can touch real runtime data.
"""

from __future__ import annotations

import pytest

from api import history as history_store


@pytest.fixture(autouse=True)
def isolated_history(tmp_path, monkeypatch):
    """Point the history JSONL (and its rotation/prune base dir) at a
    per-test temp dir — append/load read the module globals at call time,
    so monkeypatching suffices. No test can touch the real .bot-api/."""
    monkeypatch.setattr(history_store, "LOG_DIR", tmp_path)
    monkeypatch.setattr(history_store, "HISTORY_FILE", tmp_path / "history.jsonl")
    yield
