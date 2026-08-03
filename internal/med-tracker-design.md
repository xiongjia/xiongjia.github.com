# Med Tracker — Design Document

> A medication memory-anchor tool that solves the real problem: not "forgetting
> to take medicine" but **"forgetting whether it was taken"**. The core principle
> is **record-as-confirmation** — tapping the button and swallowing the pill are
> fused into a single action, leaving an undeniable timestamp as evidence.

## Overview

A zero-dependency, pure-frontend widget embedded in the Tools section of the
site (`docs/notes/tools/med-tracker.md`). All data lives in browser
`localStorage` under a single key (`med_tracker_v1`) and never leaves the
device. The UI is a flat, compact card layout: a status card, one big confirm
button, today's record list, and a 7-day history strip.

## Data Layer (`localStorage`)

- **Key**: `med_tracker_v1`
- **Value**: JSON object mapping date keys to ISO-8601 timestamp arrays

```json
{
  "2026-08-04": ["2026-08-04T08:15:32.123Z", "2026-08-04T12:30:15.456Z"],
  "2026-08-03": ["2026-08-03T08:20:10.789Z"],
  "2026-08-02": []
}
```

- **Key format**: `YYYY-MM-DD` (local time, via `getTodayKey()`)
- **Entry format**: `Date.toISOString()` (UTC, preserves full precision)
- Records are always **appended chronologically**; array index + 1 is the
  dose ordinal ("第 N 次").
- **Read cleaning**: on the initial read, day keys not matching `YYYY-MM-DD`
  and entries that are not ISO-8601 timestamp strings (parseable) are
  dropped; a day key whose array becomes empty after filtering is removed
  entirely. Later reads hit the in-memory cache, which is clean by
  construction.

### Persistence semantics

| Action                | Data kept? |
| --------------------- | ---------- |
| Refresh page          | ✅         |
| Close browser         | ✅         |
| Reboot machine        | ✅         |
| Clear browser data    | ❌         |
| Change device/browser | ❌         |

All reads/writes are wrapped in `try/catch`: the module keeps an in-memory
cache. `getData()` returns the cache after the first successful read (and
also caches `{}` when storage is unreadable); `saveData()` updates the cache
and returns a boolean — `true` on a successful `localStorage` write, `false`
when `setItem` throws. If `localStorage` is blocked (privacy mode, quota),
the widget degrades gracefully to in-memory operation for the current
session; failed writes surface a warning toast so the user knows the data is
session-only.

## Core Logic

### `recordDose()` — the primary write path

1. Load data, ensure today's key exists
1. Compute `now` and the last recorded timestamp
1. **5-minute dedup**: if `now - lastDose < 5 min`, show a toast
   ("5 分钟内刚吃过（N 分钟前），无需重复", elapsed minutes omitted
   when < 1 min) and abort — prevents accidental double-taps from
   polluting the record
1. Otherwise append `now.toISOString()`, persist, toast confirmation, re-render

### Time formatting

- Records display as `HH:MM:SS` (seconds precision) to remove
  "was that today or yesterday?" ambiguity
- `font-variant-numeric: tabular-nums` keeps digits monospaced-aligned
- Date header renders as `YYYY年M月D日` (Chinese UI)

### `undoLast()` — remove the most recent dose

1. Load data; bail out if today has no records
1. `list.pop()` the last entry, then re-render
1. If the list becomes empty, the day key is deleted (storage stays clean)
1. Toast shows the removed time; **no confirmation** — deleting just the
   newest entry is low-risk

### `clearToday()` — wipe all of today's records

1. Guard: bail out if today has no records
1. `window.confirm()` — destructive and irreversible, so a second
   confirmation is required
1. Delete today's key, persist, re-render, toast

### Day rollover

`render()` recomputes the "today" key on every call; the page also listens to
`visibilitychange` and re-renders when the tab regains focus, so crossing
midnight while the tab is hidden resets the status card to
"今日尚未服药" without manual refresh. For always-on displays (e.g. a tablet
mounted next to the pill box), a `setTimeout` chain scheduled for the next
midnight re-renders even while the tab stays visible. A `storage` event
listener invalidates the cache and re-renders when another tab writes, so
multiple open tabs stay in sync. History is never cleared.

## UI Layout

### Page structure (top-to-bottom)

```
📅 date header
💊 status card        → icon + "今日已服药 N 次" + "上次：HH:MM:SS"
[ ✅ 确认已服药 ]      → full-width primary button
今日记录              → today's doses, newest first, "第 N 次" badge
近 7 天               → 7 day cells: dot + weekday label + count
```

### Status card

Two states, differentiated by **border color + tinted background + icon**:

| State               | Icon | Border/bg                                  |
| ------------------- | ---- | ------------------------------------------ |
| Not taken (default) | 💊   | neutral border, faint red-tinted icon disc |
| Taken               | ✓    | green border + green tinted bg             |

Transitions are 0.3s ease for a soft state change.

### Confirm button

- Full width, `padding: 0.875rem`, rounded 10px
- Background `--md-primary-fg-color`, text `--md-primary-bg-color`; hover
  dims via opacity
- `:focus-visible` outline uses `--md-accent-fg-color` for keyboard a11y

### Today's record list

- Each row: time (tabular-nums, left) + badge "第 N 次" (green pill, right)
- Rows rendered with `.map(...).reverse()` → **newest first**
- Empty state: centered muted "今天还没有服药记录"
- Section header carries two mini-buttons (`↩ 撤销上次`, `🗑 清空今日`),
  shown **only while today has ≥1 record** (`.med-hide` toggled in
  `render()`):
  - `↩ 撤销上次` — pops the newest entry, no confirmation
  - `🗑 清空今日` — deletes all of today's records after `confirm()`

### 7-day history strip

Seven flex cells (`flex: 1`), left-to-right oldest→today. Each cell:

- **Dot** (10px circle), color semantics:
  - `taken` (green): that day has ≥1 dose
  - `missed` (light red): past day, zero doses
  - `pending` (border gray): today, not yet recorded
- **Label**: weekday character (日一二三四五六) or "今天"
- **Count**: `N次` / `未` (past, none) / `-` (today, none)
- Today's cell gets a highlighted border

### Toast

Fixed at bottom-center, slides up on `.show`, auto-hides after 2s,
`pointer-events: none`, `role="status"` + `aria-live="polite"` for
screen-reader announcements.

## Styling Conventions

- Lives in the shared `docs/assets/stylesheets/tools.css` (alongside Ramen
  Timer `.rt-*`), keyed by `.med-*` prefix
- Theme tokens use Material for MkDocs CSS variables
  (`--md-default-fg-color*`, `--md-typeset-color`, `--md-primary-fg-color`,
  `--md-primary-bg-color`, `--md-accent-fg-color`)
- Semantic green/red are scoped custom properties on `.med-tracker`
  (`--med-positive`, `--med-warn-tint`, `--med-missed-dot`,
  `--med-row-bg`), with `[data-md-color-scheme="slate"]` overrides — no
  `prefers-color-scheme` media query needed (Material applies
  `data-md-color-scheme` on `<body>`)
- Flat design: no shadows, compact radii (8–12px), neutral row tint
- `@media (max-width: 480px)` tightens history gaps for narrow phones

## Edge Cases

- **Double tap within 5 min**: blocked by dedup; the toast states
  "5 分钟内刚吃过（N 分钟前），无需重复" (elapsed minutes omitted when
  < 1 min)
- **localStorage unavailable**: all get/set in `try/catch`, degrade to memory
- **Day rollover while hidden**: `visibilitychange` re-render
- **Corrupt stored JSON**: `JSON.parse` guarded, falls back to `{}`;
  non-object payloads (string/array/null), non-`YYYY-MM-DD` keys, and
  non-ISO entries are dropped on read, so `render()` / `recordDose()`
  never crash
- **Today with zero doses**: dot shown as `pending` (gray), count `-`
- **Midnight boundary on history**: yesterday's cell flips from "今天"
  (pending) to a real weekday; `missed` only applies to past days
- **Undo with no records**: guarded — silently no-ops, buttons stay hidden
- **Clear with no records**: guarded — no-ops without showing the dialog
- **Clear cancellation**: user dismisses `confirm()` → nothing is deleted
- **Timezone change (accepted limitation)**: timestamps are stored as UTC
  ISO and rendered in the current timezone, so after a device timezone
  change old records' wall-clock times shift. Deliberately not addressed
  (home pill-box use); a fix would change the data schema.

## Dependencies

| Component       | Usage                         |
| --------------- | ----------------------------- |
| Vanilla JS      | All state + rendering         |
| `localStorage`  | Persistence (guarded)         |
| Material tokens | Light/dark theme via CSS vars |
| No JS libraries | Zero external dependencies    |

## Extensions (future)

| Direction  | Idea                                                     |
| ---------- | -------------------------------------------------------- |
| Multi-med  | Add med names, track several meds at once                |
| Dosage     | Record the dose per intake                               |
| Export     | CSV/JSON export for doctor visits                        |
| Reminders  | `setInterval` in-page reminder (no system notifications) |
| Statistics | SVG month-view adherence chart                           |

## Related

- [Tools index](../docs/notes/tools/index.md) — site listing
- [Ramen Timer Tool](../docs/notes/tools/ramen-timer.md) — sibling tool,
  same `.tools.css` shared stylesheet
- [Architecture](./architecture.md)
