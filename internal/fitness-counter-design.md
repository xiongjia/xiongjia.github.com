# Fitness Counter — Design Document

> Version: 1.0
> Date: 2026-08-05
> Status: implemented
> Location: Notes site tools section (`docs/notes/tools/fitness.md`)

## 1. Overview

A lightweight daily workout counter for the Notes site. It tracks strength and
bodyweight exercises (sets × reps), estimates calorie expenditure, and shows
progress toward a daily goal. The tool is a static-page widget rendered by
vanilla JS; all data lives in the browser's `localStorage` and resets
automatically at midnight.

Core positioning:

- **Lightweight** — open the page and start counting, no configuration needed
- **Focused** — solves exactly three problems: counting, goal tracking, kcal
- **Instant feedback** — every action re-renders the summary and progress bar immediately

## 2. Page & File Layout

| Path                                  | Purpose                                                                                                                |
| ------------------------------------- | ---------------------------------------------------------------------------------------------------------------------- |
| `docs/notes/tools/fitness.md`         | Tool page: page heading, mount point `#fitness-app`, usage notes                                                       |
| `docs/assets/stylesheets/fitness.css` | Styles using Material theme variables + dark-mode overrides                                                            |
| `docs/assets/javascripts/fitness.js`  | Logic: state / render / calcKcal / storage, IIFE + `DOMContentLoaded`                                                  |
| `mkdocs.yml`                          | Registers both files in `extra_css` / `extra_javascript` **and** in the minify plugin's `css_files` / `js_files` lists |
| `docs/notes/tools/index.md`           | Added Fitness row to the tools listing table; removed it from the health index                                         |

> **Build pitfall (learned):** the minify plugin only processes files listed in
> its `css_files` / `js_files` arrays. New assets must be added there in
> addition to `extra_css` / `extra_javascript`, otherwise they are dropped from
> the production build.

## 3. UI Specification

### 3.1 Color system — adapted from Kimi tokens to Material theme

The source design (`gym-plan.md`) used Kimi design-system tokens
(`--kimi-color-*`). Because this site runs Material for MkDocs (primary: blue
grey, accent: deep purple) with automatic light/dark switching, every token was
mapped to Material CSS variables:

| Kimi token             | Material variable (light)                        | Usage                                        |
| ---------------------- | ------------------------------------------------ | -------------------------------------------- |
| `text-primary`         | `var(--md-default-fg-color)`                     | Titles, numbers, active tab                  |
| `text-secondary`       | `var(--md-default-fg-color--light)`              | Section headings                             |
| `text-tertiary`        | `var(--md-default-fg-color--lighter)`            | Labels, timestamps, placeholders             |
| `surface-muted`        | `var(--md-default-fg-color--lightest)`           | Card backgrounds                             |
| `border`               | `var(--md-default-fg-color--lightest)`           | Borders, dividers                            |
| `accent` (kcal number) | `var(--md-accent-fg-color)`                      | Kcal value (deep purple), data emphasis only |
| `positive` (goal met)  | semantic green: `#2e7d32` light / `#66bb6a` dark | Progress bar when goal reached               |
| `danger` (delete)      | semantic red: `#d32f2f` light / `#ef5350` dark   | Delete / clear buttons                       |

Dark mode is handled via `[data-md-color-scheme="slate"]` overrides for the two
semantic colors; all other colors come from Material variables and switch
automatically. No hardcoded values are used outside the semantic pairs.

Design principles:

- Black/white/grey base; accent reserved for data visualization (kcal)
- Semantic colors (positive/danger) only for meaning, never as base palette
- Card backgrounds use `surface-muted` (theme variable), never hardcoded white/grey

### 3.2 Typography & spacing

- All counters, times, and percentages use `font-variant-numeric: tabular-nums`
  so numbers do not jitter while updating
- Overview numbers: 28px / weight 500 / line-height 1.1
- Spacing scale: 4 / 8 / 12 / 16 / 20 / 24 / 32 px; module gap 20px, card
  padding 12–16px
- Border radius: cards 10px, inputs/buttons 8–10px, stepper buttons 8px
- Exercise picker is a **tab strip** (equal-width tabs, emoji on the first line
  and the name on the second to avoid wrapping in the narrow 420px container);
  the active tab gets an inverted solid fill (black-on-white in light mode,
  white-on-black in dark mode) for maximum visibility

### 3.3 Motion

| Scenario              | Duration | Easing   | Detail                        |
| --------------------- | -------- | -------- | ----------------------------- |
| Progress bar width    | 300ms    | ease-out | smooth goal tracking          |
| Delete button reveal  | 150ms    | ease-out | opacity only, no layout shift |
| Button press feedback | 60ms     | ease-out | slight opacity change         |

### 3.4 Responsive

| Breakpoint | Layout                                                                 |
| ---------- | ---------------------------------------------------------------------- |
| < 375px    | Overview switches to 2 columns (sets+reps on one row, kcal full width) |
| 375–480px  | 3 equal columns (default)                                              |
| > 480px    | Container centered, max-width 420px                                    |

## 4. Calorie Calculation (MET method)

```
kcal = MET × weight(kg) × duration(hours)
duration(hours) = sets × reps × secondsPerRep / 3600
```

| Exercise          | Emoji | MET | secondsPerRep | Note                               |
| ----------------- | ----- | --- | ------------- | ---------------------------------- |
| dumbbell (举哑铃) | 🏋️    | 5   | 4             | strength                           |
| situp (仰卧起坐)  | 🧘    | 4   | 3             | core                               |
| pushup (俯卧撑)   | 💪    | 6   | 3             | upper-body bodyweight              |
| squat (深蹲)      | 🦵    | 6   | 3             | lower-body bodyweight              |
| plank (平板支撑)  | 🧎    | 3   | 1             | static core — reps are **seconds** |

Result is rounded with `Math.round`. Verified example: 70kg × pushup 3×12 →
36 reps × 3s = 108s → 6 × 70 × (108/3600) = 12.6 → **13 kcal**.

> This is an estimate; actual expenditure varies with form, rest time, and
> individual differences.

## 5. Data Structures

### 5.1 Record

```typescript
interface Record {
  id: string;        // crypto.randomUUID(); fallback "timestamp-seq-random" (also unique across tabs)
  exercise: string;  // dumbbell | situp | pushup | squat | plank
  name: string;      // Chinese display name
  sets: number;      // 1–50
  reps: number;      // per-set reps (seconds for plank), 1–999
  kcal: number;      // estimated kcal for this record
  time: string;      // "HH:MM" when added
}
```

> **Learned pitfalls:**
>
> - `Date.now()` alone collides when records are added within the same
>   millisecond, and a delete would remove both — ids are now
>   `crypto.randomUUID()` strings.
> - `Date.now() * 10000 + seq` is also unsafe: the product exceeds
>   `Number.MAX_SAFE_INTEGER`, so `+seq` gets swallowed by float rounding.
> - Deletion compares with `String(r.id) !== String(id)` so legacy numeric ids
>   (pre-UUID) are still deletable.

### 5.2 App state

```typescript
interface AppState {
  records: Record[];                 // today's records, newest first (unshift)
  dailyGoal: number;                 // default 5, settable 1–100
  userWeight: number;                // default 70 kg, 30–200
  lastDate: string;                  // "YYYY-MM-DD" for cross-day reset
  draft: { exercise: string; sets: number; reps: number };  // input panel state
  showGoalModal: boolean;
}
```

### 5.3 localStorage

```
key:   fitness_counter_v1
value: { records, dailyGoal, userWeight, lastDate }
```

Cross-day handling: on `DOMContentLoaded`, if `lastDate !== today` the records
are cleared, `lastDate` is updated, and the new state is **persisted
immediately** (so stale data never lingers even if the user closes the page
without interacting). Draft input values are intentionally not persisted.

## 6. Interaction Flows

### 6.1 Add record

```
select exercise tab → adjust sets/reps (+/− or direct input) → weight (remembered)
→ click 添加记录 · 💪 俯卧撑 → calc kcal → unshift Record → save → re-render (summary,
progress bar, list prepend)
```

The add button always shows the currently selected exercise's emoji + name
("添加记录 · 💪 俯卧撑"), so the active picker state is always visible even
independently of the tab styling. Tabs and record rows also show the emoji.

### 6.2 Delete / clear / reset

- Delete button is `opacity: 0` by default, revealed on row hover /
  `focus-within`; click filters the record by id and re-renders

- Clear button appears when hovering the list section; it uses a two-step
  confirm ("清空" → "确认清空？", auto-disarm after 3s) instead of a native dialog

- **Reset today** button sits right below the overview cards (prominent,
  danger-outline, restart SVG icon): a two-step confirm ("重置今日" →
  "确认重置？") clears today's records and re-renders

- The **设置** (daily goal) button carries a settings SVG icon; both icons are
  inline Material-style SVGs colored via `currentColor`

### 6.3 Set daily goal

Modal dialog (centered, overlay `rgba(0,0,0,0.4)`): input 1–100, Save / Cancel,
close on overlay click or `Esc`. `Enter` in the input saves. Focus is moved to
the input when opened.

### 6.4 Input handling

- Direct input updates the draft without re-rendering (keeps focus); `blur`
  normalizes the input's own value **without rebuilding the DOM** (rebuilding
  would remove the buttons mid-`mousedown`, swallowing the following `click`)
- `Enter` in any input field of the entry panel quickly adds a record; `Enter`
  in the goal modal saves it, `Esc` closes
- Weight input saves via a 300ms debounce; all list interactions use event
  delegation on the app root
- Clear and reset share a two-step-confirm helper (`twoStepConfirm`); the cancel
  button in the goal modal always closes (the overlay `data-overlay-anchor`
  guard only applies to blank-area clicks)

## 7. Implementation Notes

- Vanilla JS IIFE + `DOMContentLoaded`, matching the existing `retire.js` pattern
- State-driven rendering: every mutation goes through state → `render()` rebuilds
  the widget DOM; no ad-hoc DOM manipulation
- Clamps: sets 1–50, reps 1–999, weight 30–200, goal 1–100
- Accessibility: `aria-label` on icon buttons; `role="tablist"` / `role="tab"` +
  `aria-selected` on the exercise picker; `role="progressbar"` +
  `aria-valuenow` on the goal bar; `aria-modal` dialog; full keyboard
  navigation (Tab / Enter / Esc)
- Storage failures (private mode, quota) are caught and degrade to
  session-only operation
- All dynamic HTML interpolations go through an `esc()` helper, so a tampered
  `localStorage` payload (or a future user-defined exercise name) cannot inject
  markup
- A `storage` event listener reloads state when another tab writes, keeping
  multiple tabs in sync while preserving the current draft input; the in-progress
  input's value and caret are captured before the re-render and restored after,
  so typing is not interrupted. An un-persisted weight entry (still inside its
  300ms debounce window) is merged back into state so a concurrent sync cannot
  revert it

## 8. Acceptance Checklist

- [x] Adding a record updates the three overview numbers immediately
- [x] Progress bar transitions smoothly and turns green when the goal is met
- [x] Delete button reveals on hover; deleting recalculates summaries; clear works
- [x] Reset-today button (two-step confirm) clears today's records and the overview
- [x] Goal modal opens, edits, saves, cancels (overlay click and Esc)
- [x] Empty state shows guidance text, hidden once records exist
- [x] Dark mode switches all colors via Material variables (semantic pairs override)
- [x] Numbers are tabular-nums, no jitter during rapid updates
- [x] Keyboard operable (Tab navigation, Enter confirm, Esc close)
- [x] localStorage persistence + cross-day reset verified

Verified by a DOM-shim smoke test (49 assertions) covering add/id-uniqueness/
legacy-numeric-id deletion/step/blur-normalization/goal/cancel-blank-area/
delete/debounced weight/reset/clear/Enter-submit, an XSS-injection regression,
a cross-tab storage sync check (incl. focus/value restoration), and a separate
cross-day reset test.

## 9. Future Ideas

Out of scope for v1 (tracked separately if pursued):

- Historical calendar / charts
- Custom exercises with user-defined MET
- Rest timer / plank countdown mode
- Data export (CSV / image)
- Heart-rate or wearable API integration
