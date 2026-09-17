"""Combined macros module for health tracking.

Loads and combines macros from weight, retire, and running modules.
"""

import importlib.util
import os
import sys

_dir = os.path.dirname(os.path.abspath(__file__))
_MKDOCS_YML = "mkdocs.yml"


def _find_repo_root(start: str) -> str:
    """Walk up from *start* until a directory holding mkdocs.yml is found.

    Avoids a hardcoded ``parents[N]``: that silently points at the wrong
    directory if the macros move, and the failure then surfaces much later as a
    confusing ModuleNotFoundError from an unrelated module.
    """
    candidate = start
    while True:
        if os.path.isfile(os.path.join(candidate, _MKDOCS_YML)):
            return candidate
        parent = os.path.dirname(candidate)
        if parent == candidate:
            return os.getcwd()
        candidate = parent


# the macros plugin loads this file by path (no package), so make the repo root
# importable before exec'ing the sibling modules — they import the root-level
# `shared/` package (see shared/__init__.py)
_REPO_ROOT = _find_repo_root(_dir)
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)


def _load_from_file(filename):
    """Load a Python module from a file path (same directory)."""
    path = os.path.join(_dir, filename)
    module_name = filename.replace(".py", "")
    spec = importlib.util.spec_from_file_location(module_name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_weight_mod = _load_from_file("weight_macros.py")
_retire_mod = _load_from_file("retire_macros.py")
_running_mod = _load_from_file("running_macros.py")


def define_env(env):
    """Register all health macros from weight, retire, and running modules."""
    _weight_mod.define_env(env)
    _retire_mod.define_env(env)
    _running_mod.define_env(env)
