"""Validate the film & TV archive (see ``poe film-tv-check``).

Checks the archive the sync produced — cheap local ones by default, Douban's
R2 bucket only with ``--check-remote`` (missing rclone/R2 credentials then skip
with a notice instead of reporting false orphans):

- ``covers`` / ``user.cover`` keys are archive-relative and well formed
  (``covers/<douban_id>/NN.webp``) — the local files are *not* required to exist,
  because a full mirror is deliberately not kept;
- ``user.watched_at`` agrees with the year file the record lives in;
- ``slug`` is globally unique and every slug with details is assigned;
- ``user.hidden`` / ``user.hidden_comment`` never leak into derived JSON;
- ``meta.machine_hash`` still matches the machine fields (hand-edit warning);
- ``meta.taxonomy_version`` is current, and the check lists which records would
  change ``regions`` / ``category`` if recomputed under the current taxonomy;
- undated records, pending details, deleted subjects, duplicate ids;
- **completeness**: the rows in the archive must cover the totals the list pages
  advertised (``.cache/film-tv/state/walk.json``) — an incomplete ``--full`` walk
  is otherwise indistinguishable from a complete archive;
- local cover files that no record references (orphans of an interrupted run);
- region aliases that the taxonomy does not know yet (candidates to add);
- with ``--check-remote``: cover keys missing from R2 + orphaned cover files.

Usage::

    uv run poe film-tv-check
    uv run poe film-tv-check --only shawshank-redemption
    uv run poe film-tv-check --since 2026-09-01
    uv run poe film-tv-check --check-remote
    uv run poe film-tv-check --data-quality   # fixed report → .cache/film-tv/reports/
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.bucket_sync import resolve_remote  # noqa: E402
from scripts.sync_film_tv import SyncError, load_config  # noqa: E402
from shared.bucket import find_mapping  # noqa: E402
from shared.env import load_env_files  # noqa: E402
from shared.film_tv_model import (  # noqa: E402
    Taxonomy,
    assign_year,
    machine_hash,
    validate_cover_key,
)
from shared.film_tv_store import (  # noqa: E402
    NON_YEAR_FILES,
    Entry,
    file_prefix,
    read_entries,
    year_file_name,
)
from shared.mkdocs_yaml import load_extra  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

SEVERITY_ORDER = {"error": 0, "warn": 1, "info": 2}


class Findings:
    """Collected issues, grouped by check, with a fixed-shape summary."""

    def __init__(self) -> None:
        self.items: list[dict] = []

    def add(self, severity: str, check: str, message: str, *, subject_id: str = "") -> None:
        self.items.append(
            {
                "severity": severity,
                "check": check,
                "id": subject_id,
                "message": message,
            }
        )

    @property
    def errors(self) -> list[dict]:
        return [item for item in self.items if item["severity"] == "error"]

    def counts(self) -> dict[str, int]:
        return dict(Counter(item["severity"] for item in self.items))


def load_archive(
    data_dir: Path, *, only: str | None, since: str | None
) -> list[tuple[Path, Entry]]:
    """Read every year file, optionally limited by slug (``--only``) or date."""
    records: list[tuple[Path, Entry]] = []
    for path in sorted(data_dir.glob("*.yml")):
        if path.name in NON_YEAR_FILES:
            continue
        for entry in read_entries(path):
            if only and entry.machine.get("slug") != only:
                continue
            if since:
                stamp = str(entry.meta.get("detail_synced_at") or "")
                if stamp < since:
                    continue
            records.append((path, entry))
    return records


def check_records(records, taxonomy: Taxonomy, findings: Findings) -> dict:
    """Local, cheap checks (no network, no R2)."""
    slugs: dict[str, str] = {}
    undated: list[str] = []
    undated_pending: list[str] = []
    undated_confirmed: list[str] = []
    undated_gone: list[str] = []
    regions_seen: Counter = Counter()
    categories: Counter = Counter()
    types: Counter = Counter()
    statuses: Counter = Counter()
    stats = {
        "records": len(records),
        "details_pending": 0,
        "undated": 0,
        "undated_ids": [],
        "undated_pending": [],
        "undated_confirmed": [],
        "undated_gone": [],
        "deleted": 0,
        "hidden": 0,
        "hidden_comment": 0,
        "scores": 0,
        "taxonomy_stale": [],
        "reclassify": [],
    }

    for path, entry in records:
        subject_id = entry.id
        machine, user, meta = entry.machine, entry.user, entry.meta
        types[str(machine.get("type"))] += 1
        statuses[str(machine.get("status"))] += 1

        # --- slugs ---------------------------------------------------------
        slug = str(machine.get("slug") or "")
        if not slug:
            # an empty slug never enters the uniqueness map (it would collide with
            # every other slug-less record). A record that is gone on Douban can
            # never get one: nothing is left to fetch, so it is finished rather
            # than pending.
            if not meta.get("missing_since"):
                stats["details_pending"] += 1
        elif slug in slugs:
            findings.add(
                "error",
                "slug",
                f"duplicate slug {slug!r} (also used by {slugs[slug]})",
                subject_id=subject_id,
            )
        else:
            slugs[slug] = subject_id

        # --- cover keys ----------------------------------------------------
        for key in list(machine.get("covers") or []):
            problem = validate_cover_key(str(key), subject_id=subject_id)
            if problem:
                findings.add("error", "cover-key", problem, subject_id=subject_id)
        user_cover = str(user.get("cover") or "")
        if user_cover:
            problem = validate_cover_key(user_cover, subject_id=subject_id)
            if problem:
                findings.add("error", "user-cover", problem, subject_id=subject_id)

        # --- dates / year file ---------------------------------------------
        watched_at = str(user.get("watched_at") or "")
        if watched_at and not DATE_RE.match(watched_at):
            findings.add(
                "error", "watched-at", f"not an ISO date: {watched_at!r}", subject_id=subject_id
            )
        year = assign_year(machine.get("marked_at"), watched_at)
        expected = year_file_name(file_prefix(machine.get("type")), year)
        if path.name != expected:
            findings.add(
                "error",
                "file-year",
                f"stored in {path.name} but belongs in {expected}",
                subject_id=subject_id,
            )
        if not machine.get("marked_at") and not watched_at:
            stats["undated"] += 1
            undated.append(subject_id)
            # three very different situations: the detail page may still bring the
            # 看过 date, the subject may be gone (nothing left to publish), or the
            # details are in and the date really has to be set by hand
            if meta.get("missing_since"):
                undated_gone.append(subject_id)
            elif meta.get("detail_synced_at"):
                undated_confirmed.append(subject_id)
            else:
                undated_pending.append(subject_id)

        # --- machine hash (hand edits of machine fields) --------------------
        stored_hash = meta.get("machine_hash")
        if stored_hash and stored_hash != machine_hash(machine):
            findings.add(
                "warn",
                "machine-hash",
                "machine fields were edited by hand — the next sync overwrites them",
                subject_id=subject_id,
            )

        # --- taxonomy freshness / reclassification --------------------------
        if meta.get("taxonomy_version") != taxonomy.rules_version:
            stats["taxonomy_stale"].append(subject_id)
        genres = list(machine.get("genres") or [])
        type_value = machine.get("type")
        new_category = taxonomy.classify_category(genres, type_value)
        if machine.get("category") and new_category != machine.get("category"):
            stats["reclassify"].append((subject_id, machine.get("category"), new_category))
        for region in machine.get("regions") or []:
            value = str(region)
            # a stored value that is still a taxonomy *alias* means normalization
            # did not run: that is a real defect, not a new vocabulary entry
            if value in taxonomy.regions:
                findings.add(
                    "error",
                    "region-alias",
                    f"stored region {value!r} is a taxonomy alias — it should have been "
                    f"normalized to {'/'.join(taxonomy.regions[value])!r}",
                    subject_id=subject_id,
                )
            elif any(ch.isascii() and ch.isalpha() for ch in value):
                findings.add(
                    "info",
                    "region-new",
                    f"region value {value!r} is not a known short name — add an alias to taxonomy",
                    subject_id=subject_id,
                )
            regions_seen[value] += 1

        if meta.get("missing_since"):
            stats["deleted"] += 1
        if user.get("hidden"):
            stats["hidden"] += 1
        if user.get("hidden_comment"):
            stats["hidden_comment"] += 1
        if machine.get("douban_score") is not None:
            stats["scores"] += 1
        categories[str(machine.get("category"))] += 1

    if undated:
        parts = []
        if undated_confirmed:
            parts.append(
                f"{len(undated_confirmed)} already synced and will stay dateless — they need "
                f"a user.watched_at by hand (e.g. {', '.join(undated_confirmed[:5])})"
            )
        if undated_pending:
            parts.append(
                f"{len(undated_pending)} still waiting for their detail page — the date may "
                "still arrive with it"
            )
        if undated_gone:
            parts.append(
                f"{len(undated_gone)} are gone on Douban — no date can be recovered, so they "
                "are skipped from the published data"
            )
        findings.add(
            "warn" if undated_confirmed else "info",
            "undated",
            f"{len(undated)} record(s) have neither marked_at nor user.watched_at; "
            + "; ".join(parts),
        )
    stats["undated_ids"] = undated
    stats["undated_confirmed"] = undated_confirmed
    stats["undated_pending"] = undated_pending
    stats["undated_gone"] = undated_gone
    stats["slugs"] = slugs
    stats["regions"] = regions_seen
    stats["categories"] = categories
    stats["type_counts"] = types
    stats["status_counts"] = statuses
    return stats


def check_derived_json(json_dir: Path, records, findings: Findings) -> dict:
    """Hidden records/comments must not appear in the published shards.

    Contract (``film-tv-derive``): ``index.json`` carries
    ``months: {YYYY-MM → {shard, offset, count, by_type}}`` and each
    ``shard-*.json`` carries ``{count, first_date, last_date, items}``. Records
    with ``user.hidden`` are absent, and records with ``user.hidden_comment``
    carry no ``comment``.
    """
    info = {"shards": 0, "entries": 0, "missing": [], "shards_loaded": []}
    index_path = json_dir / "index.json"
    if not index_path.is_file():
        findings.add("info", "json", "no derived JSON yet — run `poe film-tv-derive`")
        return info
    try:
        index = json.loads(index_path.read_text(encoding="utf-8"))
    except ValueError as exc:
        findings.add("error", "json", f"index.json is not valid JSON: {exc}")
        return info
    if not isinstance(index, dict):
        findings.add("error", "json", "index.json must be a month → shard mapping")
        return info

    hidden_ids = {entry.id for _path, entry in records if entry.user.get("hidden")}
    hidden_comment_ids = {entry.id for _path, entry in records if entry.user.get("hidden_comment")}
    # index shape: {shard_size, shards, totals, months: {YYYY-MM: {shard, …}}}
    months = index.get("months")
    if not isinstance(months, dict):
        findings.add("error", "json", "index.json has no `months` mapping — re-run film-tv-derive")
        return info
    shard_names = {value.get("shard") for value in months.values() if isinstance(value, dict)}
    for name in sorted(str(n) for n in shard_names if n):
        shard_path = json_dir / name
        if not shard_path.is_file():
            info["missing"].append(name)
            continue
        info["shards"] += 1
        try:
            shard = json.loads(shard_path.read_text(encoding="utf-8"))
        except ValueError as exc:
            findings.add("error", "json", f"{name}: invalid JSON ({exc})")
            continue
        info["shards_loaded"].append(shard)
        items = shard.get("items") or []
        info["entries"] += len(items)
        if shard.get("count") is not None and shard.get("count") != len(items):
            findings.add("error", "json", f"{name}: count={shard['count']} but {len(items)} items")
        for item in items:
            subject_id = str(item.get("id") or "")
            if subject_id in hidden_ids or item.get("hidden"):
                findings.add("error", "json-leak", f"{name}: hidden record {subject_id}")
            if subject_id in hidden_comment_ids and item.get("comment"):
                findings.add(
                    "error", "json-leak", f"{name}: hidden comment leaked for {subject_id}"
                )
    if info["missing"]:
        findings.add("error", "json", f"missing shard files: {', '.join(info['missing'][:10])}")

    # freshness: the derived files are committed alongside the year YAML, so a
    # mismatch means someone edited/synced one side only (the plan's `source_hash`
    # intent, without storing a hash)
    totals = index.get("totals") or {}
    expected = totals.get("records")
    skipped = int(totals.get("skipped") or 0)
    actual = len(records)
    if isinstance(expected, int) and expected != actual:
        findings.add(
            "error",
            "derived-stale",
            f"derived data is stale: index.json says {expected} records, the year files have "
            f"{actual} — run `poe film-tv-derive`",
        )
    # records gone on Douban *and* dateless are deliberately not published
    info["skipped"] = skipped
    info["published"] = actual - skipped
    shard_total = sum(shard.get("count") or 0 for shard in info.get("shards_loaded", []))
    published = info["published"]
    if info["shards"] and shard_total != published:
        findings.add(
            "error",
            "derived-stale",
            f"derived data is stale: shards hold {shard_total} records, the year files"
            f" have {published} publishable ones ({actual} − {skipped} gone/dateless) — run"
            " `poe film-tv-derive`",
        )
    return info


def check_walk_total(state_dir: Path, records, findings: Findings) -> dict:
    """The archive must cover the totals the collection lists advertised.

    ``walk.json`` holds each tab's page-header total from the last ``--full`` walk
    (``collect/movie`` = 3092, ``collect/tv`` = 1200, …). Fewer archived records
    than the sum of those totals means the walk never finished — the failure mode
    that used to be silent: an empty page mid-list ended a tab and the resulting
    archive looked perfectly healthy to every other check.

    ``missing_since`` records are counted: a subject Douban reports as deleted is
    still one of the rows the header counts (only `--prune` takes a row out of the
    list, and those leftover records merely *inflate* the count — an equal number
    of prunes could mask a truncation, but a healthy archive is never flagged).
    """
    path = Path(state_dir) / "walk.json"
    info: dict = {"state": str(path), "totals": {}, "expected": 0, "records": 0}
    if not path.is_file():
        findings.add(
            "info",
            "walk-total",
            "no walk state yet (no `--full` walk recorded) — skipping the completeness check",
        )
        return info
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except ValueError:
        findings.add("warn", "walk-total", "walk.json is not valid JSON — skipped")
        return info
    totals = {
        str(tab): int(value)
        for tab, value in (payload.get("total") or {}).items()
        if isinstance(value, int) and value
    }
    info["totals"] = totals
    info["expected"] = sum(totals.values())
    info["records"] = len(records)
    if info["expected"] and info["records"] < info["expected"]:
        findings.add(
            "error",
            "walk-total",
            f"the archive holds {info['records']} record(s) but the list pages report "
            f"{info['expected']} ({', '.join(f'{tab}={n}' for tab, n in sorted(totals.items()))}) "
            "— an earlier `--full` walk did not finish. Re-run "
            "`uv run poe sync-film-tv --full` (it resumes from the recorded cursor)",
        )
    return info


def check_local_covers(cover_dir: Path, records, findings: Findings) -> dict:
    """Local cover files that no record references (orphans of an interrupted run).

    Missing local files are fine (only recent years are kept locally, the rest is
    uploaded to R2), but a file that exists *and* is referenced by nothing is
    either a leftover duplicate or a cover whose record never landed.
    """
    root = Path(cover_dir)
    info: dict = {"local": 0, "referenced": 0, "orphans": []}
    if not root.is_dir():
        return info
    referenced = {
        str(key)
        for _path, entry in records
        for key in [*(entry.machine.get("covers") or []), entry.user.get("cover")]
        if key
    }
    local = sorted(path.relative_to(root).as_posix() for path in root.rglob("*.webp"))
    info["local"] = len(local)
    info["referenced"] = len(set(local) & referenced)
    orphans = [key for key in local if key not in referenced]
    info["orphans"] = orphans
    if orphans:
        findings.add(
            "info",
            "local-orphan",
            f"{len(orphans)} local cover file(s) are referenced by no record "
            f"(e.g. {', '.join(orphans[:3])}) — `uv run poe sync-film-tv --dedupe-covers`"
            " reports the byte-identical duplicates of a referenced cover",
        )
    return info


def check_bucket_config(findings: Findings, *, local_prefix: str) -> dict:
    """``extra.bucket`` mapping and ``extra.film_tv`` must agree."""
    mapping = find_mapping(load_extra("bucket", label="film-tv-check"), "film-tv")
    info = {"mapping": mapping}
    if mapping is None:
        findings.add("error", "bucket", "extra.bucket.mappings has no `film-tv` mapping")
        return info
    if not str(mapping.get("prefix", "")).startswith(local_prefix.rstrip("/")):
        findings.add(
            "error",
            "bucket",
            f"mapping prefix {mapping.get('prefix')!r} does not cover {local_prefix!r}",
        )
    remote_prefix = str(mapping.get("remote_prefix") or "").strip("/")
    base_url = str(mapping.get("base_url") or "").rstrip("/")
    if remote_prefix and not base_url.endswith(remote_prefix):
        findings.add(
            "error",
            "bucket",
            f"base_url {base_url!r} does not end with remote_prefix {remote_prefix!r}",
        )
    return info


def check_remote(mapping: dict | None, records, findings: Findings) -> dict:
    """Compare cover keys against the R2 bucket (skipped without rclone/creds)."""
    remote = _remote_listing(mapping, findings)
    if remote is None:
        return {"checked": False}
    # `rclone lsf` prints paths *relative* to the directory it listed, which is
    # <remote_prefix> — exactly the archive-root-relative keys we compare against
    remote_files = set(remote)
    referenced = {
        str(key)
        for _path, entry in records
        for key in [*(entry.machine.get("covers") or []), entry.user.get("cover")]
        if key
    }
    missing = sorted(referenced - remote_files)
    for key in missing[:20]:
        findings.add("warn", "remote-missing", f"referenced cover is not in R2: {key}")
    orphans = sorted(remote_files - referenced)
    for key in orphans[:20]:
        findings.add("info", "remote-orphan", f"R2 cover is not referenced by any record: {key}")
    return {"checked": True, "missing": len(missing), "orphans": len(orphans)}


def _remote_listing(mapping: dict | None, findings: Findings) -> list[str] | None:
    """``rclone lsf`` over the film-tv remote dir, or ``None`` when unavailable."""
    if mapping is None:
        findings.add("warn", "remote", "no film-tv mapping — skipping the remote check")
        return None
    rclone = shutil.which("rclone")
    if rclone is None:
        findings.add("info", "remote", "rclone not installed — skipping the remote check")
        return None
    remote_name = resolve_remote(None, label="film-tv-check")
    target = f"{remote_name}:{mapping.get('bucket')}/{mapping.get('remote_prefix')}"
    try:
        result = subprocess.run(
            [rclone, "lsf", "-R", "--files-only", target],
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        findings.add("info", "remote", f"rclone failed ({exc.__class__.__name__}) — skipped")
        return None
    if result.returncode != 0:
        findings.add("info", "remote", "rclone could not list the bucket — skipped")
        return None
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def data_quality_report(
    stats: dict,
    findings: Findings,
    taxonomy: Taxonomy,
    *,
    walk: dict | None = None,
    covers: dict | None = None,
    derived: dict | None = None,
) -> dict:
    """Fixed-shape report (written to .cache/film-tv/reports/<ts>.json)."""
    total = stats["records"] or 1
    return {
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "taxonomy_version": taxonomy.rules_version,
        "records": stats["records"],
        "types": stats["type_counts"],
        "categories": stats["categories"],
        "statuses": stats["status_counts"],
        "details_pending": stats["details_pending"],
        "details_pending_ratio": round(stats["details_pending"] / total, 4),
        "undated": stats["undated"],
        "undated_ids": stats["undated_ids"],
        "undated_confirmed": len(stats["undated_confirmed"]),
        "undated_pending": len(stats["undated_pending"]),
        "undated_gone": len(stats["undated_gone"]),
        # comes from the derived index (the derivation decides what is publishable),
        # so the report follows the derive if its skip rule ever changes
        "records_published": (derived or {}).get("published") or stats["records"],
        "deleted": stats["deleted"],
        "hidden": stats["hidden"],
        "hidden_comment": stats["hidden_comment"],
        "with_douban_score": stats["scores"],
        "taxonomy_stale": len(stats["taxonomy_stale"]),
        "would_reclassify": [
            {"id": subject_id, "from": old, "to": new}
            for subject_id, old, new in stats["reclassify"][:50]
        ],
        "regions": dict(stats["regions"].most_common()),
        "findings": findings.counts(),
        "list_totals": (walk or {}).get("totals") or {},
        "records_expected": (walk or {}).get("expected", 0),
        "local_covers": (covers or {}).get("local", 0),
        "local_cover_orphans": len((covers or {}).get("orphans") or []),
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate the film & TV archive")
    parser.add_argument("--only", default=None, help="check just this slug")
    parser.add_argument("--since", default=None, help="only records synced on/after this date")
    parser.add_argument(
        "--check-remote", action="store_true", help="also compare cover keys against R2"
    )
    parser.add_argument(
        "--data-quality", action="store_true", help="write a fixed-format report to .cache/"
    )
    parser.add_argument("--quiet", action="store_true", help="only report errors")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    load_env_files()
    try:
        config = load_config()
    except SyncError as exc:
        print(f"film-tv-check: {exc}", file=sys.stderr)
        return 1
    taxonomy = Taxonomy.load(config.taxonomy_path)

    records = load_archive(config.data_dir, only=args.only, since=args.since)
    filtered = args.only is not None or args.since is not None
    findings = Findings()
    stats = check_records(records, taxonomy, findings)
    bucket_info = check_bucket_config(findings, local_prefix=config.local_prefix)
    json_info = check_derived_json(config.json_dir, records, findings)
    # a filtered run sees a subset of the archive: no completeness answer, and
    # "unreferenced" covers would be meaningless
    if filtered:
        walk_info: dict = {"expected": 0, "records": 0, "totals": {}}
        cover_info: dict = {"local": 0, "referenced": 0, "orphans": []}
    else:
        walk_info = check_walk_total(config.state_dir, records, findings)
        cover_info = check_local_covers(config.cover_dir, records, findings)
    remote_info = {"checked": False}
    if args.check_remote:
        remote_info = check_remote(bucket_info.get("mapping"), records, findings)

    print(f"film-tv-check: {stats['records']} records, taxonomy v{taxonomy.rules_version}")
    print(
        f"  types {stats['type_counts']} | categories {stats['categories']} | "
        f"slugs {len(stats['slugs'])}"
    )
    print(
        f"  details pending {stats['details_pending']} | undated {stats['undated']} | "
        f"deleted {stats['deleted']} | hidden {stats['hidden']}"
    )
    if stats["regions"]:
        top = ", ".join(f"{name}×{count}" for name, count in stats["regions"].most_common(8))
        print(f"  regions: {top}")
    if stats["taxonomy_stale"]:
        print(f"  records on an older taxonomy_version: {len(stats['taxonomy_stale'])}")
    if stats["reclassify"]:
        print(f"  would be re-classified under the current rules: {len(stats['reclassify'])}")
        for subject_id, old, new in stats["reclassify"][:10]:
            print(f"    {subject_id}: {old} → {new}")
    if bucket_info.get("mapping"):
        print(f"  bucket mapping: {bucket_info['mapping'].get('remote_prefix')} → R2")
    print(
        f"  derived json: {json_info['shards']} shard(s), {json_info['entries']} entries"
        if json_info["shards"] or json_info["entries"]
        else "  derived json: not generated yet (run `poe film-tv-derive`)"
    )
    if not filtered:
        expected = walk_info.get("expected") or 0
        if expected:
            print(
                f"  completeness: {walk_info.get('records', 0)} record(s) vs {expected} "
                "advertised by the lists"
            )
        else:
            print("  completeness: no walk state yet (run `poe sync-film-tv --full`)")
        if cover_info.get("local"):
            print(
                f"  local covers: {cover_info['local']} file(s), "
                f"{cover_info['referenced']} referenced, {len(cover_info['orphans'])} orphaned"
            )
    if remote_info.get("checked"):
        print(
            f"  remote: {remote_info['missing']} missing, {remote_info['orphans']} orphaned covers"
        )

    shown = [item for item in findings.items if not (args.quiet and item["severity"] != "error")]
    if shown:
        print(f"\nfindings ({len(shown)}):")
        for item in sorted(
            shown, key=lambda i: (SEVERITY_ORDER[i["severity"]], i["check"], i["id"])
        ):
            prefix = {"error": "ERROR", "warn": "WARN ", "info": "info "}[item["severity"]]
            where = f" [{item['id']}]" if item["id"] else ""
            print(f"  {prefix} {item['check']}{where}: {item['message']}")

    if args.data_quality:
        reports = REPO_ROOT / ".cache" / "film-tv" / "reports"
        reports.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%dT%H%M%S")
        path = reports / f"{stamp}.json"
        path.write_text(
            json.dumps(
                data_quality_report(
                    stats,
                    findings,
                    taxonomy,
                    walk=walk_info,
                    covers=cover_info,
                    derived=json_info,
                ),
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        print(f"\nreport written: {path}")

    errors = findings.errors
    print(f"\n{len(errors)} error(s), {len(findings.items) - len(errors)} other finding(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
