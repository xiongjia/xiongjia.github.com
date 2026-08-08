"""Record a daily weight reading into docs/notes/health/data/weight.yml.

Usage:
    uv run poe update-weight 82            # today's weight (default date)
    uv run poe update-weight 82 2026-08-05 # weight on a specific date
    uv run poe update-weight 82 --date 2026-08-05
    uv run poe update-weight 81.6 yesterday

Notes:
- The date defaults to today; `yesterday`/`today` and ISO dates
  (YYYY-MM-DD) are accepted.
- Missing target weeks are appended automatically, using the same
  `# Week N — Mon YYYY-MM-DD` comment format as `poe add-weight-week`.
- A date before the `start_date` anchor in weight.yml is rejected.
- Comment lines in the YAML are preserved (edits are text-level).
- Only the target day's value is rewritten; other days keep their exact text.
"""

import argparse
import re
import sys
from datetime import date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from typing import NamedTuple

import yaml

# bootstrap repo root so `shared/` is importable regardless of how this runs
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shared.date import parse_date_strict  # noqa: E402

DATA_PATH = "docs/notes/health/data/weight.yml"

_DAYS_LINE = re.compile(r"^(\s*)- days:\s*\[(.*)\]\s*$")

_WEEKDAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")


class UpdateInfo(NamedTuple):
    """Result metadata for a single weight update.

    ``week_index`` is 0-based, ``day_index`` is 0=Mon, ``overwrote`` is the
    previous value on the same day (or None), ``appended`` is the number of
    new weeks added to reach the target week.
    """

    week_index: int
    day_index: int
    overwrote: float | None
    appended: int


def _format_weight(weight: float) -> str:
    """Format a weight to 2 decimals with half-up rounding.

    Goes through ``Decimal`` on the string form to avoid float artifacts and
    Python's banker's rounding (e.g. ``round(82.005, 2)`` -> ``82.0``).
    """
    return str(Decimal(str(weight)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def _resolve_date(raw: str | None, now: datetime | None = None) -> date:
    """Resolve the date argument to a date (default: today)."""
    now = now or datetime.now()
    if not raw:
        return now.date()
    s = raw.strip().lower()
    if s in ("today", "今天"):
        return now.date()
    if s in ("yesterday", "昨天"):
        return (now - timedelta(days=1)).date()
    parsed = parse_date_strict(raw)
    if parsed is None:
        raise ValueError(f"unparseable date {raw!r} (use YYYY-MM-DD, today or yesterday)")
    return parsed.date()


def _find_days_entries(lines: list[str]) -> list[tuple[int, str, str]]:
    """Return (line index, indentation, inner list text) per `- days:` entry."""
    found = []
    for i, line in enumerate(lines):
        m = _DAYS_LINE.match(line.rstrip("\n"))
        if m:
            found.append((i, m.group(1), m.group(2)))
    return found


def _append_weeks(
    lines: list[str],
    num_weeks: int,
    anchor: date,
    count: int,
    day_entries: list[tuple[int, str, str]],
) -> list[str]:
    """Append `count` empty weeks as line elements after the last week entry."""
    # match the indentation of existing entries (2 spaces by default)
    entry_indent = day_entries[0][1] if day_entries else "  "
    new_lines: list[str] = []
    for offset in range(1, count + 1):
        week_num = num_weeks + offset
        week_start = anchor + timedelta(days=(week_num - 1) * 7)
        new_lines.append(f"{entry_indent}# Week {week_num} — Mon {week_start:%Y-%m-%d}\n")
        new_lines.append(f"{entry_indent}- days: [null, null, null, null, null, null, null]\n")

    if day_entries:
        insert_at = day_entries[-1][0] + 1
    else:
        # weeks section exists but is empty (bare `weeks:` or inline `weeks: []`)
        # — insert right after the key so the entries become its list children
        for i, line in enumerate(lines):
            stripped = line.rstrip("\n")
            m = re.match(r"^\s*weeks:", stripped)
            if m:
                if not re.match(r"^\s*weeks:\s*$", stripped):
                    # `weeks: []` (possibly with a trailing comment) — drop the
                    # inline list so the new entries become its block children;
                    # keeps any trailing comment, avoids a second `weeks:` key
                    comment = re.search(r"#.*$", stripped)
                    tail = f" {comment.group(0)}" if comment else ""
                    trail = "\n" if line.endswith("\n") else ""
                    lines[i] = f"{m.group(0)}{tail}{trail}"
                insert_at = i + 1
                break
        else:
            # no weeks: key at all — append a fresh section at the end
            sep = "\n" if (lines and not lines[-1].endswith("\n")) else ""
            header = [
                f"{sep}\n",
                "# 7 days per week; use null for missed days\n",
                "# Week start dates are shown in comments to help identify each week\n",
                "weeks:\n",
            ]
            return lines + header + new_lines

    # keep the previous line from gluing onto the first new line
    if insert_at > 0 and not lines[insert_at - 1].endswith("\n"):
        new_lines.insert(0, "\n")
    return lines[:insert_at] + new_lines + lines[insert_at:]


def apply_update(content: str, weight: float, target: date) -> tuple[str, UpdateInfo]:
    """Return ``(updated_content, info)`` or raise ``ValueError``.

    ``info`` is an ``UpdateInfo`` (see its docstring for field semantics).
    """
    if not 0 < weight < 500:
        raise ValueError(f"weight must be a positive number in kg, got {weight!r}")
    try:
        data = yaml.safe_load(content)
    except yaml.YAMLError as exc:
        raise ValueError(f"invalid YAML: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError("top level of weight.yml must be a YAML mapping")

    start_str = data.get("start_date")
    if not start_str:
        raise ValueError("missing `start_date` in weight.yml")
    start = parse_date_strict(str(start_str))
    if start is None:
        raise ValueError(f"unparseable start_date {start_str!r}")
    anchor = start.date() - timedelta(days=start.date().weekday())  # Monday-aligned

    if target < anchor:
        raise ValueError(f"date {target} is before the first week (Mon {anchor})")

    week_index = (target - anchor).days // 7
    day_index = target.weekday()  # 0=Mon ... 6=Sun

    weeks = data.get("weeks") or []
    lines = content.splitlines(keepends=True)
    day_entries = _find_days_entries(lines)
    if len(day_entries) != len(weeks):
        raise ValueError(
            f"found {len(day_entries)} inline `- days:` line(s) but {len(weeks)} week(s) "
            "in YAML — a week may be written in block style; edit the file manually"
        )

    appended = 0
    if week_index >= len(weeks):
        appended = week_index - len(weeks) + 1
        lines = _append_weeks(lines, len(weeks), anchor, appended, day_entries)
        day_entries = _find_days_entries(lines)

    line_idx, indent, list_text = day_entries[week_index]
    values = yaml.safe_load(f"[{list_text}]")
    if not isinstance(values, list) or len(values) != 7:
        raise ValueError(f"week {week_index + 1} days entry must be a 7-item list")

    old = values[day_index]
    overwrote: float | None = None
    # only numeric YAML values get an overwrite notice — bool is a subclass of
    # int (would print "1") and quoted strings may not be meaningful numbers
    if isinstance(old, (int, float)) and not isinstance(old, bool):
        overwrote = float(old)

    weight_str = _format_weight(weight)
    tokens = [t.strip() for t in list_text.split(",")]
    if len(tokens) == len(values):
        # per-slot text surgery: only touch the target slot so the exact raw
        # text (and precision) of every other day's value is preserved
        tokens[day_index] = weight_str
        new_list = ", ".join(tokens)
    else:
        # unusual formatting (quoted values, etc.) — rebuild from parsed values
        def _fmt(v: object) -> str:
            if v is None:
                return "null"
            if isinstance(v, bool):
                return str(v).lower()  # keep `true`/`false` instead of 1.00
            try:
                return _format_weight(float(v))
            except (TypeError, ValueError):
                return str(v)

        new_list = ", ".join(_fmt(v) for v in values)

    trail = "\n" if lines[line_idx].endswith("\n") else ""
    lines[line_idx] = f"{indent}- days: [{new_list}]{trail}"

    new_content = "".join(lines)

    # safety net: the edit must still parse and keep the expected structure —
    # a corrupted weight.yml would break the whole site build at macro time
    try:
        check = yaml.safe_load(new_content)
    except yaml.YAMLError as exc:
        raise ValueError(
            f"internal error: edit produced invalid YAML — nothing written ({exc})"
        ) from exc
    if not isinstance(check, dict) or len(check.get("weeks") or []) != len(weeks) + appended:
        raise ValueError("internal error: edit changed the weeks structure — nothing written")

    return new_content, UpdateInfo(
        week_index=week_index,
        day_index=day_index,
        overwrote=overwrote,
        appended=appended,
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Record a daily weight reading into docs/notes/health/data/weight.yml"
    )
    parser.add_argument("weight", type=float, help="Weight in kg, e.g. 82 or 81.6")
    parser.add_argument(
        "date",
        nargs="?",
        default=None,
        help="Date to record (default: today); YYYY-MM-DD, today or yesterday",
    )
    parser.add_argument(
        "--date",
        dest="date_flag",
        default=None,
        help="Same as the positional date argument",
    )
    args = parser.parse_args()

    if not 0 < args.weight < 500:
        parser.error(f"weight must be a positive number in kg, got {args.weight!r}")

    if args.date_flag and args.date:
        parser.error("give the date either positionally or with --date, not both")

    try:
        target = _resolve_date(args.date_flag or args.date)
    except ValueError as exc:
        parser.error(str(exc))

    filepath = Path.cwd() / DATA_PATH
    if not filepath.is_file():
        print(f"Error: {filepath} not found!", file=sys.stderr)
        sys.exit(1)

    try:
        content = filepath.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        print(f"Error: cannot read {filepath}: {exc}", file=sys.stderr)
        sys.exit(1)

    try:
        new_content, info = apply_update(content, args.weight, target)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    try:
        filepath.write_text(new_content, encoding="utf-8")
    except OSError as exc:
        print(f"Error: cannot write {filepath}: {exc}", file=sys.stderr)
        sys.exit(1)

    print(
        f"✅ Recorded {_format_weight(args.weight)} kg on {target} "
        f"({_WEEKDAYS[info.day_index]}, week {info.week_index + 1})"
    )
    if info.overwrote is not None:
        print(f"   (overwrote previous value {info.overwrote:g} on the same day)")
    if info.appended:
        print(f"   Appended {info.appended} new week(s) to {DATA_PATH}")
    print(
        "   Run `uv run poe server` to preview; "
        "`poe update-health-summary` refreshes the AI summary"
    )


if __name__ == "__main__":
    main()
