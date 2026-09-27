"""Douban HTML parser tests (film & TV archive).

The fixtures in ``tests/fixtures/film_tv/`` are **trimmed copies of real Douban
pages** (regions sliced verbatim by ``.cache/film-tv/spike/build_fixtures.py``) so
these tests fail when the real markup changes in a way the parsers care about.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from shared.film_tv_parse import (
    parse_interest,
    parse_list_page,
    parse_photos_page,
    parse_subject_page,
    photo_url,
    title_part,
    upgrade_photo_size,
)

FIXTURES = Path(__file__).parent / "fixtures" / "film_tv"


def fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def test_list_page_total_and_item_count():
    page = parse_list_page(fixture("collect-list.html"))

    assert page.total == 4292
    assert len(page.items) == 9


def test_list_page_includes_last_item_and_keeps_field_variants():
    """`item last`, unrated and deleted rows must all survive parsing."""
    page = parse_list_page(fixture("collect-list.html"))
    by_id = {item.id: item for item in page.items}

    # the final row of a page carries `class="item last"` — a plain
    # `class="item"` selector silently drops it (spike finding)
    assert "1951286" in by_id
    assert by_id["1951286"].user_rating == 3

    # unrated: no rating span, but the watching date is still there
    unrated = by_id["26996734"]
    assert unrated.user_rating is None
    assert unrated.marked_at == "2019-12-01"

    # deleted subjects come with no date/rating and a flag
    deleted = by_id["34447531"]
    assert deleted.deleted is True
    assert deleted.marked_at is None
    assert deleted.title == "未知电影"
    assert by_id["10549231"].deleted is True
    assert by_id["10549231"].title == "宇宙战舰大和号2199"

    # the 标签 line is optional and space separated
    assert by_id["36909418"].tags == ["Movie"]
    # intro is the collapsed one-liner with cast/region/runtime
    assert "蒂姆·罗宾斯" in by_id["36909418"].intro or "薛景求" in by_id["36909418"].intro


def test_list_page_parses_do_items_with_comments():
    page = parse_list_page(fixture("do-list.html"))
    by_id = {item.id: item for item in page.items}

    assert page.total == 17
    assert by_id["26584183"].comment == "Winter finally came, part 1"
    assert by_id["26584183"].user_rating is None
    assert by_id["26584183"].marked_at == "2019-04-16"
    assert by_id["25919897"].comment == "就是喜欢，不解释"
    # collect lists never expose comments — that is why the fingerprint cannot
    # rely on them (see shared/film_tv_model.fingerprint)
    assert parse_list_page(fixture("collect-list.html")).items[0].comment == ""


def test_title_part_strips_original_title():
    assert title_part("凶降喜讯 / 굿뉴스") == "凶降喜讯"
    assert title_part("肖申克的救赎") == "肖申克的救赎"


def test_credits_get_the_original_name_from_the_celebrities_block():
    """Douban's `#info` rows are Chinese-only; `#celebrities` carries `中文 原文`."""
    subject = parse_subject_page(fixture("subject-movie.html"), subject_id="1292052")

    assert subject.directors == ["Frank Darabont（弗兰克·德拉邦特）"]
    assert subject.casts[0] == "Tim Robbins（蒂姆·罗宾斯）"
    assert subject.writers == ["Frank Darabont（弗兰克·德拉邦特）"]
    assert len(subject.casts) == 25  # still every credited actor


def test_cjk_names_keep_the_chinese_form_by_default():
    # 杨磊 Lei Yang: the Latin part is pinyin, so `hint` keeps the Chinese name
    subject = parse_subject_page(fixture("subject-tv.html"), subject_id="26647087")
    assert subject.directors == ["杨磊"]
    assert subject.casts[:2] == ["张鲁一", "于和伟"]

    latin = parse_subject_page(
        fixture("subject-tv.html"), subject_id="26647087", person_style="latin"
    )
    assert latin.directors == ["Lei Yang（杨磊）"]

    zh = parse_subject_page(fixture("subject-movie.html"), subject_id="1292052", person_style="zh")
    assert zh.directors == ["弗兰克·德拉邦特"]


@pytest.mark.parametrize(
    ("title", "style", "expected"),
    [
        ("弗兰克·德拉邦特 Frank Darabont", "hint", "Frank Darabont（弗兰克·德拉邦特）"),
        ("弗兰克·德拉邦特 Frank Darabont", "latin", "Frank Darabont（弗兰克·德拉邦特）"),
        ("弗兰克·德拉邦特 Frank Darabont", "zh", "弗兰克·德拉邦特"),
        ("杨磊 Lei Yang", "hint", "杨磊"),
        ("杨磊 Lei Yang", "latin", "Lei Yang（杨磊）"),
        ("金惠秀 Hye-soo Kim", "hint", "金惠秀"),
        ("Alex Regnery", "hint", "Alex Regnery"),
        ("无原文", "hint", "无原文"),
        ("", "hint", ""),
    ],
)
def test_person_label_styles(title, style, expected):
    from shared.film_tv_parse import person_label

    assert person_label(title, style) == expected


def test_parse_celebrities_and_split():
    from shared.film_tv_parse import parse_celebrities, split_person_title

    celebrities = parse_celebrities(fixture("subject-movie.html"))
    assert celebrities["27253735"] == "弗兰克·德拉邦特 Frank Darabont"
    assert celebrities["27260288"] == "蒂姆·罗宾斯 Tim Robbins"
    assert split_person_title(celebrities["27253735"]) == ("弗兰克·德拉邦特", "Frank Darabont")
    assert split_person_title("杨磊") == ("", "")


def test_subject_movie_fields():
    subject = parse_subject_page(fixture("subject-movie.html"), subject_id="1292052")

    assert subject.title == "肖申克的救赎"
    assert subject.original_title == "The Shawshank Redemption"
    assert subject.year == 1994  # 2026 re-release must not win over the original
    assert subject.genres == ["剧情", "犯罪"]
    assert subject.regions_raw == ["美国"]
    assert subject.languages == ["英语"]
    assert subject.runtime == 142
    assert subject.episodes is None
    assert subject.douban_score == 9.7
    assert subject.douban_score_count == 3345023
    assert subject.directors == ["Frank Darabont（弗兰克·德拉邦特）"]
    assert subject.writers == ["Frank Darabont（弗兰克·德拉邦特）"]
    assert len(subject.casts) == 25  # truncation to 10 happens in the model layer
    assert subject.cover_url.endswith("/view/photo/s_ratio_poster/public/p2934829882.jpg")
    assert "片长" in subject.info_keys and "IMDb" in subject.info_keys


def test_subject_movie_interest_block():
    subject = parse_subject_page(fixture("subject-movie.html"), subject_id="1292052")
    interest = subject.interest

    assert interest.status == "collect"
    assert interest.status_word == "这部电影"
    assert interest.marked_at == "2008-06-01"
    assert interest.user_rating == 5
    assert interest.tags == ["Movie", "ENU", "Drama"]
    assert interest.comment == "有些鸟是关不住地,他们的羽翼太过辉煌..."


def test_subject_tv_fields_and_interest_without_comment():
    subject = parse_subject_page(fixture("subject-tv.html"), subject_id="26647087")

    assert subject.title == "三体"
    assert subject.original_title is None  # mainpic alt equals the title
    assert subject.year == 2023
    assert subject.episodes == 30
    assert subject.first_aired == "2023-01-15"
    assert subject.runtime == 45  # 单集片长, used when 片长 is absent
    assert subject.aliases == ["三体(剧版)", "Three-Body"]
    assert subject.interest.status == "collect"
    assert subject.interest.status_word == "这部电视剧"
    assert subject.interest.user_rating == 4
    assert subject.interest.tags == []
    assert subject.interest.comment == ""


def test_subject_foreign_tv_original_title():
    subject = parse_subject_page(fixture("subject-korean-tv.html"), subject_id="37501131")

    assert subject.title == "现在不是出轨的问题"
    assert subject.original_title == "지금 불륜이 문제가 아닙니다"
    assert subject.regions_raw == ["韩国"]
    assert subject.interest.marked_at == "2026-09-23"


def test_parse_interest_without_block():
    assert parse_interest("<html><body>nothing</body></html>").status is None


def test_photos_page_and_size_upgrade():
    photos = parse_photos_page(fixture("photos.html"))

    assert len(photos) == 30
    assert photos[0].photo_id == "p480747492.jpg"
    assert photos[0].url == "https://img3.doubanio.com/view/photo/m/public/p480747492.jpg"
    assert photos[0].name.startswith("正式海报")
    assert upgrade_photo_size(photos[0].url) == (
        "https://img3.doubanio.com/view/photo/l/public/p480747492.jpg"
    )
    assert photo_url("p480747492.jpg") == (
        "https://img3.doubanio.com/view/photo/l/public/p480747492.jpg"
    )


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("142分钟", 142), ("60分钟(E1-E2)", 60), ("", None), ("109分钟", 109)],
)
def test_minutes_parsing(raw, expected):
    from shared.film_tv_parse import minutes

    assert minutes(raw) == expected
