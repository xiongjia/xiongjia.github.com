# Weight Tracker — Design Document

> Personal weight tracking with macros-generated tables and Mermaid trend charts.

## Overview

Four-tier architecture:

- **Data layer**: YAML file (`docs/health/data/weight.yml`) — the only file to maintain
- **Macro layer**: Python module (`docs/health/macros/weight_macros.py`) — renders info cards, tables, charts
- **Aggregator**: `health_macros.py` — combines weight and retirement macros into one entry point for MkDocs macros plugin
- **Tool layer**: `scripts/add_weight_week.py` — adds new empty weeks to the YAML file

## Data Layer (`weight.yml`)

```yaml
# Height in cm (set once)
cm: 176

# Anchor date: Monday of week 1
start_date: "2026-07-27"

# 7 days per week; null for skipped days
weeks:
  # Week 1 — Mon 2026-07-27
  - days: [null, 82.35, 81.50, null, null, null, null]

# i18n labels (currently Chinese UI)
labels:
  height: 身高
  latest: 最新体重
  bmi: BMI
  healthy_range: 健康体重范围
  # ... (see actual file for full list)
```

### Data Validation

- `cm` (height) is required — missing triggers error message
- `start_date` is required for date calculation — missing triggers warning
- `weeks[]` can be empty (shows "No data yet")
- Days are `null` or a float weight value

### Date Calculation

`start_date` is the Monday of week 1. Each subsequent week is calculated as
`start_date + 7 * week_index`. The `add_weight_week.py` tool preserves this
by computing the next Monday from `start_date`.

## Macro Layer (`weight_macros.py`)

Four macros registered via `define_env(env)`:

### `weight_info()` — Summary Cards

Renders info cards using CSS class `.weight-cards` / `.weight-card` (styled
by `weight.css`):

- **Height**: fixed `cm` value
- **Latest weight**: last non-null value from all weeks
- **BMI**: calculated + Chinese classification label (colored)
- **Healthy range**: 18.5×h² ~ 23.9×h²

Plus a BMI formula/standard note line with color-coded ranges.

### `weight_progress()` — BMI Spectrum Bar

Visual progress bar from BMI 14 to 32 with 4 color zones:

- Blue (< 18.5, underweight)
- Green (18.5–23.9, normal)
- Orange (24–27.9, overweight)
- Red (≥ 28, obese)

A triangle marker (▼) indicates current BMI position. Labels at 14, 18.5, 24,
28, 32.

### `weight_table()` — Weekly Details (Markdown)

Two collapsible accordion sections:

1. **Last 4 Weeks** (expanded by default):

   - Daily values per day-of-week (Chinese day labels)
   - Weekly average (bold)
   - BMI for the week (colored by classification)

1. **All Weeks** (collapsed):

   - Week number + date range
   - Weekly average
   - BMI (colored)
   - Change vs previous week (↑/↓/→ with delta)

### `weight_chart()` — Mermaid Trend Chart

Renders `xychart-beta` Mermaid block:

- X-axis: week date ranges
- Y-axis: weight kg (auto-scaled with 0.5 padding)
- Line: weekly average values

Requires at least 2 weeks with data — otherwise shows a placeholder message.

### BMI Calculation

```
BMI = weight(kg) / (height(m)²)
```

Chinese standard classification:

| Category    | Range     | CSS Color        |
| ----------- | --------- | ---------------- |
| Underweight | < 18.5    | Blue `#2196f3`   |
| Normal      | 18.5–23.9 | Green `#4caf50`  |
| Overweight  | 24–27.9   | Orange `#ff9800` |
| Obese       | ≥ 28      | Red `#f44336`    |

## Aggregator (`health_macros.py`)

A lightweight module that imports `weight_macros.py` and `retire_macros.py` at
runtime and delegates `define_env(env)` to both. This is the module referenced
in `mkdocs.yml` → `plugins.macros.module_name`.

## Tool Layer (`add_weight_week.py`)

A CLI tool to add empty weeks to `weight.yml`:

```bash
uv run poe add-weight-week        # add 1 empty week
uv run poe add-weight-week -- 3   # add 3 empty weeks at once
```

Key design decisions:

- **Text-level manipulation**: Reads file content as string (not YAML
  serialize/deserialize) to preserve comments and formatting
- **Week numbering**: Counts existing `- days:` occurrences to determine next
  week number
- **Date labeling**: If `start_date` exists, computes the correct Monday date
  for each new week (aligned to `start_date.weekday()` → Monday)
- **Insertion point**: Places new entries before `# Display labels (i18n)`
  section; appends to end if that marker doesn't exist

## UI Layout

### Page Structure (top-to-bottom)

The `weight.md` page is assembled from four macros interleaved with horizontal rules:

```
{{ weight_info() }}       → info cards + BMI formula note
______________________________________________________________________  (hr)
{{ weight_progress() }}   → BMI spectrum progress bar
______________________________________________________________________  (hr)
{{ weight_table() }}      → last 4 weeks (expanded) + all weeks (collapsed)
______________________________________________________________________  (hr)
{{ weight_chart() }}      → Mermaid trend chart
```

### weight_info() — Summary Cards

**Cards** (`.weight-cards`):

- `display: flex; flex-wrap: wrap; gap: 12px; margin: 1em 0`
- Each card (`.weight-card`): `flex: 1 1 140px; min-width: 120px;` — wraps to next
  row when container is narrower than 2 card widths
- Card inner structure: `.label` (0.78em, muted color) + `.value` (1.25em, bold, primary color)
- Typically renders 4 cards in one row: Height → Latest Weight → BMI → Healthy Range

**Note line** (`.weight-note`):

- `display: flex; flex-wrap: wrap; gap: 8px; align-items: center; font-size: 0.82em`
- Content: `BMI = ...` formula text, then `|` separator, then 4 color-coded standard labels
- Each standard label uses inline `style="color: ..."` matching its BMI zone color
  (blue → green → orange → red)

### weight_progress() — BMI Spectrum Bar

**Structure** (`.weight-progress`):

```
[h4] BMI Progress
[current] BMI: 24.5 (Overweight)
[bar container: .weight-bmi-bar]
  [.bmi-segment] * 4  ← absolute positioned, colored zones
  [.bmi-marker] ▼     ← absolute positioned at current BMI
[.weight-bmi-labels]
  14    18.5    24    28    32
```

**Bar container** (`.weight-bmi-bar`):

- `position: relative; width: 100%; height: 20px; border-radius: 10px; overflow: hidden; background: #e0e0e0`
- Contains 4 `.bmi-segment` divs, each `position: absolute; top: 0; height: 100%`,
  with `left` and `width` computed as percentages of the 14–32 BMI range
- Segment colors: `#2196f3` (blue, \<18.5), `#4caf50` (green, 18.5–23.9),
  `#ff9800` (orange, 24–27.9), `#f44336` (red, ≥28)

**Marker** (`.bmi-marker`):

- `position: absolute; top: -6px; transform: translateX(-50%)` — sits above the bar
- ▼ character, `font-size: 1.2em`, with subtle text-shadow for contrast
- Position computed as `(bmi - 14) / (32 - 14) * 100%`

**Labels** (`.weight-bmi-labels`):

- `display: flex; justify-content: space-between; font-size: 0.72em`
- Five ticks: 14, 18.5, 24, 28, 32

### weight_table() — Weekly Tables

Two MkDocs admonition accordions, rendered as standard Markdown tables
inside `???` / `???+` blocks (not custom HTML):

**Last 4 Weeks** (`???+`, expanded by default):

- Columns: Week | Daily Values (一二三四五六日) | Avg | BMI
- Row per week: `W{n} (MM-DD~MM-DD) | val1 / val2 / ... | **avg** | **BMI**`
- BMI cell colored via inline `<span style="color:...">` wrapping

**All Weeks** (`???`, collapsed):

- Columns: Week | Dates | Avg (kg) | BMI | vs Last Week
- Change column: `+0.50 ↑` / `-0.30 ↓` / `+0.00 →` with bold formatting

Both tables inherit MkDocs Material's built-in table and admonition styling —
no custom CSS needed.

### weight_chart() — Mermaid Trend Chart

Generated as a ```` ```mermaid ```` code block rendered by the mermaid2 plugin:

- The mermaid2 plugin injects `<script>` tags on pages containing mermaid blocks
- The `mermaid_assets.py` hook ensures the mermaid JS bundle is cached locally
- Chart width: 100% of content area (no fixed width)
- Chart height: auto-calculated by Mermaid based on data points
- Requires ≥2 data points; otherwise renders a plain text placeholder

### Dark Mode

Custom CSS classes (`.weight-cards`, `.weight-bmi-bar`, etc.) use Material
theme CSS variables (`--md-default-fg-color--lightest`, `--md-primary-fg-color`,
etc.) for backgrounds and text colors, so dark mode is handled automatically.

Only the BMI marker triangle has an explicit `[data-md-color-scheme="slate"]`
override for its `color` and `text-shadow` to ensure legibility against the
dark background.

## Dependencies

| Package  | Usage        |
| -------- | ------------ |
| `pyyaml` | YAML parsing |

Note: `Pillow` is used project-wide by `scripts/optimize_images.py` for
WebP conversion, but is not a direct dependency of the weight macros.

## Related

- [Retirement Countdown Design](./retirement-countdown-design.md)
- [Architecture](./architecture.md)
