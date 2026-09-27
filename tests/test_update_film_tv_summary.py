"""Tests for `poe update-film-tv-summary` (prompt + block replacement).

The `pi` CLI is never called: `run_pi` is monkeypatched, so these tests pin the
digest, the prompt, and the "only the marked block is rewritten" contract.
"""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts import update_film_tv_summary as summary  # noqa: E402

STATS = {
    "total": 3,
    "by_type": {"movie": 2, "tv": 1},
    "by_category": {"feature": 2, "anime": 1},
    "by_year": {"2025": 1, "2026": 2},
    "by_region": {"冰岛": 1, "中国": 2, "美国": 1},  # unsorted on purpose
    "hours": 10,
    "average_rating": 4.0,
    "rated": 3,
}
PEOPLE = {
    "people": [
        {"name": "王牌导演", "roles": ["director"], "works": 3, "avg_rating": 4.5},
        {"name": "小演员", "roles": ["actor"], "works": 1, "avg_rating": 5.0},
        {"name": "常驻演员", "roles": ["actor"], "works": 2, "avg_rating": 3.5},
    ]
}
RECORDS = [
    {"id": "1", "title": "第一部", "date": "2026-09-01", "rating": 5, "genres": ["剧情"]},
    {"id": "2", "title": "第二部", "date": "2026-08-01", "rating": 4, "genres": ["剧情", "喜剧"]},
    {"id": "3", "title": "第三部", "date": "2025-05-01", "rating": None, "genres": ["动画"]},
]


@pytest.fixture
def assets(tmp_path) -> Path:
    (tmp_path / "stats.yml").write_text(
        yaml.safe_dump(STATS, allow_unicode=True, sort_keys=True), encoding="utf-8"
    )
    (tmp_path / "people.yml").write_text(
        yaml.safe_dump(PEOPLE, allow_unicode=True, sort_keys=True), encoding="utf-8"
    )
    (tmp_path / "shard-0001.json").write_text(
        json.dumps({"count": len(RECORDS), "items": RECORDS}, ensure_ascii=False), encoding="utf-8"
    )
    return tmp_path


def test_digest_sorts_distributions_by_count(assets):
    digest = summary.build_digest(assets)

    assert digest["by_region"][0] == ("中国", 2)  # not alphabetical (冰岛 first)
    assert digest["by_category"][0] == ("电影长片", 2)  # labels are translated
    assert digest["by_year"] == [("2026", 2), ("2025", 1)]
    assert digest["rating_distribution"] == {"5": 1, "4": 1, "3": 0, "2": 0, "1": 0}
    assert digest["top_genres"][0] == ("剧情", 2)
    assert digest["span"] == ("2025-05-01", "2026-09-01")
    assert [row[1] for row in digest["recent"]] == ["第一部", "第二部", "第三部"]


def test_digest_people_boards(assets):
    digest = summary.build_digest(assets)

    assert digest["top_directors"] == [("王牌导演", 3)]
    assert digest["top_actors"] == [("常驻演员", 2), ("小演员", 1)]
    # the average-rating board needs >= 3 works, so the one-work actor is out
    assert digest["top_rated_people"] == [("王牌导演", 4.5, 3)]


def test_digest_without_data_raises(tmp_path):
    with pytest.raises(summary.SummaryError, match="no derived data"):
        summary.build_digest(tmp_path)


def test_prompt_embeds_the_digest_and_forbids_invention(assets):
    prompt = summary.build_prompt(summary.build_digest(assets), date(2026, 9, 27))

    assert "条目总数：3（电影 2 / 剧集 1）" in prompt
    assert "总时长约 10 小时" in prompt
    assert "地区 Top：中国 2、冰岛 1、美国 1" in prompt
    assert "不要编造" in prompt
    assert "今天是 2026-09-27" in prompt


@pytest.mark.parametrize("body", ["新总结", "多行\n总结\n\n- 一\n- 二"])
def test_replace_summary_block_only_touches_the_block(body):
    page = f"# 标题\n\n{BEGIN}旧内容\n\n更多旧内容\n{END}\n\n## 下一节\n"

    updated = summary.replace_summary_block(page, body)

    assert "旧内容" not in updated
    assert updated.startswith("# 标题\n\n")
    assert updated.endswith("## 下一节\n")
    assert body in updated
    # idempotent: replacing again with the same text changes nothing further
    assert summary.replace_summary_block(updated, body) == updated


BEGIN = "<!-- ai-summary:begin -->"
END = "<!-- ai-summary:end -->"


def test_replace_summary_block_requires_markers():
    with pytest.raises(summary.SummaryError, match="markers not found"):
        summary.replace_summary_block("# 没有标记\n", "内容")


def test_replace_summary_block_rejects_swapped_markers():
    # a mangled page must not be "patched": slicing from end to start would
    # duplicate the text between the markers
    page = f"# 标题\n\n{END}\n正文\n{BEGIN}\n"
    with pytest.raises(summary.SummaryError, match="appears before"):
        summary.replace_summary_block(page, "内容")


def test_dry_run_prints_the_prompt_without_calling_pi(assets, monkeypatch, capsys):
    monkeypatch.setattr(summary, "_assets_dir", lambda: assets)
    monkeypatch.setattr(summary, "load_env_files", lambda: None)
    monkeypatch.setattr(summary, "run_pi", lambda *a, **k: pytest.fail("dry-run must not call pi"))

    assert summary.main(["--dry-run"]) == 0

    assert "观影记录分析助手" in capsys.readouterr().out


def test_main_writes_the_block_into_the_page(assets, tmp_path, monkeypatch, capsys):
    page = tmp_path / "index.md"
    page.write_text(f"# 🎬 Film & TV\n\n{BEGIN}\n\n占位\n\n{END}\n", encoding="utf-8")
    monkeypatch.setattr(summary, "_assets_dir", lambda: assets)
    monkeypatch.setattr(summary, "INDEX_PAGE", page)
    monkeypatch.setattr(summary, "load_env_files", lambda: None)
    monkeypatch.setattr(
        summary,
        "run_pi",
        lambda prompt, model=None, timeout=300: ("## 口味\n\n爱看剧情片。", "Test Model"),
    )

    assert summary.main([]) == 0

    written = page.read_text(encoding="utf-8")
    assert "爱看剧情片。" in written
    assert "Test Model" in written and "更新*" in written
    assert "占位" not in written
    assert written.startswith("# 🎬 Film & TV")
    assert "summary updated" in capsys.readouterr().out


def test_main_leaves_the_page_alone_when_pi_fails(assets, tmp_path, monkeypatch, capsys):
    page = tmp_path / "index.md"
    original = f"# 🎬\n\n{BEGIN}\n\n占位\n\n{END}\n"
    page.write_text(original, encoding="utf-8")
    monkeypatch.setattr(summary, "_assets_dir", lambda: assets)
    monkeypatch.setattr(summary, "INDEX_PAGE", page)
    monkeypatch.setattr(summary, "load_env_files", lambda: None)

    def boom(*_args, **_kwargs):
        raise RuntimeError("pi exploded")

    monkeypatch.setattr(summary, "run_pi", boom)

    assert summary.main([]) == 1

    assert page.read_text(encoding="utf-8") == original  # untouched
    assert "nothing written" in capsys.readouterr().err


def test_main_reports_missing_data(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(summary, "_assets_dir", lambda: tmp_path)
    monkeypatch.setattr(summary, "load_env_files", lambda: None)

    assert summary.main([]) == 1
    assert "no derived data" in capsys.readouterr().err
