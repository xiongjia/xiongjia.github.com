"""Sync the Douban film & TV collection into per-year YAML files.

Usage::

    uv run poe sync-film-tv                       # incremental (new/changed items)
    uv run poe sync-film-tv --full --limit 300    # first pass, batched
    uv run poe sync-film-tv --limit 300           # continue the detail backfill
    uv run poe sync-film-tv --refresh-details 20  # re-read details after editing comments
    uv run poe sync-film-tv --only shawshank-redemption --covers 8
    uv run poe sync-film-tv --prune --dry-run
    uv run poe sync-film-tv --dedupe-covers --confirm  # drop duplicated local covers

A ``--full`` walk keeps its per-tab cursor in ``.cache/film-tv/state/walk.json``
and resumes there on the next ``--full`` run; an empty list page mid-walk is
retried and, when the page header still reports more rows than were stored, the
walk aborts instead of silently truncating the archive.

Session policy (design §1.1/§4 — account-call minimisation): collection lists are
read **anonymously** (Douban serves them to anyone; the logged-in variant only
adds per-item edit controls), so the repeated, high-volume part of a sync never
touches the account. Only subject pages and photo albums — gated behind a login
— use the stored cookie. Cover candidates default to the single main poster that
the subject page already carries (`covers_default: 1`), so a first full pass costs
exactly one account request per item and nothing more.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shared.douban_auth import (  # noqa: E402
    SEC_CHALLENGE_HOST,
    USER_AGENT,
    build_session,
    check_cookies,
    ensure_cookies,
    load_cookie_header,
)
from shared.env import load_env_files  # noqa: E402
from shared.film_tv_model import (  # noqa: E402
    Taxonomy,
    assign_year,
    build_machine,
    cover_key,
    merge_record,
    record_fingerprint,
)
from shared.film_tv_parse import (  # noqa: E402
    PERSON_NAME_STYLES,
    ListItem,
    ListPage,
    Subject,
    parse_list_page,
    parse_photos_page,
    parse_subject_page,
    subject_from_dict,
    subject_to_dict,
    upgrade_photo_size,
)
from shared.film_tv_store import (  # noqa: E402
    NON_YEAR_FILES,
    PERSON_IDS_FILE,
    Entry,
    file_prefix,
    merge_person_ids,
    read_entries,
    read_person_ids,
    sort_entries,
    write_file,
    write_person_ids,
    year_file_name,
)
from shared.mkdocs_yaml import load_extra  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent

LIST_URL = (
    "https://movie.douban.com/people/{user_id}/{kind}"
    "?start={start}&sort=time&rating=all&filter=all&mode=list&type={type_filter}"
)
SUBJECT_URL = "https://movie.douban.com/subject/{subject_id}/"
PHOTOS_URL = "https://movie.douban.com/subject/{subject_id}/photos?type=R"

PAGE_SIZE = 30
LIST_DELAY = 2.0
DETAIL_DELAY = 2.0
COVER_DELAY = 0.5
MAX_RETRIES = 2
RETRY_BACKOFF = 5.0
REQUEST_TIMEOUT = 30
#: an empty list page mid-walk is retried this many times before the walk aborts
EMPTY_PAGE_RETRIES = 2
#: extra fetches an empty *subject* page gets before it counts as gone
EMPTY_SUBJECT_RETRIES = 1
#: default detail-fetch cap per run (batching keeps the account traffic gentle);
#: ``--limit 0`` means "everything queued"
DEFAULT_LIMIT = 50
REFRESH_DETAILS_DEFAULT = 20
#: rows walked between two skeleton flushes (bounds the loss when a walk aborts)
FLUSH_EVERY = 200
KINDS = ("collect", "do")
TYPE_TABS = ("movie", "tv")


class SyncError(RuntimeError):
    """A sync precondition failed (credentials, blocked request, bad config)."""


class BlockedError(SyncError):
    """Douban answered with its anti-bot gate — stop instead of hammering."""


class GoneError(SyncError):
    """The subject no longer exists on Douban (``404``) — a permanent answer.

    The row can still be in the collection list (Douban keeps 看过 rows whose
    subject was taken down), and such a row is exactly the one without a date:
    the list carries no date span and the subject page cannot supply the 看过 /
    标记 date. Nothing can be recovered, so the record is marked gone
    (``meta.missing_since``) and skipped from the published archive.
    """


@dataclass
class Config:
    """``extra.film_tv`` from mkdocs.yml, with repo-local paths resolved."""

    data_dir: Path
    json_dir: Path
    local_prefix: str
    cover_dir: Path
    covers_default: int
    cover_max_dimension: int
    cover_quality: int
    person_name_style: str = "hint"

    @property
    def taxonomy_path(self) -> Path:
        return self.data_dir / "taxonomy.yml"

    @property
    def state_dir(self) -> Path:
        return REPO_ROOT / ".cache" / "film-tv" / "state"

    @property
    def reports_dir(self) -> Path:
        return REPO_ROOT / ".cache" / "film-tv" / "reports"


def load_config() -> Config:
    """Read the film-tv block from mkdocs.yml (absolute, repo-anchored paths)."""
    raw = load_extra("film_tv", label="sync-film-tv")
    if not raw:
        raise SyncError("mkdocs.yml has no extra.film_tv block")

    def resolve(key: str, default: str) -> Path:
        value = str(raw.get(key, default)).strip("/")
        return REPO_ROOT / value

    def number(key: str, default: int) -> int:
        value = raw.get(key, default)
        return int(value) if str(value).strip().isdigit() else default

    local_prefix = str(raw.get("local_prefix", "assets/bucket/film-tv/")).strip("/") + "/"
    person_name_style = str(raw.get("person_name_style", "hint")).strip() or "hint"
    if person_name_style not in PERSON_NAME_STYLES:
        # a typo would silently degrade every person label to the Chinese name
        raise SyncError(
            f"extra.film_tv.person_name_style must be one of "
            f"{', '.join(PERSON_NAME_STYLES)} (got {person_name_style!r})"
        )
    return Config(
        data_dir=resolve("data_dir", "docs/notes/film-tv/data"),
        json_dir=resolve("json_dir", "docs/notes/film-tv/assets"),
        local_prefix=local_prefix,
        cover_dir=REPO_ROOT / "docs" / local_prefix.rstrip("/"),
        covers_default=number("covers_default", 1),
        cover_max_dimension=number("cover_max_dimension", 800),
        cover_quality=number("cover_quality", 80),
        person_name_style=person_name_style,
    )


# --- state cache -------------------------------------------------------------


class State:
    """Local, git-ignored scratch: detail cache, cover id map, failures, walk progress.

    ``walk.json`` keeps ``{"cursor": {tab: next start}, "total": {tab: header total}}``
    so an interrupted ``--full`` walk resumes instead of re-walking 100+ pages, and
    ``film-tv-check`` can tell an incomplete archive from a complete one.
    """

    def __init__(self, directory: Path):
        self.directory = directory
        self.details_dir = directory / "details"
        self.cover_map_path = directory / "covers.json"
        self.failures_path = directory / "failures.json"
        self.walk_path = directory / "walk.json"
        self.directory.mkdir(parents=True, exist_ok=True)
        self.cover_map: dict[str, dict[str, str]] = self._load_json(self.cover_map_path, {})
        self.failures: dict[str, str] = self._load_json(self.failures_path, {})
        self.walk: dict[str, dict] = self._load_json(self.walk_path, {})

    @staticmethod
    def _load_json(path: Path, default):
        if not path.is_file():
            return default
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except ValueError:
            return default

    def detail(self, subject_id: str) -> Subject | None:
        path = self.details_dir / f"{subject_id}.json"
        if not path.is_file():
            return None
        try:
            return subject_from_dict(json.loads(path.read_text(encoding="utf-8")))
        except (ValueError, TypeError):
            return None

    def save_detail(self, subject_id: str, subject: Subject) -> None:
        self.details_dir.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(subject_to_dict(subject), ensure_ascii=False, indent=1)
        (self.details_dir / f"{subject_id}.json").write_text(payload + "\n", encoding="utf-8")

    def cover_keys(self, subject_id: str) -> dict[str, str]:
        """``photo_id → cover key`` for one subject (empty when unknown)."""
        return dict(self.cover_map.get(subject_id, {}))

    def remember_cover(self, subject_id: str, photo_id: str, key: str) -> None:
        self.cover_map.setdefault(subject_id, {})[photo_id] = key

    # --- walk progress (survives an interrupted `--full` walk) ---------------

    def walk_cursor(self, tab: str) -> int:
        """Next ``start`` for a tab, or 0 when the tab has never been walked."""
        value = (self.walk.get("cursor") or {}).get(tab)
        return int(value) if isinstance(value, int) else 0

    def set_walk_cursor(self, tab: str, start: int) -> None:
        self.walk.setdefault("cursor", {})[tab] = int(start)

    def clear_walk_cursor(self, tab: str) -> None:
        (self.walk.get("cursor") or {}).pop(tab, None)

    def walk_total(self, tab: str) -> int | None:
        """Last page-header total seen for a tab (``None`` when never recorded)."""
        value = (self.walk.get("total") or {}).get(tab)
        return int(value) if isinstance(value, int) else None

    def set_walk_total(self, tab: str, total: int) -> None:
        self.walk.setdefault("total", {})[tab] = int(total)

    def save_walk(self) -> None:
        self._write_json(self.walk_path, self.walk)

    def save(self) -> None:
        self._write_json(self.cover_map_path, self.cover_map)
        self._write_json(self.failures_path, self.failures)
        self.save_walk()

    @staticmethod
    def _write_json(path: Path, payload: dict) -> None:
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=1, sort_keys=True) + "\n",
            encoding="utf-8",
        )


# --- HTTP --------------------------------------------------------------------


def anonymous_session() -> requests.Session:
    """Session for the collection lists — deliberately cookie-free."""
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        }
    )
    return session


def request(
    session: requests.Session,
    url: str,
    *,
    what: str,
    headers: dict | None = None,
) -> requests.Response:
    """GET with bounded retries; abort on Douban's anti-bot gate.

    ``429``/``503``/timeouts are retried with a linear backoff (max 2 retries —
    a full walk already hit a ``ReadTimeout`` mid-run in the spike). A redirect
    or response that lands on ``sec.douban.com`` means the session/IP is being
    challenged: raise :class:`BlockedError` instead of retrying.

    ``418`` is Douban's image-CDN anti-hotlink answer: it is reported as a plain
    failure (the caller skips that one cover) rather than retried.
    """
    last_error: Exception | None = None
    for attempt in range(MAX_RETRIES + 1):
        try:
            response = session.get(
                url, timeout=REQUEST_TIMEOUT, allow_redirects=False, headers=headers
            )
        except requests.RequestException as exc:
            last_error = exc
            if attempt == MAX_RETRIES:
                raise SyncError(f"{what}: {exc.__class__.__name__} on {url}") from exc
            time.sleep(RETRY_BACKOFF * (attempt + 1))
            continue
        if response.status_code in (301, 302, 303, 307, 308):
            location = response.headers.get("location", "")
            if SEC_CHALLENGE_HOST in location:
                raise BlockedError(
                    f"{what}: Douban anti-bot challenge ({location[:80]}) — stopping. "
                    "Re-check the cookie with `poe film-tv-login --check` and retry later."
                )
            if "accounts/login" in location or "passport/login" in location:
                raise SyncError(f"{what}: redirected to the login page — refresh the cookie")
            raise SyncError(f"{what}: unexpected redirect to {location[:80]}")
        if response.status_code in (429, 503) and attempt < MAX_RETRIES:
            time.sleep(RETRY_BACKOFF * (attempt + 1))
            continue
        if response.status_code == 403:
            raise BlockedError(f"{what}: HTTP 403 (rate limited / blocked) — stopping")
        if response.status_code == 404:
            raise GoneError(f"{what}: HTTP 404 (gone on Douban)")
        if response.status_code != 200:
            raise SyncError(f"{what}: HTTP {response.status_code}")
        return response
    raise SyncError(f"{what}: exhausted retries ({last_error})")


def fetch_list_page(
    session: requests.Session, *, user_id: str, kind: str, type_filter: str, start: int
) -> ListPage:
    url = LIST_URL.format(user_id=user_id, kind=kind, start=start, type_filter=type_filter)
    response = request(session, url, what=f"list {kind}/{type_filter}@{start}")
    return parse_list_page(response.text)


def fetch_subject(
    session: requests.Session, subject_id: str, *, person_style: str = "hint"
) -> Subject:
    response = request(
        session, SUBJECT_URL.format(subject_id=subject_id), what=f"subject {subject_id}"
    )
    return parse_subject_page(response.text, subject_id=subject_id, person_style=person_style)


# --- list walking ------------------------------------------------------------


def needs_detail(item: ListItem, kind: str, type_filter: str, baseline: dict[str, Entry]) -> bool:
    """Whether a list row requires (re-)fetching its detail page.

    Only list-visible data participates, so a detail refill can never look like a
    Douban-side change (see ``shared.film_tv_model.fingerprint``). *baseline* is a
    snapshot of the index taken before the walk, so storing skeletons during the
    walk cannot hide a change from this run.
    """
    entry = baseline.get(item.id)
    if entry is None:
        return True
    if item.deleted:
        # nothing to fetch: the row only ever (re-)marks meta.missing_since
        return not entry.meta.get("missing_since")
    if entry.meta.get("missing_since"):
        return True  # the subject is back on Douban
    current = record_fingerprint(
        {
            "status": kind,
            "type": type_filter,
            "title": item.title,
            "user_rating": item.user_rating,
            "marked_at": item.marked_at,
            "tags": item.tags,
        },
        item,
    )
    return current != entry.meta.get("fingerprint")


def walk_lists(
    ctx: "SyncContext",
    *,
    user_id: str,
    baseline: dict[str, Entry],
    max_pages: int | None,
    full: bool,
    resume: bool = False,
) -> tuple[list[tuple[ListItem, str, str]], list[tuple[ListItem, str, str]], int]:
    """Walk every list tab, storing each row's skeleton.

    Returns ``(rows, queue, pages)``. The queue is decided against *baseline*
    (the pre-walk index) and every row is then written as a skeleton record, so a
    first pass leaves a complete archive to short-circuit against next time.

    Default mode stops as soon as a whole page brings nothing new or changed: a
    page-sized margin over the per-item rule in the design, so an older edit on
    the next page is never missed because of one unchanged row.

    Two failure modes are handled explicitly, because a truncated archive looks
    exactly like a complete one afterwards:

    * an **empty page mid-list** is retried (Douban answers an empty list while
      it is soft-throttling a session — the first full walk lost the oldest ~900
      movies that way) and, when the page header still advertises more rows than
      were stored, the walk **aborts loudly** with the progress kept;
    * a ``--full`` walk records its per-tab progress in ``walk.json``, so an
      interrupted first pass resumes where it stopped. An incremental run never
      resumes (the newest rows are always on the first pages) and never writes a
      cursor; ``--prune`` must not resume either — it compares *every* row in the
      archive against the walk, so skipping the head would mark it deleted.

    When the anonymous session is challenged, the page is retried anonymously
    once, then the rest of the walk continues on the account session (the
    logged-in variant is tolerated longer); ``ctx.list_account_pages`` counts how
    many pages that cost, so the account traffic stays visible.
    """
    rows: list[tuple[ListItem, str, str]] = []
    queue: list[tuple[ListItem, str, str]] = []
    pages = 0
    flushed = 0
    for kind in KINDS:
        for type_filter in TYPE_TABS:
            tab = f"{kind}/{type_filter}"
            # a fresh cookie-free session per tab: a challenge on one tab must not
            # push the whole walk onto the account session (the cookie is the last
            # resort, and list traffic is supposed to stay anonymous)
            session = ctx.list_session
            resume_from = ctx.state.walk_cursor(tab) if resume else 0
            start = resume_from
            tab_total = ctx.state.walk_total(tab)
            remaining = None if tab_total is None else max(0, tab_total - resume_from)
            seen_here: set[str] = set()
            empty_pages = 0
            tab_pages = 0
            completed = False
            if resume_from:
                print(f"  {tab}: resuming the full walk at start={resume_from}", flush=True)
            while True:
                try:
                    page = fetch_list_page(
                        session, user_id=user_id, kind=kind, type_filter=type_filter, start=start
                    )
                except BlockedError:
                    if session is ctx.account_session:
                        raise
                    print(
                        "  anonymous list access was challenged — retrying it once",
                        file=sys.stderr,
                        flush=True,
                    )
                    time.sleep(RETRY_BACKOFF)
                    try:
                        page = fetch_list_page(
                            ctx.list_session,
                            user_id=user_id,
                            kind=kind,
                            type_filter=type_filter,
                            start=start,
                        )
                    except BlockedError:
                        print(
                            "  … anonymous access is still challenged — continuing on the "
                            "account session (this is what the cookie is for)",
                            file=sys.stderr,
                            flush=True,
                        )
                        session = ctx.account_session
                        ctx.list_used_account = True
                        page = fetch_list_page(
                            session,
                            user_id=user_id,
                            kind=kind,
                            type_filter=type_filter,
                            start=start,
                        )
                pages += 1
                tab_pages += 1
                if session is ctx.account_session:
                    ctx.list_account_pages += 1
                if page.total is not None:
                    tab_total = page.total
                    remaining = max(0, page.total - resume_from)
                    ctx.state.set_walk_total(tab, page.total)
                if not page.items:
                    if not remaining or len(seen_here) >= remaining:
                        completed = True
                        break
                    empty_pages += 1
                    if empty_pages > EMPTY_PAGE_RETRIES:
                        raise SyncError(
                            f"list {tab}: page start={start} came back empty while the header "
                            f"reports {tab_total} item(s) and only {len(seen_here)} were stored "
                            "— Douban is throttling the walk. Progress is kept: re-run "
                            "`poe sync-film-tv --full` (it resumes from the recorded cursor)."
                        )
                    print(
                        f"  {tab}: empty page at start={start} but only "
                        f"{len(seen_here)}/{remaining} row(s) stored — retrying",
                        file=sys.stderr,
                        flush=True,
                    )
                    time.sleep(RETRY_BACKOFF * empty_pages)
                    continue
                empty_pages = 0
                for item in page.items:
                    if needs_detail(item, kind, type_filter, baseline):
                        queue.append((item, kind, type_filter))
                    rows.append((item, kind, type_filter))
                    seen_here.add(item.id)
                    # `item-show deleted` is Douban's own mark that the subject was
                    # taken down (its title is then the 未知电影 placeholder and it
                    # carries no date). Remember that here: a backlog task rebuilt
                    # from the stored record no longer sees the flag, and fetching
                    # such a subject only answers 404 / an empty page.
                    entry = ctx.merge(
                        item,
                        kind=kind,
                        type_filter=type_filter,
                        subject=None,
                        missing_since=ctx.today if item.deleted else None,
                        missing_reason="gone" if item.deleted else None,
                    )
                    if not item.deleted and entry.meta.get("missing_reason") == "pruned":
                        # the row is back in my collection: only a *pruned* record is
                        # revived here — a subject that answered 404 stays marked
                        # (probing it again is exactly what the mark avoids)
                        entry.meta["missing_since"] = None
                        entry.meta["missing_reason"] = None
                        print(f"  {tab}: {item.id} is back in the collection", flush=True)
                stop = (max_pages is not None and tab_pages >= max_pages) or (
                    not full
                    and not any(
                        needs_detail(item, kind, type_filter, baseline) for item in page.items
                    )
                )
                print(
                    f"  {tab} start={start:5d}: {len(page.items):2d} items (total {page.total})",
                    flush=True,
                )
                if len(rows) - flushed >= FLUSH_EVERY:
                    ctx.state.save()
                    ctx.write()
                    flushed = len(rows)
                start += PAGE_SIZE
                if full:
                    # this page is stored: a later `--full` run continues here
                    ctx.state.set_walk_cursor(tab, start)
                    ctx.state.save_walk()
                if stop:
                    break
                time.sleep(LIST_DELAY)
            if completed and full:
                ctx.state.clear_walk_cursor(tab)
                ctx.state.save_walk()
    return rows, queue, pages


# --- covers ------------------------------------------------------------------


def convert_to_webp(
    data: bytes, target: Path, *, max_dimension: int, quality: int
) -> tuple[int, int]:
    """Write *data* (JPEG from Douban's CDN) as a size-capped WebP."""
    from PIL import Image

    with Image.open(io.BytesIO(data)) as image:
        image = image.convert("RGB")
        width, height = image.size
        if max_dimension and max(width, height) > max_dimension:
            scale = max_dimension / max(width, height)
            image = image.resize(
                (max(1, round(width * scale)), max(1, round(height * scale))), Image.LANCZOS
            )
        target.parent.mkdir(parents=True, exist_ok=True)
        image.save(target, "WEBP", quality=quality, method=6)
        return image.size


def store_cover(
    session: requests.Session,
    *,
    config: Config,
    state: State,
    subject_id: str,
    index: int,
    photo_id: str,
    url: str,
    counts: dict,
) -> bool:
    """Download one cover candidate as ``covers/<douban_id>/NN.webp``."""
    key = cover_key(subject_id, index)
    target = config.cover_dir / key
    if target.is_file():
        state.remember_cover(subject_id, photo_id, key)
        return False
    # the image CDN rejects hotlinks (HTTP 418) unless a Referer is sent
    response = request(
        session,
        upgrade_photo_size(url),
        what=f"cover {subject_id}/{index:02d}",
        headers={"Referer": "https://movie.douban.com/"},
    )
    size = convert_to_webp(
        response.content,
        target,
        max_dimension=config.cover_max_dimension,
        quality=config.cover_quality,
    )
    state.remember_cover(subject_id, photo_id, key)
    counts["covers"] += 1
    print(f"    cover {key} {size[0]}x{size[1]} {target.stat().st_size // 1024}KB", flush=True)
    time.sleep(COVER_DELAY)
    return True


def fetch_album_candidates(session: requests.Session, subject_id: str, wanted: int) -> list:
    """First *wanted* poster candidates from the album page (one request)."""
    response = request(
        session, PHOTOS_URL.format(subject_id=subject_id), what=f"photos {subject_id}"
    )
    return parse_photos_page(response.text)[:wanted]


def ensure_covers(
    session: requests.Session,
    *,
    config: Config,
    state: State,
    subject: Subject,
    index: dict[str, Entry],
    wanted: int,
    counts: dict,
) -> list[str]:
    """Make sure the record has *wanted* cover candidates; return **all** live keys.

    ``wanted == 1`` uses the subject page's main poster (no extra request — the
    default). Larger values fetch the photo album on demand. Keys are only ever
    appended: existing candidates stay untouched.

    Repeated runs must not download anything: a record that already references
    ``wanted`` covers whose files are present is satisfied as-is, and a referenced
    file that went missing is refilled **under its own key** (never as a new
    candidate — that used to duplicate the poster on every state-cache change).
    """
    subject_id = subject.id
    entry = index.get(subject_id)
    existing = [str(key) for key in (entry.machine.get("covers") or [])] if entry else []
    ensured: list[str] = []
    main_photo = re.search(r"(p\d+\.jpg|p\d+\.webp)", subject.cover_url or "")
    main_id = main_photo.group(1) if main_photo else ""
    known = state.cover_keys(subject_id)

    def has_cover_file(key: str) -> bool:
        return bool(key) and (config.cover_dir / key).is_file()

    def cover_index(key: str) -> int:
        match = re.search(r"/(\d{2})\.webp$", key)
        return int(match.group(1)) if match else 0

    def next_index() -> int:
        staged = max([cover_index(key) for key in existing + ensured] or [0]) + 1
        while (config.cover_dir / cover_key(subject_id, staged)).is_file():
            staged += 1
        return staged

    def download(photo_id: str, url: str, at_index: int) -> None:
        try:
            if store_cover(
                session,
                config=config,
                state=state,
                subject_id=subject_id,
                index=at_index,
                photo_id=photo_id,
                url=url,
                counts=counts,
            ):
                ensured.append(state.cover_keys(subject_id)[photo_id])
        except (SyncError, OSError, ValueError) as exc:
            # one bad poster must not fail the item (or the run): besides request
            # failures this covers a non-image body (`Image.open` → OSError) and
            # a decoder error (ValueError)
            counts["failed"] += 1
            state.failures[f"cover:{subject_id}"] = str(exc)
            print(f"    cover failed: {exc.__class__.__name__}: {exc}", file=sys.stderr)

    # 1) every referenced key that still has its file is satisfied
    for key in existing:
        if has_cover_file(key):
            ensured.append(key)

    # 2) a referenced key whose file disappeared is refilled at its own index
    for key in existing:
        if has_cover_file(key):
            continue
        index_of_key = cover_index(key)
        if index_of_key == 1 and main_id and subject.cover_url:
            print(f"    cover {key} missing — refilling", file=sys.stderr)
            download(main_id, subject.cover_url, 1)
        else:
            counts["failed"] += 1
            state.failures[f"cover:{subject_id}"] = f"missing local file, unknown photo: {key}"
            print(f"    cover {key} missing locally; re-run with --covers N", file=sys.stderr)

    # 3) top up to `wanted` (only when below the target). A poster already known
    #    to the state cache is re-attached rather than re-downloaded — that is how
    #    a yml that lost its `covers` reference is repaired.
    if len(ensured) < wanted and subject.cover_url and main_id:
        known_key = known.get(main_id, "")
        if has_cover_file(known_key):
            ensured.append(known_key)
        elif known_key:
            download(main_id, subject.cover_url, cover_index(known_key) or next_index())
        else:
            download(main_id, subject.cover_url, next_index())

    if wanted > 1 and len(ensured) < wanted:
        try:
            candidates = fetch_album_candidates(session, subject.id, wanted)
        except SyncError as exc:
            print(f"    album unavailable: {exc}", file=sys.stderr)
            candidates = []
        for candidate in candidates:
            if len(ensured) >= wanted:
                break
            if candidate.photo_id == main_id or candidate.photo_id in known:
                continue
            download(candidate.photo_id, candidate.url, next_index())
    return sorted(set(ensured))


def cover_digest(path: Path) -> str:
    return hashlib.md5(path.read_bytes()).hexdigest()


def dedupe_local_covers(
    config: Config,
    index: dict[str, Entry],
    *,
    dry_run: bool,
    sample: int = 10,
) -> int:
    """Drop local cover files that duplicate a *referenced* file in the same dir.

    A run interrupted between two state saves used to lose the ``photo_id → key``
    map for the last records it fetched, so the same poster was downloaded again
    as the next ``NN`` and the first copy stayed behind as an orphan (never
    referenced, therefore never uploaded — but downloaded for nothing). The sync
    now saves the map per item; this repairs the damage already done.

    Only byte-identical siblings of a referenced file are removed: an
    unreferenced file that nothing duplicates is kept, because it may belong to a
    record whose skeleton has not been written yet.
    """
    root = config.cover_dir
    if not root.is_dir():
        print("film-tv-dedupe: no local cover directory — nothing to do")
        return 0
    referenced = {
        str(key)
        for entry in index.values()
        for key in [*(entry.machine.get("covers") or []), entry.user.get("cover")]
        if key
    }
    known: dict[str, dict[str, str]] = {}
    for key in sorted(referenced):
        path = root / key
        if path.is_file():
            known.setdefault(str(Path(key).parent), {})[cover_digest(path)] = key

    duplicates: list[tuple[Path, str]] = []
    for path in sorted(root.rglob("*.webp")):
        key = path.relative_to(root).as_posix()
        if key in referenced:
            continue
        twin = known.get(str(path.parent.relative_to(root)), {}).get(cover_digest(path))
        if twin:
            duplicates.append((path, twin))

    freed = sum(path.stat().st_size for path, _ in duplicates) / 1024 / 1024
    for path, twin in duplicates[:sample]:
        print(f"    - {path.relative_to(root)} (same bytes as {twin})")
    if len(duplicates) > sample:
        print(f"    … and {len(duplicates) - sample} more")
    if not dry_run:
        for path, _twin in duplicates:
            path.unlink()
    print(
        f"film-tv-dedupe: {len(duplicates)} duplicate local cover file(s) ({freed:.1f} MB)"
        + (" — dry-run, re-run with --confirm to delete" if dry_run else " deleted")
    )
    return len(duplicates)


# --- record updates ----------------------------------------------------------


def load_index(config: Config) -> dict[str, Entry]:
    """All stored records by subject id (the incremental baseline; no extra file)."""
    index: dict[str, Entry] = {}
    for path in sorted(config.data_dir.glob("*.yml")):
        if path.name in NON_YEAR_FILES:
            continue
        for entry in read_entries(path):
            if entry.id:
                index[entry.id] = entry
    return index


def taken_slugs(index: dict[str, Entry]) -> set[str]:
    return {str(entry.machine.get("slug")) for entry in index.values() if entry.machine.get("slug")}


def pending_details(index: dict[str, Entry]) -> list[Entry]:
    """Records whose detail page was never fetched, newest first.

    Records with **no date at all** come first: their list row carried no date
    span, so the detail page is the only source of the 看过 date (``interest``
    block) — and until it lands the record cannot be placed in a year file, the
    pages have nothing to group it under and the year statistics are incomplete.
    They sort last by date, so without this they would wait for the whole backfill
    (19 of 4292 records on the first pass). Records that are gone on Douban are
    not pending at all and are skipped here.
    """
    pending = [
        entry
        for entry in index.values()
        if not entry.meta.get("detail_synced_at") and not entry.meta.get("missing_since")
    ]
    dateless: list[Entry] = []
    dated: list[Entry] = []
    for entry in sort_entries(pending):
        (dateless if not entry.effective_date() else dated).append(entry)
    return dateless + dated


def write_records(config: Config, index: dict[str, Entry]) -> list[str]:
    """Rewrite the year files from the index; report the ones that changed.

    The index is the source of truth, so a record that migrated to another
    watching year is both written into its new file and dropped from the old one
    (an emptied year file is removed by :func:`write_file`).
    """
    by_file: dict[str, list[Entry]] = {}
    for entry in index.values():
        name = year_file_name(file_prefix(entry.machine.get("type")), _entry_year(entry))
        by_file.setdefault(name, []).append(entry)
    written: list[str] = []
    for name, entries in sorted(by_file.items()):
        path = config.data_dir / name
        if write_file(path, sort_entries(entries)):
            written.append(name)
    for path in sorted(config.data_dir.glob("*.yml")):
        if path.name in NON_YEAR_FILES:
            continue
        if path.name not in by_file and path.is_file():
            path.unlink()  # year file emptied by migrations
            written.append(path.name)
    return written


def _entry_year(entry: Entry) -> str | None:
    return assign_year(entry.machine.get("marked_at"), entry.user.get("watched_at"))


# --- main sync ---------------------------------------------------------------


@dataclass
class Task:
    """One detail-page job: which row, which list it came from, and why."""

    item: ListItem
    kind: str
    type_filter: str
    #: True for ``--refresh-details``: bypass the fetch cache on purpose
    refresh: bool = False


def item_from_entry(entry: Entry) -> ListItem:
    """Rebuild the list-row view of a stored record (backfill / refresh jobs)."""
    return ListItem(
        id=entry.id,
        title=str(entry.machine.get("title") or ""),
        user_rating=entry.machine.get("user_rating"),
        marked_at=entry.machine.get("marked_at"),
        tags=list(entry.machine.get("tags") or []),
        comment=str(entry.machine.get("douban_comment") or ""),
    )


def cap_queue(tasks: list[Task], limit: int | None) -> list[Task]:
    """Apply ``--limit`` to a queue whose head is already the newest work.

    ``build_queue`` puts this run's new/changed rows first and the pending
    backfill after them, so a small ``--limit`` can never starve a film the
    developer just marked: it is fetched even when thousands of older skeletons
    are still missing their details (and it is safe to interrupt at any point —
    the rest stay queued as skeletons).
    """
    if not limit:
        return list(tasks)
    return tasks[:limit]


def build_queue(
    *,
    queued: list[tuple[ListItem, str, str]],
    index: dict[str, Entry],
    refresh_details: int | None,
) -> list[Task]:
    """Detail queue: new/changed rows first, then the backfill (dateless, newest).

    ``--refresh-details N`` replaces the backfill with the N most recently marked
    records that already have details (the "I edited some comments on Douban"
    case), which is the only job that bypasses the fetch cache.
    """
    tasks = [Task(item, kind, type_filter) for item, kind, type_filter in queued]
    queued_ids = {task.item.id for task in tasks}
    if refresh_details is not None:
        for entry in sort_entries(list(index.values())):
            if len(tasks) - len(queued) >= refresh_details:
                break
            if entry.meta.get("detail_synced_at") and entry.id not in queued_ids:
                tasks.append(
                    Task(
                        item_from_entry(entry),
                        str(entry.machine.get("status") or "collect"),
                        str(entry.machine.get("type") or ""),
                        refresh=True,
                    )
                )
        return tasks
    for entry in pending_details(index):
        if entry.id not in queued_ids:
            tasks.append(
                Task(
                    item_from_entry(entry),
                    str(entry.machine.get("status") or "collect"),
                    str(entry.machine.get("type") or ""),
                )
            )
    return tasks


@dataclass
class SyncContext:
    """Shared state of one sync run (avoids threading eight arguments around)."""

    config: Config
    taxonomy: Taxonomy
    state: State
    index: dict[str, Entry]
    session: requests.Session
    list_session: requests.Session
    account_session: requests.Session
    counts: dict
    taken: set[str]
    covers: int
    #: archive person directory (personage id → display label), grown as details land
    persons: dict[str, str] = field(default_factory=dict)
    dry_run: bool = False
    list_used_account: bool = False
    #: list pages that had to go through the account session (see `walk_lists`)
    list_account_pages: int = 0
    today: str = field(default_factory=lambda: date.today().isoformat())

    def merge(
        self,
        item: ListItem,
        *,
        kind: str,
        type_filter: str,
        subject: Subject | None,
        missing_since: str | None = None,
        missing_reason: str | None = None,
        covers_added: list[str] | None = None,
    ) -> Entry:
        """Merge one row (+ detail) into the index and return the stored entry."""
        existing = self.index.get(item.id)
        fields = build_machine(
            list_item=item,
            subject=subject,
            type_=type_filter or None,
            status=kind,
            taxonomy=self.taxonomy,
        )
        entry = merge_record(
            existing,
            fields=fields,
            subject=subject,
            subject_id=item.id,
            taxonomy=self.taxonomy,
            taken_slugs=self.taken,
            fingerprint_value=record_fingerprint(
                {
                    "status": kind,
                    "type": type_filter,
                    "title": item.title,
                    "user_rating": item.user_rating,
                    "marked_at": item.marked_at,
                },
                item,
            ),
            covers_added=covers_added,
            detail_fetched=subject is not None,
            today=self.today,
            missing_since=missing_since,
            missing_reason=missing_reason,
        )
        if existing is None:
            self.counts["new"] = self.counts.get("new", 0) + 1
        if not self.dry_run:  # a dry run must leave the working tree untouched
            self.index[item.id] = entry
            slug = str(entry.machine.get("slug") or "")
            # only real slugs are reserved: an empty string would make the very
            # next record collide with ""
            if slug:
                self.taken.add(slug)
        return entry

    def apply_covers(
        self,
        item: ListItem,
        *,
        kind: str,
        type_filter: str,
        subject: Subject,
        entry: Entry,
    ) -> None:
        """Fetch cover candidates for a just-synced record (never drops any)."""
        if self.covers <= 0:
            return
        ensured = ensure_covers(
            self.session,
            config=self.config,
            state=self.state,
            subject=subject,
            index=self.index,
            wanted=self.covers,
            counts=self.counts,
        )
        known = {str(key) for key in (entry.machine.get("covers") or [])}
        new_keys = [key for key in ensured if key not in known]
        if new_keys:
            # re-merge so `covers` and `meta.machine_hash` stay consistent
            self.merge(
                item,
                kind=kind,
                type_filter=type_filter,
                subject=subject,
                covers_added=new_keys,
            )

    def write(self) -> list[str]:
        return write_records(self.config, self.index)


def run_sync(args) -> int:
    load_env_files()
    config = load_config()
    taxonomy = Taxonomy.load(config.taxonomy_path)
    state = State(config.state_dir)
    index = load_index(config)
    print(
        f"film-tv sync: {len(index)} records stored, taxonomy v{taxonomy.rules_version}, "
        f"{'dry-run' if args.dry_run else 'writing'}"
    )

    if args.dedupe_covers:
        # offline maintenance: no cookie, no network, nothing else to sync
        dedupe_local_covers(config, index, dry_run=not args.confirm)
        return 0

    if args.only:
        return sync_one(args, config=config, taxonomy=taxonomy, state=state, index=index)

    credential = check_cookies(load_cookie_header())
    if not credential.ok:
        print(f"Douban cookie unusable ({credential.reason}) — running the login flow")
        credential = ensure_cookies()
    if not credential.ok or not credential.user_id:
        raise SyncError(f"no usable Douban session: {credential.reason}")
    user_id = credential.user_id
    print(f"  session: user {user_id} (lists are read anonymously)")

    counts = {"details": 0, "covers": 0, "failed": 0, "missing": 0, "new": 0}
    cookie_header = load_cookie_header() or ""
    ctx = SyncContext(
        config=config,
        taxonomy=taxonomy,
        state=state,
        index=index,
        session=build_session(cookie_header),
        list_session=anonymous_session(),
        account_session=build_session(cookie_header),
        counts=counts,
        taken=taken_slugs(index),
        covers=args.covers,
        persons=read_person_ids(config.data_dir / PERSON_IDS_FILE),
        dry_run=args.dry_run,
    )
    baseline = dict(index)
    seen, queued, pages = walk_lists(
        ctx,
        user_id=user_id,
        baseline=baseline,
        max_pages=args.pages,
        full=args.full,
        # `--prune` compares the whole archive against the walk, so it must never
        # resume mid-list (the skipped head would be marked as deleted)
        resume=args.full and not args.prune,
    )
    account_note = (
        f" [account session: {ctx.list_account_pages}/{pages} pages]"
        if ctx.list_used_account
        else " [anonymous]"
    )
    print(
        f"  walk: {len(seen)} rows from {pages} page(s), {len(queued)} need a detail refill"
        + account_note
    )
    if not args.dry_run:
        ctx.write()
        ctx.state.save()

    tasks = build_queue(queued=queued, index=index, refresh_details=args.refresh_details)
    # `--prune` only marks the records that dropped out of the collection; the
    # detail queue stays what it is, so a prune run never re-fetches the whole
    # archive (or starves the pending backfill with its `--limit`)
    queue = cap_queue(tasks, DEFAULT_LIMIT if args.limit is None else args.limit)
    print(
        f"  queue: {len(queue)} details "
        f"({sum(1 for task in queue if task.refresh)} forced refresh, "
        f"{sum(1 for task in queue if not task.refresh)} new/changed or backfill)"
    )
    if args.dry_run:
        for task in queue:
            marker = "refresh" if task.refresh else "fetch"
            print(
                f"    would {marker} {task.kind}/{task.type_filter} {task.item.id} "
                f"{task.item.title[:36]}"
            )
        if args.prune:
            _report_prune(seen, index)
        return 0

    total = len(queue)
    for position, task in enumerate(queue, start=1):
        _sync_item(ctx, task, progress=(position, total))
        if position % 50 == 0:  # flush so a crash loses at most one batch
            ctx.state.save()
            ctx.write()
            save_person_ids(ctx)
            print(f"  … flushed after {position} details", flush=True)

    if args.prune:
        counts["missing"] += _apply_prune(ctx, seen)

    written = ctx.write()
    save_person_ids(ctx)
    state.save()
    print(
        f"\ndetails {counts['details']} | covers {counts['covers']} | failed {counts['failed']} "
        f"| new {counts['new']} | missing {counts['missing']} | files written {len(written)}"
    )
    print(backfill_progress(index))
    if written:
        print("  " + ", ".join(written))
    run_derive_hook()
    return 0


def subject_is_empty(subject: Subject) -> bool:
    """True when the page carried nothing: the subject was taken down.

    Douban answers an empty shell for some removed subjects — no title, no score,
    no genres and no ``#interest_sect_level``. The HTML fixtures in
    ``tests/fixtures/film_tv/`` pin the parsers, so an empty parse means the page
    really is empty rather than the markup having drifted.
    """
    interest = subject.interest
    return not any(
        (
            str(subject.title or "").strip(),
            subject.douban_score is not None,
            subject.year,
            subject.genres,
            subject.directors,
            subject.casts,
            subject.runtime,
            subject.cover_url,
            interest.status,
            interest.marked_at,
            interest.user_rating is not None,
        )
    )


def _fetch_detail(
    ctx: SyncContext,
    item: ListItem,
    label: str,
    *,
    kind: str,
    type_filter: str,
    dated: bool,
) -> Subject | None:
    """Fetch one detail page, confirming an empty answer once.

    Returns the subject, or ``None`` when there is nothing more to do with this
    item: it is **gone** on Douban (the record has been marked missing) or the
    fetch **failed** (recorded in ``state.failures``, retried on a later run).

    An empty page is what Douban answers both for a taken-down subject and while
    it is throttling a session, and being wrong is expensive: a record marked
    missing is neither fetched nor published again (the mark is cleared only when
    a later fetch succeeds). So an empty page is re-fetched once, and a record
    that *has* a date is never marked missing from it — an empty page for a
    dated record is treated as a failure and retried later.
    """
    for attempt in range(EMPTY_SUBJECT_RETRIES + 1):
        try:
            subject = fetch_subject(ctx.session, item.id, person_style=ctx.config.person_name_style)
            ctx.counts["details"] += 1
            time.sleep(DETAIL_DELAY)
        except BlockedError:
            raise
        except GoneError as exc:
            _mark_gone(ctx, item, kind=kind, type_filter=type_filter, label=label, why=str(exc))
            return None
        except SyncError as exc:
            ctx.counts["failed"] += 1
            ctx.state.failures[item.id] = str(exc)
            print(f"  {label} {item.id} FAILED: {exc}", file=sys.stderr, flush=True)
            return None
        if not subject_is_empty(subject):
            ctx.state.save_detail(item.id, subject)
            ctx.persons = merge_person_ids(
                ctx.persons, {pid: name for name, pid in subject.person_ids.items()}
            )
            return subject
        if attempt < EMPTY_SUBJECT_RETRIES:
            print(
                f"  {label} {item.id} empty subject page — retrying once (a throttled "
                "session answers empty too)",
                file=sys.stderr,
                flush=True,
            )
            time.sleep(RETRY_BACKOFF)
    if dated:
        ctx.counts["failed"] += 1
        ctx.state.failures[item.id] = "empty subject page"
        print(f"  {label} {item.id} FAILED: empty subject page", file=sys.stderr, flush=True)
        return None
    _mark_gone(ctx, item, kind=kind, type_filter=type_filter, label=label, why="empty page")
    return None


def _mark_gone(
    ctx: SyncContext,
    item: ListItem,
    *,
    kind: str,
    type_filter: str,
    label: str,
    why: str,
) -> None:
    """Keep the record as an archive entry, marked so it is never fetched again."""
    ctx.counts["missing"] = ctx.counts.get("missing", 0) + 1
    ctx.state.failures.pop(item.id, None)
    print(f"  {label} {item.id} gone on Douban — skipped ({why})", flush=True)
    ctx.merge(
        item,
        kind=kind,
        type_filter=type_filter,
        subject=None,
        missing_since=ctx.today,
        missing_reason="gone",
    )


def _sync_item(ctx: SyncContext, task: Task, *, progress: tuple[int, int]) -> None:
    """Fetch (or reuse) one row's detail page and merge it into the index."""
    item, kind, type_filter = task.item, task.kind, task.type_filter
    label = f"[{progress[0]}/{progress[1]}]"
    if item.deleted:
        _mark_gone(ctx, item, kind=kind, type_filter=type_filter, label=label, why="deleted")
        return

    existing = ctx.index.get(item.id)
    dated = bool(item.marked_at) or bool(existing and existing.user.get("watched_at"))
    # The cache only rescues a crashed run: a record that already has a detail
    # timestamp is either unchanged (not queued), changed (must be re-fetched) or
    # explicitly refreshed. A record without one may still have a cached parse
    # from a run that died before writing the files.
    cached = None
    if not task.refresh and (existing is None or not existing.meta.get("detail_synced_at")):
        cached = ctx.state.detail(item.id)
    # an empty page is not usable as a cache entry: fetching again either confirms
    # "gone" or gets the real page
    subject = cached if cached is not None and not subject_is_empty(cached) else None
    if subject is None:
        subject = _fetch_detail(ctx, item, label, kind=kind, type_filter=type_filter, dated=dated)
        if subject is None:
            return  # gone (marked as missing) or failed (recorded) — nothing to do
    entry = ctx.merge(item, kind=kind, type_filter=type_filter, subject=subject)
    verb = "refreshed" if task.refresh else "synced"
    print(
        f"  {label} {verb} {item.id} {entry.machine.get('title', '')[:30]}"
        f" [{entry.machine.get('category')}]",
        flush=True,
    )
    ctx.apply_covers(item, kind=kind, type_filter=type_filter, subject=subject, entry=entry)
    # the cover map is what keeps a re-run from downloading the same poster as a
    # new `NN.webp`; saving it per item (instead of only at the 50-item flush)
    # means an interrupted batch cannot orphan the files it just wrote
    ctx.state.save()


def _report_prune(seen, index: dict[str, Entry]) -> int:
    """Dry-run listing of records no longer present in the collection."""
    seen_ids = {item.id for item, _kind, _type in seen}
    missing = [
        entry
        for subject_id, entry in index.items()
        if subject_id not in seen_ids and not entry.meta.get("missing_since")
    ]
    for entry in missing:
        print(f"    would mark missing: {entry.id} {entry.machine.get('title', '')[:30]}")
    return len(missing)


def _apply_prune(ctx: SyncContext, seen) -> int:
    """Mark records that dropped out of the collection (``--prune --full``).

    Refuses to run on an empty walk: Douban answering an empty list (login wall /
    broken markup) would otherwise mark the *whole* archive as missing.
    """
    if not seen:
        raise SyncError(
            "--prune refused: the list walk returned no rows — nothing to compare "
            "against (run without --prune, check `film-tv-login --check`)"
        )
    seen_ids = {item.id for item, _kind, _type in seen}
    missing = 0
    for subject_id, entry in ctx.index.items():
        if subject_id in seen_ids or entry.meta.get("missing_since"):
            continue
        missing += 1
        entry.meta["missing_since"] = ctx.today
        # the row left my collection: a later walk that sees it again undoes this
        entry.meta["missing_reason"] = "pruned"
        print(f"    missing: {subject_id} {entry.machine.get('title', '')[:30]}")
    return missing


def sync_one(
    args, *, config: Config, taxonomy: Taxonomy, state: State, index: dict[str, Entry]
) -> int:
    """``--only <slug>``: refresh one record without walking any list."""
    target = next(
        (entry for entry in index.values() if entry.machine.get("slug") == args.only), None
    )
    if target is None:
        raise SyncError(f"--only {args.only}: no stored record has that slug")
    print(f"  --only {args.only}: {target.id} {target.machine.get('title', '')}")
    if args.dry_run:
        print(f"    would fetch {target.id}")
        return 0
    credential = check_cookies(load_cookie_header())
    if not credential.ok:
        credential = ensure_cookies()
    if not credential.ok:
        raise SyncError(f"no usable Douban session: {credential.reason}")
    counts = {"details": 0, "covers": 0, "failed": 0, "missing": 0, "new": 0}
    header = load_cookie_header() or ""
    session = build_session(header)
    kind = str(target.machine.get("status") or "collect")
    ctx = SyncContext(
        config=config,
        taxonomy=taxonomy,
        state=state,
        index=index,
        session=session,
        list_session=session,
        account_session=session,
        counts=counts,
        taken=taken_slugs(index),
        covers=args.covers,
    )
    _sync_item(
        ctx,
        Task(item_from_entry(target), kind, str(target.machine.get("type") or ""), refresh=True),
        progress=(1, 1),
    )
    written = ctx.write()
    save_person_ids(ctx)
    state.save()
    print(f"\ndetails {counts['details']} | covers {counts['covers']} | failed {counts['failed']}")
    if written:
        print("  written: " + ", ".join(written))
    run_derive_hook()
    return 0


def backfill_progress(index: dict[str, Entry]) -> str:
    """Overall first-pass progress: how many records still need their details.

    The per-item counter only shows the current batch, which says nothing about
    how far the 4292-record backfill has come — this line does.

    Records marked missing are **not** pending: nothing can be fetched for them
    (``gone`` on Douban, or pruned from the collection), so counting them would
    leave this line stuck above zero for good. They are reported separately; the
    ``details`` share still counts every synced record against the whole archive.
    """
    total = len(index)
    if not total:
        return "progress: no records yet"
    fetchable = [entry for entry in index.values() if not entry.meta.get("missing_since")]
    done = sum(1 for entry in index.values() if entry.meta.get("detail_synced_at"))
    pending = sum(1 for entry in fetchable if not entry.meta.get("detail_synced_at"))
    share = done / total * 100
    line = f"progress: details {done}/{total} ({share:.1f}%) | pending {pending}"
    gone = total - len(fetchable)
    if gone:
        line += f" | gone {gone}"
    return line


def save_person_ids(ctx: SyncContext) -> None:
    """Persist the archive person directory (id → name) when it grew."""
    if ctx.dry_run or not ctx.persons:
        return
    path = ctx.config.data_dir / PERSON_IDS_FILE
    if write_person_ids(path, ctx.persons):
        print(f"  people directory: {len(ctx.persons)} entries → {path.name}")


def run_derive_hook() -> None:
    """Run the derived-data step (design §3) after a successful write."""
    script = REPO_ROOT / "scripts" / "film_tv_derive.py"
    if not script.is_file():
        print("derive: skipped (scripts/film_tv_derive.py is missing from this checkout)")
        return
    print("derive: running scripts/film_tv_derive.py", flush=True)
    sys.stdout.flush()  # keep the child's output in order when piped
    subprocess.run([sys.executable, str(script)], check=False)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Sync the Douban film & TV collection into year files",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help=f"max detail pages per run (0 = all queued; default {DEFAULT_LIMIT})",
    )
    parser.add_argument(
        "--pages",
        type=int,
        default=None,
        help="stop after N list pages per tab (debugging / smoke tests; unsafe with --prune)",
    )
    parser.add_argument(
        "--full",
        action="store_true",
        help="walk every list page even when nothing changed (first pass / with --prune)",
    )
    parser.add_argument(
        "--prune",
        action="store_true",
        help="with --full: mark records no longer in the collection as missing (implies --full)",
    )
    parser.add_argument(
        "--covers",
        type=int,
        default=None,
        help="cover candidates per item (default: extra.film_tv.covers_default = main poster only)",
    )
    parser.add_argument("--only", default=None, help="refresh just this slug (skips the list walk)")
    parser.add_argument(
        "--refresh-details",
        nargs="?",
        const=REFRESH_DETAILS_DEFAULT,
        type=int,
        default=None,
        help="re-read the details of the N most recently marked records, ignoring fingerprints "
        f"(default {REFRESH_DETAILS_DEFAULT}) — use after editing comments on Douban",
    )
    parser.add_argument(
        "--dedupe-covers",
        action="store_true",
        help="offline: delete local cover files that duplicate a referenced one "
        "(dry-run unless --confirm)",
    )
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="with --dedupe-covers: actually delete the reported duplicates",
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="print the plan without fetching or writing"
    )
    args = parser.parse_args(argv)
    if args.prune:
        args.full = True
        if args.pages is not None:
            parser.error("--prune needs a complete walk: drop --pages")
    if args.only and args.limit is not None:
        print("--only ignores --limit", file=sys.stderr)
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    # load_env_files() happens in run_sync (the single entry point for both main
    # and the tests)
    config = load_config()
    if args.covers is None:
        args.covers = config.covers_default
    try:
        return run_sync(args)
    except BlockedError as exc:
        print(f"\nABORTED: {exc}", file=sys.stderr)
        return 2
    except SyncError as exc:
        print(f"\nERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
