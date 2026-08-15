"""Unit tests for scripts/bucket_upload.py — filename sanitization, rename
rule rendering, key resolution, temp dir handling and rclone command
construction.

rclone is mocked (no bucket, no credentials); conversion uses a real tiny
PNG so the WebP target and local copy are produced. End-to-end upload against
a real R2 bucket stays developer-side (see internal/bucket-design.md →
bucket-upload section). The upload path needs a read-write R2 token.
"""

import base64
import sys
from datetime import datetime
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import scripts.bucket_sync as bsync  # noqa: E402
import scripts.bucket_upload as bu  # noqa: E402

# 1x1 red PNG
_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJ"
    "AAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)

CFG = {
    "mappings": [
        {
            "prefix": "assets/bucket/",
            "bucket": "web-assets",
            "remote_prefix": "data/img",
        }
    ],
    "upload": {
        "rule": "img/{Y}/{m}/{d}_{h}{i}{s}_{filename}",
        "fallback_name": "noname",
        "tmp_dir": ".bucket",
        "max_size_mb": 10,
    },
}

NOW = datetime(2026, 8, 16, 10, 11, 12)


class FakeDateTime(datetime):
    @classmethod
    def now(cls, tz=None):
        return NOW


@pytest.fixture()
def run(monkeypatch, tmp_path, clear_bucket_env):
    """Patch rclone, config, repo root and clock; return captured commands."""
    calls: list[list[str]] = []

    def _fake_call(cmd, **kwargs):
        calls.append(cmd)
        return 0

    monkeypatch.setattr(bu.shutil, "which", lambda _: "/usr/bin/rclone")
    monkeypatch.setattr(bu, "_bucket_config", lambda: CFG)
    monkeypatch.setattr(bu, "load_env_files", lambda: None)
    monkeypatch.setattr(bu.subprocess, "call", _fake_call)
    monkeypatch.setattr(bu, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(bu, "datetime", FakeDateTime)
    monkeypatch.setattr(bsync, "available_remotes", lambda: ["r2", "env-remote"])
    return calls


def _main(monkeypatch, argv):
    monkeypatch.setattr(sys, "argv", ["bucket-upload", *argv])
    return bu.main()


def _png(tmp_path, name="photo.png") -> Path:
    src = tmp_path / name
    src.write_bytes(_PNG)
    return src


# --- sanitize_filename ---


class TestSanitize:
    def test_spaces_become_underscores(self):
        assert bu.sanitize_filename("My Photo 2024") == "my_photo_2024"
        assert bu.sanitize_filename("My  Photo") == "my_photo"  # runs collapse

    def test_keep_underscores(self):
        assert bu.sanitize_filename("IMG_2024") == "img_2024"

    def test_mixed_removes_non_ascii(self):
        assert bu.sanitize_filename("照片 photo") == "photo"
        assert bu.sanitize_filename("café") == "caf"  # é cut

    def test_pure_chinese_falls_back(self):
        assert bu.sanitize_filename("我的照片") == "noname"

    def test_no_ascii_alphanumerics_falls_back(self):
        assert bu.sanitize_filename("") == "noname"
        assert bu.sanitize_filename("---") == "noname"

    def test_custom_fallback(self):
        assert bu.sanitize_filename("照片", "no-name") == "no-name"


# --- render_rule ---


class TestRenderRule:
    def test_default_rule(self):
        out = bu.render_rule("img/{Y}/{m}/{d}_{h}{i}{s}_{filename}", NOW, "myphoto")
        assert out == "img/2026/08/16_101112_myphoto"

    def test_custom_rule(self):
        assert bu.render_rule("{Y}/{m}/{filename}", NOW, "myphoto") == "2026/08/myphoto"

    def test_unknown_tokens_kept(self):
        assert bu.render_rule("img/{Y}/{x}", NOW, "myphoto") == "img/2026/{x}"

    def test_zero_padding(self):
        early = datetime(2026, 1, 3, 4, 5, 6)
        assert (
            bu.render_rule("img/{Y}/{m}/{d}_{h}{i}{s}_{filename}", early, "p")
            == "img/2026/01/03_040506_p"
        )


# --- main: end-to-end (rclone mocked) ---


class TestMain:
    def test_upload_flow(self, run, monkeypatch, tmp_path, capsys):
        src = _png(tmp_path)
        assert _main(monkeypatch, ["--confirm", str(src)]) == 0

        # rclone copyto from the temp file to remote:bucket/key
        assert run == [
            [
                "rclone",
                "copyto",
                str(tmp_path / ".bucket/img/2026/08/16_101112_photo.webp"),
                "r2:web-assets/data/img/img/2026/08/16_101112_photo.webp",
                "--s3-no-check-bucket",
                "--progress",
            ]
        ]
        # local preview copy written, temp cleaned up
        local = tmp_path / "docs/assets/bucket/img/2026/08/16_101112_photo.webp"
        assert local.exists()
        assert not (tmp_path / ".bucket").exists()  # temp dir removed with the file

        out = capsys.readouterr().out
        assert "key:   data/img/img/2026/08/16_101112_photo.webp" in out
        assert "link:  assets/bucket/img/2026/08/16_101112_photo.webp" in out

    def test_default_is_dry_run(self, run, monkeypatch, tmp_path, capsys):
        """No --confirm → preview only: no rclone call, nothing written
        (no local copy, no temp dir)."""
        src = _png(tmp_path)
        assert _main(monkeypatch, [str(src)]) == 0
        assert run == []
        assert not (tmp_path / "docs").exists()
        assert not (tmp_path / ".bucket").exists()
        out = capsys.readouterr().out
        assert "[DRY-RUN] rclone copyto" in out
        assert "--confirm" in out  # hints how to actually upload

    def test_size_limit_rejects_oversized(self, run, monkeypatch, tmp_path, capsys):
        src = _png(tmp_path)  # ~70 bytes
        assert _main(monkeypatch, ["--confirm", "--max-size-mb", "0.000001", str(src)]) == 1
        assert run == []  # never reaches rclone
        assert "exceeds" in capsys.readouterr().err

    def test_size_limit_env_override(self, run, monkeypatch, tmp_path):
        monkeypatch.setenv("BUCKET_UPLOAD_MAX_SIZE_MB", "0.000001")
        assert _main(monkeypatch, ["--confirm", str(_png(tmp_path))]) == 1
        assert run == []

    def test_size_limit_default_ok(self, run, monkeypatch, tmp_path):
        # 70-byte png is far below the default 10MB limit
        assert _main(monkeypatch, ["--confirm", str(_png(tmp_path))]) == 0
        assert run[0][0] == "rclone"

    def test_dedupe_same_second(self, run, monkeypatch, tmp_path):
        # a previous upload already produced the local copy → same-second retry
        # gets a -2 suffix
        src = _png(tmp_path)
        existing = tmp_path / "docs/assets/bucket/img/2026/08/16_101112_photo.webp"
        existing.parent.mkdir(parents=True)
        existing.write_bytes(_PNG)

        assert _main(monkeypatch, ["--confirm", str(src)]) == 0
        key = "data/img/img/2026/08/16_101112_photo-2.webp"
        assert key in run[0][3]
        assert (tmp_path / "docs/assets/bucket/img/2026/08/16_101112_photo-2.webp").exists()

    def test_upload_failure_keeps_temp(self, run, monkeypatch, tmp_path):
        src = _png(tmp_path)

        def _fail(cmd, **kwargs):
            return 1

        monkeypatch.setattr(bu.subprocess, "call", _fail)

        assert _main(monkeypatch, ["--confirm", str(src)]) == 1
        temp = tmp_path / ".bucket/img/2026/08/16_101112_photo.webp"
        assert temp.exists()  # kept for retry
        assert not (tmp_path / "docs").exists()

    def test_missing_path_fails(self, run, monkeypatch, tmp_path):
        assert _main(monkeypatch, [str(tmp_path / "nope.png")]) == 1
        assert run == []

    def test_tilde_expansion(self, run, monkeypatch, tmp_path):
        """A leading ~ resolves against $HOME (shell doesn't expand it inside
        double quotes)."""
        _png(tmp_path)  # creates tmp_path/photo.png
        monkeypatch.setenv("HOME", str(tmp_path))
        assert _main(monkeypatch, ["--confirm", "~/photo.png"]) == 0
        assert "r2:web-assets/data/img/img/2026/08/16_101112_photo.webp" in run[0][3]

    def test_unsupported_extension_fails(self, run, monkeypatch, tmp_path):
        webp = tmp_path / "photo.webp"
        webp.write_bytes(_PNG)
        assert _main(monkeypatch, [str(webp)]) == 1
        assert run == []

    def test_no_rclone_raises(self, monkeypatch, tmp_path, clear_bucket_env):
        monkeypatch.setattr(bu.shutil, "which", lambda _: None)
        monkeypatch.setattr(bu, "_bucket_config", lambda: CFG)
        monkeypatch.setattr(bu, "load_env_files", lambda: None)
        monkeypatch.setattr(bu, "REPO_ROOT", tmp_path)
        with pytest.raises(SystemExit):
            _main(monkeypatch, ["--confirm", str(_png(tmp_path))])

    def test_no_mappings_fails(self, run, monkeypatch, tmp_path):
        monkeypatch.setattr(bu, "_bucket_config", lambda: {})
        with pytest.raises(SystemExit):
            _main(monkeypatch, ["--confirm", str(_png(tmp_path))])


# --- resolution order: CLI > env > mkdocs.yml ---


class TestResolutionOrder:
    def test_cli_rule_beats_env(self, run, monkeypatch, tmp_path):
        monkeypatch.setenv("BUCKET_UPLOAD_RULE", "{Y}/{m}/{filename}")
        _main(monkeypatch, ["--confirm", "--rule", "custom/{Y}", str(_png(tmp_path))])
        assert "r2:web-assets/data/img/custom/2026" in run[0][3]

    def test_env_rule_beats_config(self, run, monkeypatch, tmp_path):
        monkeypatch.setenv("BUCKET_UPLOAD_RULE", "{Y}/{m}/{filename}")
        _main(monkeypatch, ["--confirm", str(_png(tmp_path))])
        assert "r2:web-assets/data/img/2026/08/photo.webp" in run[0][3]

    def test_config_default(self, run, monkeypatch, tmp_path):
        _main(monkeypatch, ["--confirm", str(_png(tmp_path))])
        assert "r2:web-assets/data/img/img/2026/08/16_101112_photo.webp" in run[0][3]

    def test_sync_remote_env_shared(self, run, monkeypatch, tmp_path):
        monkeypatch.setenv("BUCKET_SYNC_REMOTE", "env-remote")
        _main(monkeypatch, ["--confirm", str(_png(tmp_path))])
        assert "env-remote:web-assets/data/img/" in run[0][3]

    def test_remote_prefix_env(self, run, monkeypatch, tmp_path):
        monkeypatch.setenv("BUCKET_SYNC_REMOTE_PREFIX", "other/dir")
        _main(monkeypatch, ["--confirm", str(_png(tmp_path))])
        assert "r2:web-assets/other/dir/img/2026/08/16_101112_photo.webp" in run[0][3]

    def test_tmp_dir_env(self, run, monkeypatch, tmp_path):
        monkeypatch.setenv("BUCKET_UPLOAD_TMP_DIR", "staging")
        _main(monkeypatch, ["--confirm", str(_png(tmp_path))])
        assert run[0][2] == str(tmp_path / "staging/img/2026/08/16_101112_photo.webp")

    def test_cli_tmp_dir_beats_env(self, run, monkeypatch, tmp_path):
        monkeypatch.setenv("BUCKET_UPLOAD_TMP_DIR", "staging")
        _main(monkeypatch, ["--confirm", "--tmp-dir", "cli-tmp", str(_png(tmp_path))])
        assert run[0][2] == str(tmp_path / "cli-tmp/img/2026/08/16_101112_photo.webp")


# --- max size limit resolution ---


class TestMaxSize:
    def test_invalid_inputs_fall_back(self, clear_bucket_env):
        assert bu._resolve_max_size_mb("abc", "") == 10
        assert bu._resolve_max_size_mb("inf", "") == 10  # would crash int(float('inf'))
        assert bu._resolve_max_size_mb("nan", "") == 10
        assert bu._resolve_max_size_mb("-5", "") == 10
        assert bu._resolve_max_size_mb("0", "") == 10

    def test_fractional_mb_kept(self, clear_bucket_env):
        # 0.5MB → 512 KiB byte limit (not truncated to 0MB)
        assert bu._resolve_max_size_mb("0.5", "") == 0.5
        assert int(bu._resolve_max_size_mb("0.5", "") * 1024 * 1024) == 512 * 1024

    def test_cli_beats_config(self, clear_bucket_env):
        assert bu._resolve_max_size_mb("20", "10") == 20

    def test_config_and_default(self, clear_bucket_env):
        assert bu._resolve_max_size_mb(None, "5") == 5
        assert bu._resolve_max_size_mb(None, "") == 10
