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
    # NOTE: no local field — local mode is server-wide (BOT_API_LOCAL), not
    # a per-request choice.


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
    # console-only: detailed help rendered as a muted line under the field
    # (and as its tooltip), so users understand the expected format and
    # semantics — e.g. text-moment's `meta` KEY=VALUE block. UI copy: the
    # text may contain Chinese examples (unlike the rest of this module).
    help: str | None = None
    # comma-separated sibling field names that must NOT be set together with
    # this one (e.g. text-moment's "Time from photo EXIF" vs "Time"): a
    # both-set submission raises a ValueError naming both fields.
    conflicts_with: str | None = None
    # comma-separated sibling field names that MUST be set for this field to
    # make sense (e.g. "Time from photo EXIF" requires the uploaded images).
    # A missing dependency raises a ValueError before any worktree starts.
    requires: str | None = None
    # checkbox-only, console-only: sibling field names turned OFF (disabled +
    # cleared) while the box is checked — the inverse of ``enables``. Prevents
    # a conflict in the UI instead of only rejecting it server-side (e.g.
    # "Time from photo EXIF" disables the manual "Time" input).
    disables: str | None = None


class UploadFileItem(BaseModel):
    name: str
    data: str  # base64 payload (no ``data:`` prefix)
    save_as: str | None = None  # optional custom save filename (default: name)


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
            "help": (
                "Moment body text (Markdown supported, e.g. **bold**, "
                "[links](https://…), lists). Required: photo-only moments are "
                "Telegram-only (the console cannot pass --no-editor), so add "
                "at least one character even for a picture."
            ),
        },
        {
            "name": "time",
            "type": "text",
            "label": "Time (no spaces: 9am / 21:30 / 2026-08-09T14:30)",
            "arg": "--time",
            "tab": "Content",
            "conflicts_with": "time_from_exif",
            "help": (
                "Publish time; leave empty to use now. No spaces — the bot "
                "spec re-splits on whitespace, so use 2026-08-09T14:30 (not "
                "2026-08-09 14:30). Cannot be combined with 'Time from photo "
                "EXIF'."
            ),
        },
        {
            "name": "time_from_exif",
            "type": "checkbox",
            "label": "Time from photo EXIF",
            "default": False,
            "arg": "--time-from-exif",
            "emit": "checked",
            "tab": "Content",
            "conflicts_with": "time",
            "requires": "images",
            "disables": "time",
            "help": (
                "Use the uploaded photo's EXIF capture time (DateTimeOriginal) "
                "as the moment date — the first photo carrying one wins, the "
                "rest are ignored. Requires at least one uploaded image and is "
                "mutually exclusive with Time. Photos without EXIF (screenshots, "
                "stripped files) fall back to now with a warning."
            ),
        },
        {
            "name": "slug",
            "type": "text",
            "label": "Slug (optional, no spaces)",
            "arg": "--slug",
            "tab": "Content",
            "help": (
                "Optional filename slug appended as DD-HHMM-<slug>.md — letters, "
                "digits, underscore and hyphen only (no spaces or slashes)."
            ),
        },
        {
            "name": "tags",
            "type": "text",
            "label": "Tags (comma-separated, e.g. food,film)",
            "arg": "--tags",
            "tab": "Content",
            "help": (
                "Comma-separated tags shown as #tag links on the timeline. "
                "`general` is always added automatically. Tags also decide which "
                "Meta fields apply (see the Meta tab)."
            ),
        },
        {
            "name": "draft",
            "type": "checkbox",
            "label": "Save as draft (hidden in production)",
            "default": False,
            "arg": "--draft",
            "emit": "checked",
            "tab": "Content",
            "help": (
                "Draft moments are hidden from the production build but stay "
                "visible on the dev server (MKDOCS_INCLUDE_DRAFTS)."
            ),
        },
        {
            "name": "images",
            "type": "images",
            "label": "Images (each row: path + optional caption)",
            "tab": "Images",
            "upload": True,
            "help": (
                "Each photo is converted to WebP and uploaded to the bucket; the "
                "moment links it with a relative assets/bucket/ path. The caption "
                "becomes the image alt text. 'save as' (optional) renames every "
                "file in this batch, keeping the original extension."
            ),
        },
        {
            "name": "no_upload",
            "type": "checkbox",
            "label": "Stage image locally only (skip bucket upload)",
            "default": False,
            "arg": "--no-upload",
            "emit": "checked",
            "tab": "Images",
            "help": (
                "Convert + stage the WebP under docs/assets/bucket/ without "
                "uploading it to R2 — upload later with PicList or "
                "`poe bucket-upload`."
            ),
        },
        {
            "name": "place",
            "type": "text",
            "label": "Place (display text, no spaces)",
            "arg": "--place",
            "tab": "Location",
            "help": (
                "Location label shown on the moment (display text only). "
                "Coordinates come from the photo EXIF or the fields below."
            ),
        },
        {
            "name": "set_gps",
            "type": "checkbox",
            "label": "Set coordinates",
            "default": False,
            "enables": "lng,lat,crs",
            "tab": "Location",
            "help": (
                "Leave OFF to take GPS from the uploaded photo's EXIF (WGS-84) "
                "automatically — no coordinates are sent in that case. Turn ON "
                "to type coordinates or use '📍 Use my location'; explicit "
                "values always win over photo EXIF."
            ),
        },
        {
            "name": "lng",
            "type": "number",
            "label": "Longitude",
            "step": 0.000001,
            "arg": "--lng",
            "tab": "Location",
            "help": "Longitude in the selected coordinate system (e.g. 121.473701).",
        },
        {
            "name": "lat",
            "type": "number",
            "label": "Latitude",
            "step": 0.000001,
            "arg": "--lat",
            "tab": "Location",
            "help": "Latitude in the selected coordinate system (e.g. 31.230416).",
        },
        {
            "name": "crs",
            "type": "select",
            "label": "Coordinate system",
            "options": ["wgs84", "gcj02"],
            "default": "wgs84",
            "arg": "--crs",
            "tab": "Location",
            "help": (
                "wgs84 = GPS / OpenStreetMap (photo EXIF and browser location). "
                "gcj02 = Amap/Baidu; converted to WGS-84 before saving."
            ),
        },
        {
            "name": "region",
            "type": "text",
            "label": "Map region (optional: shanghai)",
            "arg": "--region",
            "tab": "Location",
            "help": (
                "Basemap region override (e.g. shanghai). Leave empty to "
                "auto-probe the region from the coordinates."
            ),
        },
        {
            "name": "meta",
            "type": "repeat",
            "label": "Meta KEY=VALUE (no spaces, e.g. rating=4)",
            "arg": "--meta",
            "tab": "Meta",
            "help": (
                "Structured metadata, one KEY=VALUE row each (values must not "
                "contain spaces). Keys depend on the moment's tags, as "
                "configured in mkdocs.yml extra.moment.meta_fields: "
                "food → name + rating, film → name + rating, misc → name. "
                "Examples: name=老上海面馆, rating=4 — rating is an integer "
                "1–5 rendered as ★ stars (out-of-range values are hidden). "
                "A photo's EXIF camera/photo_date are added automatically. "
                "Unknown keys are kept in the frontmatter but not rendered."
            ),
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
_TASK_ORDER = [
    "text-moment",
    "weight",
    "enu",
    "sync-running",
    "collect",
    "collect-todo",
    "collect-idea",
]


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
        by_name: dict[str, dict[str, Any]] = {}
        for f in fields:
            # duplicate names would collide in collectFields + the help ids
            if f["name"] in by_name:
                raise RuntimeError(f"task {task!r}: duplicate field name {f['name']!r}")
            by_name[f["name"]] = f
        enabled_targets: set[str] = set()
        disabled_targets: set[str] = set()
        for f in fields:
            name = f["name"]
            relations = {
                "enables": _split_names(f.get("enables") or ""),
                "conflicts_with": _split_names(f.get("conflicts_with") or ""),
                "requires": _split_names(f.get("requires") or ""),
                "disables": _split_names(f.get("disables") or ""),
            }
            enabled_targets.update(relations["enables"])
            disabled_targets.update(relations["disables"])
            # enables/disables only act on checkbox inputs (the console wires
            # them in the checkbox branch) — anywhere else is dead config
            for prop in ("enables", "disables"):
                if relations[prop] and f.get("type") != "checkbox":
                    raise RuntimeError(
                        f"task {task!r}: field {name!r} declares {prop!r} but is not a checkbox"
                    )
            for target in relations["enables"]:
                # a gated field is an optional option by definition —
                # required + gate is contradictory (assemble_args would
                # silently drop it)
                if target in by_name and by_name[target].get("required"):
                    raise RuntimeError(
                        f"task {task!r}: gated field {target!r} must not be required"
                    )
            for prop, targets in relations.items():
                for target in targets:
                    if target not in by_name:
                        verb = "conflicts with" if prop == "conflicts_with" else prop
                        raise RuntimeError(
                            f"task {task!r}: field {name!r} {verb} unknown field {target!r}"
                        )
                    if target == name:
                        raise RuntimeError(
                            f"task {task!r}: field {name!r} lists itself in {prop!r}"
                        )
        # one field governed by both an `enables` and a `disables` checkbox
        # would have its disabled state decided by call order in the console
        overlap = sorted(enabled_targets & disabled_targets)
        if overlap:
            raise RuntimeError(
                f"task {task!r}: fields both enabled and disabled by checkboxes: {overlap}"
            )


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
        rest_name = declared[-1][:-3]
        declared = declared[:-1]
        return TaskSchema(
            task=task,
            fields=[
                FieldSchema(name=name, label=name, required=True, arg=i)
                for i, name in enumerate(declared)
            ]
            + [
                FieldSchema(
                    name=rest_name,
                    label=rest_name,
                    type="text",
                    required=True,
                    arg=len(declared),
                )
            ],
        )
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


def _is_field_set(field: FieldSchema, value: Any) -> bool:
    """Whether a submitted value counts as present (``requires``/``conflicts_with``).

    Checkboxes use the same truthiness as assembly (``_as_bool``), so a raw
    client sending ``"false"`` is treated as unchecked; list/dict fields
    (``images``/``repeat``) count only when non-empty; everything else counts
    when it carries non-blank text.
    """
    if field.type == "checkbox":
        return _as_bool(value)
    if value is None:
        return False
    if isinstance(value, dict):
        return bool(value)
    if isinstance(value, list):
        if field.type == "images":
            # mirror assembly: only a row with a path yields an --image arg,
            # so [{"path": ""}] must NOT satisfy `requires: images`
            return any(
                str(row.get("path") or "").strip()
                if isinstance(row, dict)
                else str(row or "").partition("|")[0].strip()
                for row in value
            )
        # a list of blank strings (e.g. [""]) is not a value either
        return any(str(v).strip() for v in value)
    return str(value).strip() != ""


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
    ``ValueError`` on a missing required field, on a set field whose
    ``requires`` dependency is absent, and on ``conflicts_with`` fields that
    are both set.
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
    # cross-field constraints (`requires` / `conflicts_with`): validate BEFORE
    # building args, so a bad combination fails with a clear 422 instead of a
    # CLI error after a worktree + subprocess have already been started. A
    # gated-off field is dropped from the args, so it neither satisfies a
    # `requires` nor triggers a `conflicts_with`.
    by_name = {f.name: f for f in schema.fields}
    for f in schema.fields:
        if f.name in gated_off or not (f.requires or f.conflicts_with):
            continue
        if not _is_field_set(f, fields.get(f.name, f.default)):
            continue
        for dep in _split_names(f.requires or ""):
            dep_field = by_name.get(dep)
            if dep_field is None:
                continue
            if dep in gated_off or not _is_field_set(dep_field, fields.get(dep, dep_field.default)):
                raise ValueError(
                    f"field {f.name!r} requires {dep!r} — provide {dep!r} or clear {f.name!r}"
                )
        for other in _split_names(f.conflicts_with or ""):
            other_field = by_name.get(other)
            if other in gated_off or other_field is None:
                continue
            if _is_field_set(other_field, fields.get(other, other_field.default)):
                raise ValueError(
                    f"fields {f.name!r} and {other!r} are mutually exclusive — clear one of them"
                )
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
