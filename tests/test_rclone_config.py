"""Unit tests for scripts/rclone_config.py — non-interactive remote init.

Mocks rclone (no real R2 credentials / network): asserts env validation,
endpoint derivation, create-vs-update choice, and that secrets are never
echoed. Real configuration stays developer-side.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import scripts.rclone_config as rc  # noqa: E402


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv("R2_ACCOUNT_ID", "acct123")
    monkeypatch.setenv("R2_ACCESS_KEY_ID", "ak-secret")
    monkeypatch.setenv("R2_SECRET_ACCESS_KEY", "sk-secret")
    monkeypatch.setattr(rc.shutil, "which", lambda _: "/usr/bin/rclone")
    monkeypatch.setattr(rc, "load_env_files", lambda: None)
    monkeypatch.setattr(rc, "_existing_remotes", lambda: set())


@pytest.fixture()
def run(monkeypatch):
    calls: list[list[str]] = []

    def _fake_call(cmd, **kwargs):
        calls.append(cmd)
        return 0

    monkeypatch.setattr(rc.subprocess, "call", _fake_call)
    return calls


def _main(monkeypatch, argv=None):
    monkeypatch.setattr(sys, "argv", ["rclone-config-init", *(argv or [])])
    return rc.main()


class TestConfigCommand:
    def test_create_default_remote_and_endpoint(self, run, monkeypatch):
        assert _main(monkeypatch) == 0
        cmd = run[0]
        assert cmd[:3] == ["rclone", "config", "create"]
        assert cmd[3] == "r2"
        assert "provider=Cloudflare" in cmd
        assert "endpoint=https://acct123.r2.cloudflarestorage.com" in cmd

    def test_custom_remote_and_endpoint(self, run, monkeypatch):
        _main(monkeypatch, ["--remote", "myr2", "--endpoint", "https://custom.example"])
        cmd = run[0]
        assert cmd[3] == "myr2"
        assert "endpoint=https://custom.example" in cmd

    def test_endpoint_from_env(self, run, monkeypatch):
        monkeypatch.setenv("R2_ENDPOINT", "https://env.example")
        _main(monkeypatch, [])
        assert "endpoint=https://env.example" in run[0]

    def test_remote_name_from_env(self, run, monkeypatch):
        monkeypatch.setenv("BUCKET_SYNC_REMOTE", "envremote")
        _main(monkeypatch, [])
        assert run[0][3] == "envremote"

    def test_remote_name_legacy_alias(self, run, monkeypatch):
        # R2_REMOTE accepted as an alias for backwards compatibility
        monkeypatch.setenv("BUCKET_SYNC_REMOTE", "")
        monkeypatch.setenv("R2_REMOTE", "legacyremote")
        _main(monkeypatch, [])
        assert run[0][3] == "legacyremote"

    def test_update_when_exists(self, run, monkeypatch):
        monkeypatch.setattr(rc, "_existing_remotes", lambda: {"r2"})
        _main(monkeypatch, [])
        assert run[0][:3] == ["rclone", "config", "update"]

    def test_force_recreates(self, run, monkeypatch):
        monkeypatch.setattr(rc, "_existing_remotes", lambda: {"r2"})
        _main(monkeypatch, ["--force"])
        assert run[0][:3] == ["rclone", "config", "create"]

    def test_secrets_never_echoed(self, run, monkeypatch, capsys):
        _main(monkeypatch, [])
        out = capsys.readouterr().out
        assert "ak-secret" not in out
        assert "sk-secret" not in out
        assert "access_key_id=***" in out

    def test_no_network_verify_by_default(self, run, monkeypatch):
        _main(monkeypatch, [])
        assert len(run) == 1  # only config create/update — no lsd/lsf

    def test_verify_bucket_lsf(self, run, monkeypatch):
        _main(monkeypatch, ["--verify-bucket", "mybucket"])
        assert run[-1][:2] == ["rclone", "lsf"]
        assert run[-1][2] == "r2:mybucket/"


class TestValidation:
    def test_missing_account_id(self, monkeypatch):
        monkeypatch.delenv("R2_ACCOUNT_ID")
        with pytest.raises(SystemExit):
            _main(monkeypatch, [])

    def test_missing_access_key(self, monkeypatch):
        monkeypatch.delenv("R2_ACCESS_KEY_ID")
        with pytest.raises(SystemExit):
            _main(monkeypatch, [])

    def test_missing_secret(self, monkeypatch):
        monkeypatch.delenv("R2_SECRET_ACCESS_KEY")
        with pytest.raises(SystemExit):
            _main(monkeypatch, [])

    def test_missing_rclone(self, monkeypatch):
        monkeypatch.setattr(rc.shutil, "which", lambda _: None)
        with pytest.raises(SystemExit):
            _main(monkeypatch, [])

    def test_failure_propagates(self, run, monkeypatch):
        def _fail(cmd, **kwargs):
            run.append(cmd)
            return 1

        monkeypatch.setattr(rc.subprocess, "call", _fail)
        assert _main(monkeypatch, []) == 1
