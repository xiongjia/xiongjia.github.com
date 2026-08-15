"""Pydantic request/response models + task schema metadata.

The engine registry (``mkdocs.yml extra.bot.tasks`` + ``scripts.git_bot.TASKS``)
remains the source of truth for what the bot can run; this file adds UI field
metadata (label/type/step/options) and the field → engine-arg mapping on top.
The console task *list* is a curated subset of the registry in usage order
(weight → enu → sync-running) — other engine tasks stay runnable via
``/api/bot/run`` but are hidden from the quick-task pane.
"""

from __future__ import annotations

from typing import Any

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
    # ``--flag value`` (checkbox: emitted when unchecked, e.g. --no-draft).
    # A checkbox with ``enables`` gates a sibling field (UI); it may also
    # carry an ``arg``, emitted when unchecked like any checkbox flag — the
    # gate itself is enforced in assemble_args.
    arg: int | str | None = None
    # checkbox-only: name of a sibling field this checkbox gates in the UI
    # (the sibling starts disabled and is cleared until the box is checked)
    enables: str | None = None


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
        {"name": "content", "type": "textarea", "label": "Content", "required": True, "arg": 0},
        {"name": "time", "type": "text", "label": "Time (optional)", "arg": "--time"},
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
_TASK_ORDER = ["weight", "enu", "sync-running"]


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
            if enables not in by_name:
                raise RuntimeError(
                    f"task {task!r}: field {f['name']!r} enables unknown field {enables!r}"
                )
            # a gated field is an optional option by definition — required +
            # gate is contradictory (assemble_args would silently drop it)
            if by_name[enables].get("required"):
                raise RuntimeError(f"task {task!r}: gated field {enables!r} must not be required")


validate_schemas()


def task_names() -> list[str]:
    """Console task list: curated usage order (weight → enu → sync-running).

    Other engine tasks (health-summary, text-moment, create-post) remain
    valid for ``/api/bot/run`` but are hidden from this list.
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
    # weight's date is only sent when "Specify date" is checked)
    gated_off = {
        g.enables
        for g in schema.fields
        if g.type == "checkbox" and g.enables and not _as_bool(fields.get(g.name, g.default))
    }
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
                if not _as_bool(value):
                    flags.append(f.arg)
            elif value is not None and value != "":
                flags += [f.arg, str(value)]
    return positional + flags
