"""Film & TV record-model tests: taxonomy, slugs, fingerprint, merge, paths."""

from __future__ import annotations

from pathlib import Path

import pytest

from shared.film_tv_model import (
    CAST_LIMIT,
    Taxonomy,
    TitleOnly,
    assign_year,
    build_machine,
    cover_key,
    fingerprint,
    machine_hash,
    make_slug,
    merge_record,
    slugify,
    validate_cover_key,
)
from shared.film_tv_parse import parse_list_page, parse_subject_page
from shared.film_tv_store import Entry

FIXTURES = Path(__file__).parent / "fixtures" / "film_tv"
TAXONOMY = Path(__file__).resolve().parents[1] / "docs" / "notes" / "film-tv" / "data"
TAXONOMY = TAXONOMY / "taxonomy.yml"


def fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


@pytest.fixture
def taxonomy() -> Taxonomy:
    return Taxonomy.load(TAXONOMY)


def list_item(**overrides):
    item = parse_list_page(fixture("collect-list.html")).items[0]
    for key, value in overrides.items():
        setattr(item, key, value)
    return item


def subject(name: str = "subject-movie.html"):
    return parse_subject_page(fixture(name), subject_id="1292052")


# --- taxonomy ----------------------------------------------------------------


def test_taxonomy_loads_rules_and_regions(taxonomy):
    assert taxonomy.rules_version >= 1  # bumped when a rule change ships
    assert taxonomy.normalize_region("中国大陆") == ["中国"]
    assert taxonomy.normalize_region("法国") == ["法国"]  # unknown values pass through
    assert taxonomy.normalize_region("") == []
    # a compound alias expands so a co-production counts for every region
    assert taxonomy.normalize_region("港台") == ["香港", "台湾"]


def test_taxonomy_normalize_regions_dedupes_and_keeps_order(taxonomy):
    assert taxonomy.normalize_regions(["中国大陆", "美国", "中国"]) == ["中国", "美国"]
    assert taxonomy.normalize_regions(["港台", "香港"]) == ["香港", "台湾"]


@pytest.mark.parametrize(
    ("genres", "type_", "expected"),
    [
        (["纪录片"], "movie", "documentary"),
        (["真人秀", "音乐"], "movie", "variety"),
        (["剧情", "动画"], "tv", "anime"),  # 动画剧集 counts as anime (confirmed)
        (["动画"], "movie", "anime"),
        (["剧情"], "tv", "series"),
        (["喜剧"], "movie", "feature"),
        ([], None, "other"),
        ([], "movie", "feature"),
    ],
)
def test_category_classification(taxonomy, genres, type_, expected):
    assert taxonomy.classify_category(genres, type_) == expected


def test_taxonomy_rejects_bad_rules(tmp_path):
    bad = tmp_path / "taxonomy.yml"
    bad.write_text("rules_version: 1\ncategories:\n  - category: nope\n", encoding="utf-8")
    with pytest.raises(ValueError):
        Taxonomy.load(bad)

    no_fallback = tmp_path / "t2.yml"
    no_fallback.write_text(
        "rules_version: 1\ncategories:\n  - category: feature\n    type: movie\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError):
        Taxonomy.load(no_fallback)

    bad_version = tmp_path / "t3.yml"
    bad_version.write_text("rules_version: 0\ncategories:\n  - category: other\n", encoding="utf-8")
    with pytest.raises(ValueError):
        Taxonomy.load(bad_version)


def test_taxonomy_shipped_file_is_valid(taxonomy):
    assert taxonomy.path == TAXONOMY
    assert taxonomy.categories[-1] == {"category": "other"}


# --- slugs -------------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("The Shawshank Redemption", "the-shawshank-redemption"),
        ("Amélie", "amelie"),
        ("刺激1995(台)", "1995"),
        ("三体", ""),
        ("", ""),
    ],
)
def test_slugify(raw, expected):
    assert slugify(raw) == expected


def test_make_slug_prefers_original_title_then_aliases_then_id():
    original = TitleOnly(title="肖申克的救赎", original_title="The Shawshank Redemption")
    assert make_slug(original, subject_id="1", taken=set()) == "the-shawshank-redemption"

    chinese_only = TitleOnly(title="三体", aliases=["三体(剧版)", "Three-Body"])
    assert make_slug(chinese_only, subject_id="2", taken=set()) == "three-body"

    no_ascii = TitleOnly(title="无英文名")
    assert make_slug(no_ascii, subject_id="42", taken=set()) == "douban-42"


def test_make_slug_collision_escalation():
    taken = {"dune"}
    assert (
        make_slug(TitleOnly(title="Dune"), subject_id="1", taken=taken, year="2021") == "dune-2021"
    )
    taken.add("dune-2021")
    assert make_slug(TitleOnly(title="Dune"), subject_id="1", taken=taken) == "dune-2"
    taken.add("dune-2")
    taken.add("dune-3")
    third = make_slug(TitleOnly(title="Dune"), subject_id="1", taken=taken)
    assert third.startswith("dune-") and third not in {"dune", "dune-2", "dune-3"}


def test_make_slug_falls_back_to_the_id_hash_after_the_numeric_phase():
    # the numeric escalation is bounded (-2 … -9), so the documented id-hash
    # suffix is actually reachable instead of being dead code
    taken = {"dune", *(f"dune-{index}" for index in range(2, 10))}
    slug = make_slug(TitleOnly(title="Dune"), subject_id="1292052", taken=taken)
    assert slug == "dune-b4ea07"
    assert slug in taken
    # even a crowded hash namespace still returns a unique slug
    crowded = {
        "dune",
        *(f"dune-{index}" for index in range(2, 10)),
        slug,
        *(f"dune-b4ea07-{index}" for index in range(2, 5)),
    }
    nxt = make_slug(TitleOnly(title="Dune"), subject_id="1292052", taken=crowded)
    assert nxt == "dune-b4ea07-5"


# --- fingerprint / machine hash ---------------------------------------------


def test_fingerprint_tracks_list_visible_fields_only():
    base = dict(
        status="collect",
        type_="movie",
        title="Dune",
        user_rating=4,
        marked_at="2021-10-01",
        tags=["Scifi"],
        comment="",
    )
    same = dict(base)
    assert fingerprint(**base) == fingerprint(**same)
    assert fingerprint(**base) != fingerprint(**{**base, "user_rating": 5})
    assert fingerprint(**base) != fingerprint(**{**base, "status": "do"})
    assert fingerprint(**base) != fingerprint(**{**base, "title": "Dune 2"})


def test_machine_hash_covers_every_machine_field():
    machine = {"id": "1", "title": "Dune", "covers": ["covers/dune/01.webp"], "slug": "dune"}
    baseline = machine_hash(machine)
    assert (
        machine_hash(
            {"id": "1", "title": "Dune", "covers": ["covers/dune/01.webp"], "slug": "dune"}
        )
        == baseline
    )
    assert machine_hash({**machine, "slug": "dune-2"}) != baseline
    assert machine_hash({**machine, "covers": []}) != baseline


def test_assign_year_prefers_user_value():
    assert assign_year("2009-05-01", None) == "2009"
    assert assign_year("2009-05-01", "2011-01-02") == "2011"
    assert assign_year(None, None) is None
    assert assign_year("", "") is None


# --- cover keys (path safety) ------------------------------------------------


def test_cover_keys_are_archive_relative_and_id_keyed():
    # covers are keyed by the Douban id (the merge key), not by a derived slug
    assert cover_key("1292052", 1) == "covers/1292052/01.webp"
    assert validate_cover_key("covers/1292052/01.webp", subject_id="1292052") is None
    assert validate_cover_key("covers/1292052/user-01.webp", subject_id="1292052") is None


@pytest.mark.parametrize(
    "key",
    [
        "",
        "/covers/1292052/01.webp",
        "assets/bucket/film-tv/covers/1292052/01.webp",
        "covers/../1292052/01.webp",
        "covers/1292052/../../etc/passwd",
        "covers/1292052/1.webp",
        "covers/1292052/01.jpg",
        "covers/1292052/01.webp/../../x",
        "covers/dune/01.webp",  # slug-based keys are no longer legal
    ],
)
def test_validate_cover_key_rejects_unsafe_values(key):
    assert validate_cover_key(key, subject_id="1292052") is not None


def test_validate_cover_key_rejects_another_subject():
    assert validate_cover_key("covers/999/01.webp", subject_id="1292052") is not None


# --- build_machine / merge_record -------------------------------------------


def test_build_machine_uses_detail_and_truncates_casts(taxonomy):
    item = list_item()
    machine = build_machine(
        list_item=item, subject=subject(), type_="movie", status="collect", taxonomy=taxonomy
    )

    assert machine["id"] == item.id
    assert machine["title"] == "肖申克的救赎"
    assert machine["original_title"] == "The Shawshank Redemption"
    assert machine["type"] == "movie"
    assert machine["category"] == "feature"
    assert machine["status"] == "collect"
    assert len(machine["credits"]["casts"]) == CAST_LIMIT
    assert machine["regions"] == ["美国"]
    assert "episodes" not in machine  # tv-only field
    assert "slug" not in machine and "covers" not in machine  # sticky, added by merge


def test_build_machine_without_detail_keeps_list_fields(taxonomy):
    item = list_item(id="999", title="尚未抓详情", user_rating=3, marked_at="2020-02-02")
    machine = build_machine(
        list_item=item, subject=None, type_="tv", status="collect", taxonomy=taxonomy
    )

    assert machine["title"] == "尚未抓详情"
    assert machine["category"] is None
    assert machine["marked_at"] == "2020-02-02"
    assert machine["episodes"] is None
    assert machine["year"] is None


def test_build_machine_trusts_the_subject_page_for_my_tags(taxonomy):
    # the subject page is the authority for my tags: when the user cleared them
    # there, an empty list must win over the (stale) row — otherwise
    # `--refresh-details`/backfill rows, which rebuild ListItem from the stored
    # record, would resurrect deleted tags on every run
    subj = subject()
    subj.interest.tags = []
    machine = build_machine(
        list_item=list_item(tags=["Scifi"]),
        subject=subj,
        type_="movie",
        status="collect",
        taxonomy=taxonomy,
    )
    assert machine["tags"] == []

    # without a detail page the row's tags are all we have
    skeleton = build_machine(
        list_item=list_item(tags=["Scifi"]),
        subject=None,
        type_="movie",
        status="collect",
        taxonomy=taxonomy,
    )
    assert skeleton["tags"] == ["Scifi"]


def _fields(taxonomy, item=None, subj=None, type_="movie", status="collect"):
    return build_machine(
        list_item=item or list_item(),
        subject=subj if subj is not None else subject(),
        type_=type_,
        status=status,
        taxonomy=taxonomy,
    )


def test_merge_record_allocates_slug_and_sets_meta(taxonomy):
    subj = subject()
    entry = merge_record(
        None,
        fields=_fields(taxonomy, subj=subj),
        subject=subj,
        subject_id="1292052",
        taxonomy=taxonomy,
        taken_slugs=set(),
        fingerprint_value="a1b2c3d4",
        detail_fetched=True,
        today="2026-09-27",
    )

    assert isinstance(entry, Entry)
    assert entry.machine["slug"] == "the-shawshank-redemption"
    assert entry.machine["covers"] == []
    assert entry.meta == {
        "detail_synced_at": "2026-09-27",
        "taxonomy_version": taxonomy.rules_version,
        "fingerprint": "a1b2c3d4",
        "machine_hash": entry.meta["machine_hash"],
        "missing_since": None,
        "missing_reason": None,
    }
    assert entry.user_raw == ""  # the store substitutes the default block


def test_merge_record_is_sticky_and_keeps_human_block(taxonomy):
    subj = subject()
    existing = Entry(
        machine={
            "id": "1292052",
            "slug": "sticky-slug",
            "covers": ["covers/sticky-slug/01.webp"],
            "title": "旧标题",
        },
        user={"watched_at": "2011-01-02", "my_rating": 3},
        user_raw="  user:\n    my_rating: 3\n",
        meta={"detail_synced_at": "2020-01-01", "fingerprint": "old"},
    )
    entry = merge_record(
        existing,
        fields=_fields(taxonomy, subj=subj),
        subject=subj,
        subject_id="1292052",
        taxonomy=taxonomy,
        taken_slugs=set(),
        fingerprint_value="new",
        covers_added=["covers/sticky-slug/02.webp"],
        detail_fetched=True,
        today="2026-09-27",
    )

    assert entry.machine["slug"] == "sticky-slug"  # never re-derived
    assert entry.machine["covers"] == [
        "covers/sticky-slug/01.webp",
        "covers/sticky-slug/02.webp",
    ]
    assert entry.user == {"watched_at": "2011-01-02", "my_rating": 3}
    assert entry.user_raw == "  user:\n    my_rating: 3\n"  # byte-identical
    assert entry.meta["detail_synced_at"] == "2026-09-27"
    assert entry.meta["fingerprint"] == "new"


def test_merge_record_never_drops_covers_on_rerun(taxonomy):
    subj = subject()
    existing = Entry(machine={"id": "1", "slug": "s", "covers": ["covers/s/01.webp"]})
    entry = merge_record(
        existing,
        fields=_fields(taxonomy, subj=subj),
        subject=subj,
        subject_id="1",
        taxonomy=taxonomy,
        taken_slugs=set(),
        fingerprint_value="x",
        detail_fetched=False,
        today="2026-09-27",
    )
    assert entry.machine["covers"] == ["covers/s/01.webp"]
    assert entry.meta["detail_synced_at"] is None  # no detail fetched this run


def test_merge_record_marks_missing_subjects(taxonomy):
    item = list_item(id="10549231", title="宇宙战舰大和号2199", deleted=True)
    fields = build_machine(
        list_item=item, subject=None, type_="movie", status="collect", taxonomy=taxonomy
    )
    entry = merge_record(
        None,
        fields=fields,
        subject=None,
        subject_id=item.id,
        taxonomy=taxonomy,
        taken_slugs=set(),
        fingerprint_value="deadbeef",
        detail_fetched=False,
        today="2026-09-27",
        missing_since="2026-09-27",
    )
    assert entry.meta["missing_since"] == "2026-09-27"
    assert entry.machine["slug"] == ""  # no detail → no slug yet


def test_merge_record_clears_missing_when_the_detail_fetch_succeeds(taxonomy):
    """A live subject page disproves "gone": the mark must not outlive it."""
    subj = subject()
    existing = Entry(
        machine={"id": "1292052", "slug": "s", "covers": [], "title": "旧标题"},
        user={},
        user_raw="",
        meta={
            "detail_synced_at": "2020-01-01",
            "missing_since": "2026-01-01",
            "missing_reason": "gone",
        },
    )

    entry = merge_record(
        existing,
        fields=_fields(taxonomy, subj=subj),
        subject=subj,
        subject_id="1292052",
        taxonomy=taxonomy,
        taken_slugs=set(),
        fingerprint_value="new",
        detail_fetched=True,
        today="2026-09-28",
    )

    assert entry.meta["missing_since"] is None
    assert entry.meta["missing_reason"] is None


def test_merge_record_keeps_and_stamps_the_missing_reason(taxonomy):
    """A list-only merge records *why* the record is away, and never clears it."""
    subj = subject()
    existing = Entry(
        machine={"id": "1292052", "slug": "s", "covers": [], "title": "旧标题"},
        user={},
        user_raw="",
        meta={"detail_synced_at": "2020-01-01", "missing_since": "2026-01-01"},
    )

    stale = merge_record(
        existing,
        fields=_fields(taxonomy, subj=subj),
        subject=None,
        subject_id="1292052",
        taxonomy=taxonomy,
        taken_slugs=set(),
        fingerprint_value="new2",
        detail_fetched=False,
        today="2026-09-28",
    )
    assert stale.meta["missing_since"] == "2026-01-01"  # sticky

    pruned = merge_record(
        existing,
        fields=_fields(taxonomy, subj=subj),
        subject=None,
        subject_id="1292052",
        taxonomy=taxonomy,
        taken_slugs=set(),
        fingerprint_value="new3",
        detail_fetched=False,
        today="2026-09-28",
        missing_since="2026-09-28",
        missing_reason="pruned",
    )
    assert pruned.meta["missing_reason"] == "pruned"
