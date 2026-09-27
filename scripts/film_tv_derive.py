"""Generate the film & TV archive's derived data (shards, month index, stats).

Output goes to ``docs/notes/film-tv/assets/`` (committed, because the front end
fetches it at runtime — the year YAMLs stay ``exclude_docs``). Everything here is
**deterministic**: no timestamps, stable ordering and formatting, and a file
whose content did not change is not rewritten, so a no-op sync produces no diff.

Produces:

- ``index.json`` — ``{shard_size, shards, totals, months:
  {"YYYY-MM": {shard, offset, count, by_type}}}``;
- ``shard-NNNN.json`` — ``SHARD_SIZE`` records per file, time-descending, each
  with ``count`` / ``first_date`` / ``last_date`` self-check fields;
- ``stats.yml`` — archive statistics (totals, hours, averages, registries);
- ``people.yml`` — the 影人 boards (director / actor / writer).

Usage::

    uv run poe film-tv-derive
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.sync_film_tv import SyncError  # noqa: E402
from scripts.sync_film_tv import load_config as load_sync_config  # noqa: E402
from shared.bucket import find_mapping  # noqa: E402
from shared.env import load_env_files  # noqa: E402
from shared.film_tv_store import (  # noqa: E402
    NON_YEAR_FILES,
    PERSON_IDS_FILE,
    Entry,
    read_entries,
    read_person_ids,
)
from shared.mkdocs_yaml import load_extra  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent

#: records per shard (design §3: first screen reads shard-0001 only)
SHARD_SIZE = 200
#: People aggregation bounds: one-off bit-part names would balloon the committed
#: file (≈5MB at archive scale) while the boards only need repeats
PEOPLE_MIN_WORKS = 2
PEOPLE_LIMIT = 2000
SHARD_NAME = "shard-{index:04d}.json"
SHARD_RE = re.compile(r"^shard-\d{4}\.json$")


@dataclass
class Config:
    data_dir: Path
    json_dir: Path
    cover_base: str
    shard_size: int = SHARD_SIZE


def load_config() -> Config:
    """Archive paths (shared with the sync) plus the bucket URL for covers."""
    try:
        paths = load_sync_config()
    except SyncError as exc:
        raise SystemExit(f"film-tv-derive: {exc}") from exc
    # Cover URLs are baked into the JSON: the page cannot rely on the bucket
    # plugin's HTML rewriting for data it fetches at runtime. Re-run derive after
    # switching bucket base_url (or set MKDOCS_BUCKET_BASE_URL[_FILM_TV]).
    mapping = find_mapping(load_extra("bucket", label="film-tv-derive"), "film-tv")
    cover_base = str((mapping or {}).get("base_url") or "").rstrip("/")
    return Config(
        data_dir=paths.data_dir,
        json_dir=paths.json_dir,
        cover_base=cover_base,
    )


def load_records(config: Config) -> list[Entry]:
    records: list[Entry] = []
    for path in sorted(config.data_dir.glob("*.yml")):
        if path.name in NON_YEAR_FILES:
            continue
        records.extend(read_entries(path))
    return records


def effective_rating(machine: dict, user: dict) -> int | None:
    """``user.my_rating`` (hand correction) wins over the Douban rating."""
    value = user.get("my_rating")
    if value is None:
        value = machine.get("user_rating")
    return int(value) if value not in (None, "") else None


def effective_date(machine: dict, user: dict) -> str:
    return str(user.get("watched_at") or machine.get("marked_at") or "")


def effective_cover(machine: dict, user: dict) -> str:
    """Archive-relative cover key (``user.cover`` wins, else the first candidate)."""
    cover = str(user.get("cover") or "").strip()
    if cover:
        return cover
    covers = machine.get("covers") or []
    return str(covers[0]) if covers else ""


PERSON_RE = re.compile(r"^(?P<latin>.+?)\uff08(?P<zh>.+)\uff09$")


def person_id_map(aliases: dict[str, str], directory: dict[str, str]) -> dict[str, str]:
    """``显示名 → personage id`` built from the archive's person directory.

    Names may still be stored in their short Chinese form in older records, so the
    alias table (which maps those to the enriched label) is walked as well.
    """
    reverse = {name: person_id for person_id, name in directory.items()}
    mapping = dict(reverse)
    for short_name, rich_name in aliases.items():
        person_id = reverse.get(rich_name)
        if person_id:
            mapping.setdefault(short_name, person_id)
    return mapping


def person_aliases(records: list[Entry]) -> dict[str, str]:
    """``中文名 → 原文本名（中文名）`` for every annotated person in the archive.

    A person only gets their original name when they appear in an entry's
    ``#celebrities`` block, so the same actor can be stored as
    ``Frank Darabont（弗兰克·德拉邦特）`` in one record and ``弗兰克·德拉邦特`` in
    another. This alias table lets the derived JSON and the 影人 aggregation use
    one form for everyone (otherwise the boards split the same person in two).
    """
    aliases: dict[str, str] = {}
    for entry in records:
        credits = entry.machine.get("credits") or {}
        for key in ("directors", "casts", "writers"):
            for name in credits.get(key) or []:
                match = PERSON_RE.match(str(name))
                if match:
                    aliases.setdefault(match.group("zh"), str(name))
    return aliases


def present(entry: Entry, config: Config, aliases: dict[str, str] | None = None) -> dict:
    """One record as the front end needs it (no hidden data, no bucket prefix)."""
    machine, user = entry.machine, entry.user
    cover = effective_cover(machine, user)
    credits = machine.get("credits") or {}

    def people(key: str) -> list[str]:
        names = [str(name) for name in credits.get(key) or []]
        if not aliases:
            return names
        return [aliases.get(name, name) for name in names]

    record = {
        "id": entry.id,
        "slug": str(machine.get("slug") or ""),
        "title": str(machine.get("title") or ""),
        "year": machine.get("year"),
        "type": machine.get("type"),
        "category": machine.get("category"),
        "status": machine.get("status"),
        "rating": effective_rating(machine, user),
        "douban_score": machine.get("douban_score"),
        "date": effective_date(machine, user),
        "genres": list(machine.get("genres") or []),
        "regions": list(machine.get("regions") or []),
        "tags": list(user.get("my_tags") or machine.get("tags") or []),
        "runtime": machine.get("runtime"),
        "cover": cover,
        "url": str(machine.get("douban_url") or ""),
        "directors": people("directors"),
        "casts": people("casts"),
        "writers": people("writers"),
        "pending": not entry.meta.get("detail_synced_at"),
        "missing": bool(entry.meta.get("missing_since")),
    }
    if machine.get("episodes"):
        record["episodes"] = machine["episodes"]
    if machine.get("original_title"):
        record["original_title"] = machine["original_title"]
    # hidden_comment keeps the comment out of the published data entirely
    if not user.get("hidden_comment"):
        comment = str(machine.get("douban_comment") or "")
        if comment:
            record["comment"] = comment
    review = str(user.get("review") or "").strip()
    if review:
        record["review"] = review
    if config.cover_base and cover:
        record["cover_url"] = f"{config.cover_base}/{cover}"
    return record


def build_shards(records: list[dict], *, shard_size: int) -> list[dict]:
    """Split time-descending records into fixed-size shards with self-checks."""
    shards = []
    for start in range(0, len(records), shard_size):
        chunk = records[start : start + shard_size]
        shards.append(
            {
                "count": len(chunk),
                "first_date": chunk[0]["date"] if chunk else None,
                "last_date": chunk[-1]["date"] if chunk else None,
                "items": chunk,
            }
        )
    return shards


def build_index(records: list[dict], *, shard_size: int) -> dict:
    """Month → shard/offset/count map, plus the totals the UI needs."""
    months: dict[str, dict] = {}
    for position, record in enumerate(records):
        month = (record["date"] or "")[:7]
        if not month:
            month = "undated"
        shard_index = position // shard_size
        entry = months.setdefault(
            month,
            {
                "shard": SHARD_NAME.format(index=shard_index + 1),
                "offset": position % shard_size,
                "count": 0,
                # per-type counts let a movies/tv page show its own calendar volume
                "by_type": {},
            },
        )
        entry["count"] += 1
        type_key = record["type"] or "unknown"
        entry["by_type"][type_key] = entry["by_type"].get(type_key, 0) + 1
    shard_count = (len(records) + shard_size - 1) // shard_size
    return {
        "shard_size": shard_size,
        # explicit list: `months` only pins the shard holding each month's first
        # record, so it can skip shards (a month can span two of them)
        "shards": [SHARD_NAME.format(index=number) for number in range(1, shard_count + 1)],
        "totals": {
            "records": len(records),
            "movies": sum(1 for r in records if r["type"] == "movie"),
            "tv": sum(1 for r in records if r["type"] == "tv"),
            "rated": sum(1 for r in records if r["rating"] is not None),
            "pending": sum(1 for r in records if r["pending"]),
        },
        "months": months,
    }


def watch_hours(records: list[dict]) -> int:
    """Total watch time in hours (rounded).

    Movies contribute their runtime; tv contributes per-episode runtime × episode
    count — a tv entry without an episode count is skipped rather than counted as
    one episode.
    """
    minutes = 0
    for record in records:
        runtime = record.get("runtime") or 0
        if not runtime:
            continue
        if record.get("type") == "tv":
            episodes = record.get("episodes") or 0
            if episodes:
                minutes += runtime * episodes
        else:
            minutes += runtime
    return round(minutes / 60)


def stats_payload(records: list[dict]) -> dict:
    """Deterministic archive statistics (the index page renders these at build time)."""
    years = Counter((r["date"] or "")[:4] for r in records if r["date"])
    categories = Counter(r["category"] or "unknown" for r in records)
    types = Counter(r["type"] or "unknown" for r in records)
    regions: Counter = Counter()
    for record in records:
        for region in record["regions"]:
            regions[region] += 1
    ratings = [r["rating"] for r in records if r["rating"] is not None]
    return {
        "total": len(records),
        "rated": len(ratings),
        "hours": watch_hours(records),
        "average_rating": round(sum(ratings) / len(ratings), 2) if ratings else None,
        "by_year": dict(sorted(years.items(), reverse=True)),
        "by_type": dict(sorted(types.items())),
        "by_category": dict(sorted(categories.items())),
        "by_region": dict(regions.most_common()),
    }


def people_payload(
    records: list[dict],
    *,
    min_works: int = PEOPLE_MIN_WORKS,
    limit: int = PEOPLE_LIMIT,
    ids: dict[str, str] | None = None,
) -> list[dict]:
    """Director / actor / writer aggregation for the people boards."""
    people: dict[str, dict] = {}

    def add(name: str, role: str, record: dict) -> None:
        person = people.setdefault(
            name, {"name": name, "works": [], "roles": set(), "ratings": [], "years": []}
        )
        if record["id"] not in person["works"]:
            person["works"].append(record["id"])
        person["roles"].add(role)
        if record["rating"] is not None:
            person["ratings"].append(record["rating"])
        if record["date"]:
            person["years"].append(int(record["date"][:4]))

    for record in records:
        for name in record["directors"]:
            add(name, "director", record)
        for name in record["casts"]:
            add(name, "actor", record)
        for name in record.get("writers") or []:
            add(name, "writer", record)
    entries = []
    for person in people.values():
        if len(person["works"]) < min_works:
            continue
        person_id = (ids or {}).get(person["name"], "")
        entries.append(
            {
                "name": person["name"],
                "douban_id": person_id or None,
                "douban_url": f"https://www.douban.com/personage/{person_id}/"
                if person_id
                else None,
                "roles": sorted(person["roles"]),
                "works": len(person["works"]),
                "ratings": person["ratings"],
                "avg_rating": (
                    round(sum(person["ratings"]) / len(person["ratings"]), 2)
                    if person["ratings"]
                    else None
                ),
                "first_year": min(person["years"]) if person["years"] else None,
                "last_year": max(person["years"]) if person["years"] else None,
            }
        )
    entries.sort(key=lambda p: (-p["works"], p["name"]))
    return entries[:limit]


def dumps(payload) -> str:
    """Stable JSON text (sorted keys, fixed separators, unicode kept)."""
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=1) + "\n"


def dump_yaml(payload) -> str:
    class _Dumper(yaml.SafeDumper):
        pass

    _Dumper.add_representer(
        dict, lambda d, data: d.represent_mapping("tag:yaml.org,2002:map", data, flow_style=False)
    )
    return yaml.dump(
        payload, Dumper=_Dumper, allow_unicode=True, sort_keys=True, width=10**6, indent=2
    )


def write_if_changed(path: Path, text: str) -> bool:
    """Write only when the content differs (keeps no-op runs diff-free)."""
    if path.is_file() and path.read_text(encoding="utf-8") == text:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return True


def run(*, dry_run: bool = False, shard_size: int | None = None) -> int:
    load_env_files()
    config = load_config()
    if shard_size:
        # testing knob: a small shard size exercises the client-side paging across
        # shards without needing a multi-thousand-record archive
        config.shard_size = shard_size
    entries = load_records(config)
    if not entries:
        print("film-tv-derive: no records yet — run `poe sync-film-tv` first")
        return 1

    aliases = person_aliases(entries)
    records = [present(entry, config, aliases) for entry in entries if not entry.user.get("hidden")]
    hidden = len(entries) - len(records)
    records.sort(key=lambda r: (r["date"], r["id"]), reverse=True)

    shards = build_shards(records, shard_size=config.shard_size)
    index = build_index(records, shard_size=config.shard_size)
    directory = read_person_ids(config.data_dir / PERSON_IDS_FILE)
    people_entries = people_payload(records, ids=person_id_map(aliases, directory))
    stats = stats_payload(records)
    stats["people"] = len(people_entries)
    stats["pending"] = index["totals"]["pending"]

    planned: dict[str, str] = {
        "index.json": dumps(index),
        "stats.yml": dump_yaml(stats),
        "people.yml": dump_yaml({"people": people_entries}),
    }
    for number, shard in enumerate(shards, start=1):
        planned[SHARD_NAME.format(index=number)] = dumps(shard)

    stale = [
        path
        for path in config.json_dir.glob("shard-*.json")
        if SHARD_RE.match(path.name) and path.name not in planned
    ]
    changed = sorted(
        name for name, text in planned.items() if not _same(config.json_dir / name, text)
    )
    print(
        f"film-tv-derive: {len(records)} records ({hidden} hidden), {len(shards)} shard(s), "
        f"{len(changed)} file(s) to write" + (f", {len(stale)} stale to remove" if stale else "")
    )
    for name in changed:
        print(f"  write {name}")
    for path in stale:
        print(f"  remove {path.name}")
    if dry_run:
        return 0

    for name, text in planned.items():
        write_if_changed(config.json_dir / name, text)
    for path in stale:
        path.unlink()
    print(
        f"  totals: {stats['total']} records, avg {stats['average_rating']} "
        f"({stats['rated']}/{stats['total']} rated), {len(people_entries)} people, "
        f"{stats['pending']} pending details"
    )
    return 0


def _same(path: Path, text: str) -> bool:
    return path.is_file() and path.read_text(encoding="utf-8") == text


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate the film & TV archive's derived data")
    parser.add_argument("--dry-run", action="store_true", help="print what would change")
    parser.add_argument(
        "--shard-size",
        type=int,
        default=None,
        help=f"records per shard (default {SHARD_SIZE}; small values are for testing paging)",
    )
    args = parser.parse_args(argv)
    return run(dry_run=args.dry_run, shard_size=args.shard_size)


if __name__ == "__main__":
    sys.exit(main())
