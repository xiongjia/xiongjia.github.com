# Health Summary — Design Document

> AI-generated health status summary + suggestions on the Health Monitor index
> page, refreshed on demand via a script that calls the local `pi` CLI. Never
> generated during `mkdocs build`.

## Overview

The Health Monitor index (`docs/notes/health/index.md`) shows three tracks —
Retirement Countdown, Weight Track, Running Track. This feature adds a
「💡 健康状态总结与建议」section below the Mermaid overview graph: a concise,
LLM-written status summary with actionable suggestions, based on the real
data of all three tracks.

The key design constraint: **the AI suggestion must not be (re)generated on
every build**. Builds are deterministic, offline and cheap. Instead a script
generates the summary on demand and commits the result as a static fragment;
`mkdocs build` only embeds it.

```
retire.yml ─┐
weight.yml ─┼─► scripts/update_health_summary.py  (uv run poe update-health-summary)
running.yml─┘        │ 1. compute deterministic stats (reuse macros math)
                     │ 2. build a prompt embedding the stats
                     ▼ 3. call local pi CLI (pi -p --mode json) — AI writes the summary
        docs/notes/health/_summary.md   (???+ note card, overwritten each run)
                     │ 4. mkdocs build embeds it via <!-- include: ... -->
                     ▼
        docs/notes/health/index.md   (💡 健康状态总结与建议 section)
```

## Design Decisions

### On-demand generation, not build-time

- `mkdocs build` / `mkdocs serve` must stay offline, deterministic and fast —
  an AI call (network + tokens) has no place in the build pipeline
- The summary is regenerated only when the user runs
  `uv run poe update-health-summary`, typically after updating the data
  (`add-weight-week`, `sync-running`) or when a fresh take is wanted
- Each run **overwrites** `_summary.md` — there is exactly one current
  summary, no history, no accumulation

### Local `pi` CLI as the LLM gateway

- The script shells out to the locally installed `pi` CLI
  (`shutil.which("pi")`, clear error if missing) instead of talking to an LLM
  API directly — reuses the user's existing provider/auth/model config
  (no API keys in the repo, no new dependencies)
- Invocation is non-interactive and side-effect-free:
  `pi -p --no-session --no-tools --no-context-files --mode json "<prompt>"`
  - `-p` print mode: process the prompt once and exit
  - `--no-session`: no session persistence between runs (one-shot)
  - `--no-tools`: pure text generation — the agent cannot read/edit files
  - `--no-context-files`: ignore repo context file `AGENTS.md` — the prompt is
    self-contained
  - `--mode json`: emits a JSON event stream; the final assistant text is
    parsed from the last `message_end` event (`content[].type == "text"`,
    skipping `thinking` parts)
- The provider/model used for the answer is read back from the same event
  (`message.provider` / `message.model`) and prettified into a readable label
  (`deepseek-v4-flash` → `DeepSeek V4 Flash`) shown in the card title
- Model override via `--model` (e.g. `anthropic/claude-sonnet-4`); timeout
  via `--timeout` (default 300s)

### Statistics computed in the script, not by the LLM

The prompt embeds concrete numbers, not raw YAML dumps:

- **Retirement** — gender, age (derived from the birth date), target date
  (expected if set and still in the future, else legal), remaining
  years/months/days, progress %; reuses `retire_macros._compute_retirement`
  (same Chinese delay-reform math as the page)
- **Weight** — latest weight + date, BMI + status, week-over-week delta,
  healthy range, and a weekly-average series (the prompt embeds only the
  most recent 12 weeks so it does not grow unboundedly); reuses
  `weight_macros` helpers
- **Running** — totals, last-30-days / last-7-days runs & km, last run date,
  most recent consecutive-day streak (ending at the latest run), avg HR;
  reuses `running_macros`

The macros' pure helpers are imported by adding
`docs/notes/health/macros/` to `sys.path` (same trick as `tests/conftest.py`),
so the script can never drift from what the pages render. Guards return `{}`
for missing/invalid data and the prompt simply skips that section.

### Prompt

The prompt follows the shared health-analysis template (role setting →
「用户基础信息」 → 「体重变化记录」 → 「跑步运动记录」 → 「退休倒计时」 →
「分析要求」 → 「输出要求」). Template sections this site has no data for —
sleep, subjective feelings, body composition, physiological metrics, target
weight, per-run pace / max heart rate — are deliberately omitted.

- plain markdown body only — no `#`/`##` headings (it is embedded under an
  existing `##` heading), no code fences, no pleasantries
- `###`/bold subsections allowed: overall verdict → per-track status →
  2–4 concrete suggestions tied to the numbers
- 250–400 characters, 简体中文, pragmatic, no medical-style absolutes

## Output: `docs/notes/health/_summary.md`

The fragment is a Material collapsible card, **expanded by default**:

```markdown
???+ note "🤖 AI 健康建议 · DeepSeek V4 Flash · 2026-08-03 10:38"
    体重趋势健康、跑步习惯优秀，核心矛盾是“跑得勤、瘦得慢”……
    **当前状态**
    - 体重：BMI 26.4（超重），本周 -0.34 kg……
    - 跑步：近 30 天 30 次 / 129.4 km……连续 57 天无休息日是最大隐患
    **建议**
    1. 每周设 1–2 天休息，或改游泳、力量训练
    1. 若体重连续 2 周回升，先核对该时段记录再调整
```

- `???+` renders as `<details class="note" open>` — expanded, collapsible
- Card title carries the model label + update timestamp (no command mention —
  the page is for readers, the tooling note lives in the script docstring)
- Inner body is mdformat-normalized by the script before being indented 4
  spaces into the card (ordered lists normalize to `1.` like `poe fmt`)

### Why the fragment is excluded from `poe fmt` / `check-fmt`

mdformat (CommonMark) treats the 4-space-indented admonition content as a
code block and mangles it. Therefore:

- `pyproject.toml` adds `--exclude docs/notes/health/_summary.md` to all four
  mdformat commands (`format-md`, `format`, `fmt`, `check-fmt`)
- The script itself calls `mdformat.text()` on the AI body (with the `gfm`
  extension) before wrapping — the committed file stays style-consistent
- ruff never sees the file (`.md`), so only the mdformat exclude is needed

## Page Integration

`docs/notes/health/index.md`, below the Mermaid graph:

```markdown
## 💡 健康状态总结与建议

<!-- include: notes/health/_summary.md -->
```

- `plugins/snippet_include.py` splices the fragment at build time (same
  mechanism as `notes/_index_content.md`)
- `mkdocs.yml` `exclude_docs: notes/health/_summary.md` prevents the fragment
  from being built as a standalone page — it exists only for inclusion
- `force_render_paths: "notes/health/*"` already covers the page; the include
  content needs no macros

## CLI

```
uv run poe update-health-summary                # regenerate + overwrite
uv run poe update-health-summary --dry-run      # print prompt (with stats), no AI call
uv run poe update-health-summary --model anthropic/claude-sonnet-4
uv run poe update-health-summary --output /tmp/summary.md   # preview elsewhere
```

Failure handling: any `pi` error (missing binary, non-zero exit, timeout, no
assistant text) prints to stderr, exits `1`, and **leaves the existing
summary untouched** — a stale-but-valid page beats a broken one.

## Testing

`tests/test_update_health_summary.py` (no pi invocation, offline):

- Statistics computation from sample data dicts (retire/weight/running,
  including empty/invalid data guards and the retired-person branch)
- `extract_text` (skips `thinking` parts, takes last assistant message),
  `extract_model`, `prettify_model`
- `clean_ai_text` — unwraps fences (with/without language tag, inline ```` ``` ````
  preserved), strips stray H1/H2 headings
- `build_prompt` embeds the numbers; skips missing sections; retired stats
  render「退休状态：已退休 🎉」instead of a countdown
- `write_summary` produces the `???+ note` wrapper with model + timestamp,
  indents the body, normalizes ordered lists, strips code fences, falls back
  on empty output, never mentions the command
- `run_pi` command construction pinned (exact flags, encoding, timeout)
- `main()` end-to-end with `run_pi`/`load_yaml` monkeypatched: writes the
  file, `--dry-run` writes nothing, pi failure/OSError preserves the previous
  file, directory `--output` is rejected

## Non-Goals

- Build-time generation (the summary is static between manual refreshes)
- Talking to LLM APIs directly — provider/auth/model config stays with `pi`
- Versioning/history of suggestions — each run overwrites the previous one
- Health advice as medical guidance — the prompt explicitly asks for
  pragmatic, non-prescriptive language

## Future Work

- Schedule regeneration in CI on data changes (the running auto-sync is
  local-only, but a health-summary refresh could be CI-triggered), committing
  `_summary.md` only when content changes
- Emoji status summary (e.g. 🟢/🟡/🔴 per track) computed deterministically,
  with the LLM only writing the narrative

## Related

- [Health Monitor](../docs/notes/health/index.md)
- [Retirement Countdown Design](./retirement-countdown-design.md)
- [Weight Tracker Design](./weight-tracker-design.md)
- [Running Track Design](./running-track-design.md)
- [Architecture — Design Documents](./architecture.md#design-documents)
