"""Combined macros module for health tracking.

Loads and combines macros from weight_macros and retire_macros.
"""

import importlib.util
import os

_dir = os.path.dirname(__file__)


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


def define_env(env):
    """Register all health macros from weight and retire modules."""
    _weight_mod.define_env(env)
    _retire_mod.define_env(env)
