"""Unit tests for scripts/bucket_sync.py — rclone command construction.

These tests mock rclone (no bucket, no credentials): they assert the exact
rclone commands the script builds, including subdirectory scoping
(remote_prefix) and the CLI > env > mkdocs.yml resolution order. The script
is read-only (pull only — uploads happen in PicList). End-to-end sync
against a real R2 bucket stays developer-side (see
internal/bucket-design.md → Developer Verification Steps).
"""

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import scripts.bucket_sync as bs  # noqa: E402

CFG = {
    "mappings": [
        {
            "prefix": "assets/bucket/",
            "remote_prefix": "web-assets/img",
        }
    ],
}


@pytest.fixture()
def run(monkeypatch, clear_bucket_env):
    """Patch rclone & config access; return the captured command list."""
    calls: list[list[str]] = []

    def _fake_call(cmd, **kwargs):
        calls.append(cmd)
        return 0

    monkeypatch.setattr(bs.shutil, "which", lambda _: "/usr/bin/rclone")
    monkeypatch.setattr(bs, "_bucket_config", lambda: CFG)
    monkeypatch.setattr(bs, "load_env_files", lambda: None)
    monkeypatch.setattr(bs.subprocess, "call", _fake_call)
    monkeypatch.setattr(bs, "available_remotes", lambda: ["r2", "env-remote", "cli-remote"])
    return calls


def _main(monkeypatch, argv):
    monkeypatch.setattr(sys, "argv", ["bucket-sync", *argv])
    return bs.main()


class TestPull:
    def test_dry_run_by_default(self, run, monkeypatch):
        assert _main(monkeypatch, ["pull"]) == 0
        cmd = run[0]
        assert cmd[:2] == ["rclone", "sync"]
        assert "--dry-run" in cmd
        # bucket falls back to remote name when mapping has none
        assert "r2:r2/web-assets/img/" in cmd

    def test_confirm_applies(self, run, monkeypatch):
        assert _main(monkeypatch, ["pull", "--confirm"]) == 0
        assert "--dry-run" not in run[0]

    def test_subdirectory_scope(self, run, monkeypatch):
        _main(monkeypatch, ["pull", "--remote-prefix", "abc/123"])
        assert "r2:r2/abc/123/" in run[0]

    def test_explicit_bucket(self, run, monkeypatch):
        _main(monkeypatch, ["pull", "--bucket", "bucket1", "--remote-prefix", "abc/123"])
        assert "r2:bucket1/abc/123/" in run[0]


class TestNoPush:
    def test_push_rejected(self, monkeypatch):
        monkeypatch.setenv("BUCKET_SYNC_REMOTE", "x")
        with pytest.raises(SystemExit):
            _main(monkeypatch, ["push"])


class TestResolutionOrder:
    def test_cli_beats_env_and_config(self, run, monkeypatch):
        monkeypatch.setenv("BUCKET_SYNC_REMOTE", "env-remote")
        _main(monkeypatch, ["pull", "--remote", "cli-remote"])
        assert "cli-remote:cli-remote/web-assets/img/" in run[0]

    def test_env_beats_config(self, run, monkeypatch):
        monkeypatch.setenv("BUCKET_SYNC_REMOTE", "env-remote")
        monkeypatch.setenv("BUCKET_SYNC_REMOTE_PREFIX", "env-dir")
        _main(monkeypatch, ["pull"])
        assert "env-remote:env-remote/env-dir/" in run[0]

    def test_config_default(self, run, monkeypatch, capsys):
        monkeypatch.delenv("BUCKET_SYNC_REMOTE", raising=False)
        _main(monkeypatch, ["pull"])
        # remote falls back to the hardcoded default r2 (remote name is
        # local-only — .env / default, never mkdocs.yml)
        assert "r2:r2/web-assets/img/" in run[0]
        # and a warning explains the bucket fallback (silent fallbacks caused
        # confusing 403s against R2)
        assert "WARNING bucket name fell back" in capsys.readouterr().err

    def test_no_mappings_fails(self, run, monkeypatch):
        monkeypatch.setattr(bs, "_bucket_config", lambda: {})
        monkeypatch.delenv("BUCKET_SYNC_REMOTE", raising=False)
        with pytest.raises(SystemExit):
            _main(monkeypatch, ["pull"])


class TestRemoteResolution:
    """Remote auto-detection from rclone listremotes."""

    def test_auto_detect_single_remote(self, run, monkeypatch):
        monkeypatch.setattr(bs, "available_remotes", lambda: ["web-assets-rw"])
        assert _main(monkeypatch, ["pull"]) == 0
        assert "web-assets-rw:web-assets-rw/web-assets/img/" in run[0]

    def test_auto_detect_prefers_r2(self, run, monkeypatch):
        monkeypatch.setattr(bs, "available_remotes", lambda: ["a", "r2", "b"])
        assert _main(monkeypatch, ["pull"]) == 0
        assert "r2:r2/web-assets/img/" in run[0]

    def test_stale_env_remote_warns_and_falls_back(self, run, monkeypatch, capsys):
        monkeypatch.setattr(bs, "available_remotes", lambda: ["web-assets-rw"])
        monkeypatch.setenv("BUCKET_SYNC_REMOTE", "web-assets-readonly")
        assert _main(monkeypatch, ["pull"]) == 0
        assert "web-assets-rw:web-assets-rw/web-assets/img/" in run[0]
        assert "not configured" in capsys.readouterr().err

    def test_cli_remote_beats_auto_detect(self, run, monkeypatch):
        monkeypatch.setattr(bs, "available_remotes", lambda: ["web-assets-rw"])
        assert _main(monkeypatch, ["pull", "--remote", "web-assets-rw"]) == 0
        assert "web-assets-rw:web-assets-rw/web-assets/img/" in run[0]

    def test_multi_remote_warns_when_unpinned(self, run, monkeypatch, capsys):
        """Several remotes and no explicit choice → pick the first, warn loudly
        (uploads must not silently go to the wrong account)."""
        monkeypatch.setattr(bs, "available_remotes", lambda: ["prod-bucket", "test-bucket"])
        assert _main(monkeypatch, ["pull"]) == 0
        assert "prod-bucket:prod-bucket/web-assets/img/" in run[0]
        err = capsys.readouterr().err
        assert "multiple rclone remotes" in err
        assert "prod-bucket" in err

    def test_multi_remote_no_warning_when_pinned(self, run, monkeypatch, capsys):
        monkeypatch.setattr(bs, "available_remotes", lambda: ["prod-bucket", "test-bucket"])
        _main(monkeypatch, ["pull", "--remote", "test-bucket"])
        assert "multiple rclone remotes" not in capsys.readouterr().err
        assert "test-bucket:test-bucket/web-assets/img/" in run[0]


class TestNoRclone:
    def test_errors_when_rclone_missing(self, run, monkeypatch):
        monkeypatch.setattr(bs.shutil, "which", lambda _: None)
        with pytest.raises(SystemExit):
            _main(monkeypatch, ["pull"])


class TestEnvLoading:
    """Real load_env_files precedence: shell > .env.local > .env."""

    @pytest.fixture()
    def envdir(self, tmp_path):
        (tmp_path / ".env").write_text(
            "SHARED=from-env\nONLY_ENV=env-value\nFROM_SHELL=should-not-win\n",
            encoding="utf-8",
        )
        (tmp_path / ".env.local").write_text(
            "SHARED=from-local\nONLY_LOCAL=local-value\n", encoding="utf-8"
        )
        return tmp_path

    def test_local_overrides_env(self, envdir, monkeypatch):
        monkeypatch.delenv("SHARED", raising=False)
        monkeypatch.delenv("ONLY_ENV", raising=False)
        monkeypatch.delenv("ONLY_LOCAL", raising=False)
        bs.load_env_files(envdir)
        assert os.environ.get("SHARED") == "from-local"  # .env.local wins over .env
        assert os.environ.get("ONLY_ENV") == "env-value"
        assert os.environ.get("ONLY_LOCAL") == "local-value"

    def test_shell_env_never_overridden(self, envdir, monkeypatch):
        monkeypatch.setenv("FROM_SHELL", "shell-wins")
        bs.load_env_files(envdir)
        assert os.environ.get("FROM_SHELL") == "shell-wins"
