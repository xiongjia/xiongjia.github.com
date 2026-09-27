"""Combined macros entry point for the whole site.

mkdocs-macros accepts exactly one local ``module_name``, so this file is that
entry: it loads every section's macro module by path and delegates
``define_env`` to each of them.

- ``docs/notes/health/macros/health_macros.py`` — health pages (weight / retire /
  running); it in turn loads its own siblings.
- ``shared/macros/film_tv_macros.py`` — the film & TV archive pages.

Adding a section = one more ``_load_from_file`` entry here (plus the section's
paths in ``force_render_paths``).

Note the plugin resolves ``module_name`` as a **path** under the project root
(``module_name: shared/macros/loader``), not as a dotted package name.
"""

from __future__ import annotations

import importlib.util
import os
import sys

_dir = os.path.dirname(os.path.abspath(__file__))
_MKDOCS_YML = "mkdocs.yml"


def _find_repo_root(start: str) -> str:
    """Walk up from *start* until a directory holding mkdocs.yml is found.

    Same trick as the section macro modules: a hardcoded number of ``dirname``
    calls silently points at the wrong directory if this file moves, and the
    failure surfaces much later as a ModuleNotFoundError.
    """
    candidate = start
    while True:
        if os.path.isfile(os.path.join(candidate, _MKDOCS_YML)):
            return candidate
        parent = os.path.dirname(candidate)
        if parent == candidate:
            return os.getcwd()
        candidate = parent


_REPO_ROOT = _find_repo_root(_dir)
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

#: section macro modules, in load order
_MODULES = (
    os.path.join(_REPO_ROOT, "docs", "notes", "health", "macros", "health_macros.py"),
    os.path.join(_dir, "film_tv_macros.py"),
)


def _load_from_file(path: str):
    """Load a macro module from a file path (same trick as health_macros).

    Missing files fail here with the path spelled out: the repo root is derived
    from this file's location, so a moved/renamed section module would otherwise
    surface as an opaque ``AttributeError`` on a ``None`` spec.
    """
    if not os.path.isfile(path):
        raise FileNotFoundError(f"section macro module not found: {path}")
    module_name = os.path.splitext(os.path.basename(path))[0]
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_loaded = [_load_from_file(path) for path in _MODULES]


def define_env(env) -> None:
    """Register every section's macros (each module owns its own ``define_env``)."""
    for module in _loaded:
        define_env_fn = getattr(module, "define_env", None)
        if define_env_fn is not None:
            define_env_fn(env)
