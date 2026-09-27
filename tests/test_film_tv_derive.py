"""Tests for the film & TV archive's derived data + page macros.

The derive step is the contract between the YAML archive and the front end, so
these tests pin determinism (a no-op run writes nothing), the privacy rules
(hidden records / hidden comments never reach the JSON), the shard self-check
fields, and the markup the macros hand to the pages.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts import film_tv_derive  # noqa: E402
from shared.film_tv_store import Entry, write_file  # noqa: E402
from shared.macros import film_tv_macros  # noqa: E402


def make_entry(record_id: str, *, date: str = "2026-09-25", type_: str = "movie", **extra) -> Entry:
    machine = {
        "id": record_id,
        "title": f"影片 {record_id}",
        "original_title": "Original Title",
        "year": 2021,
        "type": type_,
        "category": "feature",
        "status": "collect",
        "user_rating": 4,
        "douban_score": 7.5,
        "marked_at": date,
        "tags": ["Movie"],
        "genres": ["剧情"],
        "regions": ["美国"],
        "languages": ["英语"],
        "runtime": 120,
        "credits": {"directors": ["导演 A"], "casts": ["演员 B"], "writers": ["编剧 C"]},
        "slug": f"slug-{record_id}",
        "covers": [f"covers/slug-{record_id}/01.webp"],
        "douban_url": f"https://movie.douban.com/subject/{record_id}/",
    }
    machine.update(extra.pop("machine", {}))
    meta = {
        "detail_synced_at": "2026-09-27",
        "taxonomy_version": 1,
        "fingerprint": "x" * 8,
        "machine_hash": "y" * 8,
        "missing_since": None,
    }
    meta.update(extra.pop("meta", {}))
    return Entry(machine=machine, user=extra.pop("user", {}), user_raw="", meta=meta)


@pytest.fixture
def config(tmp_path, monkeypatch) -> film_tv_derive.Config:
    data_dir = tmp_path / "data"
    json_dir = tmp_path / "assets"
    data_dir.mkdir(parents=True)
    cfg = film_tv_derive.Config(
        data_dir=data_dir,
        json_dir=json_dir,
        cover_base="https://cdn.example.com/data/film-tv",
        shard_size=2,
    )
    monkeypatch.setattr(film_tv_derive, "load_env_files", lambda: None)
    monkeypatch.setattr(film_tv_derive, "load_config", lambda: cfg)
    return cfg


def run_derive() -> int:
    return film_tv_derive.run()


# --- derived JSON ------------------------------------------------------------


def test_watch_hours_counts_movies_and_tv_episodes():
    records = [
        {"type": "movie", "runtime": 120},  # 2h
        {"type": "movie", "runtime": None},  # skipped
        {"type": "tv", "runtime": 45, "episodes": 10},  # 7.5h
        {"type": "tv", "runtime": 45},  # no episode count → skipped
        {"type": "movie", "runtime": 150},  # 2.5h
    ]
    assert film_tv_derive.watch_hours(records) == 12
    assert film_tv_derive.watch_hours([]) == 0


def test_derive_writes_shards_index_stats_and_people(config):
    write_file(
        config.data_dir / "movies-2026.yml", [make_entry("1"), make_entry("2", date="2026-09-20")]
    )
    write_file(
        config.data_dir / "tv-2026.yml",
        [make_entry("3", date="2026-08-01", type_="tv")],
    )

    assert run_derive() == 0

    index = json.loads((config.json_dir / "index.json").read_text(encoding="utf-8"))
    assert index["shard_size"] == 2
    assert index["totals"] == {
        "records": 3,
        "movies": 2,
        "tv": 1,
        "rated": 3,
        "pending": 0,
    }
    assert index["months"]["2026-09"] == {
        "shard": "shard-0001.json",
        "offset": 0,
        "count": 2,
        "by_type": {"movie": 2},
    }
    assert index["months"]["2026-08"]["by_type"] == {"tv": 1}

    first = json.loads((config.json_dir / "shard-0001.json").read_text(encoding="utf-8"))
    second = json.loads((config.json_dir / "shard-0002.json").read_text(encoding="utf-8"))
    assert first["count"] == 2 and first["first_date"] == "2026-09-25"
    assert first["last_date"] == "2026-09-20"
    assert second["count"] == 1
    assert [item["id"] for item in first["items"]] == ["1", "2"]

    stats = (config.json_dir / "stats.yml").read_text(encoding="utf-8")
    assert "total: 3" in stats
    assert "people: 3" in stats  # one director, actor and writer
    people = (config.json_dir / "people.yml").read_text(encoding="utf-8")
    assert "导演 A" in people and "演员 B" in people


def test_person_aliases_unify_the_same_person_across_records():
    """A person annotated in one entry must read the same in every entry."""
    first = make_entry(
        "1",
        machine={
            "credits": {
                "directors": ["Frank Darabont（弗兰克·德拉邦特）"],
                "casts": ["Tim Robbins（蒂姆·罗宾斯）"],
                "writers": [],
            }
        },
    )
    second = make_entry(
        "2",
        machine={
            "credits": {
                "directors": ["弗兰克·德拉邦特"],  # this entry had no celebrities block
                "casts": ["蒂姆·罗宾斯", "摩根·弗里曼"],
                "writers": [],
            }
        },
    )

    aliases = film_tv_derive.person_aliases([first, second])

    assert aliases == {
        "弗兰克·德拉邦特": "Frank Darabont（弗兰克·德拉邦特）",
        "蒂姆·罗宾斯": "Tim Robbins（蒂姆·罗宾斯）",
    }


def test_derive_applies_person_aliases_to_shards_and_people(config):
    write_file(
        config.data_dir / "movies-2026.yml",
        [
            make_entry(
                "1",
                machine={
                    "credits": {
                        "directors": ["Frank Darabont（弗兰克·德拉邦特）"],
                        "casts": [],
                        "writers": [],
                    }
                },
            ),
            make_entry(
                "2",
                machine={
                    "credits": {
                        "directors": ["弗兰克·德拉邦特"],
                        "casts": [],
                        "writers": [],
                    }
                },
            ),
        ],
    )
    run_derive()

    shard = json.loads((config.json_dir / "shard-0001.json").read_text(encoding="utf-8"))
    directors = {item["id"]: item["directors"] for item in shard["items"]}
    assert directors["1"] == ["Frank Darabont（弗兰克·德拉邦特）"]
    assert directors["2"] == ["Frank Darabont（弗兰克·德拉邦特）"]  # alias applied

    people = yaml.safe_load((config.json_dir / "people.yml").read_text(encoding="utf-8"))
    names = [person["name"] for person in people["people"]]
    assert names == ["Frank Darabont（弗兰克·德拉邦特）"]  # one person, not two


def test_derive_is_deterministic_and_skips_unchanged_files(config, capsys):
    write_file(config.data_dir / "movies-2026.yml", [make_entry("1")])
    run_derive()
    before = {path.name: path.read_text(encoding="utf-8") for path in config.json_dir.iterdir()}

    run_derive()

    after = {path.name: path.read_text(encoding="utf-8") for path in config.json_dir.iterdir()}
    assert before == after
    assert "0 file(s) to write" in capsys.readouterr().out


def test_derive_excludes_hidden_records_and_hidden_comments(config):
    write_file(
        config.data_dir / "movies-2026.yml",
        [
            make_entry("1", user={"hidden": True}),
            make_entry("2", machine={"douban_comment": "秘密短评"}, user={"hidden_comment": True}),
            make_entry("3", machine={"douban_comment": "公开短评"}, user={"review": "我的影评"}),
        ],
    )
    run_derive()

    shard = json.loads((config.json_dir / "shard-0001.json").read_text(encoding="utf-8"))
    ids = [item["id"] for item in shard["items"]]
    assert ids == ["3", "2"]  # record 1 is gone entirely
    by_id = {item["id"]: item for item in shard["items"]}
    assert "comment" not in by_id["2"]  # hidden_comment keeps it out of the JSON
    assert by_id["3"]["comment"] == "公开短评"
    assert by_id["3"]["review"] == "我的影评"
    index = json.loads((config.json_dir / "index.json").read_text(encoding="utf-8"))
    assert index["totals"]["records"] == 2


def test_derive_uses_user_overrides_for_rating_date_and_cover(config):
    write_file(
        config.data_dir / "movies-2026.yml",
        [
            make_entry(
                "1",
                machine={"user_rating": 3, "marked_at": "2026-01-01"},
                user={
                    "my_rating": 5,
                    "watched_at": "2011-03-03",
                    "cover": "covers/slug-1/user-01.webp",
                },
            )
        ],
    )
    run_derive()

    record = json.loads((config.json_dir / "shard-0001.json").read_text(encoding="utf-8"))["items"][
        0
    ]
    assert record["rating"] == 5
    assert record["date"] == "2011-03-03"
    assert record["cover"] == "covers/slug-1/user-01.webp"
    assert record["cover_url"] == "https://cdn.example.com/data/film-tv/covers/slug-1/user-01.webp"


def test_derive_removes_stale_shards(config):
    write_file(config.data_dir / "movies-2026.yml", [make_entry(str(i)) for i in range(1, 7)])
    run_derive()
    assert (config.json_dir / "shard-0003.json").is_file()

    write_file(config.data_dir / "movies-2026.yml", [make_entry("1")])
    run_derive()

    assert not (config.json_dir / "shard-0003.json").exists()
    assert sorted(p.name for p in config.json_dir.glob("shard-*.json")) == ["shard-0001.json"]


def test_derive_marks_pending_records(config):
    write_file(
        config.data_dir / "movies-2026.yml",
        [make_entry("1"), make_entry("2", meta={"detail_synced_at": None})],
    )
    run_derive()

    shard = json.loads((config.json_dir / "shard-0001.json").read_text(encoding="utf-8"))
    pending = {item["id"]: item["pending"] for item in shard["items"]}
    assert pending == {"1": False, "2": True}
    index = json.loads((config.json_dir / "index.json").read_text(encoding="utf-8"))
    assert index["totals"]["pending"] == 1


def test_stats_payload_on_empty_input():
    stats = film_tv_derive.stats_payload([])
    assert stats["total"] == 0
    assert stats["average_rating"] is None


def test_derive_without_records_is_an_error(config, capsys):
    assert run_derive() == 1
    assert "no records yet" in capsys.readouterr().out


# --- macros ------------------------------------------------------------------


class FakePage:
    def __init__(self, url: str):
        self.url = url


class FakeEnv:
    """Minimal stand-in for mkdocs-macros' env (only what the module uses)."""

    def __init__(self, url: str = "notes/film-tv/movies/"):
        self.page = FakePage(url)
        self.macros: dict = {}

    def macro(self, fn):
        self.macros[fn.__name__] = fn
        return fn


def load_macros(url: str = "notes/film-tv/movies/") -> FakeEnv:
    env = FakeEnv(url)
    film_tv_macros.define_env(env)
    return env


def test_combined_loader_registers_both_sections():
    """`shared/macros/loader.py` is the module_name the macros plugin loads."""
    from shared.macros import loader

    env = FakeEnv("notes/health/running/")
    loader.define_env(env)

    # the health module's macros and the film-tv module's macros both land here
    assert "film_tv_page" in env.macros
    assert {"weight_chart", "running_all", "retire_grid"} <= set(env.macros)


def test_combined_loader_reports_a_missing_section_module():
    from shared.macros import loader

    with pytest.raises(FileNotFoundError, match="section macro module not found"):
        loader._load_from_file("does/not/exist.py")


def test_macro_registers_the_expected_macros():
    env = load_macros()
    assert set(env.macros) == {
        "film_tv_page",
        "film_tv_stats",
        "film_tv_chart",
        "film_tv_people",
        "film_tv_note",
    }


def test_page_macro_markup_and_assets_base():
    env = load_macros("notes/film-tv/movies/")
    html = env.macros["film_tv_page"]("movie")

    assert 'class="film-tv" data-kind="movie"' in html
    assert 'data-json-base="../assets/"' in html
    # local mirror base for the cover fallback (page-relative)
    assert 'data-cover-local-base="../../../assets/bucket/film-tv/"' in html
    for marker in (
        "film-tv__banner",
        "film-tv__calendar",
        "film-tv__filters",
        "film-tv__chips",
        "film-tv__list",
        "film-tv__pager",
        "film-tv-dialog",
    ):
        assert marker in html

    index_html = load_macros("notes/film-tv/").macros["film_tv_page"]("")
    assert 'data-json-base="assets/"' in index_html
    assert 'data-cover-local-base="../../assets/bucket/film-tv/"' in index_html
    assert 'data-kind=""' in index_html


def test_page_macro_always_includes_the_dialog():
    html = load_macros().macros["film_tv_page"]("tv")
    assert "film-tv-dialog" in html
    assert "data-show-calendar" not in html  # the calendar is never hidden by markup


def test_stats_macro_reports_missing_stats(tmp_path, monkeypatch):
    monkeypatch.setattr(film_tv_macros, "_REPO_ROOT", str(tmp_path))
    html = load_macros().macros["film_tv_stats"]()
    assert "暂无统计数据" in html


def test_stats_macro_renders_cards_and_bars(tmp_path, monkeypatch):
    assets = tmp_path / "docs" / "notes" / "film-tv" / "assets"
    assets.mkdir(parents=True)
    (assets / "stats.yml").write_text(
        "total: 42\nrated: 40\naverage_rating: 3.75\npeople: 17\npending: 2\n"
        "by_category:\n  feature: 30\n  anime: 12\n"
        "by_year:\n  '2026': 20\n  '2025': 22\n"
        "by_region:\n  中国: 30\n  美国: 12\n"
        "by_type:\n  movie: 30\n  tv: 12\n"
        "hours: 128\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(film_tv_macros, "_REPO_ROOT", str(tmp_path))
    env = load_macros("notes/film-tv/")

    html = env.macros["film_tv_stats"]()
    assert html.count('class="film-tv-stat__card"') == 4
    assert '<span class="film-tv-stat__number">42</span>' in html
    assert "3.75" in html
    assert "电影" in html and "动漫" in html  # category labels are translated
    assert 'class="film-tv-stat__bar"' in html

    note = env.macros["film_tv_note"]()
    assert "2" in note and "待补详情" in note


def test_people_macro_renders_boards_and_links(tmp_path, monkeypatch):
    assets = tmp_path / "docs" / "notes" / "film-tv" / "assets"
    assets.mkdir(parents=True)
    (assets / "people.yml").write_text(
        "people:\n"
        "- name: 王家卫\n  roles: [director]\n  works: 5\n  avg_rating: 4.4\n"
        '  first_year: 2009\n  last_year: 2020\n  douban_id: "27480954"\n'
        "- name: 张曼玉\n  roles: [actor]\n  works: 4\n  avg_rating: 4.5\n"
        "  first_year: 2010\n  last_year: 2020\n"
        "- name: 小编剧\n  roles: [writer]\n  works: 3\n  avg_rating: 3.0\n"
        "  first_year: 2015\n  last_year: 2016\n"
        "- name: 只演过两部的\n  roles: [actor]\n  works: 2\n  avg_rating: 5.0\n"
        "  first_year: 2021\n  last_year: 2021\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(film_tv_macros, "_REPO_ROOT", str(tmp_path))

    html = load_macros("notes/film-tv/people/").macros["film_tv_people"]()

    assert html.count('class="film-tv-people__board"') == 3
    assert "导演 · 作品最多 Top 50" in html
    assert "演员 · 作品最多 Top 50" in html
    assert "编剧 · 作品最多 Top 50" in html
    assert "平均分最高" not in html  # the average-rating board was dropped
    # names link back into the archive (one level up from people/) filtered by that
    # person; the query value is percent-encoded so names with &/" stay valid
    assert 'href="../?person=%E7%8E%8B%E5%AE%B6%E5%8D%AB"' in html
    # ...and the row carries the personage id so info can be filled in later
    assert 'href="https://www.douban.com/personage/27480954/"' in html
    assert "张曼玉" in html and "4.5" in html
    # every board is a works ranking, so the two-work actor shows up in 演员
    assert "只演过两部的" in html


def test_people_payload_carries_douban_ids(config):
    # two works, so the person clears the people.yml min_works threshold
    credits = {
        "directors": ["Frank Darabont（弗兰克·德拉邦特）"],
        "casts": [],
        "writers": [],
    }
    write_file(
        config.data_dir / "movies-2026.yml",
        [
            make_entry("1", machine={"credits": credits}),
            make_entry("2", machine={"credits": credits}),
        ],
    )
    (config.data_dir / "person-ids.yml").write_text(
        'people:\n  "27253735": Frank Darabont（弗兰克·德拉邦特）\n', encoding="utf-8"
    )

    run_derive()

    people = yaml.safe_load((config.json_dir / "people.yml").read_text(encoding="utf-8"))["people"]
    row = next(person for person in people if "Darabont" in person["name"])
    assert row["douban_id"] == "27253735"
    assert row["douban_url"] == "https://www.douban.com/personage/27253735/"


def test_person_id_map_resolves_short_aliases():
    directory = {"27253735": "Frank Darabont（弗兰克·德拉邦特）"}
    aliases = {"弗兰克·德拉邦特": "Frank Darabont（弗兰克·德拉邦特）"}

    mapping = film_tv_derive.person_id_map(aliases, directory)

    assert mapping["Frank Darabont（弗兰克·德拉邦特）"] == "27253735"
    assert mapping["弗兰克·德拉邦特"] == "27253735"


def test_person_directory_is_not_read_as_a_year_file(tmp_path, config):
    (config.data_dir / "person-ids.yml").write_text('people:\n  "1": 某人\n', encoding="utf-8")
    write_file(config.data_dir / "movies-2026.yml", [make_entry("1")])

    assert len(film_tv_derive.load_records(config)) == 1  # the directory is skipped


def test_people_macro_without_data(tmp_path, monkeypatch):
    monkeypatch.setattr(film_tv_macros, "_REPO_ROOT", str(tmp_path))
    html = load_macros().macros["film_tv_people"]()
    assert "暂无影人统计" in html


def test_chart_macro_emits_the_client_side_container(tmp_path, monkeypatch):
    """The chart is rendered by film-tv-chart.js (it has range controls), so the
    macro only emits the container + the asset base it should fetch."""
    assets = tmp_path / "docs" / "notes" / "film-tv" / "assets"
    assets.mkdir(parents=True)
    (assets / "index.json").write_text(
        json.dumps(
            {
                "totals": {"records": 3, "movies": 2, "tv": 1},
                "months": {
                    "2026-08": {"count": 2, "by_type": {"movie": 2, "tv": 0}},
                    "2026-09": {"count": 1, "by_type": {"movie": 0, "tv": 1}},
                },
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(film_tv_macros, "_REPO_ROOT", str(tmp_path))
    env = load_macros("notes/film-tv/")

    html = env.macros["film_tv_chart"]()

    assert '<details class="film-tv-chart" data-kind=""' in html
    assert 'data-json-base="assets/"' in html
    assert "<summary>📈 观影量（影视）" in html
    # the closed hint is the *archive* total (all months, all types), while the
    # chart's own summary line reports the window it drew — the two must be labelled
    # differently or they look like a contradiction
    assert "归档共 3 条" in html
    assert "归档共 2 条" in env.macros["film_tv_chart"]("movie")
    assert "归档共 1 条" in env.macros["film_tv_chart"]("tv")
    for marker in ("film-tv-chart__controls", "film-tv-chart__summary", "film-tv-chart__canvas"):
        assert marker in html
    # the same macro scopes the chart to one kind, and subpages get a relative base
    movie = env.macros["film_tv_chart"](kind="movie")
    assert 'data-kind="movie"' in movie and "观影量（电影）" in movie
    subpage = load_macros("notes/film-tv/movies/").macros["film_tv_chart"](kind="movie")
    assert 'data-json-base="../assets/"' in subpage


def test_note_macro_reports_a_complete_archive(tmp_path, monkeypatch):
    assets = tmp_path / "docs" / "notes" / "film-tv" / "assets"
    assets.mkdir(parents=True)
    (assets / "stats.yml").write_text("total: 3\npending: 0\n", encoding="utf-8")
    monkeypatch.setattr(film_tv_macros, "_REPO_ROOT", str(tmp_path))
    assert "全部条目都有详情" in load_macros().macros["film_tv_note"]()


def test_note_macro_does_not_claim_completion_without_stats(tmp_path, monkeypatch):
    # an empty archive (no derived stats at all) must not read as "all complete"
    monkeypatch.setattr(film_tv_macros, "_REPO_ROOT", str(tmp_path))
    note = load_macros().macros["film_tv_note"]()
    assert "还没有数据" in note
    assert "全部条目都有详情" not in note


def test_people_rows_escape_and_quote_messy_names(tmp_path, monkeypatch):
    assets = tmp_path / "docs" / "notes" / "film-tv" / "assets"
    assets.mkdir(parents=True)
    (assets / "people.yml").write_text(
        "people:\n"
        '- name: "A & B \\"quoted\\" <b>"\n'
        "  roles: [actor]\n  works: 3\n  avg_rating: 4.0\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(film_tv_macros, "_REPO_ROOT", str(tmp_path))
    html = load_macros().macros["film_tv_people"]()
    assert "&amp; B" in html and "&lt;b&gt;" in html  # escaped for the markup
    assert "?person=A%20%26%20B" in html  # and quoted for the query string
