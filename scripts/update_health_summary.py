"""Regenerate the health status summary on the health index page.

The health index page (`docs/notes/health/index.md`) embeds the Markdown
fragment `docs/notes/health/_summary.md` under the「💡 健康状态总结与建议」
heading. The fragment is intentionally NOT generated during `mkdocs build` —
it is refreshed on demand by this script:

1. Read the three data files (`retire.yml`, `weight.yml`, `running.yml`)
2. Compute deterministic statistics from them (reusing the macros' math)
3. Build a prompt that embeds those statistics
4. Call the locally installed `pi` CLI (`pi -p --mode json`) to have an AI
   write a concise Chinese health summary + suggestions
5. Write the AI text into a `???+ note` card (model + timestamp in the
   title), overwriting the previous summary at `_summary.md`

If the `pi` call fails, the existing summary is left untouched.

Usage:
    uv run poe update-health-summary              # regenerate + write
    uv run poe update-health-summary --dry-run    # print prompt, no AI call
    uv run poe update-health-summary --model anthropic/claude-sonnet-4
    uv run poe update-health-summary --output /tmp/summary.md  # preview elsewhere
"""

import argparse
import json
import re
import shutil
import subprocess
import sys
import textwrap
from datetime import date, datetime, timedelta
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "docs" / "notes" / "health" / "data"
DEFAULT_OUTPUT = REPO_ROOT / "docs" / "notes" / "health" / "_summary.md"

# The health macros own the retirement/weight/running math. Reuse their pure
# helpers (same import trick as tests/conftest.py) so this script can never
# drift from what the pages render.
_MACROS_DIR = REPO_ROOT / "docs" / "notes" / "health" / "macros"
if str(_MACROS_DIR) not in sys.path:
    sys.path.insert(0, str(_MACROS_DIR))

import retire_macros  # noqa: E402
import running_macros  # noqa: E402
import weight_macros  # noqa: E402

_GENDER_LABELS = {"male": "男性", "female_cadre": "女干部", "female_worker": "女工人"}
_BMI_LABELS = {"underweight": "偏瘦", "normal": "正常", "overweight": "超重", "obese": "肥胖"}
_BRAND_LABELS = {
    "deepseek": "DeepSeek",
    "anthropic": "Anthropic",
    "openai": "OpenAI",
    "google": "Google",
    "groq": "Groq",
    "qwen": "Qwen",
    "zhipu": "智谱",
    "ollama": "Ollama",
    "mistral": "Mistral",
    "claude": "Claude",
}

# Only the most recent N weekly averages are embedded in the prompt, so the
# weight section does not grow unboundedly as data accumulates over time.
_WEEKLY_RECORD_LIMIT = 12


# ---------------------------------------------------------------------------
#  Data loading + statistics
# ---------------------------------------------------------------------------


def load_yaml(path: Path) -> dict:
    """Load a YAML data file; missing/empty files become {}."""
    if not path.is_file():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def compute_retire_stats(data: dict, today: date) -> dict:
    """Retirement countdown summary (empty dict when data is unusable)."""
    birth_str = data.get("birth_date")
    gender = data.get("gender")
    if not birth_str or not gender:
        return {}
    try:
        raw_birth = datetime.strptime(str(birth_str), "%Y-%m-%d").date()
        birth = raw_birth.replace(day=1)
    except (ValueError, TypeError):
        return {}
    ret = retire_macros._compute_retirement(
        birth,
        gender,
        data.get("work_start_age", 22),
        data.get("expected_retire_age"),
        today=today,
    )
    if not ret:
        return {}
    expected = ret.get("expected_retire")
    # an expected plan whose date already passed is stale — fall back to the
    # legal retirement target so the countdown never reads "0 days left"
    target = expected if (expected is not None and expected > today) else ret["final_retire"]
    total_months = ret.get("expected_total_months") if target == expected else ret["total_months"]
    months_lived = ret["months_lived"]
    remaining = max(0, total_months - months_lived)
    age = max(
        0,
        today.year - raw_birth.year - ((today.month, today.day) < (raw_birth.month, raw_birth.day)),
    )
    return {
        "gender": _GENDER_LABELS.get(gender, gender),
        "age": age,
        "expected_age": ret.get("expected_retire_age"),
        "target_date": target,
        "is_retired": ret["is_retired"],
        "total_months": total_months,
        "months_lived": months_lived,
        "remaining_years": remaining // 12,
        "remaining_months": remaining % 12,
        "days_remaining": max(0, (target - today).days),
        "progress_pct": min(100.0, months_lived / total_months * 100),
    }


def _latest_weight_reading(data: dict, start: datetime) -> tuple[float | None, date | None]:
    """Latest non-null weight plus its calendar date (None when absent).

    `start` is the anchor week (see `weight_macros._parse_start`), parsed once
    by the caller and shared with the weekly-series computation.
    """
    for i, week in reversed(list(enumerate(data.get("weeks", [])))):
        for j, value in reversed(list(enumerate(week.get("days", [])))):
            if value is not None:
                return float(value), (start + timedelta(days=i * 7 + j)).date()
    return None, None


def compute_weight_stats(data: dict) -> dict:
    """Weight/BMI summary (empty dict when data is unusable)."""
    cm = data.get("cm")
    if not cm:
        return {}
    hm = cm / 100.0
    stats = {
        "cm": cm,
        "healthy_min": 18.5 * hm * hm,
        "healthy_max": 23.9 * hm * hm,
    }
    # parse the anchor week once — shared by the latest reading and the weekly series
    start = weight_macros._parse_start(data)
    if start is not None:
        latest, latest_date = _latest_weight_reading(data, start)
    else:
        latest, latest_date = None, None
    stats["latest"] = latest
    stats["latest_date"] = latest_date
    if latest is not None:
        bmi = weight_macros._bmi(latest, cm)
        stats["bmi"] = bmi
        stats["bmi_status"] = _BMI_LABELS.get(weight_macros._bmi_status_key(bmi), "")
    avgs = [
        (sum(v) / len(v) if (v := [float(d) for d in w.get("days", []) if d is not None]) else None)
        for w in data.get("weeks", [])
    ]
    valid_avgs = [a for a in avgs if a is not None]
    if valid_avgs:
        stats["latest_week_avg"] = valid_avgs[-1]
        if len(valid_avgs) >= 2:
            stats["delta"] = valid_avgs[-1] - valid_avgs[-2]
    # weekly averages with week-start dates, for the "体重变化记录" prompt section
    if start is not None:
        stats["weekly"] = [
            {"week_start": (start + timedelta(days=i * 7)).date().isoformat(), "avg": a}
            for i, a in enumerate(avgs)
            if a is not None
        ]
    return stats


def _run_date(activity: dict) -> date | None:
    """Local activity date (None when unparseable)."""
    dt = running_macros._activity_date(activity)
    return dt.date() if dt else None


def _run_streak(runs: list[dict]) -> int:
    """Consecutive calendar days with at least one run, ending at the newest."""
    days = sorted({d for d in (_run_date(a) for a in runs) if d})
    if not days:
        return 0
    streak = 1
    prev = days[-1]
    for d in reversed(days[:-1]):
        if (prev - d).days == 1:
            streak += 1
            prev = d
        else:
            break
    return streak


def compute_running_stats(data: dict, today: date) -> dict:
    """Running summary (empty dict when there are no activities)."""
    runs = running_macros._runs(data)
    if not runs:
        return {}
    total_km = sum(float(a.get("distance") or 0) for a in runs) / 1000.0
    total_sec = sum(running_macros._parse_moving_time(a.get("moving_time")) or 0 for a in runs)
    total_elev = sum(float(a.get("elevation_gain") or 0) for a in runs)
    hrs = [float(a.get("average_heartrate")) for a in runs if a.get("average_heartrate")]

    def _filter(cutoff: date) -> list[dict]:
        return [a for a in runs if (d := _run_date(a)) and d >= cutoff]

    recent30 = _filter(today - timedelta(days=30))
    week7 = _filter(today - timedelta(days=7))
    latest = _run_date(runs[0])
    return {
        "runs": len(runs),
        "total_km": total_km,
        "total_time_h": total_sec / 3600,
        "elevation": total_elev,
        "recent30_runs": len(recent30),
        "recent30_km": sum(float(a.get("distance") or 0) for a in recent30) / 1000.0,
        "week7_runs": len(week7),
        "avg_hr": (sum(hrs) / len(hrs)) if hrs else None,
        "latest_date": latest,
        "streak": _run_streak(runs),
    }


# ---------------------------------------------------------------------------
#  Prompt building
# ---------------------------------------------------------------------------


def _basic_info_lines(retire: dict, weight: dict) -> list[str]:
    """「用户基础信息」 lines (empty when neither data source has entries).

    Gender/age come from the retirement profile, height/weight from the
    weight profile.
    """
    basic = []
    if retire:
        if retire.get("gender"):
            basic.append(f"- 性别：{retire['gender']}")
        if retire.get("age"):
            basic.append(f"- 年龄：{retire['age']} 岁")
    if weight:
        basic.append(f"- 身高：{weight['cm']} cm")
        if weight.get("latest") is not None:
            when = weight["latest_date"] or "最近"
            basic.append(f"- 当前体重：{weight['latest']:.2f} kg（{when}）")
            basic.append(f"- BMI：{weight['bmi']:.1f}（{weight['bmi_status']}）")
        basic.append(
            f"- 健康体重范围：{weight['healthy_min']:.1f} – {weight['healthy_max']:.1f} kg"
            "（BMI 18.5–23.9）",
        )
    return basic


def _weight_record_lines(weight: dict) -> list[str]:
    """「体重变化记录」 lines: weekly-average series + week-over-week trend."""
    if not weight or (not weight.get("weekly") and weight.get("delta") is None):
        return []
    lines = ["### 体重变化记录"]
    if weight.get("weekly"):
        weeks = weight["weekly"][-_WEEKLY_RECORD_LIMIT:]
        series = " → ".join(f"{w['week_start']} {w['avg']:.2f} kg" for w in weeks)
        if len(weight["weekly"]) > _WEEKLY_RECORD_LIMIT:
            series = "… " + series
        lines.append(f"- 周均记录：{series}")
    if weight.get("delta") is not None:
        if weight["delta"] > 0.01:
            trend = "上升"
        elif weight["delta"] < -0.01:
            trend = "下降"
        else:
            trend = "持平"
        lines.append(
            f"- 周均趋势：{weight['latest_week_avg']:.2f} kg，较上一周{trend}"
            f"（{weight['delta']:+.2f} kg）",
        )
    return lines


def _running_record_lines(running: dict) -> list[str]:
    """「跑步运动记录」 lines: aggregated stats (no per-run pace / max HR)."""
    if not running:
        return []
    lines = [
        "### 跑步运动记录",
        f"- 累计：{running['runs']} 次 / {running['total_km']:.1f} km / "
        f"{running['total_time_h']:.1f} 小时 / 爬升 {running['elevation']:.0f} m",
        f"- 最近 30 天：{running['recent30_runs']} 次 / {running['recent30_km']:.1f} km",
        f"- 最近 7 天：{running['week7_runs']} 次",
        f"- 最近一次跑步：{running['latest_date']}｜最近连续跑步：{running['streak']} 天",
    ]
    if running.get("avg_hr"):
        lines.append(f"- 平均心率：{running['avg_hr']:.0f} bpm")
    return lines


def _retire_countdown_lines(retire: dict) -> list[str]:
    """「退休倒计时」 lines (site-specific data, empty when absent)."""
    if not retire:
        return []
    target_label = ""
    if retire.get("expected_age"):
        target_label = f"（预期 {retire['expected_age']} 岁退休）"
    if retire["is_retired"]:
        status_line = "退休状态：已退休 🎉"
        progress_line = "进度：100%"
    else:
        if retire["remaining_years"] and retire["remaining_months"]:
            remaining_str = f"{retire['remaining_years']} 年 {retire['remaining_months']} 个月"
        elif retire["remaining_years"]:
            remaining_str = f"{retire['remaining_years']} 年"
        else:
            remaining_str = f"{retire['remaining_months']} 个月"
        status_line = f"距离退休：{remaining_str}（约 {retire['days_remaining']} 天）"
        progress_line = (
            f"进度：{retire['progress_pct']:.1f}%（已过 {retire['months_lived']} 个月 / "
            f"共 {retire['total_months']} 个月）"
        )
    return [
        "### 退休倒计时",
        f"- 目标退休日：{retire['target_date']}{target_label}",
        f"- {status_line}",
        f"- {progress_line}",
    ]


def build_prompt(stats: dict, today: date) -> str:
    """Build the AI prompt embedding the computed health statistics.

    Follows the shared health-analysis prompt template (role setting → basic
    info → data records → analysis requirements → output format), keeping only
    the data this site actually records: weight, running and the retirement
    plan. Template sections this site has no data for — sleep, subjective
    feelings, body composition, physiological metrics, target weight, per-run
    pace / max heart rate — are deliberately omitted.
    """
    retire, weight, running = stats.get("retire"), stats.get("weight"), stats.get("running")
    lines = [
        "你是我的健康数据分析师，擅长结合体重变化与跑步数据进行综合健康评估。",
        f"以下是截至 {today:%Y-%m-%d} 的健康数据，请为我的个人健康监控页面",
        "写一份简短、务实、可执行的「健康状态总结与建议」，输出要具体、有数据支撑、避免空泛建议。",
        "",
        f"## 数据摘要（截至 {today:%Y-%m-%d}）",
    ]

    basic = _basic_info_lines(retire, weight)
    if basic:
        lines.append("### 用户基础信息")
        lines += basic
    lines += _weight_record_lines(weight)
    lines += _running_record_lines(running)
    lines += _retire_countdown_lines(retire)

    lines += [
        "",
        "## 分析要求",
        "请基于以上数据完成以下分析：",
        "1. **体重趋势分析**：结合 BMI 与周环比变化，判断当前体重区间",
        "   （偏瘦 / 正常 / 超重 / 肥胖）与趋势方向（上升 / 下降 / 平台期）。",
        "2. **跑步表现分析**：结合累计跑量、最近 30 天跑量、跑步频率与连续跑步天数，",
        "   判断运动习惯的稳定性与趋势。",
        "3. **体重与运动关联**：分析跑步频率 / 强度与体重变化之间的相关性，",
        "   判断运动对体重管理的效果。",
        "4. **饮食与生活方式建议**：如体重未按预期下降，从热量平衡角度",
        "   给出具体可执行的饮食调整建议。",
        "5. **里程碑设定**：根据当前进度设定合理的短期（1 个月）和中期（3–6 个月）",
        "   体重目标，给出时间线。",
        "6. **风险预警**：识别体重反弹信号、过度训练风险（如连续跑步天数过长、",
        "   跑量突增）等潜在问题。",
        "7. **一句话总结**：用一句话概括当前健康状态与核心建议。",
        "",
        "## 输出要求",
        "1. 使用简体中文，语气真诚、务实、不夸张、不说教，不做医疗诊断式的绝对结论。",
        "2. 只输出 Markdown 正文；不要输出任何 `#` 或 `##` 标题，不要包裹代码围栏，",
        "   不要前后缀寒暄。内容会直接嵌入到页面「💡 健康状态总结与建议」二级标题之下。",
        "3. 建议结构（小节用 `###` 标题或加粗）：",
        "   - 一句话总体评价；",
        "   - 「当前状态」：体重 / 跑步 / 退休规划 各 1–2 句，点出亮点与隐患；",
        "   - 「建议」：2–4 条具体、可执行、与上面数据直接相关的建议。",
        "4. 全文 250–400 字。",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
#  pi invocation + output handling
# ---------------------------------------------------------------------------


def _last_assistant_message(events: str) -> dict | None:
    """The final assistant message from pi's JSON event stream."""
    last: dict | None = None
    for raw in events.splitlines():
        raw = raw.strip()
        if not raw:
            continue
        try:
            evt = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if evt.get("type") == "message_end":
            msg = evt.get("message") or {}
            if msg.get("role") == "assistant":
                last = msg
    return last


def extract_text(events: str) -> str | None:
    """Extract the final assistant text from pi's JSON event stream."""
    msg = _last_assistant_message(events)
    if msg is None:
        return None
    parts = [c.get("text", "") for c in msg.get("content", []) if c.get("type") == "text"]
    text = "".join(parts).strip()
    return text or None


def extract_model(events: str) -> str | None:
    """Model id used for the final answer (e.g. 'deepseek-v4-flash')."""
    msg = _last_assistant_message(events)
    if msg is None:
        return None
    return msg.get("model") or None


def prettify_model(model: str | None) -> str:
    """Turn a model id into a readable label: 'deepseek-v4-flash' → 'DeepSeek V4 Flash'."""
    if not model:
        return "本地 AI"
    tokens = [t for t in re.split(r"[-_/]+", model) if t]
    head = _BRAND_LABELS.get(tokens[0].lower(), tokens[0].capitalize())
    rest = " ".join(_title_token(t) for t in tokens[1:])
    return " ".join(p for p in (head, rest) if p)


def _title_token(token: str) -> str:
    """Capitalize a model-id token; size suffixes like '32b' → '32B'."""
    if re.fullmatch(r"\d+[a-z]+", token):
        return token.upper()
    return token.capitalize()


def clean_ai_text(text: str) -> str:
    """Strip stray code fences and leading H1/H2 headings from the model output."""
    text = text.strip()
    if text.startswith("```"):
        # unwrap a single ```...``` fence; drop an optional language tag line
        parts = text.split("```")
        if len(parts) >= 3:
            inner = parts[1]
            first, _, rest = inner.partition("\n")
            if first.strip():
                inner = rest
            text = inner.strip()
    lines = text.splitlines()
    while lines and re.match(r"^#{1,2}\s+", lines[0]):
        lines = lines[1:]
    return "\n".join(lines).strip()


def run_pi(prompt: str, model: str | None = None, timeout: int = 300) -> tuple[str, str]:
    """Call the local pi CLI; return (assistant text, readable model label)."""
    pi_bin = shutil.which("pi")
    if not pi_bin:
        raise RuntimeError("pi CLI not found on PATH — install pi-coding-agent")
    cmd = [pi_bin, "-p", "--no-session", "--no-tools", "--no-context-files", "--mode", "json"]
    if model:
        cmd += ["--model", model]
    cmd.append(prompt)
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"pi timed out after {timeout}s") from exc
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip()[-500:]
        raise RuntimeError(f"pi exited with code {proc.returncode}: {detail}")
    text = extract_text(proc.stdout)
    if not text:
        raise RuntimeError("pi produced no assistant text")
    return text, prettify_model(extract_model(proc.stdout))


def _format_markdown(text: str) -> str:
    """Normalize with mdformat (matching `poe fmt`) so CI check-fmt stays green."""
    try:
        import mdformat
    except ImportError:
        return text
    try:
        return mdformat.text(text, extensions=["gfm"])
    except Exception:
        # deliberate fallback: an unformattable body is better than a crash;
        # the fragment is excluded from CI mdformat so this cannot fail checks
        try:
            return mdformat.text(text)
        except Exception:
            return text


def write_summary(path: Path, ai_text: str, model_label: str, generated_at: datetime) -> Path:
    """Write the AI summary inside a collapsible card (expanded by default).

    The whole fragment is a `???+ note` admonition so the page can collapse it;
    the inner body is cleaned (fences/headings stripped) and mdformat-normalized
    before being indented into the card. The file is excluded from
    `poe fmt`/`check-fmt` (admonition indentation is not CommonMark), see the
    `--exclude` in pyproject.toml.
    """
    body = _format_markdown(clean_ai_text(ai_text)).strip()
    if not body:
        # model returned only fences/headings — keep the card informative
        body = "（本轮未生成内容）"
    safe_label = model_label.replace('"', "'")
    title = f"🤖 AI 健康建议 · {safe_label} · {generated_at:%Y-%m-%d %H:%M}"
    content = f'???+ note "{title}"\n' + textwrap.indent(body, "    ") + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
#  CLI
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    def _positive_int(value: str) -> int:
        n = int(value)
        if n <= 0:
            raise argparse.ArgumentTypeError("must be a positive integer")
        return n

    parser = argparse.ArgumentParser(
        prog="update-health-summary",
        description="Regenerate the health status summary via the local pi CLI.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="print the prompt (with stats) and exit without calling pi",
    )
    parser.add_argument(
        "--model",
        help="pi model override, e.g. anthropic/claude-sonnet-4",
    )
    parser.add_argument(
        "--timeout", type=_positive_int, default=300, help="pi call timeout in seconds"
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="output markdown file")
    args = parser.parse_args(argv)
    if args.output.is_dir():
        parser.error(f"output path is a directory: {args.output}")

    today = date.today()
    stats = {
        "retire": compute_retire_stats(load_yaml(DATA_DIR / "retire.yml"), today),
        "weight": compute_weight_stats(load_yaml(DATA_DIR / "weight.yml")),
        "running": compute_running_stats(load_yaml(DATA_DIR / "running.yml"), today),
    }
    prompt = build_prompt(stats, today)

    if args.dry_run:
        print(prompt)
        return 0

    try:
        text, model_label = run_pi(prompt, model=args.model, timeout=args.timeout)
    except (RuntimeError, OSError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        print(f"Keep existing {args.output} unchanged", file=sys.stderr)
        return 1

    out = write_summary(args.output, text, model_label, datetime.now().astimezone())
    print(f"✅ Health summary updated → {out}（{model_label}）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
