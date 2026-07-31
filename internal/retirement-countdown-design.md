# Retirement Countdown — Design Document

> Chinese progressive retirement policy (effective 2025-01-01) calculator with
> visual countdown.

## Overview

Implements China's 渐进式延迟退休 (progressive delayed retirement) policy using
MkDocs macros for server-side rendering and JavaScript for client-side
interactivity. Displays info cards, progress bars, and a monthly grid
visualization from birth to retirement.

## Data Layer (`retire.yml`)

```yaml
nationality: china        # only china supported
birth_date: "1981-08-12"  # YYYY-MM-DD
gender: male              # male | female_cadre | female_worker
work_start_age: 22        # age when started working (default: 22)
expected_retire_age: 55   # optional, user's personal plan

labels:
  gender_male: 男性
  gender_female_cadre: 女干部
  gender_female_worker: 女工人
  # ... (see actual file for full i18n labels, currently Chinese UI)
```

## Calculation Logic

### Policy Rules

| Identity      | Original Age | Delay Rate           | Max Delay           | Final Age |
| ------------- | ------------ | -------------------- | ------------------- | --------- |
| Male          | 60           | 1 month per 4 months | 36 months (3 years) | 63        |
| Female cadre  | 55           | 1 month per 4 months | 36 months (3 years) | 58        |
| Female worker | 50           | 1 month per 2 months | 60 months (5 years) | 55        |

### Formula

```
Reform start: 2025-01-01
Original retirement: birth + original_age (month-aligned)

If original_retirement <= 2025-01:
    delay = 0 (unaffected by reform)
Else:
    elapsed_months = months_between(2025-01, original_retirement)
    delay = min(max_delay, elapsed_months / delay_rate)

Final retirement = original_retirement + delay
```

### Expected Retirement

An optional personal-plan field (`expected_retire_age`). Only meaningful when
the value is **less than** the original retirement age. If set, the system
renders a secondary progress bar and grid marker alongside the legal
retirement data.

## Macro Layer (`retire_macros.py`)

Two macros registered via `define_env(env)`:

### `retire_info()` — Summary

Two states:

**Retired** (current date ≥ final retirement):

- Celebration banner (🎉😊🎉) with retirement date and duration

**Not retired**:

- Info cards: birth date, identity, work start age, work years,
  original retirement age, delay months, expected retirement (if set),
  legal retirement age, retirement date
- **Dual progress bars**:
  - ⚖️ Legal retirement progress (primary color)
  - 🎯 Expected retirement progress (purple, `#7c4dff`)
    Each bar shows: months passed, total months, percentage, remaining time

### `retire_grid()` — Monthly Grid

A dense month-by-month grid from birth to final retirement:

- **Monthly header**: 12-month labels (1-12)
- **Year rows**: Year label on left, 12 cells for each month
- **Cell types** (colored by JS runtime):
  - `pre-work`: lighter shade (work start age boundary)
  - `filled`: months already lived (worked period)
  - `current`: 🚶‍➡️ emoji (current month)
  - `expected`: 📌 marker (expected retirement month, if different from legal)
  - `legal`: ⭐ marker (final legal retirement month)
  - Future months: transparent (default)
- **Legend**: Worked, Pre-work, Now, Future, Expected, Legal

## Client-Side Interactivity (`retire.js`)

A vanilla JS script that runs on `DOMContentLoaded`:

1. Reads `data-retire-total`, `data-birth-year`, `data-birth-month` from the
   `.retire-grid` element (set by the macro)
1. Computes current month index: `(currentYear - birthYear) * 12 + (currentMonth - birthMonth)`
1. Iterates all `.retire-cell[data-month-index]` cells:
   - Past cells (index < current): add `.filled` class
   - Current cell (index === current): add `.current` class + content `🚶‍➡️`
   - Future cells: leave empty (transparent, default CSS)
   - Pre-work cells (`.pre-work`): lighter fill color
   - All cells if retired (currentIdx >= lastIdx): all `.retired` class (green)

## UI Layout

### Page Structure (top-to-bottom)

The `retire.md` page is assembled from:

```
{{ retire_info() }}         → cards / banner + progress bars
______________________________________________________________________  (hr)
{{ retire_grid() }}         → legend + monthly grid
______________________________________________________________________  (hr)
### 📐 Retire Formula...   → static Markdown table & formula
```

### retire_info() — Cards & Progress

**Cards section** (`.retire-cards`):

- CSS `display: flex; flex-wrap: wrap; gap: 12px`
- Each card (`.retire-card`): `flex: 1 1 140px; min-width: 120px` — auto-wraps when
  the container is narrower than 2 card widths
- Content inside each card: `.label` (small, muted) + `.value` (large, bold, primary color)
- Items are rendered as a flat list of `<div>` pairs (no `<table>`)

**Banner** (`.retire-banner`, only shown when already retired):

- Full-width, centered text, `padding: 2em 1em`
- Gradient background (light mode: yellow `#fff9c4`→`#fff176`; dark mode: brown `#5d4e37`→`#3e3525`)
- Three lines: emoji (🎉😊🎉), title (2em, bold), subtitle (retire date + duration, muted)

**Progress section** (under cards):

- Dual progress sections stacked vertically:
  1. ⚖️ **Legal** heading → stats line (passed / total) → progress bar (10px height, rounded) → stats line (percentage / remaining)
  1. 🎯 **Expected** heading (only if `expected_retire_age` is set) → same sub-structure, bar in purple `#7c4dff`
- `.retire-progress-bar`: `width: 100%; height: 10px; background: --md-default-fg-color--lightest; border-radius: 5px; overflow: hidden`
- `.retire-progress-bar .fill`: `height: 100%; background: --md-primary-fg-color; transition: width 0.6s ease`
- `.retire-progress-stats`: `display: flex; justify-content: space-between; font-size: 0.85em`

### retire_grid() — Legend & Grid

**Legend** (`.retire-legend`):

- `display: flex; gap: 18px; flex-wrap: wrap; font-size: 0.82em`
- Each entry: color dot `.legend-dot` (11×11px, rounded) + label text

**Month header** (`.retire-month-header`):

- Flex row with a `.spacer` (3.5em, aligns with year labels) + 12 month labels (`.m-label`, 36px each, 0.55em font, centered)

**Grid** (`.retire-grid`):

- `display: flex; flex-direction: column; gap: 1px`
- **Each year row** (`.retire-year-row`):
  - `display: flex; align-items: center; gap: 6px`
  - Year label (`.retire-year-label`): 3.5em wide, right-aligned, tabular-nums, 0.7em
  - Cells container (`.retire-cells`): `display: flex; gap: 1px; flex-wrap: nowrap`
  - Individual cell (`.retire-cell`): 36×18px, `border-radius: 2px`, `border: 1px solid --md-default-fg-color--lightest`

**Cell color states** (applied by JS):

- Default (future): transparent background
- `.filled` (past): `#546e7a` (dark mode: `#78909c`)
- `.pre-work.filled` (before work age): lighter `#cfd8dc` (dark mode: `#546e7a`)
- `.retired` (all cells if past final date): green `#4caf50` (dark mode: `#66bb6a`)
- `.current`: no background, displays 🚶‍➡️ emoji
- `.retire-cell-last` (legal retirement month): ⭐ emoji, no background
- `.retire-cell-expected` (expected retirement month): 📌 emoji, no background

### Responsive Breakpoint

At `max-width: 600px`:

- Grid cells shrink from 36×18 → 28×14 px
- Month labels shrink from 36px → 28px width, font 0.55em → 0.45em
- Year labels shrink from 3.5em → 3em width, font 0.7em → 0.6em

### Dark Mode

All color tokens have explicit `[data-md-color-scheme="slate"]` overrides.
Layout properties (flex, gap, padding, margin) are shared — only colors change.
No `prefers-color-scheme` media query needed because Material for MkDocs
applies `data-md-color-scheme` on `<body>` via its palette toggle.

## Edge Cases

- **Birth date after reform start** (after 2025-01): Delay calculated
  proportionally
- **Birth date before reform** + original retirement before 2025-01: Zero delay
- **Already retired** (current ≥ final): Banner mode, no cards/progress
- **Invalid gender**: Error message listing valid options (`male`, `female_cadre`, `female_worker`)
- **Missing `retire.yml`**: Error message showing expected path
- **Invalid date format**: Error message showing expected format
- **Expected retirement ≥ original**: Ignored (silently falls back to legal only)

## Dependencies

| Component                | Usage                         |
| ------------------------ | ----------------------------- |
| `pyyaml`                 | Data file parsing             |
| MkDocs macros plugin     | Macro execution               |
| Vanilla JS               | Client-side grid filling      |
| No external JS libraries | Zero client-side dependencies |

## Related

- [Weight Tracker Design](./weight-tracker-design.md) — shares the aggregator
  `health_macros.py`
- [Architecture](./architecture.md)
