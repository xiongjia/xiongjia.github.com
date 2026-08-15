"""Unit tests for scripts/bucket_check.py — bucket assets ↔ markdown references.

The script is dry-run by design (nothing deleted/written). These tests build a
tiny fake repo under tmp_path (docs/assets/bucket/ + referencing md files) and
assert the unreferenced / missing classifications, the --only-* filters, JSON
output, draft handling and the --check-remote rclone lsf path (mocked).
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import scripts.bucket_check as bc  # noqa: E402

CFG = {
    "mappings": [{"prefix": "assets/bucket/", "bucket": "web-assets", "remote_prefix": "data/img"}]
}


def _write_bucket(repo: Path, names: list[str]) -> None:
    bucket = repo / "docs" / "assets" / "bucket" / "2026" / "08"
    bucket.mkdir(parents=True, exist_ok=True)
    for name in names:
        (bucket / name).write_bytes(b"x")


@pytest.fixture()
def repo(monkeypatch, tmp_path, clear_bucket_env):
    """Fake repo: used.webp + orphan.webp in the bucket; page.md (3 levels deep,
    like docs/moments/2026-08/) references used.webp and a missing gone.webp."""
    _write_bucket(tmp_path, ["used.webp", "orphan.webp"])
    page_dir = tmp_path / "docs" / "moments" / "2026-08"
    page_dir.mkdir(parents=True)
    (page_dir / "page.md").write_text(
        "![used](../../assets/bucket/2026/08/used.webp)\n"
        "![broken](../../assets/bucket/2026/08/gone.webp)\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(bc, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(bc, "_bucket_config", lambda: CFG)
    monkeypatch.setattr(bc, "load_env_files", lambda: None)
    return tmp_path


def _main(monkeypatch, argv):
    monkeypatch.setattr(sys, "argv", ["bucket-check", *argv])
    return bc.main()


class TestTokens:
    """Raw token extraction + cleaning (md links, frontmatter, html attrs)."""

    PREFIX = "assets/bucket/"

    def test_extract_md_links(self):
        text = "![a](../../assets/bucket/food.webp) and [b](/assets/bucket/x.webp)"
        assert bc.extract_bucket_tokens(text, self.PREFIX) == [
            "../../assets/bucket/food.webp",
            "/assets/bucket/x.webp",
        ]

    def test_extract_frontmatter_and_html(self):
        text = (
            "---\nimage: ../../assets/bucket/fm.webp\n---\n"
            '<img src="../../assets/bucket/html.webp">'
        )
        tokens = bc.extract_bucket_tokens(text, self.PREFIX)
        assert "../../assets/bucket/fm.webp" in tokens
        assert "../../assets/bucket/html.webp" in tokens

    def test_clean_token_strips_query_anchor_and_punct(self):
        assert bc.clean_token("../../assets/bucket/a.webp?w=100#frag") == (
            "../../assets/bucket/a.webp"
        )
        assert bc.clean_token('../../assets/bucket/a.webp")') == "../../assets/bucket/a.webp"

    def test_clean_token_urldecodes(self):
        assert bc.clean_token("../../assets/bucket/my%20photo.webp") == (
            "../../assets/bucket/my photo.webp"
        )


class TestResolve:
    def test_relative_from_nested_page(self, repo):
        src = repo / "docs" / "moments" / "2026-08" / "page.md"
        assert bc.resolve_link(src, "../../assets/bucket/2026/08/used.webp", repo) == (
            repo / "docs" / "assets" / "bucket" / "2026" / "08" / "used.webp"
        )

    def test_site_root_form(self, repo):
        src = repo / "docs" / "moments" / "2026-08" / "page.md"
        assert bc.resolve_link(src, "/assets/bucket/2026/08/used.webp", repo) == (
            repo / "docs" / "assets" / "bucket" / "2026" / "08" / "used.webp"
        )

    def test_empty_token(self, repo):
        assert bc.resolve_link(repo / "docs" / "x.md", "", repo) is None

    def test_nul_byte_token_ignored(self, repo):
        """A malformed token with an embedded NUL byte must not crash the check."""
        src = repo / "docs" / "moments" / "2026-08" / "page.md"
        assert bc.resolve_link(src, "../../assets/bucket/2026/08/\x00used.webp", repo) is None


class TestClassification:
    def test_unreferenced_and_missing(self, repo, monkeypatch, capsys):
        assert _main(monkeypatch, []) == 1
        out = capsys.readouterr().out
        assert "[unreferenced]" in out and "orphan.webp" in out
        assert "[missing]" in out and "gone.webp" in out

    def test_clean_repo_exits_zero(self, repo, monkeypatch):
        (repo / "docs" / "assets" / "bucket" / "2026" / "08" / "orphan.webp").unlink()
        # fix the broken link too
        page = repo / "docs" / "moments" / "2026-08" / "page.md"
        page.write_text("![used](../../assets/bucket/2026/08/used.webp)\n", encoding="utf-8")
        assert _main(monkeypatch, []) == 0

    def test_only_missing_filters_unreferenced(self, repo, monkeypatch, capsys):
        assert _main(monkeypatch, ["--only-missing"]) == 1
        out = capsys.readouterr().out
        assert "[missing]" in out and "gone.webp" in out
        assert "[unreferenced]" not in out

    def test_only_unreferenced_filters_missing(self, repo, monkeypatch, capsys):
        assert _main(monkeypatch, ["--only-unreferenced"]) == 1
        out = capsys.readouterr().out
        assert "[unreferenced]" in out and "orphan.webp" in out
        assert "[missing]" not in out

    def test_json_output(self, repo, monkeypatch, capsys):
        assert _main(monkeypatch, ["--json"]) == 1
        data = json.loads(capsys.readouterr().out)
        assert data["unreferenced"] == [
            {"rel": "2026/08/orphan.webp", "size": "0.0 KiB", "size_bytes": 1}
        ]
        assert data["missing"][0]["rel"] == "2026/08/gone.webp"
        assert data["missing"][0]["sources"] == ["docs/moments/2026-08/page.md"]

    def test_missing_local_dir_warns(self, monkeypatch, tmp_path, capsys):
        """A fresh clone has no docs/assets/bucket/ — warn + hint instead of
        silently reporting every link as missing."""
        page_dir = tmp_path / "docs" / "moments" / "2026-08"
        page_dir.mkdir(parents=True)
        (page_dir / "page.md").write_text(
            "![x](../../assets/bucket/2026/08/used.webp)\n", encoding="utf-8"
        )
        monkeypatch.setattr(bc, "REPO_ROOT", tmp_path)
        monkeypatch.setattr(bc, "_bucket_config", lambda: CFG)
        monkeypatch.setattr(bc, "load_env_files", lambda: None)
        assert _main(monkeypatch, []) == 1
        captured = capsys.readouterr()
        assert "does not exist" in captured.err
        assert "bucket-sync pull" in captured.err
        assert "0 file(s)" in captured.out

    def test_prefix_override_scopes_to_other_dir(self, monkeypatch, tmp_path, capsys):
        """--prefix points the check at a different local dir (overrides the
        first mapping's prefix)."""
        _write_bucket(tmp_path, ["used.webp"])  # default prefix dir
        other = tmp_path / "docs" / "assets" / "other" / "2026" / "08"
        other.mkdir(parents=True)
        (other / "orphan.webp").write_bytes(b"x")
        monkeypatch.setattr(bc, "REPO_ROOT", tmp_path)
        monkeypatch.setattr(bc, "_bucket_config", lambda: CFG)
        monkeypatch.setattr(bc, "load_env_files", lambda: None)
        assert _main(monkeypatch, ["--prefix", "assets/other/"]) == 1
        out = capsys.readouterr().out
        assert "docs/assets/other" in out  # scoped to the overridden dir
        assert "orphan.webp" in out
        assert "bucket/used.webp" not in out  # default-prefix dir not scanned

    def test_link_resolving_outside_bucket_dir_is_ignored(self, monkeypatch, tmp_path, capsys):
        """A link that resolves outside the local dir is neither a reference
        nor a missing link (it never hides orphans, never false-positives)."""
        _write_bucket(tmp_path, ["only.webp"])
        (tmp_path / "docs" / "page.md").write_text(
            "![x](../assets/bucket/2026/08/only.webp)\n", encoding="utf-8"
        )  # docs/../assets → outside docs/
        monkeypatch.setattr(bc, "REPO_ROOT", tmp_path)
        monkeypatch.setattr(bc, "_bucket_config", lambda: CFG)
        monkeypatch.setattr(bc, "load_env_files", lambda: None)
        assert _main(monkeypatch, []) == 1
        out = capsys.readouterr().out
        assert "only.webp" in out  # unreferenced (the invalid link doesn't count)
        assert "[missing]" not in out  # and it is not reported as a broken link


class TestDrafts:
    def test_draft_references_keep_files_by_default(self, monkeypatch, tmp_path):
        _write_bucket(tmp_path, ["only.webp"])
        page_dir = tmp_path / "docs" / "moments" / "2026-08"
        page_dir.mkdir(parents=True)
        (page_dir / "draft.md").write_text(
            "---\ndraft: true\n---\n![x](../../assets/bucket/2026/08/only.webp)\n",
            encoding="utf-8",
        )
        monkeypatch.setattr(bc, "REPO_ROOT", tmp_path)
        monkeypatch.setattr(bc, "_bucket_config", lambda: CFG)
        monkeypatch.setattr(bc, "load_env_files", lambda: None)
        assert _main(monkeypatch, []) == 0  # referenced by the draft → not orphaned

    def test_no_drafts_counts_draft_only_files_unreferenced(self, monkeypatch, tmp_path, capsys):
        _write_bucket(tmp_path, ["only.webp"])
        page_dir = tmp_path / "docs" / "moments" / "2026-08"
        page_dir.mkdir(parents=True)
        (page_dir / "draft.md").write_text(
            "---\ndraft: true\n---\n![x](../../assets/bucket/2026/08/only.webp)\n",
            encoding="utf-8",
        )
        monkeypatch.setattr(bc, "REPO_ROOT", tmp_path)
        monkeypatch.setattr(bc, "_bucket_config", lambda: CFG)
        monkeypatch.setattr(bc, "load_env_files", lambda: None)
        assert _main(monkeypatch, ["--no-drafts"]) == 1
        assert "only.webp" in capsys.readouterr().out


class TestRemote:
    def _mock_rclone(self, monkeypatch, stdout="2026/08/used.webp\n", rc=0, exc=None):
        """Standard --check-remote mocks (rclone present, remote=r2, lsf output);
        returns a dict capturing the rclone invocations (cmd + call count).
        *exc* (e.g. subprocess.TimeoutExpired) makes rclone raise instead of
        returning; *rc* simulates a failing rclone exit."""
        calls = {"cmd": None, "n": 0}
        monkeypatch.setattr(bc.shutil, "which", lambda _: "/usr/bin/rclone")
        monkeypatch.setattr(bc, "resolve_remote", lambda *a, **k: "r2")

        def _fake_run(cmd, **kwargs):
            assert cmd[:4] == ["rclone", "lsf", "-R", "--files-only"]
            calls["cmd"] = cmd
            calls["n"] += 1
            if exc is not None:
                raise exc(cmd, timeout=kwargs.get("timeout", 0))
            ns = {"returncode": rc, "stdout": stdout, "stderr": "boom" if rc else ""}
            return type("R", (), ns)()

        monkeypatch.setattr(bc.subprocess, "run", _fake_run)
        return calls

    def test_remote_missing_and_not_uploaded(self, repo, monkeypatch, capsys):
        self._mock_rclone(monkeypatch)
        assert _main(monkeypatch, ["--check-remote"]) == 1
        out = capsys.readouterr().out
        assert "[missing-remote]" in out and "gone.webp" in out
        assert "[not-uploaded]" in out and "orphan.webp" in out
        assert "used.webp" not in out.split("[not-uploaded]")[1]

    def test_remote_json(self, repo, monkeypatch, capsys):
        self._mock_rclone(monkeypatch)
        assert _main(monkeypatch, ["--check-remote", "--json"]) == 1
        data = json.loads(capsys.readouterr().out)
        assert data["remote"]["rpath"] == "r2:web-assets/data/img/"
        assert data["remote"]["missing_remote"] == ["2026/08/gone.webp"]
        assert data["remote"]["not_uploaded"] == ["2026/08/orphan.webp"]

    def test_only_missing_with_remote_drops_not_uploaded(self, repo, monkeypatch, capsys):
        self._mock_rclone(monkeypatch)
        assert _main(monkeypatch, ["--check-remote", "--only-missing"]) == 1
        out = capsys.readouterr().out
        assert "[missing]" in out and "gone.webp" in out  # local broken links kept
        assert "[missing-remote]" in out  # remote broken links kept
        assert "[not-uploaded]" not in out  # orphan direction filtered out
        assert "[unreferenced]" not in out

    def test_only_missing_with_remote_json_drops_sections(self, repo, monkeypatch, capsys):
        """JSON mode applies the same --only-* filtering as text mode."""
        self._mock_rclone(monkeypatch)
        assert _main(monkeypatch, ["--check-remote", "--only-missing", "--json"]) == 1
        data = json.loads(capsys.readouterr().out)
        assert data["missing"][0]["rel"] == "2026/08/gone.webp"
        assert data["remote"]["missing_remote"] == ["2026/08/gone.webp"]
        assert "unreferenced" not in data
        assert "not_uploaded" not in data["remote"]

    def test_only_unreferenced_with_remote_drops_missing_remote(self, repo, monkeypatch, capsys):
        self._mock_rclone(monkeypatch)
        assert _main(monkeypatch, ["--check-remote", "--only-unreferenced"]) == 1
        out = capsys.readouterr().out
        assert "[unreferenced]" in out and "orphan.webp" in out
        assert "[not-uploaded]" in out
        assert "[missing-remote]" not in out
        assert "[missing]" not in out

    def test_not_uploaded_summary_hint(self, repo, monkeypatch, capsys):
        self._mock_rclone(monkeypatch)
        assert _main(monkeypatch, ["--check-remote"]) == 1
        out = capsys.readouterr().out
        assert "hint: not-uploaded files are absent from the bucket" in out

    def test_remote_bucket_and_prefix_overrides(self, repo, monkeypatch, capsys):
        calls = self._mock_rclone(monkeypatch)
        _main(
            monkeypatch,
            ["--check-remote", "--bucket", "bucket1", "--remote-prefix", "abc/123"],
        )
        assert calls["cmd"][-1] == "r2:bucket1/abc/123/"

    def test_remote_flags_imply_check_remote(self, repo, monkeypatch, capsys):
        """--remote/--bucket/--remote-prefix without --check-remote must run the
        bucket check — never silently degrade to a local-only check."""
        calls = self._mock_rclone(monkeypatch)
        assert _main(monkeypatch, ["--remote", "r2", "--json"]) == 1
        data = json.loads(capsys.readouterr().out)
        assert "remote" in data
        assert data["remote"]["rpath"] == "r2:web-assets/data/img/"
        assert calls["n"] == 1  # rclone lsf really ran

    def test_bucket_flag_implies_check_remote(self, repo, monkeypatch, capsys):
        self._mock_rclone(monkeypatch, stdout="")
        assert _main(monkeypatch, ["--bucket", "bucket1", "--json"]) == 1
        data = json.loads(capsys.readouterr().out)
        assert data["remote"]["rpath"] == "r2:bucket1/data/img/"

    def test_prefix_alone_stays_local(self, repo, monkeypatch, capsys):
        """--prefix scopes the LOCAL dir only — it must not trigger a remote check."""
        assert _main(monkeypatch, ["--prefix", "assets/bucket/", "--json"]) == 1
        data = json.loads(capsys.readouterr().out)
        assert "remote" not in data

    def test_no_drafts_with_remote(self, monkeypatch, tmp_path, capsys):
        """--no-drafts + --check-remote: draft-referenced files become both
        unreferenced and not-uploaded (empty remote in this fixture)."""
        _write_bucket(tmp_path, ["only.webp"])
        page_dir = tmp_path / "docs" / "moments" / "2026-08"
        page_dir.mkdir(parents=True)
        (page_dir / "draft.md").write_text(
            "---\ndraft: true\n---\n![x](../../assets/bucket/2026/08/only.webp)\n",
            encoding="utf-8",
        )
        monkeypatch.setattr(bc, "REPO_ROOT", tmp_path)
        monkeypatch.setattr(bc, "_bucket_config", lambda: CFG)
        monkeypatch.setattr(bc, "load_env_files", lambda: None)
        self._mock_rclone(monkeypatch, stdout="")
        assert _main(monkeypatch, ["--check-remote", "--no-drafts"]) == 1
        out = capsys.readouterr().out
        assert "[unreferenced]" in out and "only.webp" in out
        assert "[not-uploaded]" in out and "only.webp" in out

    def test_lsf_timeout_raises(self, repo, monkeypatch):
        self._mock_rclone(monkeypatch, exc=subprocess.TimeoutExpired)
        with pytest.raises(SystemExit, match="timed out"):
            _main(monkeypatch, ["--check-remote"])

    def test_remote_clean_exits_zero(self, repo, monkeypatch, capsys):
        (repo / "docs" / "assets" / "bucket" / "2026" / "08" / "orphan.webp").unlink()
        page = repo / "docs" / "moments" / "2026-08" / "page.md"
        page.write_text("![used](../../assets/bucket/2026/08/used.webp)\n", encoding="utf-8")
        self._mock_rclone(monkeypatch)
        assert _main(monkeypatch, ["--check-remote"]) == 0

    def test_rclone_missing_fails(self, repo, monkeypatch):
        monkeypatch.setattr(bc.shutil, "which", lambda _: None)
        with pytest.raises(SystemExit):
            _main(monkeypatch, ["--check-remote"])

    def test_lsf_failure_raises(self, repo, monkeypatch):
        self._mock_rclone(monkeypatch, rc=1)
        with pytest.raises(SystemExit, match="rclone lsf failed"):
            _main(monkeypatch, ["--check-remote"])


class TestConfig:
    def test_no_mappings_fails(self, repo, monkeypatch):
        monkeypatch.setattr(bc, "_bucket_config", lambda: {})
        with pytest.raises(SystemExit):
            _main(monkeypatch, [])
