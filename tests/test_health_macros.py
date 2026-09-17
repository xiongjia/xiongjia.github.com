"""Unit tests for the health macros aggregator (health_macros.py).

Only the repo-root bootstrap is covered here: it is what makes the sibling
macro modules able to import the root-level `shared/` package when the macros
plugin loads them by path (the aggregation itself is covered by the
per-module tests).
"""

import os
import subprocess
import sys
import textwrap
from pathlib import Path

import health_macros

REPO_ROOT = Path(__file__).resolve().parent.parent
MACROS_DIR = REPO_ROOT / "docs" / "notes" / "health" / "macros"

# Reproduces the macros plugin's loading shape in a clean interpreter: the
# repo root is NOT importable, only the macros dir is (as the plugin's
# path-based exec behaves), and the sibling modules must still import `shared/`.
_BOOTSTRAP_PROBE = textwrap.dedent(
    """
    import importlib.util
    import os
    import sys

    repo = os.path.realpath(sys.argv[1])
    macros_dir = sys.argv[2]
    sys.path[:] = [p for p in sys.path if p and os.path.realpath(p) != repo]

    try:
        import shared  # noqa: F401
    except ModuleNotFoundError:
        pass
    else:
        raise SystemExit("precondition failed: shared was importable before the bootstrap")

    spec = importlib.util.spec_from_file_location(
        "health_macros", os.path.join(macros_dir, "health_macros.py")
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    import shared  # noqa: F401  must succeed after the bootstrap

    assert module._REPO_ROOT in sys.path, "repo root missing from sys.path"
    assert os.path.isdir(os.path.join(module._REPO_ROOT, "shared"))
    print("ok")
    """
)


def _mkdocs_yml(directory: Path) -> None:
    (directory / "mkdocs.yml").write_text("site_name: x\n", encoding="utf-8")


def test_find_repo_root_walks_up_to_mkdocs_yml(tmp_path):
    _mkdocs_yml(tmp_path)
    nested = tmp_path / "docs" / "notes" / "health" / "macros"
    nested.mkdir(parents=True)
    assert health_macros._find_repo_root(str(nested)) == str(tmp_path)


def test_find_repo_root_uses_start_dir_when_it_holds_mkdocs_yml(tmp_path):
    _mkdocs_yml(tmp_path)
    assert health_macros._find_repo_root(str(tmp_path)) == str(tmp_path)


def test_find_repo_root_falls_back_to_cwd(tmp_path, monkeypatch):
    # rename the sentinel so no ancestor can match either — the real name can
    # exist above tmp_path (e.g. TMPDIR inside a checkout), which is what would
    # make this test non-hermetic
    monkeypatch.setattr(health_macros, "_MKDOCS_YML", "no-such-sentinel.yml")
    monkeypatch.chdir(tmp_path)
    assert health_macros._find_repo_root(str(tmp_path)) == os.getcwd()


def test_bootstrap_makes_shared_importable_when_loaded_by_path():
    result = subprocess.run(
        [sys.executable, "-c", _BOOTSTRAP_PROBE, str(REPO_ROOT), str(MACROS_DIR)],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "ok"
