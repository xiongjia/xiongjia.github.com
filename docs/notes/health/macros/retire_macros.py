"""MkDocs macros for retirement countdown."""

import os
from datetime import date, datetime

import yaml

_REFORM_START = date(2025, 1, 1)

_GENDER_CONFIG = {
    "male": {
        "original_age": 60,
        "delay_rate": 4,
        "max_delay": 36,
        "label_key": "gender_male",
        "final_age": 63,
    },
    "female_cadre": {
        "original_age": 55,
        "delay_rate": 4,
        "max_delay": 36,
        "label_key": "gender_female_cadre",
        "final_age": 58,
    },
    "female_worker": {
        "original_age": 50,
        "delay_rate": 2,
        "max_delay": 60,
        "label_key": "gender_female_worker",
        "final_age": 55,
    },
}

_MONTH_LABELS = ["1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "11", "12"]


def _load_data(env):
    docs_dir = env.conf.get("docs_dir", "docs")
    data_path = os.path.join(docs_dir, "notes", "health", "data", "retire.yml")
    if not os.path.exists(data_path):
        return {}
    with open(data_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _add_months(dt, months):
    total = dt.year * 12 + (dt.month - 1) + months
    return date(total // 12, total % 12 + 1, 1)


def _month_diff(a, b):
    """Months from a to b. a must be <= b."""
    return max(0, (b.year - a.year) * 12 + (b.month - a.month))


def _compute_retirement(birth, gender, work_start_age=22, expected_retire_age=None):
    cfg = _GENDER_CONFIG.get(gender)
    if not cfg:
        return None
    orig = cfg["original_age"]
    orig_retire = date(birth.year + orig, birth.month, 1)
    if orig_retire <= _REFORM_START:
        delay = 0
    else:
        elapsed = _month_diff(_REFORM_START, orig_retire)
        delay = min(cfg["max_delay"], elapsed // cfg["delay_rate"])
    final_retire = _add_months(orig_retire, delay)
    total_m = _month_diff(birth, final_retire)
    today = date.today()

    # Expected retirement (user's own plan).
    # Ignored if >= original retirement age (no early retirement scenario).
    if expected_retire_age is not None and expected_retire_age < orig:
        exp_retire = date(birth.year + int(expected_retire_age), birth.month, 1)
        exp_total_m = _month_diff(birth, exp_retire)
    else:
        exp_retire = None
        exp_total_m = None

    return {
        "original_age": orig,
        "original_retire": orig_retire,
        "delay_months": delay,
        "final_retire": final_retire,
        "final_age_y": total_m // 12,
        "final_age_m": total_m % 12,
        "total_months": total_m + 1,
        "label_key": cfg["label_key"],
        "final_age_label": cfg["final_age"],
        "is_retired": today >= final_retire,
        "months_lived": _month_diff(birth, today) + 1,
        "work_start_month_index": work_start_age * 12,
        "work_start_age": work_start_age,
        "work_months": (
            _month_diff(date(birth.year + work_start_age, birth.month, 1), final_retire)
        ),
        "expected_retire_age": (
            int(expected_retire_age) if expected_retire_age is not None else None
        ),
        "expected_retire": exp_retire,
        "expected_total_months": exp_total_m + 1 if exp_total_m is not None else None,
        "expected_months_lived": _month_diff(birth, today) + 1 if exp_retire else None,
    }


def _banner(ret):
    labels = ret.get("_L", {})
    today = date.today()
    rm = _month_diff(ret["final_retire"], today)
    y = labels.get("year", "y")
    m = labels.get("month", "m")
    dur = f"{rm // 12} {y} {rm % 12} {m}" if rm // 12 > 0 else f"{rm} {m}"
    df = labels.get("date_format", "%Y-%m")
    subtitle = (
        f"{labels.get('retire_date', 'Retired on')}："
        f"{ret['final_retire'].strftime(df)} | "
        f"{labels.get('retired_duration', 'Retired')} {dur}"
    )
    return f"""\
<div class="retire-banner">
    <div class="emoji-line">🎉😊🎉</div>
    <div class="title">{labels.get("retired_title", "Retired!")}</div>
    <div class="subtitle">{subtitle}</div>
</div>"""


def _cards(ret):
    labels = ret.get("_L", {})
    birth = ret["_birth"]
    df = labels.get("date_format", "%Y-%m")
    items = [
        (labels.get("birth", "Birth"), birth.strftime(df)),
        (labels.get("identity", "Identity"), labels.get(ret.get("label_key", ""), "")),
        (
            labels.get("work_start", "Start work"),
            f"{ret.get('work_start_age', 22)} {labels.get('age', 'y')}",
        ),
    ]
    work_y = ret["work_months"] // 12
    work_m = ret["work_months"] % 12
    items.append(
        (
            labels.get("work_years", "Work years"),
            f"{work_y} {labels.get('year', 'y')} {work_m} {labels.get('month', 'm')}",
        ),
    )
    items.append(
        (
            labels.get("original_retire_age", "Orig retire age"),
            f"{ret['original_age']} {labels.get('age', 'y')}",
        ),
    )
    if ret["delay_months"] > 0:
        items.append(
            (
                labels.get("delay_months", "Delay"),
                f"{ret['delay_months']} {labels.get('month', 'm')}",
            ),
        )
    # Add expected retirement card if user set it
    if ret.get("expected_retire") is not None:
        exp = ret["expected_retire"]
        exp_age = ret["expected_retire_age"]
        items.append(
            (
                labels.get("expected_retire_age", "Expected retire age"),
                f"{exp_age} {labels.get('age', 'y')} ({exp.strftime(df)})",
            ),
        )
    items += [
        (
            labels.get("legal_retire_age", "Legal retire age"),
            (
                f"{ret['final_age_y']} {labels.get('age', 'y')} "
                f"{ret['final_age_m']} {labels.get('month', 'm')}"
            ),
        ),
        (labels.get("retire_date", "Retire date"), ret["final_retire"].strftime(df)),
    ]
    html_parts = ['<div class="retire-cards">\n']
    for label, value in items:
        html_parts.append(
            f'    <div class="retire-card">'
            f'<div class="label">{label}</div>'
            f'<div class="value">{value}</div>'
            f"</div>\n",
        )
    html_parts.append("</div>\n")
    return "".join(html_parts)


def _progress(ret):
    labels = ret.get("_L", {})
    pct = min(100.0, ret["months_lived"] / ret["total_months"] * 100)
    remaining = ret["total_months"] - ret["months_lived"]
    y = labels.get("year", "y")
    m = labels.get("month", "m")
    # Working months lived
    wm = max(0, ret["months_lived"] - ret.get("work_start_month_index", 0))
    work_suffix = f" ({wm} {m}{labels.get('legend_worked_short', ' worked')})" if wm > 0 else ""

    # Expected retirement progress (if set and different from legal)
    exp_html = ""
    if ret.get("expected_retire") is not None and ret.get("expected_total_months") is not None:
        exp_total = ret["expected_total_months"]
        exp_pct = min(100.0, ret["months_lived"] / exp_total * 100)
        exp_remaining = exp_total - ret["months_lived"]
        exp_html = (
            f'\n<h4 class="retire-progress-heading">'
            f"🎯 {labels.get('expected_retire_age', 'Expected')}</h4>\n"
            f'<div class="retire-progress-stats">\n'
            f"    <span>{labels.get('progress_passed', 'Passed')}："
            f"{ret['months_lived']} {m}</span>\n"
            f"    <span>{labels.get('progress_total', 'Total')}："
            f"{exp_total} {m}</span>\n"
            f"</div>\n"
            f'<div class="retire-progress-bar">\n'
            f'    <div class="fill expected" style="width:{exp_pct:.1f}%"></div>\n'
            f"</div>\n"
            f'<div class="retire-progress-stats">\n'
            f"    <span>{labels.get('progress_progress', 'Progress')}："
            f"{exp_pct:.1f}%</span>\n"
            f"    <span>{labels.get('progress_remaining', 'Remaining')}："
            f"{exp_remaining // 12} {y} {exp_remaining % 12} {m}</span>\n"
            f"</div>"
        )

    html = (
        f'\n<h4 class="retire-progress-heading">'
        f"⚖️ {labels.get('legal_retire_age', 'Legal')}</h4>\n"
        f'<div class="retire-progress-stats">\n'
        f"    <span>{labels.get('progress_passed', 'Passed')}："
        f"{ret['months_lived']} {m}{work_suffix}</span>\n"
        f"    <span>{labels.get('progress_total', 'Total')}："
        f"{ret['total_months']} {m}</span>\n"
        f"</div>\n"
        f'<div class="retire-progress-bar">\n'
        f'    <div class="fill" style="width:{pct:.1f}%"></div>\n'
        f"</div>\n"
        f'<div class="retire-progress-stats">\n'
        f"    <span>{labels.get('progress_progress', 'Progress')}：{pct:.1f}%</span>\n"
        f"    <span>{labels.get('progress_remaining', 'Remaining')}："
        f"{remaining // 12} {y} {remaining % 12} {m}</span>\n"
        f"</div>"
    )
    return html + exp_html


def _grid(ret):
    birth = ret["_birth"]
    final = ret["final_retire"]
    lines = ['<div class="retire-month-header"><span class="spacer"></span><div class="cells">']
    for m in _MONTH_LABELS:
        lines.append(f'<span class="m-label">{m}</span>')
    lines.append("</div></div>\n")

    lines.append(
        '<div class="retire-grid" '
        f'data-retire-total="{ret["total_months"]}" '
        f'data-birth-year="{birth.year}" '
        f'data-birth-month="{birth.month}">\n',
    )
    # Expected retirement index (for marker)
    exp_idx = None
    if ret.get("expected_retire") is not None:
        exp_idx = _month_diff(birth, ret["expected_retire"])
    for year in range(birth.year, final.year + 1):
        lines.append('  <div class="retire-year-row">\n')
        lines.append(f'    <span class="retire-year-label">{year}</span>\n')
        lines.append('    <div class="retire-cells">\n')
        if year == birth.year and birth.month > 1:
            for _ in range(1, birth.month):
                lines.append(
                    '      <span class="retire-cell" style="visibility:hidden"></span>\n',
                )
        start_m = 1 if year > birth.year else birth.month
        end_m = 12 if year < final.year else final.month
        for month in range(start_m, end_m + 1):
            idx = _month_diff(birth, date(year, month, 1))
            cls = " pre-work" if idx < ret.get("work_start_month_index", 264) else ""
            content = ""
            if year == final.year and month == final.month:
                cls += " retire-cell-last"
                content = "⭐"
            elif (
                exp_idx is not None
                and year == ret["expected_retire"].year
                and month == ret["expected_retire"].month
            ):
                cls += " retire-cell-expected"
                content = "📌"
            lines.append(
                f'      <span class="retire-cell{cls}" '
                f'data-month-index="{idx}" '
                f'title="{year}-{month:02d}">{content}</span>\n',
            )
        if year == final.year and final.month < 12:
            for _ in range(final.month, 12):
                lines.append(
                    '      <span class="retire-cell" style="visibility:hidden"></span>\n',
                )
        lines.append("    </div>\n")
        lines.append("  </div>\n")
    lines.append("</div>\n")
    return "".join(lines)


def define_env(env):
    """Register retirement countdown macros."""

    @env.macro
    def retire_info():
        """Retirement summary — banner (if retired) or info cards + progress."""
        data = _load_data(env)
        if not data:
            return "> config `docs/notes/health/data/retire.yml` not found"
        nationality = data.get("nationality", "china")
        if nationality != "china":
            return f"> only china nationality supported, got `{nationality}`"
        birth_str = data.get("birth_date")
        gender = data.get("gender")
        if not birth_str or not gender:
            return "> `birth_date` and `gender` required in retire.yml"
        try:
            birth = datetime.strptime(str(birth_str), "%Y-%m-%d").date().replace(day=1)
        except (ValueError, TypeError):
            return "> invalid `birth_date` format, use YYYY-MM-DD"
        if gender not in _GENDER_CONFIG:
            valid = ", ".join(_GENDER_CONFIG)
            return f"> invalid gender, must be one of: {valid}"
        work_start_age = data.get("work_start_age", 22)
        expected_retire_age = data.get("expected_retire_age")
        ret = _compute_retirement(birth, gender, work_start_age, expected_retire_age)
        if not ret:
            return "> retirement calculation failed"
        ret["_birth"] = birth
        labels = data.get("labels", {})
        ret["_L"] = labels
        html = ""
        if ret["is_retired"]:
            html += _banner(ret)
        else:
            html += _cards(ret)
            html += _progress(ret)
        return html

    @env.macro
    def retire_grid():
        """Dense monthly grid from birth to retirement."""
        data = _load_data(env)
        if not data:
            return ""
        birth_str = data.get("birth_date")
        gender = data.get("gender")
        if not birth_str or not gender:
            return ""
        try:
            birth = datetime.strptime(str(birth_str), "%Y-%m-%d").date().replace(day=1)
        except (ValueError, TypeError):
            return ""
        if gender not in _GENDER_CONFIG:
            return ""
        work_start_age = data.get("work_start_age", 22)
        expected_retire_age = data.get("expected_retire_age")
        ret = _compute_retirement(birth, gender, work_start_age, expected_retire_age)
        if not ret:
            return ""
        ret["_birth"] = birth
        labels = data.get("labels", {})
        ret["_L"] = labels
        html_parts = ['<div class="retire-legend">\n']
        html_parts.append(
            '  <span><span class="legend-dot filled"></span> '
            f"{labels.get('legend_worked', 'Worked')}</span>\n",
        )
        html_parts.append(
            '  <span><span class="legend-dot pre-work-dot"></span> '
            f"{labels.get('legend_pre_work', 'Pre-work')}</span>\n",
        )
        html_parts.append(
            f"  <span>🚶‍➡️ {labels.get('legend_now', 'Now')}</span>\n",
        )
        html_parts.append(
            '  <span><span class="legend-dot"></span> '
            f"{labels.get('legend_future', 'Future')}</span>\n",
        )
        html_parts.append(
            f"  <span>📌 {labels.get('legend_expected', 'Expected')}</span>\n",
        )
        html_parts.append(
            f"  <span>⭐ {labels.get('legend_legal', 'Legal')}</span>\n",
        )
        html_parts.append("</div>\n")
        html_parts.append(_grid(ret))
        return "".join(html_parts)
