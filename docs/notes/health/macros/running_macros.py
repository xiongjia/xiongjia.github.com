"""MkDocs macros for running tracking.

Reads the committed data file `docs/notes/health/data/running.yml` (generated
by `uv run poe sync-running`). Pace splits and route polylines are loaded
client-side by `docs/notes/health/running-route.js` from the R2 bucket copy
(`extra.bucket.mappings[].base_url`, uploaded by `poe sync-running-splits`) —
the build itself is offline and CI needs no sync step; the macros only embed
the bucket URL + map config as data attributes for the JS. The git-ignored
`.running/splits.json` is the sync pipeline's cache (Garmin API cache +
upload staging) and is never read at build time.
"""

import html
import json
import os
from datetime import datetime, timedelta
from typing import Any

import yaml

_DATA_PATH = os.path.join("notes", "health", "data", "running.yml")

# Find repo root: try __file__ based path, then CWD, then up from docs/
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = _THIS_DIR
for _ in range(5):  # up to 5 levels up
    if os.path.isfile(os.path.join(_REPO_ROOT, "mkdocs.yml")):
        break
    parent = os.path.dirname(_REPO_ROOT)
    if parent == _REPO_ROOT:
        _REPO_ROOT = os.getcwd()
        break
    _REPO_ROOT = parent
else:
    _REPO_ROOT = os.getcwd()

# Bucket/config copied into data attributes for client-side splits loading:
# running-route.js fetches splits.json from `_splits_bucket_url()` and uses the
# PMTiles/glyphs/regions config to gate route buttons and the inline map.
_PMTILES_URL = ""
_GLYPHS_URL = ""
_SUPPORTED_REGIONS: list[list[float]] = []  # [[minLng, minLat, maxLng, maxLat], ...]

_MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

# Label foreground — theme-adaptive (light/dark); fallback for non-Material contexts.
# Fallback matches the Moment stats heatmap's label color (#757575).
_LABEL_FG = "var(--md-default-fg-color--light, #757575)"


def _load_data(env: Any) -> dict:
    """Load running.yml relative to the docs directory."""
    docs_dir = env.conf.get("docs_dir", "docs")
    data_path = os.path.join(docs_dir, _DATA_PATH)
    if not os.path.exists(data_path):
        return {}
    with open(data_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    # empty/comment-only file -> None; non-dict top level (hand-edited) -> {}
    return data if isinstance(data, dict) else {}


def _no_data() -> str:
    """Friendly hint rendered when the data file is missing."""
    return "> ⚠️ 暂无跑步数据 — 运行 `poe sync-running` 同步。"


def _parse_moving_time(interval: Any) -> float | None:
    """Parse running_page interval ('0:19:42.196000') to seconds."""
    if not interval:
        return None
    try:
        parts = [float(p) for p in str(interval).split(":")]
    except ValueError:
        return None
    sec = 0.0
    for p in parts:
        sec = sec * 60 + p
    return sec


def _fmt_hours_minutes(seconds: float) -> str:
    """Format seconds as 'Xh Ym' (e.g. '12h 34m')."""
    total = int(round(seconds))
    h, rem = divmod(total, 3600)
    m = rem // 60
    if h:
        return f"{h}h {m}m"
    return f"{m}m"


def _fmt_pace(sec_per_km: float) -> str:
    """Format seconds/km as 'M:SS' (e.g. '5:32'), or '—' when absent."""
    if sec_per_km is None or sec_per_km <= 0:
        return "—"
    total = int(round(sec_per_km))
    m, s = divmod(total, 60)
    return f"{m}:{s:02d}"


def _activity_date(activity: dict) -> datetime | None:
    """Local activity timestamp (falls back to UTC start_date).

    If the primary field (start_date_local) exists but is unparseable, try the
    secondary field (start_date) before giving up.
    """
    candidates = [
        activity.get("start_date_local"),
        activity.get("start_date"),
    ]
    for raw in candidates:
        if not raw:
            continue
        try:
            return datetime.strptime(str(raw), "%Y-%m-%d %H:%M:%S")
        except ValueError:
            continue
    return None


def _runs(data: dict) -> list[dict]:
    """Activities (already filtered to Run), newest first.

    Upstream order is oldest-first; sort defensively so callers can rely on
    runs[0] being the most recent activity.
    """
    runs = list(data.get("activities") or [])

    def _sort_key(a: dict) -> datetime:
        return _activity_date(a) or datetime.min  # unparseable dates sort oldest

    return sorted(runs, key=_sort_key, reverse=True)


# ---------------------------------------------------------------------------
#  Yearly table
# ---------------------------------------------------------------------------


def _year_table(data: dict) -> str:
    runs = _runs(data)
    if not runs:
        return _no_data()

    years: dict[int, dict] = {}
    for a in runs:
        dt = _activity_date(a)
        if dt is None:
            continue
        y = years.setdefault(dt.year, {"n": 0, "km": 0.0, "sec": 0.0, "elev": 0.0, "hrs": []})
        y["n"] += 1
        y["km"] += float(a.get("distance") or 0) / 1000.0
        y["sec"] += _parse_moving_time(a.get("moving_time")) or 0
        y["elev"] += float(a.get("elevation_gain") or 0)
        if a.get("average_heartrate"):
            y["hrs"].append(float(a["average_heartrate"]))

    rows = []
    for year in sorted(years, reverse=True):
        y = years[year]
        pace = _fmt_pace(y["sec"] / y["km"]) if y["km"] else "—"
        hr = f"{sum(y['hrs']) / len(y['hrs']):.0f}" if y["hrs"] else "—"
        rows.append(
            f"<tr><td>{year}</td><td style='text-align:right'>{y['n']}</td><td style='text-align:right'>{y['km']:.1f}</td><td style='text-align:center'>{pace}</td><td style='text-align:center'>{hr}</td><td style='text-align:right'>{y['elev']:.0f}</td></tr>"  # noqa: E501
        )

    return (
        '<div class="md-typeset__scrollwrap"><div class="md-typeset__table">'
        '<table><thead><tr><th>Year</th><th style="text-align:right">Runs</th>'
        '<th style="text-align:right">Distance (km)</th><th style="text-align:center">Avg Pace</th>'
        '<th style="text-align:center">Avg HR</th><th style="text-align:right">Elevation (m)</th></tr></thead>'  # noqa: E501
        f"<tbody>{''.join(rows)}</tbody></table></div></div>"
    )


# ---------------------------------------------------------------------------
#  Monthly chart (Mermaid) — distance bar + avg HR line, merged on one plot
# ---------------------------------------------------------------------------


def _monthly_chart(data: dict) -> str:
    """Merged bar (km) + line (bpm) chart for the latest activity year.

    xychart-beta has a single y-axis and does not accept null values (v10.9),
    so the x-axis covers only months with activities — every bar/line slot
    then has a real value.
    """
    runs = _runs(data)
    if not runs:
        return _no_data()

    latest = _activity_date(runs[0])
    if latest is None:
        return _no_data()
    year = latest.year

    months: dict[int, dict] = {}
    for a in runs:
        dt = _activity_date(a)
        if dt is None or dt.year != year:
            continue
        m = months.setdefault(dt.month, {"km": 0.0, "hrs": []})
        m["km"] += float(a.get("distance") or 0) / 1000.0
        if a.get("average_heartrate"):
            m["hrs"].append(float(a["average_heartrate"]))

    if not months:
        return f"> No runs in {year} yet"

    ordered = sorted(months)
    labels = ", ".join(f'"{_MONTHS[m - 1]}"' for m in ordered)
    bars = ", ".join(f"{months[m]['km']:.1f}" for m in ordered)
    # every activity today carries HR, so the 0 fallback is defensive only:
    # mermaid 10.9 xychart rejects null values, so the month shows as 0
    lines = ", ".join(
        f"{sum(months[m]['hrs']) / len(months[m]['hrs']):.0f}" if months[m]["hrs"] else "0"
        for m in ordered
    )
    km_max = max(months[m]["km"] for m in ordered)
    hr_max = max(
        (sum(months[m]["hrs"]) / len(months[m]["hrs"]) for m in ordered if months[m]["hrs"]),
        default=0,
    )
    y_max = int((max(km_max, hr_max + 10) // 5 + 1) * 5)

    return (
        "```mermaid\n"
        "xychart-beta\n"
        f'    title "Monthly Distance (km) & Avg HR (bpm) — {year}"\n'
        f"    x-axis [{labels}]\n"
        f'    y-axis "km / bpm" 0 --> {y_max}\n'
        f"    bar [{bars}]\n"
        f"    line [{lines}]\n"
        "```"
    )


# ---------------------------------------------------------------------------
#  Activity tables (recent / all) — shared header + rows, newest first
# ---------------------------------------------------------------------------


def _splits_cfg_attrs(splits_url: str) -> str:
    """data-* attrs for client-side splits loading (bucket URL + map config)."""
    attrs = []
    if splits_url:
        attrs.append(f"data-splits-url='{html.escape(splits_url, quote=True)}'")
    if _PMTILES_URL:
        attrs.append(f"data-pmtiles='{html.escape(_PMTILES_URL, quote=True)}'")
    if _GLYPHS_URL:
        attrs.append(f"data-glyphs='{html.escape(_GLYPHS_URL, quote=True)}'")
    if _SUPPORTED_REGIONS:
        attrs.append(
            "data-regions='" + html.escape(json.dumps(_SUPPORTED_REGIONS), quote=True) + "'"
        )
    return " ".join(attrs)


def _activity_table(runs: list[dict], splits_url: str = "") -> str:
    """HTML table of activities; splits/route data is loaded client-side.

    The build has no splits access, so pace uses the elapsed moving time from
    running.yml. Each row carries data-run-id/data-when/data-name/data-km so
    running-route.js can look up the R2 splits copy, correct the pace, and
    lazily create the 📊 pace / 🗺️ route dialogs on click (no hidden <dialog>
    nodes in the DOM).
    """
    cfg_attrs = _splits_cfg_attrs(splits_url)
    rows = []

    for a in runs:
        dt = _activity_date(a)
        sec = _parse_moving_time(a.get("moving_time"))
        dur = _fmt_hours_minutes(sec) if sec else "—"
        when_dur = f"{dt.strftime('%Y-%m-%d %H:%M')} · {dur}" if dt else "—"
        name = html.escape(str(a.get("name") or "—"), quote=True)
        when_dur_esc = html.escape(when_dur, quote=True)
        km = float(a.get("distance") or 0) / 1000.0
        pace = _fmt_pace(sec / km) if sec and km else "—"
        hr = f"{float(a['average_heartrate']):.0f}" if a.get("average_heartrate") else "—"

        rid = a.get("run_id")
        data_attrs = (
            f" data-run-id='{rid}' data-when='{when_dur_esc}' data-name='{name}' data-km='{km:.2f}'"
            if rid is not None
            else ""
        )
        rows.append(
            f"<tr{data_attrs}><td>{when_dur}</td><td style='text-align:right'>{km:.2f}</td>"
            f"<td data-pace-cell style='text-align:center'>{pace}</td><td style='text-align:center'>{hr}</td></tr>"  # noqa: E501
        )

    return (
        '<p style="font-size:0.85em;color:var(--md-default-fg-color--light)">Avg HR = 平均心率 ｜ Pace = 每公里移动配速（min/km）</p>'  # noqa: E501
        '<div class="md-typeset__scrollwrap"><div class="md-typeset__table">'
        f"<table{(' ' + cfg_attrs) if cfg_attrs else ''}><thead><tr><th>日期 · 时间 · 时长</th>"
        "<th style='text-align:right'>距离 (km)</th><th style='text-align:center'>配速</th><th style='text-align:center'>心率</th></tr></thead>"  # noqa: E501
        f"<tbody>{''.join(rows)}</tbody></table></div></div>"
    )


# ---------------------------------------------------------------------------
#  Recent activities table — last 2 weeks
# ---------------------------------------------------------------------------


def _recent(data: dict, splits_url: str = "") -> str:
    runs = _runs(data)
    if not runs:
        return _no_data()

    # Last 5 activities
    rows = runs[:5]
    return _activity_table(rows, splits_url)


# ---------------------------------------------------------------------------
#  All activities table — collapsed by default
# ---------------------------------------------------------------------------


def _all(data: dict, splits_url: str = "") -> str:
    runs = _runs(data)
    if not runs:
        return _no_data()

    table = _activity_table(runs, splits_url)
    # Content is HTML (no dialogs to hoist out) — indent inside the ??? block
    return f'??? "🗂️ All Activities ({len(runs)})"\n' + "\n".join(
        f"    {line}" for line in table.rstrip().split("\n")
    )


# ---------------------------------------------------------------------------
#  Calendar heatmap — GitHub-style daily running grid
# ---------------------------------------------------------------------------


def _calendar_heatmap(data: dict, year: int | None = None) -> str:
    """GitHub-style calendar heatmap of daily running distance (km).

    Returns an HTML/CSS grid: 7 rows (Mon–Sun) × ~53 columns (weeks),
    each cell colored by total distance on that day. Pure CSS tooltip
    on hover shows the date + distance.
    """
    runs = _runs(data)
    if not runs:
        return _no_data()

    # Determine year (default: latest)
    latest = _activity_date(runs[0])
    if latest is None:
        return _no_data()
    if year is None:
        year = latest.year

    # Filter runs for the year and aggregate by date
    daily: dict[str, float] = {}
    for a in runs:
        dt = _activity_date(a)
        if dt is None or dt.year != year:
            continue
        key = dt.strftime("%Y-%m-%d")
        daily[key] = daily.get(key, 0) + float(a.get("distance") or 0) / 1000.0

    if not daily:
        return f"> {year} 年暂无跑步数据"

    # Summary line: total runs, total distance, total days
    total_runs = sum(
        1 for a in runs if _activity_date(a) is not None and _activity_date(a).year == year
    )
    total_km = sum(daily.values())
    total_days = len(daily)
    summary = f"{total_runs} 次跑步 · {total_km:.0f} 公里 · {total_days} 天"

    # Grid boundaries
    start = datetime(year, 1, 1)
    end = datetime(year, 12, 31)
    grid_start = start - timedelta(days=start.weekday())  # Monday of week 1
    grid_end = end + timedelta(days=6 - end.weekday())  # Sunday of last week
    num_weeks = (grid_end - grid_start).days // 7 + 1

    cell_w = 11  # cell width (px)
    cell_gap = 1  # gap between cells (px)
    col_w = cell_w + cell_gap  # total column width
    label_w = 40  # day label column width (px)
    cell_r = 2  # border radius

    # Color levels (km): cell classes (rh-cell / l1–l4) are styled in
    # docs/assets/stylesheets/running.css — palette mirrors the Moment stats
    # heatmap with [data-md-color-scheme="slate"] dark overrides.
    levels = [0, 1, 2, 5, 999]

    def _level(km: float) -> int:
        for i, threshold in enumerate(levels):
            if km <= threshold:
                return i
        return len(levels) - 1

    day_labels = ["", "Mon", "", "Wed", "", "Fri", ""]
    months_short = [
        "Jan",
        "Feb",
        "Mar",
        "Apr",
        "May",
        "Jun",
        "Jul",
        "Aug",
        "Sep",
        "Oct",
        "Nov",
        "Dec",
    ]

    # Build month label positions: (week_index, label) for months in the target year
    # Find the grid column (week) that contains the 1st of each month
    month_positions: list[tuple[int, str]] = []
    for m in range(1, 13):
        first_day = datetime(year, m, 1)
        # Which week column does this day fall in?
        days_from_start = (first_day - grid_start).days
        if days_from_start >= 0:
            w = days_from_start // 7
            month_positions.append((w, months_short[m - 1]))

    # ── HTML ──
    lines = []
    lines.append(
        '<div class="running-heatmap" '
        'style="font-family: -apple-system, BlinkMacSystemFont, sans-serif; '
        'font-size: 12px; overflow-x: auto; overflow-y: hidden;">'
    )
    # Cell color classes come from docs/assets/stylesheets/running.css
    # (loaded site-wide, so no per-page <style> block is needed here).
    lines.append(
        f'  <div style="font-size:0.9em;color:var(--md-default-fg-color--light);margin-bottom:0.5em">{summary}</div>'  # noqa: E501
    )

    # Month labels: absolute positioning at exact column positions
    lines.append(
        f'  <div style="position: relative; margin-left: {label_w}px; '
        f"height: 15px; font-size: 10px; color: {_LABEL_FG}; "
        f'white-space: nowrap;">'
    )
    for w, label in month_positions:
        left = w * col_w
        lines.append(
            f'    <div style="position: absolute; left: {left}px; '
            f'top: 0; line-height: 15px;">{label}</div>'
        )
    lines.append("  </div>")

    # Day grid: CSS grid, 1 label column + 53 week columns
    lines.append(
        f'  <div style="display: inline-grid; '
        f"grid-template-columns: {label_w}px repeat({num_weeks}, {col_w}px); "
        f'gap: 0;">'
    )

    # Rows: day labels + cells
    for day_idx in range(7):
        label = day_labels[day_idx]
        if label:
            lines.append(
                f'    <div style="font-size: 10px; color: {_LABEL_FG}; '
                f'line-height: {cell_w}px; text-align: left;">{label}</div>'
            )
        else:
            lines.append(f'    <div style="height: {cell_w}px;"></div>')

        for w in range(num_weeks):
            d = grid_start + timedelta(weeks=w, days=day_idx)
            key = d.strftime("%Y-%m-%d")
            km = daily.get(key, 0)
            lvl = _level(km)
            cls = "rh-cell" + (f" l{lvl}" if lvl else "")
            title = f"{key}: {km:.1f} km" if km > 0 else key
            lines.append(
                f'    <div class="{cls}" '
                f'style="width: {cell_w}px; height: {cell_w}px; '
                f'border-radius: {cell_r}px; cursor: default;" '
                f'title="{title}"></div>'
            )

    lines.append("  </div>")

    # Legend row
    lines.append(
        '  <div style="display: flex; align-items: center; gap: 3px; '
        f'margin-top: 8px; font-size: 10px; color: {_LABEL_FG};">'
    )
    lines.append("    <span>Less</span>")
    for lvl in range(len(levels)):
        cls = "rh-cell" + (f" l{lvl}" if lvl else "")
        lines.append(
            f'    <div class="{cls}" '
            f'style="width: {cell_w}px; height: {cell_w}px; border-radius: {cell_r}px;"></div>'
        )
    lines.append("    <span>More</span>")
    lines.append("  </div>")

    lines.append("</div>")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
#  Sync note
# ---------------------------------------------------------------------------


def _splits_bucket_url() -> str:
    """Construct the R2 bucket URL for splits.json from mkdocs.yml config."""
    try:
        from shared.mkdocs_yaml import load_extra

        bucket = load_extra("bucket", label="running-macros")
        if not bucket:
            return ""
        for m in bucket.get("mappings") or []:
            if "running" in str(m.get("prefix", "")):
                base = str(m.get("base_url", "")).rstrip("/")
                dk = (bucket.get("running") or {}).get("data_key", "splits.json")
                if base:
                    return f"{base}/{dk}"
    except Exception:
        pass
    return ""


def _synced_note(data: dict) -> str:
    synced_at = data.get("synced_at")
    if not synced_at:
        # never claim there is no data just because synced_at is missing
        # (only reachable via hand-edited files)
        return "> ⚠️ 未记录同步时间 — 运行 `poe sync-running` 更新。"
    return f"> 🕓 数据同步于 `{synced_at}` — 运行 `poe sync-running` 更新。"


# ---------------------------------------------------------------------------
#  Public macros
# ---------------------------------------------------------------------------


def define_env(env):
    """Register running tracking macros."""
    global _PMTILES_URL, _GLYPHS_URL, _SUPPORTED_REGIONS
    try:
        moment_cfg = (env.conf.get("extra", {}) or {}).get("moment", {}) or {}
        map_cfg = moment_cfg.get("map") or {}
        _PMTILES_URL = str(map_cfg.get("pmtiles_prefix", "") or "")
        _GLYPHS_URL = str(map_cfg.get("glyphs_url", "") or "")
        # Read supported regions (reset both so repeated define_env calls don't duplicate)
        _SUPPORTED_REGIONS = []
        for name, rcfg in (map_cfg.get("regions") or {}).items():
            bbox = rcfg.get("bbox")
            if bbox and len(bbox) == 4:
                _SUPPORTED_REGIONS.append([float(v) for v in bbox])
    except Exception:
        pass

    @env.macro
    def running_year_table():
        """Yearly stats: year, runs, distance, avg pace, avg HR, elevation."""
        return _year_table(_load_data(env))

    @env.macro
    def running_monthly_chart():
        """Merged Mermaid chart: monthly distance (bar) + avg heart rate (line)."""
        return _monthly_chart(_load_data(env))

    @env.macro
    def running_recent():
        """Table of the last 5 activities; splits loaded client-side from R2."""
        data = _load_data(env)
        return _recent(data, _splits_bucket_url())

    @env.macro
    def running_all():
        """Collapsed table of all activities; splits loaded client-side."""
        data = _load_data(env)
        return _all(data, _splits_bucket_url())

    @env.macro
    def running_synced_at():
        """Note showing when the local data was last synced."""
        return _synced_note(_load_data(env))

    @env.macro
    def running_calendar_heatmap(year=None):
        """GitHub-style calendar grid of daily running distance.

        Args:
            year: 4-digit year (default: latest year with data).
        """
        return _calendar_heatmap(_load_data(env), year)

    @env.macro
    def running_splits_note():
        """Note updated client-side once splits.json is fetched from R2."""
        return "> 💡 <span id='running-splits-note'>配速数据由浏览器从云端加载…</span>"

    @env.macro
    def running_recent_routes(max_routes=10):
        """Inline map of the most recent N routes, rendered client-side.

        The container only carries the recent runs + config (bucket URL,
        PMTiles/glyphs/regions); running-route.js fetches splits.json from R2,
        picks the dominant region and draws the map. Date-independent, so the
        view is not frozen at build time.

        Args:
            max_routes: max routes to consider (default 10).
        """
        data = _load_data(env)
        runs = _runs(data)[:max_routes]
        recent = []
        for a in runs:
            dt = _activity_date(a)
            recent.append({"run_id": a.get("run_id"), "date": dt.strftime("%m-%d") if dt else "?"})
        runs_json = html.escape(json.dumps(recent, ensure_ascii=False), quote=True)
        return (
            f'<div id="inline-routes-map" style="width:100%;height:400px;border-radius:8px;overflow:hidden;margin:0.5em 0" '  # noqa: E501
            f"data-runs='{runs_json}' "
            f"{_splits_cfg_attrs(_splits_bucket_url())}></div>"
            f'<div id="inline-routes-legend" style="display:flex;flex-wrap:wrap;gap:0.3em 1em;padding:0.3em 0;font-size:12px;color:var(--md-default-fg-color--light)"></div>'  # noqa: E501
        )
