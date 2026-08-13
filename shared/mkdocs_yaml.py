"""Shared mkdocs.yml parsing for CLI scripts (tolerates ``!ENV`` tags).

mkdocs.yml uses Material's ``!ENV [NAME, default]`` and
``!!python/name:...`` tags (emoji indices), so a plain ``yaml.safe_load``
would fail. This module parses the file with custom constructors and exposes
``extra.<key>`` blocks to CLI scripts (bucket_sync, git_bot,
optimize_images), replacing per-script copies of the same loader.

Consumers must bootstrap the repo root onto ``sys.path`` before importing
(see shared/__init__.py).
"""

import sys
from pathlib import Path

import yaml

MKDOCS_YML = Path(__file__).resolve().parent.parent / "mkdocs.yml"


class _EnvLoader(yaml.SafeLoader):
    """SafeLoader that tolerates mkdocs' ``!ENV [name, default]`` tags."""


def _env_constructor(loader: yaml.SafeLoader, node: yaml.Node) -> str:
    """Resolve mkdocs' ``!ENV`` tag: scalar form or ``!ENV [name, default]``.

    The sequence form resolves to the default value — env overrides are
    applied by the mkdocs plugins, CLI scripts read the committed fallback.
    """
    if isinstance(node, yaml.SequenceNode):
        values = loader.construct_sequence(node, deep=True)
        return str(values[1]) if len(values) > 1 else (str(values[0]) if values else "")
    return loader.construct_scalar(node) or ""


_EnvLoader.add_constructor("!ENV", _env_constructor)


def _python_name(loader: yaml.SafeLoader, suffix: str, node: yaml.Node) -> str:
    """Tolerate Material's ``!!python/name:...`` tags (emoji indices)."""
    return ""


_EnvLoader.add_multi_constructor("tag:yaml.org,2002:python/name:", _python_name)


class MkdocsYamlError(RuntimeError):
    """mkdocs.yml could not be parsed/read (raised in ``strict`` mode only)."""


def load_extra(key: str, label: str = "mkdocs_yaml", *, strict: bool = False) -> dict:
    """Read ``extra.<key>`` from mkdocs.yml (empty dict when absent/unreadable).

    *label* prefixes the stderr warning on problems, so callers keep a
    recognizable message (e.g. ``bucket-sync``). By default problems degrade
    to an empty dict with a warning; with *strict* they raise
    :class:`MkdocsYamlError` instead (callers that must fail fast, e.g.
    git_bot's task registry).
    """
    if not MKDOCS_YML.is_file():
        return {}
    try:
        data = yaml.load(MKDOCS_YML.read_text(encoding="utf-8"), Loader=_EnvLoader)
    except yaml.YAMLError as exc:
        return _degrade_or_raise(f"{label}: cannot parse {MKDOCS_YML}: {exc}", strict, cause=exc)
    if data is None:
        return {}  # empty file — treat as absent, no warning
    if not isinstance(data, dict):
        return _degrade_or_raise(f"{label}: {MKDOCS_YML} is not a mapping", strict)
    extra = data.get("extra", {})
    if not isinstance(extra, dict):
        return _degrade_or_raise(f"{label}: 'extra' in {MKDOCS_YML} is not a mapping", strict)
    block = extra.get(key, {})
    if not isinstance(block, dict):
        return _degrade_or_raise(f"{label}: 'extra.{key}' in {MKDOCS_YML} is not a mapping", strict)
    return block


def _degrade_or_raise(message: str, strict: bool, cause: BaseException | None = None) -> dict:
    """Warn on stderr and degrade to {} — or raise MkdocsYamlError when strict."""
    if strict:
        raise MkdocsYamlError(message) from cause
    print(message, file=sys.stderr)
    return {}
