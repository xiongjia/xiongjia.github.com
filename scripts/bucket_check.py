"""Cross-check bucket assets against markdown references (local + optional remote).

Bucket-managed assets live under ``docs/assets/bucket/`` (git-ignored local
mirror of the R2/S3 bucket; see internal/bucket-design.md). md files reference
them with local relative links (``../../assets/bucket/food.webp``). This
script cross-checks both directions — a local dev aid for cleanup and
broken-link detection:

- **unreferenced** — local bucket files no md/html references (cleanup
  candidates: safe to delete once verified they are not pending uploads).
- **missing** — md/html links whose bucket file is absent locally (broken
  link: the pull hasn't run, the file was never uploaded, or the link is a
  typo).

With ``--check-remote`` (needs the configured rclone remote) the missing check
runs against the actual bucket objects instead of the local mirror:

- **missing-remote** — md links whose key is absent from the bucket.
- **not-uploaded** — local bucket files absent from the bucket (pending
  upload; ``bucket-sync pull --confirm`` would delete them).

Reference scope: every ``*.md`` under ``docs/`` (drafts included by default —
a file referenced only by a draft is still referenced) plus ``*.html`` under
``docs/`` and ``overrides/``. Links are found by scanning for tokens that
contain the bucket prefix (md link targets, frontmatter image fields, inline
HTML attributes), resolved relative to the referencing file — site-root forms
(``/assets/bucket/…``) resolve against ``docs/``. Tokens that resolve outside
the bucket local dir are ignored (not counted as references, not reported).

Exit code: 0 when no issues; 1 when unreferenced files or missing links were
found (local or remote), or local files are absent from the remote. Dry-run
by design — nothing is deleted or written.

Usage:
    uv run poe bucket-check                  # local mirror check
    uv run poe bucket-check --only-missing   # just broken links
    uv run poe bucket-check --check-remote   # check against the bucket
    uv run poe bucket-check --json           # machine-readable output
    uv run poe bucket-check --no-drafts      # ignore draft pages
"""

from __future__ import annotations

import argparse
import functools
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from urllib.parse import unquote

# bootstrap repo root so `shared/` is importable regardless of how this runs
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.bucket_sync import _first_mapping, _pick, _rclone_path, resolve_remote
from shared.env import load_env_files
from shared.frontmatter import has_draft_flag
from shared.mkdocs_yaml import load_extra

REPO_ROOT = Path(__file__).resolve().parent.parent

DEFAULT_PREFIX = "assets/bucket/"

# token = a contiguous run of non-whitespace/non-quote/non-bracket chars that
# contains the bucket prefix; matches md links, frontmatter image fields and
# inline HTML attributes alike
_TOKEN_RE_TMPL = r"[^\s\"'<>()\[\]]*{prefix}[^\s\"'<>()\[\]]*"

# characters stripped from a token tail (link punctuation, closing brackets)
_TRAILING = ")]}>.,;'\""


def _bucket_config() -> dict:
    """Read ``extra.bucket`` from mkdocs.yml (empty dict when absent)."""
    return load_extra("bucket", label="bucket-check")


@functools.lru_cache(maxsize=16)
def _prefix_pattern(prefix: str) -> re.Pattern:
    """Compiled token regex for a bucket prefix (cached — compiled once per prefix
    instead of once per scanned source file)."""
    return re.compile(_TOKEN_RE_TMPL.format(prefix=re.escape(prefix)))


def extract_bucket_tokens(text: str, prefix: str) -> list[str]:
    """All text tokens containing the bucket *prefix* (as written in the file)."""
    return _prefix_pattern(prefix).findall(text)


def clean_token(token: str) -> str:
    """Normalize a raw link token: strip query/anchor and trailing punctuation,
    then URL-decode. Returns '' for tokens that end up empty."""
    for sep in ("?", "#"):
        if sep in token:
            token = token.split(sep, 1)[0]
    token = token.rstrip(_TRAILING).strip()
    return unquote(token) if token else ""


def resolve_link(src: Path, token: str, root: Path) -> Path | None:
    """Resolve a (cleaned) link token against its source file → absolute path.

    Site-root forms (``/assets/bucket/…``) resolve against ``root/docs/``;
    everything else is relative to the source file's directory. Returns None
    for empty tokens. No symlink resolution; the file may not exist.
    """
    token = clean_token(token)
    if not token or "\x00" in token:
        return None
    if token.startswith("/"):
        base = Path(os.path.normpath(str(root / "docs")))
        return Path(os.path.normpath(str(base / token.lstrip("/"))))
    return Path(os.path.normpath(str(src.parent / token)))


def _rel_to_dir(path: Path, dir_: Path) -> str | None:
    """Posix relative path of *path* under *dir_*; None when outside or == dir_."""
    try:
        rel = path.relative_to(dir_)
    except ValueError:
        return None
    if not rel.parts:
        return None
    return rel.as_posix()


def iter_source_files(root: Path):
    """Every ``*.md`` under docs/ and every ``*.html`` under docs/ + overrides/."""
    for base in (root / "docs", root / "overrides"):
        if not base.is_dir():
            continue
        yield from base.rglob("*.md")
        yield from base.rglob("*.html")


def collect_local_files(local_dir: Path) -> dict[str, Path]:
    """All files under the bucket local dir: rel posix path -> absolute path."""
    local: dict[str, Path] = {}
    if not local_dir.is_dir():
        return local
    for f in local_dir.rglob("*"):
        if f.is_file():
            local[_rel_to_dir(f, local_dir)] = f
    return local


def collect_references(root: Path, local_dir: Path, prefix: str, *, include_drafts: bool):
    """Scan md/html sources → {rel: {source files}} for links under *local_dir*.

    rel is the path of the referenced file relative to the bucket local dir
    (``2026/08/food.webp``); sources are the referencing file paths. Links
    that resolve outside the local dir are ignored.
    """
    refs: dict[str, set[Path]] = {}
    for src in iter_source_files(root):
        text = src.read_text(encoding="utf-8", errors="replace")
        if not include_drafts and has_draft_flag(text):
            continue
        for raw in extract_bucket_tokens(text, prefix):
            path = resolve_link(src, raw, root)
            if path is None:
                continue
            rel = _rel_to_dir(path, local_dir)
            if rel is not None:
                refs.setdefault(rel, set()).add(src)
    return refs


def remote_keys(rpath: str) -> set[str]:
    """Object keys under the remote path via ``rclone lsf`` (rel to *rpath*).

    Bounded by a 300s timeout so a hung rclone/proxy fails fast instead of
    blocking the check indefinitely.
    """
    cmd = ["rclone", "lsf", "-R", "--files-only", "--fast-list", rpath]
    print("+ " + " ".join(cmd), file=sys.stderr)
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, check=False, timeout=300)
    except subprocess.TimeoutExpired:
        raise SystemExit(
            "bucket-check: rclone lsf timed out after 300s — check the network/proxy "
            "(RCLONE_HTTP_PROXY) or narrow --remote-prefix"
        )
    if out.returncode != 0:
        raise SystemExit(f"bucket-check: rclone lsf failed: {out.stderr.strip()}")
    return {line.strip() for line in out.stdout.splitlines() if line.strip()}


def _size_bytes(path: Path) -> int | None:
    """File size in bytes; None when stat fails (e.g. race with a deletion)."""
    try:
        return path.stat().st_size
    except OSError:
        return None


def _fmt_size(path: Path) -> str:
    size = _size_bytes(path)
    return "?" if size is None else f"{size / 1024:.1f} KiB"


def _repo_rel(path: Path) -> str:
    try:
        return path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return str(path)


def main() -> int:
    # load git-ignored .env files (precedence: shell > .env.local > .env) so
    # R2 overrides / proxy work from .env
    load_env_files()

    parser = argparse.ArgumentParser(
        prog="bucket-check",
        description="Cross-check bucket assets vs markdown references: unreferenced "
        "local files (cleanup candidates) and md links missing from the bucket. "
        "Dry-run by design.",
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--only-unreferenced",
        action="store_true",
        help="report only unreferenced local bucket files (and, with --check-remote, "
        "files absent from the bucket)",
    )
    group.add_argument(
        "--only-missing",
        action="store_true",
        help="report only md links whose bucket file is missing (local or remote)",
    )
    parser.add_argument(
        "--check-remote",
        dest="check_remote",
        action="store_true",
        help="also check md links against the actual bucket (rclone lsf; needs the "
        "configured remote) and list local files absent from the bucket",
    )
    parser.add_argument(
        "--no-drafts",
        action="store_true",
        help="exclude draft md files (draft: true frontmatter) from the reference "
        "scan — files referenced only by drafts then count as unreferenced",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="print machine-readable JSON to stdout (diagnostics/warnings go to stderr)",
    )
    parser.add_argument(
        "--prefix",
        help=f"local prefix under docs/ (default: first mapping's 'prefix', e.g. {DEFAULT_PREFIX})",
    )
    parser.add_argument(
        "--bucket",
        help="bucket name for --check-remote (default: first mapping's 'bucket'; "
        "implies --check-remote)",
    )
    parser.add_argument(
        "--remote-prefix",
        help="object prefix inside the bucket for --check-remote (default: first mapping's "
        "'remote_prefix'; implies --check-remote)",
    )
    parser.add_argument(
        "--remote",
        help="rclone remote name for --check-remote (default: auto-detected from "
        "`rclone listremotes`; BUCKET_SYNC_REMOTE env overrides; implies --check-remote)",
    )
    args = parser.parse_args()

    # --remote / --bucket / --remote-prefix only make sense with a bucket check;
    # accept them as an implicit --check-remote so a bucket-sync-style `--remote r2`
    # never silently degrades to a local-only check
    if args.remote or args.bucket or args.remote_prefix:
        args.check_remote = True

    cfg = _bucket_config()
    mapping = _first_mapping(cfg)  # raises SystemExit when no mappings
    prefix = _pick(args.prefix, "BUCKET_SYNC_PREFIX", str(mapping.get("prefix") or DEFAULT_PREFIX))
    local_dir = REPO_ROOT / "docs" / prefix.strip("/")
    if not local_dir.is_dir():
        print(
            f"bucket-check: WARNING local bucket dir {_repo_rel(local_dir)} does not exist — "
            "referenced files will all report [missing]; run 'poe bucket-sync pull' to mirror "
            "the bucket first.",
            file=sys.stderr,
        )

    include_drafts = not args.no_drafts
    local = collect_local_files(local_dir)
    refs = collect_references(
        REPO_ROOT, local_dir, prefix.strip("/") + "/", include_drafts=include_drafts
    )

    rel_missing = sorted(rel for rel in refs if rel not in local)
    rel_unreferenced = sorted(rel for rel in local if rel not in refs)

    result = {
        "prefix": prefix,
        "local_dir": _repo_rel(local_dir),
        "local_files": len(local),
        "references": sum(len(v) for v in refs.values()),
        "unreferenced": [
            {
                "rel": rel,
                "size": _fmt_size(local[rel]),
                "size_bytes": _size_bytes(local[rel]),
            }
            for rel in rel_unreferenced
        ],
        "missing": [
            {
                "rel": rel,
                "sources": sorted(_repo_rel(s) for s in refs[rel]),
            }
            for rel in rel_missing
        ],
    }

    checked_remote = args.check_remote
    remote_name = None
    if checked_remote:
        if shutil.which("rclone") is None:
            raise SystemExit(
                "bucket-check: rclone not found — install it first (brew install rclone)"
            )
        remote_name = resolve_remote(args.remote, label="bucket-check")
        bucket = _pick(args.bucket, "BUCKET_SYNC_BUCKET", str(mapping.get("bucket") or ""))
        if not bucket:
            bucket = remote_name
            print(
                f"bucket-check: WARNING bucket name fell back to remote name {remote_name!r} — "
                "set BUCKET_SYNC_BUCKET (.env) or mappings[].bucket (mkdocs.yml) "
                "to the real bucket name (R2 console); a wrong bucket returns 403.",
                file=sys.stderr,
            )
        remote_prefix = _pick(
            args.remote_prefix, "BUCKET_SYNC_REMOTE_PREFIX", str(mapping.get("remote_prefix") or "")
        )
        rpath = _rclone_path(remote_name, bucket, remote_prefix)
        keys = remote_keys(rpath)
        result["remote"] = {
            "rpath": rpath,
            "keys": len(keys),
            "missing_remote": sorted(rel for rel in refs if rel not in keys),
            "not_uploaded": sorted(rel for rel in local if rel not in keys),
        }

    # --only-* filters: drop the sections not asked for (exit code reflects
    # only the asked-for direction)
    if args.only_unreferenced:
        result.pop("missing", None)
        if "remote" in result:
            result["remote"].pop("missing_remote", None)
    if args.only_missing:
        result.pop("unreferenced", None)
        if "remote" in result:
            result["remote"].pop("not_uploaded", None)

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        _print_text(result, local_dir, include_drafts)

    missing = result.get("missing") or []
    unreferenced = result.get("unreferenced") or []
    issues = bool(missing) or bool(unreferenced)
    if checked_remote:
        r = result["remote"]
        issues = issues or bool(r.get("missing_remote")) or bool(r.get("not_uploaded"))
    return 1 if issues else 0


def _print_text(result: dict, local_dir: Path, include_drafts: bool) -> None:
    """Human-readable report. The remote sections render iff the remote check ran
    (result carries the "remote" dict — kept in sync with `checked_remote`)."""
    local_n = result["local_files"]
    ref_n = result["references"]
    print(
        f"bucket-check: prefix {result['prefix']!r} — local dir {_repo_rel(local_dir)} "
        f"({local_n} file(s)), {ref_n} reference(s) from md/html "
        f"(drafts {'included' if include_drafts else 'excluded'})"
    )

    missing = result.get("missing") or []
    if missing:
        print(f"\n[missing] {len(missing)} md/html link(s) → no local bucket file:")
        for item in missing:
            print(f"  {item['rel']}")
            for src in item["sources"]:
                print(f"    ← {src}")

    unreferenced = result.get("unreferenced") or []
    if unreferenced:
        print(
            f"\n[unreferenced] {len(unreferenced)} local bucket file(s) not referenced "
            "by md/html (cleanup candidates):"
        )
        for item in unreferenced:
            print(f"  {item['rel']}  ({item['size']})")

    if "remote" in result:
        r = result["remote"]
        if r.get("missing_remote"):
            print(f"\n[missing-remote] {len(r['missing_remote'])} md link(s) → not in the bucket:")
            for rel in r["missing_remote"]:
                print(f"  {rel}")
        if r.get("not_uploaded"):
            print(
                f"\n[not-uploaded] {len(r['not_uploaded'])} local file(s) absent from the "
                "bucket (pending upload; `bucket-sync pull --confirm` would delete them):"
            )
            for rel in r["not_uploaded"]:
                print(f"  {rel}")

    issue_n = len(result.get("unreferenced") or []) + len(result.get("missing") or [])
    if "remote" in result:
        issue_n += len(result["remote"].get("missing_remote") or []) + len(
            result["remote"].get("not_uploaded") or []
        )
    if issue_n:
        print(f"\nSummary: {issue_n} issue(s) found → exit 1")
        if result.get("remote", {}).get("not_uploaded"):
            print(
                "hint: not-uploaded files are absent from the bucket — upload them via "
                "PicList / 'poe bucket-upload', or delete them; 'poe bucket-sync pull --confirm' "
                "would delete them"
            )
    else:
        print("\nSummary: clean — no unreferenced files, no missing links.")


if __name__ == "__main__":
    raise SystemExit(main())
