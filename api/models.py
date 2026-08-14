"""Pydantic request/response models + task schema metadata.

The task *list* is derived from the engine (``mkdocs.yml extra.bot.tasks``
+ ``scripts.git_bot.TASKS``) so the API never drifts from what the bot can
actually run; this file only adds UI field metadata (label/type/step/
options) and the field → engine-arg mapping on top.
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
    # ``--flag value`` (checkbox: emitted when unchecked, e.g. --no-draft)
    arg: int | str | None = None


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
            "name": "date",
            "type": "text",
            "label": "Date (optional, e.g. yesterday)",
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


def task_names() -> list[str]:
    """Engine-derived task list (builtins + mkdocs.yml template tasks)."""
    return sorted(TASKS)


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


def assemble_args(task: str, fields: dict[str, Any]) -> list[str]:
    """Map schema field values → the engine arg list.

    Positional fields append in schema order (required or defaulted); flag
    fields append ``[--flag, value]`` (checkbox flags append bare when
    unchecked). Raises ``ValueError`` on a missing required field.
    """
    schema = task_schema(task)
    if schema is None:
        raise ValueError(f"unknown task {task!r}")
    positional: list[str] = []
    flags: list[str] = []
    skipped_positional = False
    for f in schema.fields:
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
                if not value:
                    flags.append(f.arg)
            elif value is not None and value != "":
                flags += [f.arg, str(value)]
    return positional + flags
