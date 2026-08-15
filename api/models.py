"""Pydantic request/response models + task schema metadata.

The engine registry (``mkdocs.yml extra.bot.tasks`` + ``scripts.git_bot.TASKS``)
remains the source of truth for what the bot can run; this file adds UI field
metadata (label/type/step/options) and the field → engine-arg mapping on top.
The console task *list* is a curated subset of the registry in usage order
(weight → enu → sync-running) — other engine tasks stay runnable via
``/api/bot/run`` but are hidden from the quick-task pane.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from scripts.git_bot import TASKS


class RunRequest(BaseModel):
    task: str
    args: list[str] | None = None  # raw engine args (bypasses the schema)
    fields: dict[str, Any] | None = None  # field values; assembled via schema
    handoff: bool = True  # True: draft PR immediately (default); False: wait for CI checks
    # NOTE: no auto_merge field — never auto-merge by dev decision; any
    # extra client field (incl. auto_merge) is ignored by pydantic.


class FieldSchema(BaseModel):
    name: str
    type: str = "text"
    label: str
    required: bool = False
    default: Any = None
    options: list[str] | None = None
    step: float | None = None
    # engine-arg mapping: int = positional index, str = flag forwarded as
    # ``--flag=value`` — a single token, because the bot spec format
    # (``poe bot run "<task> <args>"``) re-splits on whitespace and a rest
    # consumer (text-moment) would absorb bare ``--flag value`` pairs into
    # the free text (repeat fields forward one ``--flag=value`` per
    # collected value — arrays from the console UI, e.g. --image / --meta).
    # Checkbox: the flag is emitted per *emit* below.
    arg: int | str | None = None
    # checkbox-only: names of sibling fields this checkbox gates in the UI
    # (comma-separated for a group, e.g. "lng,lat,crs"); the siblings start
    # disabled and are cleared until the box is checked — the gate itself is
    # enforced in assemble_args.
    enables: str | None = None
    # checkbox-only: when to emit ``arg`` — "unchecked" (default: emit when
    # the box is OFF, e.g. --no-draft) or "checked" (emit when ON, e.g.
    # --draft / --no-upload). Literal: a typo fails fast at schema build
    # instead of silently inverting the checkbox behavior.
    emit: Literal["unchecked", "checked"] = "unchecked"
    # console-only: form tab this field belongs to (fields without a tab go
    # to a single "General" pane). Tab order = first-seen order; the string
    # is the tab's display label.
    tab: str | None = None
    # console-only: repeat fields with a browser file-picker — files are
    # staged via POST /api/upload and the returned paths fill the values
    upload: bool = False


class UploadFileItem(BaseModel):
    name: str
    data: str  # base64 payload (no ``data:`` prefix)


class UploadRequest(BaseModel):
    files: list[UploadFileItem] = Field(default_factory=list)


class TaskSchema(BaseModel):
    task: str
    fields: list[FieldSchema] = Field(default_factory=list)


class RunResponse(BaseModel):
    run_id: str
    task: str
    args: str
    status: str
    started_at: str
    stream_url: str


# UI field metadata keyed by task; tasks without an entry fall back to a
# generic schema derived from the template task's declared args.
_TASK_FIELDS: dict[str, list[dict[str, Any]]] = {
    "weight": [
        {
            "name": "value",
            "type": "number",
            "label": "Weight (kg)",
            "step": 0.1,
            "required": True,
            "arg": 0,
        },
        {
            "name": "use_date",
            "type": "checkbox",
            "label": "Specify date",
            "default": False,
            "enables": "date",
        },
        {
            "name": "date",
            "type": "date",
            "label": "Date",
            "arg": "--date",
        },
    ],
    "text-moment": [
        {
            "name": "content",
            "type": "textarea",
            "label": "Content",
            "required": True,
            "arg": 0,
            "tab": "Content",
        },
        {
            "name": "time",
            "type": "text",
            "label": "Time (no spaces: 9am / 21:30 / 2026-08-09T14:30)",
            "arg": "--time",
            "tab": "Content",
        },
        {
            "name": "slug",
            "type": "text",
            "label": "Slug (optional, no spaces)",
            "arg": "--slug",
            "tab": "Content",
        },
        {
            "name": "tags",
            "type": "text",
            "label": "Tags (comma-separated, e.g. food,film)",
            "arg": "--tags",
            "tab": "Content",
        },
        {
            "name": "draft",
            "type": "checkbox",
            "label": "Save as draft (hidden in production)",
            "default": False,
            "arg": "--draft",
            "emit": "checked",
            "tab": "Content",
        },
        {
            "name": "images",
            "type": "images",
            "label": "Images (each row: path + optional caption)",
            "tab": "Images",
            "upload": True,
        },
        {
            "name": "no_upload",
            "type": "checkbox",
            "label": "Stage image locally only (skip bucket upload)",
            "default": False,
            "arg": "--no-upload",
            "emit": "checked",
            "tab": "Images",
        },
        {
            "name": "place",
            "type": "text",
            "label": "Place (display text, no spaces)",
            "arg": "--place",
            "tab": "Location",
        },
        {
            "name": "set_gps",
            "type": "checkbox",
            "label": "Set coordinates",
            "default": False,
            "enables": "lng,lat,crs",
            "tab": "Location",
        },
        {
            "name": "lng",
            "type": "number",
            "label": "Longitude",
            "step": 0.000001,
            "arg": "--lng",
            "tab": "Location",
        },
        {
            "name": "lat",
            "type": "number",
            "label": "Latitude",
            "step": 0.000001,
            "arg": "--lat",
            "tab": "Location",
        },
        {
            "name": "crs",
            "type": "select",
            "label": "Coordinate system",
            "options": ["wgs84", "gcj02"],
            "default": "wgs84",
            "arg": "--crs",
            "tab": "Location",
        },
        {
            "name": "region",
            "type": "text",
            "label": "Map region (optional: shanghai)",
            "arg": "--region",
            "tab": "Location",
        },
        {
            "name": "meta",
            "type": "repeat",
            "label": "Meta KEY=VALUE (no spaces, e.g. rating=4)",
            "arg": "--meta",
            "tab": "Meta",
        },
    ],
    "enu": [
        {"name": "word", "type": "text", "label": "Word / Phrase", "required": True, "arg": 0},
    ],
    "sync-running": [],
    "health-summary": [],
    "create-post": [
        {"name": "title", "type": "text", "label": "Post Title", "required": True, "arg": 0},
        {
            "name": "category",
            "type": "select",
            "label": "Category",
            "options": ["bits", "dev", "thought"],
            "default": "bits",
            "arg": 1,
        },
        {
            "name": "draft",
            "type": "checkbox",
            "label": "Save as draft",
            "default": True,
            "arg": "--no-draft",
        },
    ],
}


# Console quick-task pane: most-used first. Entries missing from the engine
# registry are skipped, so the list never advertises a task the bot can't run.
_TASK_ORDER = ["text-moment", "weight", "enu", "sync-running"]


def _split_names(value: str) -> list[str]:
    """Split a comma-separated field-name list (checkbox ``enables`` targets)."""
    return [part.strip() for part in value.split(",") if part.strip()]


def validate_schemas() -> None:
    """Fail fast if the curated task list or schema gates drift from the engine.

    Called at import: a curated name renamed/removed in the engine registry
    (scripts/git_bot.py / mkdocs.yml), a checkbox ``enables`` pointing at a
    nonexistent sibling, or a required field being gated must be loud — not
    silently drop a console button or a required arg.
    """
    missing = sorted(set(_TASK_ORDER) - set(TASKS))
    if missing:
        raise RuntimeError(f"curated task list missing from engine registry: {missing}")
    unknown = sorted(set(_TASK_FIELDS) - set(TASKS))
    if unknown:
        raise RuntimeError(f"schema metadata for unknown engine tasks: {unknown}")
    for task, fields in _TASK_FIELDS.items():
        by_name = {f["name"]: f for f in fields}
        for f in fields:
            enables = f.get("enables")
            if enables is None:
                continue
            for name in _split_names(enables):
                if name not in by_name:
                    raise RuntimeError(
                        f"task {task!r}: field {f['name']!r} enables unknown field {name!r}"
                    )
                # a gated field is an optional option by definition — required +
                # gate is contradictory (assemble_args would silently drop it)
                if by_name[name].get("required"):
                    raise RuntimeError(f"task {task!r}: gated field {name!r} must not be required")


validate_schemas()


def task_names() -> list[str]:
    """Console task list: curated usage order (text-moment → weight → …).

    Other engine tasks (health-summary, create-post) remain valid for
    ``/api/bot/run`` but are hidden from this list.
    """
    return [name for name in _TASK_ORDER if name in TASKS]


def task_schema(task: str) -> TaskSchema | None:
    """Schema for one task: explicit UI metadata or a generic fallback."""
    if task not in TASKS:
        return None
    fields = _TASK_FIELDS.get(task)
    if fields is not None:
        return TaskSchema(task=task, fields=[FieldSchema(**f) for f in fields])
    # generic fallback: positional required fields from declared args
    template = TASKS[task]
    declared = getattr(template, "args", []) or []
    if isinstance(template, type) or not declared:
        return TaskSchema(task=task)
    if declared[-1].endswith("..."):
        declared = declared[:-1]
    return TaskSchema(
        task=task,
        fields=[
            FieldSchema(name=name, label=name, required=True, arg=i)
            for i, name in enumerate(declared)
        ],
    )


def _as_bool(value: Any) -> bool:
    """Coerce a checkbox field value to bool.

    Raw API clients may send string spellings (e.g. ``"false"`` / ``"0"``) —
    those must not enable the option, so the standard falsy spellings (YAML
    1.1 set: false / 0 / no / off / n / f + empty) map to False.
    """
    if isinstance(value, str):
        return value.strip().lower() not in ("", "false", "0", "no", "off", "n", "f")
    return bool(value)


def _no_space(value: str, fname: str) -> None:
    """Reject whitespace in a flag value that rides the spec string.

    The bot spec format (``poe bot run "<task> <args>"``) re-splits on
    whitespace — ``--time=2026-08-09 14:30`` would silently drop the
    ``14:30`` into the moment text. Blocking with a clear message beats
    silent content corruption; the console labels already say "no spaces".
    """
    if any(ch.isspace() for ch in value):
        raise ValueError(
            f"field {fname!r}: value must not contain spaces — the bot spec "
            "format re-splits on whitespace and would corrupt the arguments "
            "(use e.g. 2026-08-09T14:30 for times, no spaces elsewhere)"
        )


def assemble_args(task: str, fields: dict[str, Any]) -> list[str]:
    """Map schema field values → the engine arg list.

    Positional fields append in schema order (required or defaulted); flag
    fields append ``[--flag, value]`` (checkbox flags append bare when
    unchecked). A field gated by an unchecked checkbox (``enables``) is
    dropped — the API contract matches the console's gated UI. Raises
    ``ValueError`` on a missing required field.
    """
    schema = task_schema(task)
    if schema is None:
        raise ValueError(f"unknown task {task!r}")
    # checkbox gates: names of fields whose gate checkbox is unchecked (e.g.
    # weight's date is only sent when "Specify date" is checked; moment
    # lng/lat/crs only when "Set coordinates" is checked)
    gated_off: set[str] = set()
    for g in schema.fields:
        if g.type == "checkbox" and g.enables and not _as_bool(fields.get(g.name, g.default)):
            gated_off.update(_split_names(g.enables))
    positional: list[str] = []
    flags: list[str] = []
    skipped_positional = False
    for f in schema.fields:
        if f.name in gated_off:
            # a dropped positional would shift later slots — mark it so a
            # later positional refuses instead of landing in the wrong slot
            if isinstance(f.arg, int):
                skipped_positional = True
            continue
        value = fields.get(f.name, f.default)
        if f.type == "images":
            # paired rows [{path, caption}] → one --image per row, the
            # caption attached inline (``path|caption``) so a sparse caption
            # stays with its image. The pairing contract is implemented in
            # three places — keep them in sync:
            #   1. JS  console collectFields (api/static/js/app.js) emits
            #      [{path, caption}] from the paired-row UI
            #   2. this branch folds caption into ``path|caption``
            #   3. create_moment.py partitions on the FIRST ``|``
            rows = value if isinstance(value, list) else ([value] if value else [])
            for row in rows:
                if isinstance(row, dict):
                    path = str(row.get("path") or "").strip()
                    cap = str(row.get("caption") or "").strip()
                elif isinstance(row, str) and "|" in row:
                    path, _, cap = row.partition("|")
                    path, cap = path.strip(), cap.strip()
                else:
                    path, cap = str(row or "").strip(), ""
                if not path:
                    continue
                _no_space(path, f.name)
                if cap:
                    _no_space(cap, f"{f.name}.caption")
                flags.append(f"--image={path}" if not cap else f"--image={path}|{cap}")
            continue
        if isinstance(f.arg, int):
            if value is None or value == "":
                if f.required:
                    raise ValueError(f"missing required field: {f.name}")
                skipped_positional = True
                continue
            if skipped_positional:
                # an empty optional positional before this one would shift
                # later positionals into the wrong engine slots — refuse
                raise ValueError(f"cannot skip positional field before {f.name}")
            positional.append(str(value))
        elif isinstance(f.arg, str):
            if f.type == "checkbox":
                checked = _as_bool(value)
                # emit picks the direction: flag when checked, or when
                # unchecked (default — create-post's --no-draft pattern)
                if checked == (f.emit == "checked"):
                    flags.append(f.arg)
            elif f.type == "repeat":
                values = value if isinstance(value, list) else [value]
                for v in values:
                    if v is not None and str(v) != "":
                        _no_space(str(v), f.name)
                        flags.append(f"{f.arg}={v}")
            elif value is not None and value != "":
                _no_space(str(value), f.name)
                flags.append(f"{f.arg}={value}")
    return positional + flags
