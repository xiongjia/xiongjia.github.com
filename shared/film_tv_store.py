"""Year-file storage for the Film & TV archive.

Storage layout (design §3): ``docs/notes/film-tv/data/movies-<YYYY>.yml`` /
``tv-<YYYY>.yml`` plus ``movies-undated.yml`` / ``tv-undated.yml``. The year is
the **watching year**; within a file records are sorted by date (newest first)
with ``id`` as a stable tiebreaker.

A file is a YAML list of records rendered from three blocks::

    - <machine fields>      # re-synced from Douban on every run
      user:                 # human block — spliced through VERBATIM
        ...
      meta:                 # sync bookkeeping

The three write rules that keep the git diff honest:

1. key order is fixed (:data:`MACHINE_KEY_ORDER` / :data:`META_KEY_ORDER`);
2. the ``user:`` block is copied byte-for-byte from the previous file — it is
   never re-serialized, so hand formatting/comments survive;
3. a file whose rendered body equals the file on disk is **not written**, and
   the ``# generated_at:`` header comment only moves when the body does.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import yaml

#: rendered key order of the machine block (before ``user:``)
MACHINE_KEY_ORDER = (
    "id",
    "title",
    "original_title",
    "year",
    "type",
    "category",
    "status",
    "user_rating",
    "douban_score",
    "douban_score_count",
    "marked_at",
    "douban_comment",
    "tags",
    "genres",
    "regions",
    "languages",
    "runtime",
    "credits",
    "episodes",
    "slug",
    "covers",
    "douban_url",
)

#: rendered key order of the ``meta:`` block (after ``user:``)
META_KEY_ORDER = (
    "detail_synced_at",
    "taxonomy_version",
    "fingerprint",
    "machine_hash",
    "missing_since",
    # why the record stopped being fetchable: "gone" (subject taken down on
    # Douban) or "pruned" (row left my collection) — only the latter is undone
    # automatically when the row shows up in a walk again
    "missing_reason",
)

#: short attribute lists rendered in flow style (``tags: [a, b]``)
FLOW_LIST_KEYS = ("tags", "genres", "regions", "languages", "directors", "casts", "writers")

#: keys of the human block, in the order a fresh block is written
USER_KEYS = (
    "cover",
    "hidden_comment",
    "my_rating",
    "my_tags",
    "watched_at",
    "review",
    "hidden",
)

DEFAULT_USER_VALUES = {
    "cover": "",
    "hidden_comment": False,
    "my_rating": None,
    "my_tags": [],
    "watched_at": "",
    "review": "",
    "hidden": False,
}

#: files in ``data/`` that are NOT year files (skipped by every reader)
NON_YEAR_FILES = ("taxonomy.yml", "person-ids.yml")

#: the person directory: personage id → display name, so later enrichment
#: (original name / avatar / birthday) can fetch ``personage/<id>/`` directly
PERSON_IDS_FILE = "person-ids.yml"
PERSON_IDS_HEADER = (
    "# 影人目录（由 scripts/sync_film_tv.py 维护，追加式）：personage id → 显示名。",
    "# 需要补充影人信息（原名 / 头像 / 生日 …）时直接用这个 id：",
    "#   https://www.douban.com/personage/<id>/",
)

HEADER_LINES = (
    "# Film & TV archive — top-level fields are machine-owned and rewritten from",
    "# Douban on every sync; edit the `user:` block freely, it is never touched.",
)

ENTRY_RE = re.compile(r"^- ", re.M)
USER_LINE_RE = re.compile(r"^  user:[ \t]*$", re.M)
META_LINE_RE = re.compile(r"^  meta:[ \t]*$", re.M)
GENERATED_AT_RE = re.compile(r"^# generated_at:\s*(.*)$", re.M)


class StoreError(RuntimeError):
    """A year file could not be read (bad structure or YAML)."""


class FlowList(list):
    """List rendered in flow style."""


class BlockDumper(yaml.SafeDumper):
    """Dumper pinning the archive's style choices (see module docstring)."""


def _represent_flow_list(dumper, data):
    return dumper.represent_sequence("tag:yaml.org,2002:seq", list(data), flow_style=True)


def _represent_dict(dumper, data):
    return dumper.represent_mapping("tag:yaml.org,2002:map", data, flow_style=False)


def _represent_str(dumper, data):
    """Quote only where a plain scalar would be read as another type.

    ``'2009-05-01'`` would parse back as a date and ``'1292052'`` as an int, so
    ISO dates / numeric-looking ids get explicit double quotes while ordinary
    text stays plain.
    """
    implicit = dumper.resolve(yaml.nodes.ScalarNode, data, (True, False))
    style = '"' if implicit != "tag:yaml.org,2002:str" else None
    return dumper.represent_scalar("tag:yaml.org,2002:str", data, style=style)


BlockDumper.add_representer(FlowList, _represent_flow_list)
BlockDumper.add_representer(dict, _represent_dict)
BlockDumper.add_representer(str, _represent_str)


@dataclass
class Entry:
    """One record: machine fields, the parsed user block, its raw text, meta."""

    machine: dict
    user: dict = field(default_factory=dict)
    user_raw: str = ""
    meta: dict = field(default_factory=dict)

    @property
    def id(self) -> str:
        return str(self.machine.get("id", ""))

    def effective_date(self) -> str:
        """Watching date driving sort order and the year file (user value wins)."""
        return str(self.user.get("watched_at") or self.machine.get("marked_at") or "")


def dump_yaml(value) -> str:
    """Deterministic YAML render (unicode, two-space indent, no wrapping)."""
    return yaml.dump(
        value,
        Dumper=BlockDumper,
        allow_unicode=True,
        default_flow_style=False,
        sort_keys=False,
        width=10**6,
        indent=2,
    )


def _flow_style_lists(value, key: str):
    """Wrap the lists that should render in flow style."""
    if key in FLOW_LIST_KEYS and isinstance(value, list):
        return FlowList(value)
    if key == "credits" and isinstance(value, dict):
        return {k: FlowList(v) if isinstance(v, list) else v for k, v in value.items()}
    return value


def render_entry(entry: Entry) -> str:
    """Render one record (machine + verbatim user block + meta)."""
    machine = {
        key: _flow_style_lists(entry.machine[key], key)
        for key in MACHINE_KEY_ORDER
        if key in entry.machine
    }
    for key in entry.machine:  # never drop an unknown key silently
        if key not in machine:
            machine[key] = entry.machine[key]
    body = dump_yaml(machine).rstrip("\n")
    rendered = "- " + body.replace("\n", "\n  ")
    user_raw = entry.user_raw or render_user_block(entry.user)
    meta = {key: entry.meta[key] for key in META_KEY_ORDER if key in entry.meta}
    for key in entry.meta:  # never drop an unknown key silently (same as machine)
        if key not in meta:
            meta[key] = entry.meta[key]
    meta_text = dump_yaml({"meta": meta}).rstrip("\n")
    meta_text = "\n".join("  " + line for line in meta_text.splitlines())
    return f"{rendered}\n{user_raw}{meta_text}\n"


def render_file(entries: list[Entry], *, generated_at: str | None = None) -> str:
    """Render a whole year file, header comment included."""
    stamp = generated_at or datetime.now().astimezone().isoformat(timespec="minutes")
    header = "\n".join([*HEADER_LINES, f"# generated_at: {stamp}"])
    return header + "\n" + "".join(render_entry(entry) for entry in entries)


def render_user_block(user: dict | None) -> str:
    """Render a ``user:`` block from values (used when there is no raw text).

    Records read from disk keep their raw block verbatim; this path exists for
    programmatic user edits (e.g. a future ``--hide`` flag) and for the default
    block of a brand-new record. Missing keys fall back to the documented
    defaults, and keys are written in :data:`USER_KEYS` order.
    """
    values = {key: (user or {}).get(key, DEFAULT_USER_VALUES[key]) for key in USER_KEYS}
    for key, value in (user or {}).items():  # keep unknown keys (future fields)
        if key not in values:
            values[key] = value
    text = dump_yaml({"user": values}).rstrip("\n")
    return "\n".join("  " + line for line in text.splitlines()) + "\n"


def default_user_block() -> str:
    """The block written for a record that has none yet (stable text)."""
    return render_user_block({})


def split_entries(body: str) -> list[str]:
    """Split file text into raw entry blocks."""
    positions = [match.start() for match in ENTRY_RE.finditer(body)]
    return [
        body[start : positions[i + 1] if i + 1 < len(positions) else len(body)]
        for i, start in enumerate(positions)
    ]


def parse_entry(block: str) -> Entry:
    """Parse one entry block, keeping the raw ``user:`` text verbatim."""
    try:
        parsed = yaml.safe_load(block)
    except yaml.YAMLError as exc:
        raise StoreError(f"cannot parse entry: {exc}") from exc
    if not isinstance(parsed, list) or not parsed or not isinstance(parsed[0], dict):
        raise StoreError("entry is not a single mapping list item")
    record = parsed[0]
    user_start = USER_LINE_RE.search(block)
    meta_start = META_LINE_RE.search(block)
    if not user_start or not meta_start:
        raise StoreError("entry must contain both `user:` and `meta:` blocks")
    return Entry(
        machine={k: v for k, v in record.items() if k not in ("user", "meta")},
        user=record.get("user") or {},
        user_raw=block[user_start.start() : meta_start.start()],
        meta=record.get("meta") or {},
    )


def read_entries(path: str | Path) -> list[Entry]:
    """Read a year file into entries (missing file → empty list)."""
    path = Path(path)
    if not path.is_file():
        return []
    text = path.read_text(encoding="utf-8")
    body = "\n".join(line for line in text.splitlines() if not line.startswith("#"))
    return [parse_entry(block) for block in split_entries(body.strip("\n") + "\n")]


def read_generated_at(path: str | Path) -> str | None:
    """The file-level ``# generated_at:`` stamp, if present."""
    path = Path(path)
    if not path.is_file():
        return None
    match = GENERATED_AT_RE.search(path.read_text(encoding="utf-8"))
    return match.group(1).strip() if match else None


def write_file(path: str | Path, entries: list[Entry], *, generated_at: str | None = None) -> bool:
    """Write a year file, or leave it byte-identical when nothing changed.

    Returns ``True`` when the file was written (or removed). An empty *entries*
    list removes the file: year files are cleaned up as records migrate to
    another watching year, and an empty file would otherwise linger as noise.
    """
    path = Path(path)
    if not entries:
        if path.is_file():
            path.unlink()
            return True
        return False

    existing = path.read_text(encoding="utf-8") if path.is_file() else None
    body = render_file(entries, generated_at=generated_at or _previous_stamp(existing))
    if existing == body:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(body, encoding="utf-8")
    tmp.replace(path)
    return True


def _previous_stamp(existing: str | None) -> str | None:
    """Reuse the old ``generated_at`` unless the body actually changes."""
    match = GENERATED_AT_RE.search(existing) if existing else None
    return match.group(1).strip() if match else None


def sort_entries(entries: list[Entry]) -> list[Entry]:
    """Newest watching date first, ``id`` descending as the stable tiebreaker."""
    return sorted(entries, key=lambda e: (e.effective_date(), e.id), reverse=True)


def year_file_name(prefix: str, year: str | None) -> str:
    """``movies`` + ``2009`` → ``movies-2009.yml`` (``None`` → ``movies-undated.yml``)."""
    return f"{prefix}-{year}.yml" if year else f"{prefix}-undated.yml"


def file_prefix(type_value) -> str:
    """``movie`` → ``movies``, ``tv`` → ``tv`` (year-file prefixes, design §3)."""
    return "tv" if str(type_value) == "tv" else "movies"


def read_person_ids(path: str | Path) -> dict[str, str]:
    """Read the person directory (``{}`` when absent or unreadable)."""
    path = Path(path)
    if not path.is_file():
        return {}
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError:
        return {}
    people = (data or {}).get("people") if isinstance(data, dict) else None
    if not isinstance(people, dict):
        return {}
    return {str(key): str(value) for key, value in people.items()}


def write_person_ids(path: str | Path, people: dict[str, str]) -> bool:
    """Write the person directory (id-sorted, no-op when unchanged)."""
    path = Path(path)
    if not people:
        return False
    body = dump_yaml({"people": {key: people[key] for key in sorted(people, key=_id_sort_key)}})
    text = "\n".join(PERSON_IDS_HEADER) + "\n" + body
    if path.is_file() and path.read_text(encoding="utf-8") == text:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return True


def _id_sort_key(value: str) -> int:
    """Numeric personage ids sort numerically; anything else sinks to the end."""
    return int(value) if value.isdigit() else 10**12


def merge_person_ids(existing: dict[str, str], found: dict[str, str]) -> dict[str, str]:
    """Merge ``id → name`` entries, keeping the longest (most complete) name.

    A person seen once as ``弗兰克·德拉邦特`` and later as
    ``Frank Darabont（弗兰克·德拉邦特）`` should keep the richer label.
    """
    merged = dict(existing)
    for person_id, name in found.items():
        current = merged.get(person_id)
        if current is None or len(name) > len(current):
            merged[person_id] = name
    return merged
