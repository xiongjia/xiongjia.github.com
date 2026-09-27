"""Unit tests for the sync/check scripts' decision logic (no network).

The fetching itself is exercised by hand (`poe sync-film-tv`) — these tests pin
the parts that decide *what* to fetch and *where* it lands: the incremental
short-circuit, the detail queue order, year-file routing, cover keys, retry /
anti-bot behaviour, and the check script's findings.
"""

from __future__ import annotations

import io
import json
from pathlib import Path

import pytest
import requests
from PIL import Image

from scripts import film_tv_check, sync_film_tv
from shared.film_tv_model import Taxonomy, cover_key, machine_hash
from shared.film_tv_parse import Interest, ListItem, Subject
from shared.film_tv_store import Entry, read_entries, write_file

TAXONOMY_PATH = (
    Path(__file__).resolve().parents[1] / "docs" / "notes" / "film-tv" / "data" / "taxonomy.yml"
)


@pytest.fixture
def taxonomy() -> Taxonomy:
    return Taxonomy.load(TAXONOMY_PATH)


def make_entry(record_id: str = "1", **machine) -> Entry:
    base = {
        "id": record_id,
        "title": "Dune",
        "type": "movie",
        "category": "feature",
        "status": "collect",
        "user_rating": 5,
        "marked_at": "2021-10-01",
        "tags": ["Scifi"],
        "genres": ["科幻"],
        "regions": ["美国"],
        "covers": [cover_key("1", 1)],
        "slug": "dune",
        "douban_url": f"https://movie.douban.com/subject/{record_id}/",
    }
    base.update(machine)
    return Entry(
        machine=base,
        user={},
        user_raw="",
        meta={
            "detail_synced_at": "2026-09-27",
            "taxonomy_version": 1,
            "fingerprint": sync_film_tv.record_fingerprint(base, ListItem(id="1", title="Dune")),
            "machine_hash": machine_hash(base),
            "missing_since": None,
        },
    )


def row(**overrides) -> ListItem:
    item = ListItem(id="1", title="Dune", user_rating=5, marked_at="2021-10-01", tags=["Scifi"])
    for key, value in overrides.items():
        setattr(item, key, value)
    return item


# --- incremental short-circuit ----------------------------------------------


def test_needs_detail_for_unknown_row():
    assert sync_film_tv.needs_detail(row(), "collect", "movie", {}) is True


def test_needs_detail_false_for_unchanged_row():
    entry = make_entry()
    assert sync_film_tv.needs_detail(row(), "collect", "movie", {"1": entry}) is False


@pytest.mark.parametrize(
    "changed",
    [
        {"user_rating": 4},
        {"title": "Dune Part Two"},
        {"marked_at": "2022-01-01"},
        {"tags": []},
        {"status": "do"},
        {"type_filter": "tv"},
    ],
)
def test_needs_detail_true_when_a_list_field_changes(changed):
    entry = make_entry()
    status = changed.pop("status", "collect")
    type_filter = changed.pop("type_filter", "movie")
    assert sync_film_tv.needs_detail(row(**changed), status, type_filter, {"1": entry}) is True


def test_needs_detail_ignores_detail_only_changes():
    """Editing the stored detail fields must not look like a Douban-side change."""
    entry = make_entry()
    entry.machine["genres"] = ["剧情"]
    entry.machine["douban_comment"] = "later added comment"
    assert sync_film_tv.needs_detail(row(), "collect", "movie", {"1": entry}) is False


def test_needs_detail_true_when_a_missing_subject_returns():
    entry = make_entry(missing_since=None)
    entry.meta["missing_since"] = "2026-01-01"
    assert sync_film_tv.needs_detail(row(), "collect", "movie", {"1": entry}) is True


def test_deleted_row_with_missing_since_is_not_requeued():
    entry = make_entry(missing_since=None)
    entry.meta["missing_since"] = "2026-01-01"
    item = row(deleted=True, marked_at=None, user_rating=None)
    assert sync_film_tv.needs_detail(item, "collect", "movie", {"1": entry}) is False


# --- detail queue ------------------------------------------------------------


def test_build_queue_backfill_is_newest_first():
    index = {
        "1": make_entry("1", marked_at="2020-01-01"),
        "2": make_entry("2", marked_at="2019-01-01"),
        "3": make_entry("3", marked_at="2021-01-01"),
    }
    for entry in index.values():
        entry.meta["detail_synced_at"] = None
    tasks = sync_film_tv.build_queue(queued=[], index=index, refresh_details=None)

    assert [task.item.id for task in tasks] == ["3", "1", "2"]
    assert all(task.refresh is False for task in tasks)


def test_build_queue_puts_changed_rows_first():
    index = {"9": make_entry("9")}
    index["9"].meta["detail_synced_at"] = None
    changed = row(id="42", title="Changed")
    tasks = sync_film_tv.build_queue(
        queued=[(changed, "collect", "movie")], index=index, refresh_details=None
    )
    assert [task.item.id for task in tasks] == ["42", "9"]


def test_build_queue_refresh_mode_targets_recent_detailed_records():
    index = {
        "1": make_entry("1", marked_at="2020-01-01"),
        "2": make_entry("2", marked_at="2021-01-01"),
    }
    tasks = sync_film_tv.build_queue(queued=[], index=index, refresh_details=1)

    assert len(tasks) == 1
    assert tasks[0].item.id == "2"  # newest first
    assert tasks[0].refresh is True
    assert tasks[0].kind == "collect" and tasks[0].type_filter == "movie"


def test_new_row_is_never_starved_by_the_pending_backfill():
    """Marking a film while the first full pass is still running must work.

    build_queue() puts the new/changed rows first and the pending skeletons
    after them, so even `--limit 1` fetches the film just marked on Douban.
    """
    index = {str(n): make_entry(str(n), marked_at=f"20{10 + n % 10}-01-01") for n in range(1, 60)}
    for entry in index.values():
        entry.meta["detail_synced_at"] = None  # 59 skeletons still pending
    fresh = row(id="999", title="刚标记的新片", marked_at="2026-09-27")

    tasks = sync_film_tv.build_queue(
        queued=[(fresh, "collect", "movie")], index=index, refresh_details=None
    )
    queue = sync_film_tv.cap_queue(tasks, 1)

    assert [task.item.id for task in queue] == ["999"]
    # and with no limit the backfill is still queued behind it
    assert len(sync_film_tv.cap_queue(tasks, 0)) == 60
    assert [task.item.id for task in sync_film_tv.cap_queue(tasks, 3)][0] == "999"


# --- prune ------------------------------------------------------------------


def _ctx(index: dict[str, Entry]):
    # only `index` / `today` are read by the prune helpers, so the rest of the
    # dataclass (sessions, state dir, taxonomy) stays uninitialised
    ctx = sync_film_tv.SyncContext.__new__(sync_film_tv.SyncContext)
    ctx.index = index
    ctx.today = "2026-09-28"
    return ctx


def test_apply_prune_marks_only_vanished_records():
    index = {
        "1": make_entry("1"),
        "2": make_entry("2"),
        "3": make_entry("3"),
    }
    index["3"].meta["missing_since"] = "2026-01-01"  # already pruned earlier
    ctx = _ctx(index)

    marked = sync_film_tv._apply_prune(ctx, [(row(), "collect", "movie")])

    assert marked == 1
    assert index["1"].meta["missing_since"] is None
    assert index["2"].meta["missing_since"] == "2026-09-28"
    assert index["3"].meta["missing_since"] == "2026-01-01"  # date not refreshed


def test_apply_prune_refuses_an_empty_walk():
    # an empty list page (login wall / broken markup) must never mark the archive
    ctx = _ctx({"1": make_entry("1")})
    with pytest.raises(sync_film_tv.SyncError, match="prune refused"):
        sync_film_tv._apply_prune(ctx, [])
    assert ctx.index["1"].meta.get("missing_since") is None


def test_report_prune_counts_pending_records_only():
    index = {"1": make_entry("1"), "2": make_entry("2")}
    index["2"].meta["missing_since"] = "2026-01-01"
    assert sync_film_tv._report_prune([(row(), "collect", "movie")], index) == 0
    assert sync_film_tv._report_prune([], index) == 1


def test_cap_queue_without_limit_returns_everything():
    tasks = [sync_film_tv.Task(row(id=str(n)), "collect", "movie") for n in range(5)]
    assert sync_film_tv.cap_queue(tasks, None) == tasks
    assert len(sync_film_tv.cap_queue(tasks, 2)) == 2


def test_item_from_entry_round_trip():
    entry = make_entry()
    item = sync_film_tv.item_from_entry(entry)
    assert (item.id, item.title, item.user_rating) == ("1", "Dune", 5)
    assert item.tags == ["Scifi"]


# --- year-file routing -------------------------------------------------------


def test_write_records_routes_by_type_and_watching_year(tmp_path):
    index = {
        "1": make_entry("1", marked_at="2021-10-01", type="movie"),
        "2": make_entry("2", marked_at="2019-05-05", type="tv"),
        "3": make_entry("3", marked_at=None, type="movie"),
    }
    index["3"].user = {"watched_at": ""}
    config = _config(tmp_path)

    written = sync_film_tv.write_records(config, index)

    assert sorted(written) == ["movies-2021.yml", "movies-undated.yml", "tv-2019.yml"]
    assert [e.id for e in read_entries(tmp_path / "movies-2021.yml")] == ["1"]


def test_write_records_migrates_on_user_date_change(tmp_path):
    index = {"1": make_entry("1", marked_at="2009-05-01")}
    config = _config(tmp_path)
    sync_film_tv.write_records(config, index)
    assert (tmp_path / "movies-2009.yml").is_file()

    index["1"].user = {"watched_at": "2011-03-03"}
    written = sync_film_tv.write_records(config, index)

    assert (tmp_path / "movies-2011.yml").is_file()
    assert not (tmp_path / "movies-2009.yml").exists()  # emptied file is removed
    assert "movies-2011.yml" in written and "movies-2009.yml" in written


def test_write_records_ignores_taxonomy_file(tmp_path):
    (tmp_path / "taxonomy.yml").write_text("rules_version: 1\n", encoding="utf-8")
    config = _config(tmp_path)
    sync_film_tv.write_records(config, {"1": make_entry()})
    assert (tmp_path / "taxonomy.yml").is_file()


def test_load_index_reads_every_year_file(tmp_path):
    config = _config(tmp_path)
    write_file(tmp_path / "movies-2021.yml", [make_entry("1")])
    write_file(tmp_path / "tv-2020.yml", [make_entry("2", type="tv")])
    (tmp_path / "taxonomy.yml").write_text("rules_version: 1\n", encoding="utf-8")

    index = sync_film_tv.load_index(config)

    assert sorted(index) == ["1", "2"]
    assert index["1"].machine["type"] == "movie"


def _config(data_dir: Path) -> sync_film_tv.Config:
    return sync_film_tv.Config(
        data_dir=data_dir,
        json_dir=data_dir,
        local_prefix="assets/bucket/film-tv/",
        cover_dir=data_dir / "covers",
        covers_default=1,
        cover_max_dimension=800,
        cover_quality=80,
        person_name_style="hint",
    )


# --- HTTP retry / anti-bot ---------------------------------------------------


class FakeResponse:
    def __init__(self, status_code=200, text="", location="", content=b""):
        self.status_code = status_code
        self.text = text
        self.content = content
        self.headers = {"location": location} if location else {}


class FakeSession:
    """Session stub: yields the queued responses, recording every call."""

    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls: list[str] = []

    def get(self, url, timeout=None, allow_redirects=False, headers=None):
        self.calls.append(url)
        result = self.responses.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


def test_request_retries_transient_failures(monkeypatch):
    monkeypatch.setattr(sync_film_tv.time, "sleep", lambda _seconds: None)
    session = FakeSession(FakeResponse(503), FakeResponse(200, text="ok"))

    response = sync_film_tv.request(session, "http://x", what="test")

    assert response.text == "ok"
    assert len(session.calls) == 2


def test_request_gives_up_after_retries(monkeypatch):
    monkeypatch.setattr(sync_film_tv.time, "sleep", lambda _seconds: None)
    session = FakeSession(*[requests.Timeout() for _ in range(4)])
    with pytest.raises(sync_film_tv.SyncError, match="Timeout"):
        sync_film_tv.request(session, "http://x", what="test")
    assert len(session.calls) == sync_film_tv.MAX_RETRIES + 1


def test_request_aborts_on_anti_bot_challenge():
    session = FakeSession(FakeResponse(302, location="https://sec.douban.com/c?r=https%3A%2F%2F"))
    with pytest.raises(sync_film_tv.BlockedError):
        sync_film_tv.request(session, "http://x", what="list")
    assert len(session.calls) == 1  # never retried


def test_request_aborts_on_403():
    session = FakeSession(FakeResponse(403))
    with pytest.raises(sync_film_tv.BlockedError):
        sync_film_tv.request(session, "http://x", what="subject")


def test_request_raises_on_login_redirect():
    session = FakeSession(FakeResponse(302, location="https://www.douban.com/accounts/login"))
    with pytest.raises(sync_film_tv.SyncError, match="login"):
        sync_film_tv.request(session, "http://x", what="subject")


def test_request_reports_418_without_retrying():
    session = FakeSession(FakeResponse(418))
    with pytest.raises(sync_film_tv.SyncError, match="HTTP 418"):
        sync_film_tv.request(session, "http://x", what="cover")
    assert len(session.calls) == 1


def test_anonymous_session_has_no_cookie():
    session = sync_film_tv.anonymous_session()
    assert "Cookie" not in session.headers
    assert "douban" in session.headers["User-Agent"].lower() or session.headers["User-Agent"]


# --- cover pipeline ----------------------------------------------------------


def test_convert_to_webp_caps_long_edge(tmp_path):
    source = io.BytesIO()
    Image.new("RGB", (1080, 1600), "red").save(source, "JPEG")
    target = tmp_path / "cover.webp"

    size = sync_film_tv.convert_to_webp(source.getvalue(), target, max_dimension=800, quality=80)

    assert size == (540, 800)
    assert target.is_file()
    with Image.open(target) as written:
        assert written.size == (540, 800)
        assert written.format == "WEBP"


def test_store_cover_skips_existing_file(tmp_path):
    config = _config(tmp_path)
    target = config.cover_dir / cover_key("1", 1)
    target.parent.mkdir(parents=True)
    target.write_bytes(b"already here")
    state = sync_film_tv.State(tmp_path / "state")
    counts = {"covers": 0}

    stored = sync_film_tv.store_cover(
        FakeSession(),
        config=config,
        state=state,
        subject_id="1",
        index=1,
        photo_id="p1.jpg",
        url="https://img3.doubanio.com/view/photo/m/public/p1.jpg",
        counts=counts,
    )

    assert stored is False
    assert counts["covers"] == 0
    assert state.cover_keys("1") == {"p1.jpg": "covers/1/01.webp"}


def test_ensure_covers_is_satisfied_by_existing_files(tmp_path):
    """A record that already has its cover must not download anything again.

    Regression: after the cover state cache switched from slug keys to Douban-id
    keys, a look-up miss re-downloaded the poster as a brand-new candidate
    (``02.webp``) on every run, duplicating every cover.
    """
    config = _config(tmp_path)
    target = config.cover_dir / cover_key("1", 1)
    target.parent.mkdir(parents=True)
    target.write_bytes(b"already here")
    state = sync_film_tv.State(tmp_path / "state")  # empty cover cache on purpose
    subject = Subject(
        id="1",
        title="Dune",
        cover_url="https://img3.doubanio.com/view/photo/s_ratio_poster/public/p1.jpg",
    )
    entry = make_entry("1")
    entry.machine["covers"] = ["covers/1/01.webp"]

    calls: list[str] = []

    class ExplodingSession:
        def get(self, url, **_kwargs):  # any request is a bug
            calls.append(url)
            raise AssertionError("no download expected")

    ensured = sync_film_tv.ensure_covers(
        ExplodingSession(),
        config=config,
        state=state,
        subject=subject,
        index={"1": entry},
        wanted=1,
        counts={"covers": 0, "failed": 0},
    )

    assert ensured == ["covers/1/01.webp"]
    assert calls == []
    assert not (config.cover_dir / cover_key("1", 2)).exists()


def test_ensure_covers_refills_a_missing_file_at_its_own_key(tmp_path):
    config = _config(tmp_path)
    config.cover_dir.mkdir(parents=True, exist_ok=True)
    state = sync_film_tv.State(tmp_path / "state")
    subject = Subject(
        id="1",
        title="Dune",
        cover_url="https://img3.doubanio.com/view/photo/s_ratio_poster/public/p1.jpg",
    )
    entry = make_entry("1")
    entry.machine["covers"] = ["covers/1/01.webp"]  # referenced, file deleted locally
    source = io.BytesIO()
    Image.new("RGB", (20, 30), "blue").save(source, "JPEG")

    class OneShotSession:
        def __init__(self, payload):
            self.payload = payload
            self.calls = 0

        def get(self, url, **_kwargs):
            self.calls += 1
            return FakeResponse(200, content=self.payload)

    session = OneShotSession(source.getvalue())
    ensured = sync_film_tv.ensure_covers(
        session,
        config=config,
        state=state,
        subject=subject,
        index={"1": entry},
        wanted=1,
        counts={"covers": 0, "failed": 0},
    )

    assert ensured == ["covers/1/01.webp"]  # same key, not a new candidate
    assert (config.cover_dir / cover_key("1", 1)).is_file()
    assert not (config.cover_dir / cover_key("1", 2)).exists()


def test_ensure_covers_reports_existing_files_without_downloading(tmp_path):
    """A yml that lost its cover reference must be repaired, not left empty."""
    config = _config(tmp_path)
    target = config.cover_dir / cover_key("1", 1)
    target.parent.mkdir(parents=True)
    target.write_bytes(b"already here")
    state = sync_film_tv.State(tmp_path / "state")
    state.remember_cover("1", "p1.jpg", "covers/1/01.webp")
    subject = Subject(
        id="1",
        title="Dune",
        cover_url="https://img3.doubanio.com/view/photo/s_ratio_poster/public/p1.jpg",
    )

    ensured = sync_film_tv.ensure_covers(
        FakeSession(),
        config=config,
        state=state,
        subject=subject,
        index={},
        wanted=1,
        counts={"covers": 0, "failed": 0},
    )

    assert ensured == ["covers/1/01.webp"]


def test_ensure_covers_survives_an_undecodable_poster(tmp_path, monkeypatch, capsys):
    """A CDN body that is not an image must fail one cover, not the whole run.

    `Image.open` raises OSError (UnidentifiedImageError) for an HTML error page;
    that used to escape ensure_covers and crash the sync.
    """
    config = _config(tmp_path)
    config.cover_dir.mkdir(parents=True, exist_ok=True)
    state = sync_film_tv.State(tmp_path / "state")
    subject = Subject(
        id="1",
        title="Dune",
        cover_url="https://img3.doubanio.com/view/photo/s_ratio_poster/public/p1.jpg",
    )
    counts = {"covers": 0, "failed": 0}

    def explode(*_args, **_kwargs):
        raise OSError("cannot identify image file")

    monkeypatch.setattr(sync_film_tv, "store_cover", explode)

    ensured = sync_film_tv.ensure_covers(
        FakeSession(),
        config=config,
        state=state,
        subject=subject,
        index={},
        wanted=1,
        counts=counts,
    )

    assert ensured == []
    assert counts["failed"] == 1
    assert "OSError" in capsys.readouterr().err


# --- check script ------------------------------------------------------------


def _write_archive(tmp_path: Path, entries: list[Entry], filename: str = "movies-2021.yml"):
    write_file(tmp_path / filename, entries)
    (tmp_path / "taxonomy.yml").write_text(
        TAXONOMY_PATH.read_text(encoding="utf-8"), encoding="utf-8"
    )


def run_checks(tmp_path: Path, taxonomy: Taxonomy):
    records = film_tv_check.load_archive(tmp_path, only=None, since=None)
    findings = film_tv_check.Findings()
    stats = film_tv_check.check_records(records, taxonomy, findings)
    return records, stats, findings


def test_check_records_passes_for_a_clean_archive(tmp_path, taxonomy):
    _write_archive(tmp_path, [make_entry("1", marked_at="2021-10-01")])
    _, stats, findings = run_checks(tmp_path, taxonomy)

    assert stats["records"] == 1
    assert findings.errors == []
    assert stats["categories"]["feature"] == 1


def test_check_records_flags_duplicate_slugs(tmp_path, taxonomy):
    _write_archive(
        tmp_path,
        [make_entry("1", slug="dune"), make_entry("2", slug="dune", marked_at="2021-10-02")],
    )
    _, _, findings = run_checks(tmp_path, taxonomy)

    assert any(item["check"] == "slug" for item in findings.errors)


def test_check_records_flags_bad_cover_key_and_user_cover(tmp_path, taxonomy):
    entry = make_entry("1")
    entry.machine["covers"] = ["assets/bucket/film-tv/covers/1/01.webp"]
    entry.user = {"cover": "covers/../1/01.webp"}
    _write_archive(tmp_path, [entry])
    _, _, findings = run_checks(tmp_path, taxonomy)

    checks = {item["check"] for item in findings.errors}
    assert {"cover-key", "user-cover"} <= checks


def test_check_records_flags_wrong_year_file(tmp_path, taxonomy):
    _write_archive(tmp_path, [make_entry("1", marked_at="2020-01-01")], "movies-2021.yml")
    _, _, findings = run_checks(tmp_path, taxonomy)

    assert any(item["check"] == "file-year" for item in findings.errors)


def test_check_records_flags_hand_edited_machine_fields(tmp_path, taxonomy):
    entry = make_entry("1")
    entry.machine["title"] = "hand edited"
    _write_archive(tmp_path, [entry])
    _, _, findings = run_checks(tmp_path, taxonomy)

    assert any(item["check"] == "machine-hash" for item in findings.items)


def test_check_records_flags_unnormalized_region(tmp_path, taxonomy):
    entry = make_entry("1")
    entry.machine["regions"] = ["中国大陆"]  # an alias, not the canonical value
    _write_archive(tmp_path, [entry])
    _, _, findings = run_checks(tmp_path, taxonomy)

    assert any(item["check"] == "region-alias" for item in findings.errors)


def test_check_records_lists_reclassification_candidates(tmp_path, taxonomy):
    entry = make_entry("1")
    entry.machine["genres"] = ["剧情", "动画"]
    entry.machine["category"] = "feature"
    entry.machine["type"] = "tv"
    _write_archive(tmp_path, [entry], "tv-2021.yml")
    _, stats, _ = run_checks(tmp_path, taxonomy)

    assert stats["reclassify"] == [("1", "feature", "anime")]


def test_check_derived_json_detects_hidden_leak(tmp_path, taxonomy):
    entry = make_entry("1")
    entry.user = {"hidden": True}
    _write_archive(tmp_path, [entry])
    json_dir = tmp_path / "assets"
    json_dir.mkdir()
    (json_dir / "index.json").write_text(
        '{"months": {"2021-10": {"shard": "shard-0001.json", "offset": 0, "count": 1}}}'
    )
    (json_dir / "shard-0001.json").write_text(
        json.dumps(
            {
                "count": 1,
                "first_date": "2021-10-01",
                "last_date": "2021-10-01",
                "items": [{"id": "1", "date": "2021-10-01"}],
            }
        )
    )
    records = film_tv_check.load_archive(tmp_path, only=None, since=None)
    findings = film_tv_check.Findings()

    info = film_tv_check.check_derived_json(json_dir, records, findings)

    assert info["shards"] == 1 and info["entries"] == 1
    assert any(item["check"] == "json-leak" for item in findings.errors)


def test_check_derived_json_reports_missing_shard(tmp_path):
    json_dir = tmp_path / "assets"
    json_dir.mkdir()
    (json_dir / "index.json").write_text(
        '{"months": {"2021-10": {"shard": "shard-0001.json", "offset": 0, "count": 1}}}'
    )
    findings = film_tv_check.Findings()

    info = film_tv_check.check_derived_json(json_dir, [], findings)

    assert info["missing"] == ["shard-0001.json"]
    assert any("missing shard" in item["message"] for item in findings.errors)


def test_check_derived_json_rejects_an_index_without_months(tmp_path):
    json_dir = tmp_path / "assets"
    json_dir.mkdir()
    (json_dir / "index.json").write_text('{"totals": {"records": 0}}')
    findings = film_tv_check.Findings()

    film_tv_check.check_derived_json(json_dir, [], findings)

    assert any("no `months`" in item["message"] for item in findings.errors)


def test_check_derived_json_flags_stale_derived_data(tmp_path):
    """Committed derived files must match the committed year files."""
    import pathlib

    from shared.film_tv_store import write_file

    data_dir = tmp_path / "data"
    data_dir.mkdir()
    json_dir = tmp_path / "assets"
    json_dir.mkdir()
    write_file(data_dir / "movies-2021.yml", [make_entry("1"), make_entry("2")])
    records = film_tv_check.load_archive(data_dir, only=None, since=None)
    # derived data only knows about one record → stale
    (json_dir / "index.json").write_text(
        json.dumps(
            {
                "totals": {"records": 1},
                "months": {"2021-10": {"shard": "shard-0001.json", "offset": 0, "count": 1}},
            }
        )
    )
    (json_dir / "shard-0001.json").write_text(
        json.dumps({"count": 1, "items": [{"id": "1", "date": "2021-10-01"}]})
    )
    findings = film_tv_check.Findings()

    film_tv_check.check_derived_json(json_dir, records, findings)

    stale = [item for item in findings.errors if item["check"] == "derived-stale"]
    assert len(stale) == 2  # index totals + shard total
    assert all("poe film-tv-derive" in item["message"] for item in stale)
    assert pathlib.Path(json_dir / "index.json").is_file()  # never writes


def test_check_bucket_config_matches_mkdocs_headings():
    findings = film_tv_check.Findings()
    info = film_tv_check.check_bucket_config(findings, local_prefix="assets/bucket/film-tv/")

    assert info["mapping"]["remote_prefix"] == "data/film-tv"
    assert info["mapping"]["base_url"].endswith("/data/film-tv")
    assert findings.errors == []


def test_build_machine_survives_a_skeleton_merge(taxonomy):
    """A list-only refresh must not clear what the detail page told us."""
    subject = Subject(
        id="1",
        title="Dune",
        genres=["科幻"],
        regions_raw=["美国"],
        runtime=155,
        interest=Interest(status="collect", marked_at="2021-10-01", user_rating=5),
    )
    fields = sync_film_tv.build_machine(
        list_item=row(), subject=subject, type_="movie", status="collect", taxonomy=taxonomy
    )
    entry = sync_film_tv.merge_record(
        None,
        fields=fields,
        subject=subject,
        subject_id="1",
        taxonomy=taxonomy,
        taken_slugs=set(),
        fingerprint_value="f" * 8,
        detail_fetched=True,
        today="2026-09-27",
    )
    index = {"1": entry}

    skeleton = sync_film_tv.build_machine(
        list_item=row(user_rating=4),
        subject=None,
        type_="movie",
        status="collect",
        taxonomy=taxonomy,
    )
    merged = sync_film_tv.merge_record(
        index["1"],
        fields=skeleton,
        subject=None,
        subject_id="1",
        taxonomy=taxonomy,
        taken_slugs=set(),
        fingerprint_value="g" * 8,
        detail_fetched=False,
        today="2026-09-27",
    )

    assert merged.machine["user_rating"] == 4  # list value updated
    assert merged.machine["genres"] == ["科幻"]  # detail value kept
    assert merged.machine["runtime"] == 155
    assert merged.machine["slug"] == entry.machine["slug"]
