"""Regenerate the film & TV archive's AI viewing summary via the local pi CLI.

Flow (mirrors `scripts/update_health_summary.py`):

1. Read the derived archive data (``assets/stats.yml`` + ``assets/people.yml`` +
   the JSON shards) and compute a compact digest — distributions, ratings, the
   影人 boards, recent watches;
2. Build a Chinese prompt embedding that digest (the summary is page content for
   a Chinese reader, so the prompt and the output are Chinese by design);
3. Call the locally installed ``pi`` CLI and read the assistant's Markdown answer;
4. Write it into the ``<!-- ai-summary:begin --> … <!-- ai-summary:end -->`` block
   of ``docs/notes/film-tv/index.md`` — **only that block** is replaced, the rest
   of the page is never touched.

If the ``pi`` call fails the existing summary stays as it was.

Usage:
    uv run poe update-film-tv-summary
    uv run poe update-film-tv-summary --dry-run            # print the prompt only
    uv run poe update-film-tv-summary --model anthropic/claude-sonnet-4
    uv run poe update-film-tv-summary --output /tmp/summary.md
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import date
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Reuse the generic pi-CLI plumbing (prompt in, cleaned Markdown out) instead of
# copying it — scripts already import each other (see bucket_upload -> bucket_sync).
from scripts.sync_film_tv import load_config  # noqa: E402
from scripts.update_health_summary import clean_ai_text, run_pi  # noqa: E402
from shared.env import load_env_files  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent
INDEX_PAGE = REPO_ROOT / "docs" / "notes" / "film-tv" / "index.md"
BEGIN_MARKER = "<!-- ai-summary:begin -->"
END_MARKER = "<!-- ai-summary:end -->"
TOP_N = 8
CATEGORY_LABELS = {
    "feature": "电影长片",
    "series": "剧集",
    "variety": "综艺",
    "anime": "动漫",
    "documentary": "纪录片",
    "other": "其他",
}


class SummaryError(RuntimeError):
    """Missing data or an unusable page (nothing is written when this is raised)."""


def _assets_dir() -> Path:
    return load_config().json_dir


def _load_yaml(path: Path) -> dict:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError):
        return {}
    return data if isinstance(data, dict) else {}


def _load_shard_records(json_dir: Path) -> list[dict]:
    records: list[dict] = []
    for path in sorted(json_dir.glob("shard-*.json")):
        try:
            shard = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        items = shard.get("items")
        if isinstance(items, list):
            records.extend(items)
    return records


def build_digest(json_dir: Path) -> dict:
    """Compact archive digest for the prompt (all numbers come from the data)."""
    stats = _load_yaml(json_dir / "stats.yml")
    people = _load_yaml(json_dir / "people.yml").get("people") or []
    records = _load_shard_records(json_dir)
    if not records and not stats:
        raise SummaryError(
            f"no derived data under {json_dir} — run `poe sync-film-tv` (it also derives)"
        )

    ratings = Counter(record["rating"] for record in records if record.get("rating"))
    genres: Counter = Counter()
    for record in records:
        genres.update(record.get("genres") or [])
    watch_dates = sorted(record["date"] for record in records if record.get("date"))
    recent = sorted(records, key=lambda record: record.get("date") or "", reverse=True)[:10]

    def by_role(role: str) -> list[dict]:
        """People with *role*, most works first (never relies on file order)."""
        matched = [person for person in people if role in (person.get("roles") or [])]
        matched.sort(
            key=lambda person: (-(person.get("works") or 0), str(person.get("name") or ""))
        )
        return matched

    directors = by_role("director")
    actors = by_role("actor")
    top_rated = [
        person for person in people if (person.get("works") or 0) >= 3 and person.get("avg_rating")
    ]
    top_rated.sort(
        key=lambda person: (-(person.get("avg_rating") or 0), -(person.get("works") or 0))
    )

    return {
        "totals": stats.get("total"),
        "by_type": stats.get("by_type") or {},
        "by_category": _by_count(stats.get("by_category") or {}, labels=CATEGORY_LABELS),
        "by_year": _by_count(stats.get("by_year") or {}),
        "by_region": _by_count(stats.get("by_region") or {}),
        "hours": stats.get("hours"),
        "average_rating": stats.get("average_rating"),
        "rated": stats.get("rated"),
        "rating_distribution": {str(star): ratings.get(star, 0) for star in range(5, 0, -1)},
        "top_genres": genres.most_common(TOP_N),
        "top_directors": [
            (person.get("name"), person.get("works")) for person in directors[:TOP_N]
        ],
        "top_actors": [(person.get("name"), person.get("works")) for person in actors[:TOP_N]],
        "top_rated_people": [
            (person.get("name"), person.get("avg_rating"), person.get("works"))
            for person in top_rated[:5]
        ],
        "span": (watch_dates[0], watch_dates[-1]) if watch_dates else None,
        "recent": [
            (record.get("date"), record.get("title"), record.get("rating")) for record in recent
        ],
    }


def _by_count(counts: dict, *, limit: int = TOP_N, labels: dict | None = None) -> list:
    """``[(label, count)]`` sorted by count desc (name as tiebreaker)."""
    labels = labels or {}
    ordered = sorted(counts.items(), key=lambda item: (-int(item[1]), str(item[0])))
    return [(labels.get(name, name), count) for name, count in ordered[:limit]]


def _pairs(rows) -> str:
    return "、".join(f"{name} {value}" for name, value in rows) or "—"


def build_prompt(digest: dict, today: date) -> str:
    """Chinese prompt embedding the digest (the output is page content)."""
    totals = digest
    lines = [
        "你是一个观影记录分析助手。下面是我从豆瓣同步到个人网站的观影归档统计，",
        "请写一段**中文**观影总结（Markdown，300–450 字），用于我自己的归档页面。",
        "",
        "## 数据",
        f"- 条目总数：{totals['totals']}（电影 {totals['by_type'].get('movie', 0)} / "
        f"剧集 {totals['by_type'].get('tv', 0)}），总时长约 {totals['hours'] or '未知'} 小时",
        "- 我的平均分："
        f"{totals['average_rating']}（已评分 {totals['rated']} / {totals['totals']}）",
        f"- 评分分布（5→1 星）：{totals['rating_distribution']}",
        f"- 观看年份分布：{_pairs(totals['by_year'])}",
        f"- 分类分布：{_pairs(totals['by_category'])}",
        f"- 地区 Top：{_pairs(totals['by_region'])}",
        f"- 类型 Top：{_pairs(totals['top_genres'])}",
        f"- 导演（作品数）：{_pairs(totals['top_directors'])}",
        f"- 演员（作品数）：{_pairs(totals['top_actors'])}",
        "- 平均分较高的影人（作品 ≥ 3）："
        + _pairs(
            [(name, f"{avg} 分 / {works} 部") for name, avg, works in totals["top_rated_people"]]
        ),
        f"- 时间跨度：{totals['span'][0]} ~ {totals['span'][1]}" if totals["span"] else "",
        "- 最近看过："
        + "、".join(
            f"{day} {title}（{rating}★）" if rating else f"{day} {title}"
            for day, title, rating in totals["recent"]
        ),
        "",
        "## 要求",
        "1. 用 3–4 个小节（例如：口味偏好、时间与习惯、影人与作者、值得回看的片子），",
        "   每节 2–3 句或一个短列表，不要写 H1/H2 大标题（页面已有标题）。",
        "2. 结论必须来自上面的数据，**不要编造**没给出的片名、数量或年份。",
        "3. 不要逐条复述数字，挑有意思的规律、变化或反差来说。",
        "4. 语气自然、像写给自己的观影片单小结，不要客套话，不要用「作为AI」之类措辞。",
        f"5. 今天是 {today.isoformat()}。",
    ]
    return "\n".join(line for line in lines if line != "")


def replace_summary_block(page: str, body: str) -> str:
    """Replace only the content between the markers (idempotent, marker-safe)."""
    if BEGIN_MARKER not in page or END_MARKER not in page:
        raise SummaryError(
            f"markers not found in {INDEX_PAGE.name} ({BEGIN_MARKER} / {END_MARKER})"
        )
    start = page.index(BEGIN_MARKER) + len(BEGIN_MARKER)
    end = page.index(END_MARKER)
    if end < start:
        # swapped/mangled markers: slicing would duplicate the text in between
        raise SummaryError(
            f"{INDEX_PAGE.name}: {END_MARKER} appears before {BEGIN_MARKER} — fix the markers"
        )
    return f"{page[:start]}\n\n{body.strip()}\n\n{page[end:]}"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Regenerate the film & TV viewing summary via the local pi CLI",
    )
    parser.add_argument("--dry-run", action="store_true", help="print the prompt and exit")
    parser.add_argument("--model", help="pi model override, e.g. anthropic/claude-sonnet-4")
    parser.add_argument("--timeout", type=int, default=300, help="pi call timeout in seconds")
    parser.add_argument("--output", help="write elsewhere (default: the index page's block)")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    load_env_files()
    json_dir = _assets_dir()
    try:
        digest = build_digest(json_dir)
    except SummaryError as exc:
        print(f"update-film-tv-summary: {exc}", file=sys.stderr)
        return 1

    prompt = build_prompt(digest, date.today())
    if args.dry_run:
        print(prompt)
        return 0

    print(f"calling pi (timeout {args.timeout}s) …", file=sys.stderr)
    try:
        text, model_label = run_pi(prompt, model=args.model, timeout=args.timeout)
    except Exception as exc:  # noqa: BLE001 — the existing summary must stay intact
        print(f"update-film-tv-summary: AI call failed ({exc}); nothing written", file=sys.stderr)
        return 1

    stamp = date.today().isoformat()
    body = f"{clean_ai_text(text)}\n\n*本地 AI（{model_label}）· {stamp} 更新*"

    if args.output:
        Path(args.output).write_text(body + "\n", encoding="utf-8")
        print(f"written to {args.output}")
        return 0

    page = INDEX_PAGE.read_text(encoding="utf-8")
    try:
        updated = replace_summary_block(page, body)
    except SummaryError as exc:
        print(f"update-film-tv-summary: {exc}", file=sys.stderr)
        return 1
    if updated != page:
        INDEX_PAGE.write_text(updated, encoding="utf-8")
    where = (
        INDEX_PAGE.relative_to(REPO_ROOT) if INDEX_PAGE.is_relative_to(REPO_ROOT) else INDEX_PAGE
    )
    print(f"summary updated ({model_label}, {len(text)} chars) → {where}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
