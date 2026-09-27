"""Record model for the Film & TV archive: taxonomy, slugs, merge rules.

This module owns the *data* half of the archive (``shared/film_tv_parse.py`` owns
Douban's markup, ``shared/film_tv_store.py`` owns the YAML files): region /
category normalization against ``taxonomy.yml``, slug generation, the incremental
fingerprint and machine-field hash, year assignment, and the merge of fresh
Douban data into an existing record while never touching the human ``user:``
block.
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from shared.film_tv_store import META_KEY_ORDER, Entry  # YAML layer (no import cycle)

#: categories a record may carry (``other`` is the documented fallback)
CATEGORIES = ("feature", "series", "variety", "anime", "documentary", "other")

#: how many cast entries to keep (Douban lists up to 68 names; leads come first)
CAST_LIMIT = 10

#: cover keys stored in the yml are archive-root relative, keyed by the Douban
#: subject id: ``covers/<douban_id>/NN.webp`` — the id is the merge key, so it is
#: unique by construction (no slug collisions, no degenerate slugs) while the
#: human-facing ``slug`` stays available for share links.
COVER_KEY_RE = re.compile(r"^covers/(?P<subject_id>\d+)/(?P<name>\d{2}|user-\d{2})\.webp$")

#: types Douban's list tabs expose
TYPES = ("movie", "tv")

#: fields only the detail page can produce — a list-only update must never clear
#: them (a skeleton refresh keeps the metadata fetched earlier)
DETAIL_DERIVED_KEYS = (
    "original_title",
    "year",
    "category",
    "douban_score",
    "douban_score_count",
    "douban_comment",
    "genres",
    "regions",
    "languages",
    "runtime",
    "credits",
    "episodes",
)

SLUG_MAX_LENGTH = 60
MIN_SLUG_LENGTH = 3
HASH_LENGTH = 8

_ASCII_SLUG_RE = re.compile(r"[^a-z0-9]+")


@dataclass
class Taxonomy:
    """Region aliases + ordered category rules, loaded from ``taxonomy.yml``."""

    rules_version: int
    #: raw Douban region → canonical short names (an alias may expand to several)
    regions: dict[str, tuple[str, ...]] = field(default_factory=dict)
    categories: list[dict] = field(default_factory=list)
    path: Path | None = None

    @classmethod
    def load(cls, path: str | Path) -> Taxonomy:
        """Read and validate ``taxonomy.yml`` (raises on unusable input)."""
        path = Path(path)
        try:
            raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        except OSError as exc:
            raise ValueError(f"cannot read taxonomy {path}: {exc}") from exc
        if not isinstance(raw, dict):
            raise ValueError(f"taxonomy {path} must be a mapping")
        version = raw.get("rules_version")
        if not isinstance(version, int) or version < 1:
            raise ValueError(f"taxonomy {path}: rules_version must be a positive integer")
        regions = raw.get("regions") or {}
        if not isinstance(regions, dict):
            raise ValueError(f"taxonomy {path}: regions must be a mapping")
        normalized_regions: dict[str, tuple[str, ...]] = {}
        for key, value in regions.items():
            names = [value] if isinstance(value, str) else value
            if not isinstance(names, list) or not all(isinstance(n, str) and n for n in names):
                raise ValueError(
                    f"taxonomy {path}: region alias {key!r} must map to a name or a list of names"
                )
            normalized_regions[str(key)] = tuple(names)
        rules = raw.get("categories") or []
        if not isinstance(rules, list) or not rules:
            raise ValueError(f"taxonomy {path}: categories must be a non-empty list")
        for rule in rules:
            if not isinstance(rule, dict) or rule.get("category") not in CATEGORIES:
                raise ValueError(f"taxonomy {path}: bad category rule {rule!r}")
            if "genres" in rule and not isinstance(rule["genres"], list):
                raise ValueError(f"taxonomy {path}: rule genres must be a list: {rule!r}")
            if rule.get("type") not in (None, *TYPES):
                raise ValueError(f"taxonomy {path}: rule type must be one of {TYPES}: {rule!r}")
        if rules[-1].get("genres") or rules[-1].get("type"):
            raise ValueError(
                f"taxonomy {path}: last category rule must be the unconditional fallback"
            )
        return cls(
            rules_version=version,
            regions=normalized_regions,
            categories=rules,
            path=path,
        )

    def normalize_region(self, raw: str) -> list[str]:
        """Douban region string → canonical short names (unknown values kept).

        A compound alias expands (``港台`` → 香港 + 台湾), so the result is always a
        list — one entry for the ordinary 1:1 aliases.
        """
        value = raw.strip()
        if not value:
            return []
        return list(self.regions.get(value, (value,)))

    def normalize_regions(self, raw_values: list[str]) -> list[str]:
        """Normalize + de-duplicate a region list, preserving input order."""
        seen: list[str] = []
        for raw in raw_values:
            for value in self.normalize_region(raw):
                if value not in seen:
                    seen.append(value)
        return seen

    def classify_category(self, genres: list[str], type_: str | None) -> str:
        """First matching rule's category (see ``taxonomy.yml`` for the order)."""
        genre_set = {g.strip() for g in genres if g and g.strip()}
        for rule in self.categories:
            if rule.get("type") and type_ != rule["type"]:
                continue
            wanted = rule.get("genres")
            if wanted and not genre_set.intersection(wanted):
                continue
            return str(rule["category"])
        return "other"


def slug_candidates(subject) -> list[str]:
    """Readable slug sources, best first: original title, then ASCII aliases.

    A Chinese-only title yields nothing ASCII, so 又名 aliases are consulted
    (e.g. 三体 → ``three-body``); if all fail the caller falls back to the id.
    """
    names: list[str] = []
    if subject.original_title:
        names.append(subject.original_title)
    names.append(subject.title or "")
    names.extend(subject.aliases or [])
    return names


def slugify(value: str) -> str:
    """ASCII slug from a title (``The Shawshank Redemption`` → ``the-shawshank-redemption``).

    Non-ASCII characters are dropped rather than transliterated: an empty result
    asks the caller to fall back to the id instead of inventing a mangled slug.
    """
    # drop alias region suffixes: 刺激1995(台) → 刺激1995
    value = re.sub(r"[（(][^）)]*[）)]", " ", value or "")
    # NFKD + ascii fold keeps latin accents (Amélie → amelie)
    folded = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    slug = _ASCII_SLUG_RE.sub("-", folded.lower()).strip("-")
    return slug[:SLUG_MAX_LENGTH].strip("-")


def slug_is_usable(slug: str) -> bool:
    """Reject degenerate slugs (``2`` from ``年会不能停！2``, ``1-52`` from an alias).

    A slug becomes a cover directory name and a permanent share anchor, so a
    too-short, digit-only or letter-less value is worse than the
    ``douban-<id>`` fallback.
    """
    return len(slug) >= MIN_SLUG_LENGTH and any(ch.isalpha() for ch in slug)


def make_slug(subject, *, subject_id: str, taken: set[str], year: int | None = None) -> str:
    """Allocate a unique, sticky slug for a subject.

    Candidates: original title → title → 又名 aliases → ``douban-<id>``; on
    collision append ``-<year>``, then ``-2``/``-3``… up to ``-9``, then
    ``-<hash6>`` (the same order the design doc specifies). *taken* is mutated
    with the result.
    """
    base = next(
        (slug for slug in map(slugify, slug_candidates(subject)) if slug_is_usable(slug)), ""
    )
    if not base:
        base = f"douban-{subject_id}"
    candidates = [base]
    if year:
        candidates.append(f"{base}-{year}")
    candidates.extend(f"{base}-{index}" for index in range(2, 10))
    digest = hashlib.sha1(subject_id.encode()).hexdigest()[:6]
    candidates.append(f"{base}-{digest}")
    for candidate in candidates:
        if candidate not in taken:
            taken.add(candidate)
            return candidate
    # the id hash itself collided (astronomically unlikely): extend it instead of
    # looping forever, so the slug stays unique and the return is total
    index = 2
    while f"{base}-{digest}-{index}" in taken:
        index += 1
    candidate = f"{base}-{digest}-{index}"
    taken.add(candidate)
    return candidate


def fingerprint(
    *,
    status: str,
    type_: str | None,
    title: str,
    user_rating: int | None,
    marked_at: str | None,
    tags: list[str],
    comment: str = "",
) -> str:
    """Hash of the fields a collection *list* page exposes.

    Only list-visible fields may participate: the sync stops paging as soon as a
    record's fingerprint matches, so including detail-page-only data would turn
    every detail refill into a phantom change. 看过的评论/标签 therefore do not
    participate (see design §2).
    """
    payload = "|".join(
        [
            status or "",
            type_ or "",
            title or "",
            "" if user_rating is None else str(user_rating),
            marked_at or "",
            " ".join(tags or []),
            comment or "",
        ]
    )
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()[:HASH_LENGTH]


def machine_hash(machine: dict) -> str:
    """Hash of the machine-owned fields (everything except ``user:`` / ``meta:``).

    Detects hand edits of machine fields — including the sticky ``slug`` /
    ``covers`` — so the next sync can warn before overwriting them.
    """
    payload = json.dumps(machine, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()[:HASH_LENGTH]


def cover_key(subject_id: str, index: int = 1) -> str:
    """Archive-root relative key of a Douban cover candidate (``01.webp``…)."""
    return f"covers/{subject_id}/{index:02d}.webp"


def validate_cover_key(key: str, *, subject_id: str | None = None) -> str | None:
    """Return an error message when *key* is not a legal archive-relative key.

    The ``covers`` / ``user.cover`` fields must never carry a full local path
    (the ``assets/bucket/film-tv/`` prefix is added by consumers) and must not be
    able to point outside the archive root.
    """
    if not key:
        return "empty key"
    if key.startswith("/") or ".." in key.split("/"):
        return f"not an archive-relative key: {key!r}"
    match = COVER_KEY_RE.match(key)
    if not match:
        return f"key must look like covers/<douban_id>/NN.webp: {key!r}"
    if subject_id and match.group("subject_id") != subject_id:
        return f"key belongs to another subject: {key!r} (expected {subject_id!r})"
    return None


def assign_year(marked_at: str | None, watched_at: str | None) -> str | None:
    """Watching year used for the storage files (``user.watched_at`` wins).

    Returns ``None`` when neither date is usable — such records live in
    ``movies-undated.yml`` / ``tv-undated.yml``.
    """
    for value in (watched_at, marked_at):
        match = re.match(r"(\d{4})-\d{2}-\d{2}", (value or "").strip())
        if match:
            return match.group(1)
    return None


def build_machine(
    *,
    list_item,
    subject=None,
    type_: str | None = None,
    status: str = "collect",
    taxonomy: Taxonomy,
) -> dict:
    """Assemble the Douban-derived machine fields of one record.

    List fields are always available; ``subject`` (the parsed detail page) fills
    the rest and is ``None`` for records still pending their first detail fetch
    (or whose subject was deleted on Douban). ``slug`` / ``covers`` are *not*
    included — they are sticky and assigned by :func:`merge_record`.
    """
    genres = list(getattr(subject, "genres", []) or [])
    regions_raw = list(getattr(subject, "regions_raw", []) or [])
    casts = list(getattr(subject, "casts", []) or [])[:CAST_LIMIT]
    interest = getattr(subject, "interest", None)
    if interest and interest.marked_at:
        marked_at = interest.marked_at
    else:
        marked_at = list_item.marked_at
    user_rating = list_item.user_rating
    if user_rating is None and interest is not None:
        user_rating = interest.user_rating

    machine = {
        "id": str(list_item.id),
        "title": (getattr(subject, "title", None) or getattr(list_item, "title", "") or "").strip(),
        "original_title": getattr(subject, "original_title", None),
        "year": getattr(subject, "year", None),
        "type": type_,
        "category": taxonomy.classify_category(genres, type_) if subject else None,
        "status": status,
        "user_rating": user_rating,
        "douban_score": getattr(subject, "douban_score", None),
        "douban_score_count": getattr(subject, "douban_score_count", None),
        "marked_at": marked_at,
        "douban_comment": (interest.comment if interest and interest.comment else None),
        "tags": list(interest.tags) if interest is not None else list(list_item.tags),
        "genres": genres,
        "regions": taxonomy.normalize_regions(regions_raw),
        "languages": list(getattr(subject, "languages", []) or []),
        "runtime": getattr(subject, "runtime", None),
        "credits": {
            "directors": list(getattr(subject, "directors", []) or []),
            "casts": casts,
            "writers": list(getattr(subject, "writers", []) or []),
        },
        "episodes": getattr(subject, "episodes", None),
        "douban_url": f"https://movie.douban.com/subject/{list_item.id}/",
    }
    if type_ != "tv":  # 集数 is a tv-only field (see design §2)
        machine.pop("episodes", None)
    return machine


@dataclass
class TitleOnly:
    """Slug source for a record whose detail page has not been fetched yet."""

    title: str = ""
    original_title: str | None = None
    aliases: list[str] = field(default_factory=list)


def merge_record(
    existing: Entry | None,
    *,
    fields: dict,
    subject=None,
    subject_id: str,
    taxonomy: Taxonomy,
    taken_slugs: set[str],
    fingerprint_value: str,
    covers_added: list[str] | None = None,
    detail_fetched: bool = False,
    today: str,
    missing_since: str | None = None,
) -> Entry:
    """Merge fresh Douban fields into a record, preserving human + sticky parts.

    - ``slug`` is **sticky**: taken from the existing record, else allocated once
      the detail page is known (an ASCII title or 又名 alias is required — a
      list-only record carries ``slug: ""`` until its first detail sync);
    - ``covers`` only ever grows (a re-run must not drop references);
    - ``user`` (block text included) is carried over untouched;
    - ``meta`` keeps ``detail_synced_at`` from earlier syncs, refreshes
      ``fingerprint`` / ``machine_hash`` / ``taxonomy_version``, and records
      ``missing_since`` when the subject vanished on Douban.
    """
    machine = dict(fields)
    if existing is not None and subject is None:
        # list-only update (skeleton / detail still pending): keep whatever the
        # detail page told us earlier instead of overwriting it with nulls
        for key in DETAIL_DERIVED_KEYS:
            if key in existing.machine:
                machine[key] = existing.machine[key]
        if not machine.get("tags"):
            machine["tags"] = list(existing.machine.get("tags") or [])
    previous_slug = str(existing.machine.get("slug") or "") if existing else ""
    if previous_slug:
        slug = previous_slug
        taken_slugs.add(slug)
    elif detail_fetched and subject is not None:
        slug = make_slug(
            subject, subject_id=subject_id, taken=taken_slugs, year=machine.get("year")
        )
    else:
        slug = ""
    machine["slug"] = slug

    covers = list(existing.machine.get("covers") or []) if existing else []
    for cover in covers_added or []:
        if cover and cover not in covers:
            covers.append(cover)
    machine["covers"] = covers

    meta = dict(existing.meta) if existing else {}
    meta["taxonomy_version"] = taxonomy.rules_version
    meta["fingerprint"] = fingerprint_value
    if detail_fetched:
        meta["detail_synced_at"] = today
    meta.setdefault("detail_synced_at", None)
    meta["missing_since"] = missing_since or meta.get("missing_since") or None
    meta["machine_hash"] = machine_hash(machine)
    for key in META_KEY_ORDER:
        meta.setdefault(key, None)

    return Entry(
        machine=machine,
        user=dict(existing.user) if existing else {},
        user_raw=existing.user_raw if existing else "",
        meta=meta,
    )


def record_fingerprint(machine: dict, list_item) -> str:
    """Fingerprint for a list item + the machine fields it produced.

    Tags/comment fall back to the row's own values, so the walk and the merge
    compute the same hash for the same row (a mismatch would make every record
    look changed on the next run).
    """
    tags = machine.get("tags") or list(getattr(list_item, "tags", None) or [])
    return fingerprint(
        status=machine.get("status") or "",
        type_=machine.get("type"),
        title=machine.get("title") or getattr(list_item, "title", "") or "",
        user_rating=machine.get("user_rating"),
        marked_at=machine.get("marked_at"),
        tags=tags,
        comment=getattr(list_item, "comment", "") or "",
    )
