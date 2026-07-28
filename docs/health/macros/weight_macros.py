"""MkDocs macros for weight tracking."""

import os
from datetime import datetime, timedelta
from typing import Any

import yaml


def _load_data(env: Any) -> dict:
    """Load weight.yml relative to the docs directory."""
    docs_dir = env.conf.get("docs_dir", "docs")
    data_path = os.path.join(docs_dir, "health", "data", "weight.yml")
    with open(data_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _parse_start(data: dict) -> datetime | None:
    """Parse start_date and align to the Monday of that week."""
    raw = data.get("start_date")
    if not raw:
        return None
    start = datetime.strptime(str(raw), "%Y-%m-%d")
    return start - timedelta(days=start.weekday())


def _date_str(dt: datetime) -> str:
    """Format date as 'Mon D' like 'Jul 27'."""
    return f"{dt.strftime('%b')} {dt.day}"


def _full_date_str(dt: datetime) -> str:
    """Format date as 'YYYY-MM-DD'."""
    return dt.strftime("%Y-%m-%d")


def _short_date_str(dt: datetime) -> str:
    """Format date as 'Mon D, YYYY' like 'Jul 27, 2026'."""
    return f"{dt.strftime('%b')} {dt.day}, {dt.year}"


def _bmi(weight: float, height_cm: int) -> float:
    """Calculate BMI from weight (kg) and height (cm)."""
    return weight / ((height_cm / 100) ** 2)


def _bmi_status(bmi: float) -> str:
    """Classify BMI per Chinese standard."""
    if bmi < 18.5:
        return "Underweight"
    if bmi < 24:
        return "Normal"
    if bmi < 28:
        return "Overweight"
    return "Obese"


def _bmi_color(bmi: float) -> str:
    """Return a CSS color for the BMI status."""
    if bmi < 18.5:
        return "#2196f3"  # Blue
    if bmi < 24:
        return "#4caf50"  # Green
    if bmi < 28:
        return "#ff9800"  # Orange
    return "#f44336"  # Red


def define_env(env):

    @env.macro
    def weight_info():
        """Macro 1: Top info bar — height, latest weight, BMI."""
        data = _load_data(env)
        h = data.get("cm")
        if not h:
            return ""

        latest = None
        for week in reversed(data.get("weeks", [])):
            for d in reversed(week.get("days", [])):
                if d is not None:
                    latest = float(d)
                    break
            if latest is not None:
                break

        if latest is None:
            return f"**Height**: {h} cm"

        bmi = _bmi(latest, h)
        status = _bmi_status(bmi)
        color = _bmi_color(bmi)
        info = (
            f"**Height**: {h} cm　|　**Latest**: {latest} kg　|　"
            f'**BMI**: {bmi:.1f} <span style="color:{color}">({status})</span>'
        )
        info += "\n\n"
        info += (
            "> BMI = weight(kg) ÷ (height(m))²\n\n"
            "> Chinese standard: "
            '<span style="color:#2196f3">Underweight &lt; 18.5</span> | '
            '<span style="color:#4caf50">Normal 18.5–23.9</span> | '
            '<span style="color:#ff9800">Overweight 24–27.9</span> | '
            '<span style="color:#f44336">Obese ≥ 28</span>'
        )
        # Calculate healthy weight range for Normal BMI (18.5–23.9)
        hm = h / 100.0
        w_min = 18.5 * hm * hm
        w_max = 23.9 * hm * hm
        info += f"\n\n> Your healthy weight range: **{w_min:.1f} kg – {w_max:.1f} kg**"
        return info

    @env.macro
    def weight_table():
        """Macro 2: Weekly details with two sections.

        Layout:
        1. 📋 Last 4 Weeks — expanded by default, merges last 4 weeks into ONE table
           with daily values, averages, and BMI.
        2. 📊 All Weeks — collapsed by default, shows all weeks' averages at a glance.
        """
        data = _load_data(env)
        h = data.get("cm")
        start = _parse_start(data)
        weeks = data.get("weeks", [])

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

        # ----------------------------------------------------------------
        # Part 1: Recent 4 Weeks merged into ONE compact table, expanded by default
        # ----------------------------------------------------------------
        recent_start = max(0, total_weeks - recent_weeks)

        # Compute date range for Last 4 Weeks
        l4w_start = start + timedelta(days=recent_start * 7)
        l4w_end = start + timedelta(days=(total_weeks - 1) * 7 + 6)

        md += '???+ "📋 Last 4 Weeks ({} ~ {})"\n'.format(
            _short_date_str(l4w_start), _short_date_str(l4w_end)
        )
        detail_header = "| Week | Daily Values (Mo/Tu/We/Th/Fr/Sa/Su) | Avg | BMI |\n"
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

            # Merge all 7 daily values into one cell, separated by " / "
            daily_cells = []
            for d in days:
                daily_cells.append(str(d) if d is not None else "—")
            daily_str = " / ".join(daily_cells)

            row = "| W{} ({}) | {} | {} | {} |\n".format(
                idx + 1, date_range, daily_str, avg_str, bmi_str
            )
            for line in row.rstrip("\n").split("\n"):
                md += f"    {line}\n"

        md += "\n"

        # ----------------------------------------------------------------
        # Part 2: All Weeks Summary — collapsible, weekly averages at a glance
        # ----------------------------------------------------------------
        md += '??? "📊 All Weeks ({} ~ {})"\n'.format(
            _short_date_str(start), _short_date_str(l4w_end)
        )
        sum_header = "| Week | Dates | Avg (kg) | BMI | vs Last Week |\n"
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

            row = f"| Week {i + 1} | {date_range} | {avg_str} | {bmi_str} | {change} |\n"
            for line in row.rstrip("\n").split("\n"):
                md += f"    {line}\n"
        md += "\n"

        return md

    @env.macro
    def weight_chart():
        """Macro 3: Weight trend chart (Mermaid xychart-beta)."""
        data = _load_data(env)
        start = _parse_start(data)
        weeks = data.get("weeks", [])

        if not start or len(weeks) < 2:
            return "> Trend chart will appear once you have at least 2 weeks of data"

        avgs, labels = [], []
        for i, week in enumerate(weeks, 1):
            valid = [float(d) for d in week.get("days", []) if d is not None]
            if valid:
                avgs.append(round(sum(valid) / len(valid), 2))
                ws = start + timedelta(days=(i - 1) * 7)
                we = ws + timedelta(days=6)
                labels.append(f'"{_full_date_str(ws)} ~ {_full_date_str(we)}"')

        if len(avgs) < 2:
            return "> Trend chart will appear once you have at least 2 complete weeks of data"

        pad = 0.5
        lo = round(min(avgs) - pad, 1)
        hi = round(max(avgs) + pad, 1)

        return (
            "```mermaid\n"
            "xychart-beta\n"
            '    title "Weight Trend (Weekly Avg kg)"\n'
            f"    x-axis [{', '.join(labels)}]\n"
            f'    y-axis "Weight (kg)" {lo} --> {hi}\n'
            f"    line [{', '.join(map(str, avgs))}]\n"
            "```"
        )
