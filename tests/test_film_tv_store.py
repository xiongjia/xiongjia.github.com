"""Year-file storage tests: key order, verbatim user block, no-op writes."""

from __future__ import annotations

import pytest

from shared.film_tv_store import (
    Entry,
    StoreError,
    default_user_block,
    read_entries,
    read_generated_at,
    render_entry,
    render_file,
    sort_entries,
    split_entries,
    write_file,
    year_file_name,
)


def make_entry(record_id: str = "1292052", **machine) -> Entry:
    base = {
        "id": record_id,
        "title": "肖申克的救赎",
        "original_title": "The Shawshank Redemption",
        "year": 1994,
        "type": "movie",
        "category": "feature",
        "status": "collect",
        "user_rating": 5,
        "douban_score": 9.7,
        "douban_score_count": 2830000,
        "marked_at": "2009-05-01",
        "douban_comment": "希望让人自由。",
        "tags": ["经典", "剧情"],
        "genres": ["剧情", "犯罪"],
        "regions": ["美国"],
        "languages": ["英语"],
        "runtime": 142,
        "credits": {"directors": ["弗兰克·德拉邦特"], "casts": ["蒂姆·罗宾斯"], "writers": []},
        "slug": "shawshank-redemption",
        "covers": ["covers/shawshank-redemption/01.webp"],
        "douban_url": "https://movie.douban.com/subject/1292052/",
    }
    base.update(machine)
    return Entry(
        machine=base,
        user={},
        user_raw="",
        meta={
            "detail_synced_at": "2026-09-27",
            "taxonomy_version": 1,
            "fingerprint": "a1b2c3d4",
            "machine_hash": "9c1e77ab",
            "missing_since": None,
        },
    )


def test_render_entry_key_order_and_style():
    text = render_entry(make_entry())

    lines = [line.strip() for line in text.splitlines()]
    assert text.startswith('- id: "1292052"\n')
    # machine block first, then user, then meta
    assert lines.index("user:") < lines.index("meta:")
    assert 'marked_at: "2009-05-01"' in text  # ISO dates quoted to stay strings
    assert "tags: [经典, 剧情]" in text  # short attribute lists stay in flow style
    assert "genres: [剧情, 犯罪]" in text
    assert "  user:\n" in text
    assert lines[-1] == "missing_since: null"


def test_render_entry_covers_is_a_block_list():
    text = render_entry(make_entry(covers=["covers/a/01.webp", "covers/a/02.webp"]))
    assert "  covers:\n  - covers/a/01.webp\n  - covers/a/02.webp\n" in text


def test_default_user_block_is_valid_yaml_and_stable():
    import yaml

    block = default_user_block()
    parsed = yaml.safe_load("record:\n" + block)
    assert parsed == {
        "record": {
            "user": {
                "cover": "",
                "hidden_comment": False,
                "my_rating": None,
                "my_tags": [],
                "watched_at": "",
                "review": "",
                "hidden": False,
            }
        }
    }
    assert default_user_block() == block


def test_write_then_read_round_trip(tmp_path):
    path = tmp_path / "movies-2009.yml"
    assert write_file(path, [make_entry()]) is True

    entries = read_entries(path)
    assert len(entries) == 1
    assert entries[0].machine["title"] == "肖申克的救赎"
    assert entries[0].meta["fingerprint"] == "a1b2c3d4"
    assert entries[0].user["hidden"] is False  # default block parsed back
    assert read_generated_at(path) is not None


def test_rewrite_without_changes_touches_nothing(tmp_path):
    path = tmp_path / "movies-2009.yml"
    write_file(path, [make_entry()])
    before = path.read_text(encoding="utf-8")

    assert write_file(path, read_entries(path)) is False
    assert path.read_text(encoding="utf-8") == before


def test_user_block_survives_machine_updates_byte_for_byte(tmp_path):
    path = tmp_path / "movies-2009.yml"
    hand_written = (
        "  user:\n"
        "    cover: covers/a/02.webp\n"
        "    my_tags: [重看, 蓝光]\n"
        "    review: |\n"
        "      第一次看是在大学宿舍。\n"
        "    hidden_comment: true\n"
        "    hidden: false\n"
    )
    entry = make_entry()
    entry.user_raw = hand_written
    write_file(path, [entry])

    loaded = read_entries(path)[0]
    assert loaded.user_raw == hand_written
    loaded.machine["user_rating"] = 4
    loaded.meta["detail_synced_at"] = "2026-09-28"
    assert write_file(path, [loaded]) is True

    text = path.read_text(encoding="utf-8")
    assert hand_written in text
    assert "  user_rating: 4" in text
    assert read_entries(path)[0].user_raw == hand_written


def test_missing_or_empty_files(tmp_path):
    path = tmp_path / "movies-2010.yml"
    assert read_entries(path) == []
    assert read_generated_at(path) is None
    assert write_file(path, []) is False  # nothing to create

    write_file(path, [make_entry()])
    assert path.is_file()
    assert write_file(path, []) is True  # empty year file gets cleaned up
    assert not path.is_file()
    assert not list(tmp_path.glob("*.tmp"))


def test_write_is_atomic_and_leaves_no_temp_files(tmp_path):
    path = tmp_path / "tv-2020.yml"
    write_file(path, [make_entry("1", type="tv"), make_entry("2", type="tv")])
    assert sorted(p.name for p in tmp_path.iterdir()) == ["tv-2020.yml"]


def test_render_file_lists_every_entry_in_order(tmp_path):
    path = tmp_path / "movies-2020.yml"
    write_file(path, [make_entry("2"), make_entry("1")])
    assert [entry.id for entry in read_entries(path)] == ["2", "1"]


def test_sort_entries_uses_user_date_then_id():
    early = make_entry("10", marked_at="2009-01-01")
    late = make_entry("20", marked_at="2020-01-01")
    moved = make_entry("30", marked_at="2009-01-01")
    moved.user = {"watched_at": "2021-05-05"}
    same_day_a = make_entry("41", marked_at="2020-01-01")
    same_day_b = make_entry("42", marked_at="2020-01-01")

    ordered = [entry.id for entry in sort_entries([early, late, moved, same_day_a, same_day_b])]
    assert ordered == ["30", "42", "41", "20", "10"]


def test_unknown_machine_key_is_preserved():
    entry = make_entry()
    entry.machine["custom_field"] = "keep me"
    assert "custom_field: keep me" in render_entry(entry)


def test_unknown_meta_key_is_preserved():
    # `meta:` is machine-owned, but a key this version does not know about must
    # survive a rewrite instead of being dropped silently
    entry = make_entry()
    entry.meta["custom_note"] = "keep meta too"
    assert "custom_note: keep meta too" in render_entry(entry)


def test_split_and_parse_rejects_entries_without_user_block():
    with pytest.raises(StoreError):
        from shared.film_tv_store import parse_entry

        parse_entry('- id: "1"\n  title: x\n  meta:\n    fingerprint: a\n')


def test_year_file_name():
    assert year_file_name("movies", "2009") == "movies-2009.yml"
    assert year_file_name("tv", None) == "tv-undated.yml"


def test_render_file_header_mentions_generated_at():
    text = render_file([make_entry()], generated_at="2026-09-27T16:30+08:00")
    assert "# generated_at: 2026-09-27T16:30+08:00" in text
    assert text.index("# generated_at") < text.index("- id:")


def test_split_entries_counts_top_level_items():
    text = render_file([make_entry("1"), make_entry("2")])
    assert len(split_entries(text)) == 2
