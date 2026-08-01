"""MkDocs macros for weight tracking.

Provides card-style info (i18n via YAML labels), BMI spectrum progress bar,
weekly details table (Markdown), and trend chart (Mermaid).
"""

import os
from datetime import datetime, timedelta
from typing import Any

import yaml

_DAY_KEYS = ["grid_mon", "grid_tue", "grid_wed", "grid_thu", "grid_fri", "grid_sat", "grid_sun"]


def _load_data(env: Any) -> dict:
    """Load weight.yml relative to the docs directory."""
    docs_dir = env.conf.get("docs_dir", "docs")
    data_path = os.path.join(docs_dir, "notes", "health", "data", "weight.yml")
    if not os.path.exists(data_path):
        return {}
    with open(data_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _parse_start(data: dict) -> datetime | None:
    """Parse start_date and align to the Monday of that week."""
    raw = data.get("start_date")
    if not raw:
        return None
    start = datetime.strptime(str(raw), "%Y-%m-%d")
    return start - timedelta(days=start.weekday())


def _bmi(weight: float, height_cm: int) -> float:
    """Calculate BMI from weight (kg) and height (cm)."""
    return weight / ((height_cm / 100) ** 2)


def _bmi_status_key(bmi: float) -> str:
    """Classify BMI per Chinese standard. Returns key for labels."""
    if bmi < 18.5:
        return "underweight"
    if bmi < 24:
        return "normal"
    if bmi < 28:
        return "overweight"
    return "obese"


def _bmi_color(bmi: float) -> str:
    """Return a CSS color for the BMI status."""
    if bmi < 18.5:
        return "#2196f3"  # Blue
    if bmi < 24:
        return "#4caf50"  # Green
    if bmi < 28:
        return "#ff9800"  # Orange
    return "#f44336"  # Red


def _latest_weight(data: dict) -> float | None:
    """Get the latest recorded weight from all weeks."""
    for week in reversed(data.get("weeks", [])):
        for d in reversed(week.get("days", [])):
            if d is not None:
                return float(d)
    return None


def _get_labels(data: dict) -> dict:
    """Get labels dict from data, with defaults for missing keys."""
    defaults = {
        "colon_sep": ": ",
        "height": "Height",
        "latest": "Latest",
        "bmi": "BMI",
        "chart_title": "Weight Trend (Weekly Avg kg)",
        "healthy_range": "Healthy Range",
        "unit_kg": "kg",
        "unit_cm": "cm",
        "underweight": "Underweight",
        "normal": "Normal",
        "overweight": "Overweight",
        "obese": "Obese",
        "bmi_formula": "BMI = weight(kg) ÷ height(m)²",
        "bmi_standard_underweight": "Underweight < 18.5",
        "bmi_standard_normal": "Normal 18.5–23.9",
        "bmi_standard_overweight": "Overweight 24–27.9",
        "bmi_standard_obese": "Obese ≥ 28",
        "progress": "Progress",
        "current": "Current",
        "grid_mon": "Mon",
        "grid_tue": "Tue",
        "grid_wed": "Wed",
        "grid_thu": "Thu",
        "grid_fri": "Fri",
        "grid_sat": "Sat",
        "grid_sun": "Sun",
        "table_recent_heading": "\U0001f4cb Last 4 Weeks",
        "table_all_heading": "\U0001f4ca All Weeks",
        "table_col_week": "Week",
        "table_col_dates": "Dates",
        "table_col_daily_values": "Daily Values",
        "table_col_avg": "Avg",
        "table_col_bmi": "BMI",
        "table_col_vs_last": "vs Last Week",
        "table_row_prefix": "W",
        "table_row_suffix": "",
    }
    labels = data.get("labels", {})
    merged = dict(defaults)
    merged.update(labels)
    return merged


def _ensure_data_valid(data: dict) -> str | None:
    """Return error string if data is invalid, else None."""
    if not data:
        return "> Config `docs/notes/health/data/weight.yml` not found"
    if not data.get("cm"):
        return "> `cm` (height) required in weight.yml"
    return None


def _date_str(dt: datetime) -> str:
    """Format date as 'MM-DD' like '07-27' (locale-neutral)."""
    return f"{dt.month:02d}-{dt.day:02d}"


def _full_date_str(dt: datetime) -> str:
    """Format date as 'YYYY-MM-DD'."""
    return dt.strftime("%Y-%m-%d")


# ---------------------------------------------------------------------------
#  Cards (retire-style summary)
# ---------------------------------------------------------------------------


def _cards(data: dict) -> str:
    """Render weight info cards (height, latest, BMI, healthy range)."""
    h = data.get("cm")
    labels = _get_labels(data)
    latest = _latest_weight(data)

    html_parts = ['<div class="weight-cards">\n']
    kf = labels.get("unit_kg", "kg")

    # Card: Height
    html_parts.append(
        f'    <div class="weight-card">'
        f'<div class="label">{labels["height"]}</div>'
        f'<div class="value">{h} {labels["unit_cm"]}</div>'
        f"</div>\n"
    )

    if latest is not None:
        bmi = _bmi(latest, h)
        status_key = _bmi_status_key(bmi)
        status_label = labels.get(status_key, status_key)
        color = _bmi_color(bmi)

        # Card: Latest weight
        html_parts.append(
            f'    <div class="weight-card">'
            f'<div class="label">{labels["latest"]}</div>'
            f'<div class="value">{latest:.2f} {kf}</div>'
            f"</div>\n"
        )

        # Card: BMI
        html_parts.append(
            f'    <div class="weight-card">'
            f'<div class="label">{labels["bmi"]}</div>'
            f'<div class="value" style="color:{color}">'
            f"{bmi:.1f} ({status_label})</div>"
            f"</div>\n"
        )

    # Card: Healthy range
    hm = h / 100.0
    w_min = 18.5 * hm * hm
    w_max = 23.9 * hm * hm
    html_parts.append(
        f'    <div class="weight-card">'
        f'<div class="label">{labels["healthy_range"]}</div>'
        f'<div class="value">{w_min:.1f} – {w_max:.1f} {kf}</div>'
        f"</div>\n"
    )

    html_parts.append("</div>\n")

    # BMI formula + standard note
    html_parts.append(
        f'<div class="weight-note">\n'
        f"  <span>{labels['bmi_formula']}</span>\n"
        f'  <span class="sep">|</span>\n'
        f'  <span style="color:#2196f3">{labels["bmi_standard_underweight"]}</span>\n'
        f'  <span class="sep">|</span>\n'
        f'  <span style="color:#4caf50">{labels["bmi_standard_normal"]}</span>\n'
        f'  <span class="sep">|</span>\n'
        f'  <span style="color:#ff9800">{labels["bmi_standard_overweight"]}</span>\n'
        f'  <span class="sep">|</span>\n'
        f'  <span style="color:#f44336">{labels["bmi_standard_obese"]}</span>\n'
        f"</div>\n"
    )

    return "".join(html_parts)


# ---------------------------------------------------------------------------
#  BMI spectrum progress bar
# ---------------------------------------------------------------------------


def _progress_bar(data: dict) -> str:
    """Render a BMI spectrum progress bar from 14 to 32 with zone colors."""
    h = data.get("cm")
    labels = _get_labels(data)
    latest = _latest_weight(data)
    if latest is None or not h:
        return ""

    bmi = _bmi(latest, h)
    bar_min, bar_max = 14.0, 32.0
    pct = max(0, min(100, (bmi - bar_min) / (bar_max - bar_min) * 100))

    def _zp(v):
        return (v - bar_min) / (bar_max - bar_min) * 100

    u18_5, u24, u28 = _zp(18.5), _zp(24.0), _zp(28.0)
    status_key = _bmi_status_key(bmi)
    status_label = labels.get(status_key, status_key)
    color = _bmi_color(bmi)

    # Build BMI segments (keep lines under 100 cols)
    seg_data = [
        (0, u18_5, "#2196f3", "&lt; 18.5"),
        (u18_5, u24 - u18_5, "#4caf50", "18.5–23.9"),
        (u24, u28 - u24, "#ff9800", "24–27.9"),
        (u28, 100 - u28, "#f44336", "≥ 28"),
    ]
    bmi_segments = ""
    for left, w, c, t in seg_data:
        bmi_segments += (
            f'        <div class="bmi-segment" '
            f'style="left:{left}%;width:{w}%;background:{c}" '
            f'title="{t}"></div>\n'
        )

    status_span = f'<span style="color:{color}">({status_label})</span>'

    return f"""\
<div class="weight-progress">
    <h4 class="weight-progress-heading">{labels["bmi"]} {labels["progress"]}</h4>
    <div class="weight-progress-stats">
        <span>{labels["current"]}{labels["colon_sep"]}{bmi:.1f} {status_span}</span>
    </div>
    <div class="weight-bmi-bar">
{bmi_segments}        <div class="bmi-marker" style="left:{pct}%">▼</div>
    </div>
    <div class="weight-bmi-labels">
        <span>14</span>
        <span>18.5</span>
        <span>24</span>
        <span>28</span>
        <span>32</span>
    </div>
</div>
"""


# ---------------------------------------------------------------------------
#  Weekly Details (original Markdown table)
# ---------------------------------------------------------------------------


def _table(data: dict) -> str:
    """Render weekly details — last 4 weeks expanded + all weeks collapsed."""
    h = data.get("cm")
    start = _parse_start(data)
    weeks = data.get("weeks", [])
    labels = _get_labels(data)

    if not weeks:
        return "> No data yet"
    if not start:
        return "> ⚠️ Set `start_date` in `weight.yml` (e.g. `2026-07-28`)"

    total_weeks = len(weeks)
    recent_weeks = 4

    # Pre-compute weekly averages for week-over-week comparison
    week_avgs = []
    for week in weeks:
        valid = [float(d) for d in week.get("days", []) if d is not None]
        week_avgs.append(sum(valid) / len(valid) if valid else None)

    md = ""

    # Part 1: Recent 4 Weeks, expanded by default
    recent_start = max(0, total_weeks - recent_weeks)
    l4w_start = start + timedelta(days=recent_start * 7)
    l4w_end = start + timedelta(days=(total_weeks - 1) * 7 + 6)

    md += '???+ "{} ({} ~ {})"\n'.format(
        labels["table_recent_heading"], _full_date_str(l4w_start), _full_date_str(l4w_end)
    )
    day_abbrs = "/".join([labels[k] for k in _DAY_KEYS])
    detail_header = (
        f"| {labels['table_col_week']} | {labels['table_col_daily_values']} ({day_abbrs}) "
        f"| {labels['table_col_avg']} | {labels['table_col_bmi']} |\n"
    )
    detail_header += "|:---|:---|:---:|:---:|\n"
    for line in detail_header.rstrip("\n").split("\n"):
        md += f"    {line}\n"

    for idx in range(recent_start, total_weeks):
        week = weeks[idx]
        days = week.get("days", [])
        week_start = start + timedelta(days=idx * 7)
        week_end = week_start + timedelta(days=6)
        date_range = f"{_date_str(week_start)}-{_date_str(week_end)}"

        avg = week_avgs[idx]
        avg_str = f"**{avg:.2f}**" if avg else "—"
        bmi_val = _bmi(avg, h)
        bmi_str = (
            (f'<span style="color:{_bmi_color(bmi_val)}">**{bmi_val:.1f}**</span>')
            if (avg and h)
            else "—"
        )

        daily_cells = []
        for d in days:
            daily_cells.append(str(d) if d is not None else "—")
        daily_str = " / ".join(daily_cells)

        row = "| {}{}{} ({}) | {} | {} | {} |\n".format(
            labels["table_row_prefix"],
            idx + 1,
            labels["table_row_suffix"],
            date_range,
            daily_str,
            avg_str,
            bmi_str,
        )
        for line in row.rstrip("\n").split("\n"):
            md += f"    {line}\n"

    md += "\n"

    # Part 2: All Weeks Summary — collapsible
    md += '??? "{} ({} ~ {})"\n'.format(
        labels["table_all_heading"], _full_date_str(start), _full_date_str(l4w_end)
    )
    sum_header = (
        f"| {labels['table_col_week']} | {labels['table_col_dates']} "
        f"| {labels['table_col_avg']} (kg) | {labels['table_col_bmi']} "
        f"| {labels['table_col_vs_last']} |\n"
    )
    sum_header += "|:---|:---:|:---:|:---:|:---:|\n"
    for line in sum_header.rstrip("\n").split("\n"):
        md += f"    {line}\n"

    for i in range(total_weeks):
        week_start = start + timedelta(days=i * 7)
        week_end = week_start + timedelta(days=6)
        date_range = f"{_date_str(week_start)}-{_date_str(week_end)}"
        avg = week_avgs[i]
        avg_str = f"**{avg:.2f}**" if avg else "—"
        bmi_val = _bmi(avg, h)
        bmi_str = (
            (f'<span style="color:{_bmi_color(bmi_val)}">**{bmi_val:.1f}**</span>')
            if (avg and h)
            else "—"
        )

        change = "—"
        if avg is not None and i > 0 and week_avgs[i - 1] is not None:
            diff = avg - week_avgs[i - 1]
            arrow = "↓" if diff < 0 else "↑" if diff > 0 else "→"
            change = f"**{diff:+.2f} {arrow}**"

        row = (
            f"| {labels['table_row_prefix']}{i + 1}{labels['table_row_suffix']} | {date_range} "
            f"| {avg_str} | {bmi_str} | {change} |\n"
        )
        for line in row.rstrip("\n").split("\n"):
            md += f"    {line}\n"
    md += "\n"

    return md


# ---------------------------------------------------------------------------
#  Trend Chart (original Mermaid)
# ---------------------------------------------------------------------------


def _chart(data: dict) -> str:
    """Render a Mermaid xychart-beta of weekly average weight."""
    labels_i18n = _get_labels(data)
    start = _parse_start(data)
    weeks = data.get("weeks", [])

    if not start or len(weeks) < 2:
        return "> Trend chart will appear once you have at least 2 weeks of data"

    avgs, date_labels = [], []
    for i, week in enumerate(weeks, 1):
        valid = [float(d) for d in week.get("days", []) if d is not None]
        if valid:
            avgs.append(round(sum(valid) / len(valid), 2))
            ws = start + timedelta(days=(i - 1) * 7)
            we = ws + timedelta(days=6)
            date_labels.append(f'"{_full_date_str(ws)} ~ {_full_date_str(we)}"')

    if len(avgs) < 2:
        return "> Trend chart will appear once you have at least 2 complete weeks of data"

    pad = 0.5
    lo = round(min(avgs) - pad, 1)
    hi = round(max(avgs) + pad, 1)

    return (
        "```mermaid\n"
        "xychart-beta\n"
        f'    title "{labels_i18n["chart_title"]}"\n'
        f"    x-axis [{', '.join(date_labels)}]\n"
        f'    y-axis "Weight (kg)" {lo} --> {hi}\n'
        f"    line [{', '.join(map(str, avgs))}]\n"
        "```"
    )


# ---------------------------------------------------------------------------
#  Public macros
# ---------------------------------------------------------------------------


def define_env(env):
    """Register weight tracking macros."""

    @env.macro
    def weight_info():
        """Summary cards — height, latest weight, BMI, healthy range."""
        data = _load_data(env)
        err = _ensure_data_valid(data)
        if err:
            return err
        return _cards(data)

    @env.macro
    def weight_progress():
        """BMI spectrum progress bar."""
        data = _load_data(env)
        err = _ensure_data_valid(data)
        if err:
            return err
        return _progress_bar(data)

    @env.macro
    def weight_table():
        """Weekly details — last 4 weeks expanded + all weeks collapsed."""
        data = _load_data(env)
        err = _ensure_data_valid(data)
        if err:
            return err
        return _table(data)

    @env.macro
    def weight_chart():
        """Mermaid trend chart of weekly avg weight."""
        data = _load_data(env)
        err = _ensure_data_valid(data)
        if err:
            return err
        return _chart(data)
