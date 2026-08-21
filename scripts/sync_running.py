"""Sync running data from Garmin API directly into the repo.

Replaces the old approach of fetching from the deployed running_page site.
Fetching is incremental: the full activity list is a cheap index; per-activity
details (splits + polyline) are only fetched for activities not yet cached.

Flow:
1. Fetch the full Garmin activity list (paginated, running only)
2. Compare against .running/splits.json — only fetch details (splits +
   polyline) for activities not yet cached
3. Failed detail fetches stay uncached, so they are retried on the next run
   (the cache check is the incremental cursor and the retry mechanism)
4. Append new activities to running.yml + update .running/splits.json

Usage:
    uv run poe sync-running
"""

from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

# bootstrap repo root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import requests
import yaml

from shared.env import load_env_files

load_env_files()

_REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_PATH = _REPO_ROOT / "docs" / "notes" / "health" / "data" / "running.yml"
CACHE_DIR = _REPO_ROOT / ".running"
CACHE_FILE = CACHE_DIR / "splits.json"
# running_page-era run_ids are millisecond-epoch timestamps (~1.7e12); Garmin
# activity ids are small (~6e8). The threshold separates the two ID spaces.
_OLD_ID_THRESHOLD = 10**9
_GARTH_CLIENT = None


def _garmin_client():
    global _GARTH_CLIENT
    if _GARTH_CLIENT:
        return _GARTH_CLIENT
    import garth

    token = os.environ.get("GARMIN_SECRET_STRING_CN")
    if not token:
        print("Error: GARMIN_SECRET_STRING_CN not set in .env", file=sys.stderr)
        sys.exit(1)
    garth.configure(domain="garmin.cn", ssl_verify=False)
    # retrying session: Garmin CN occasionally times out mid-read; without
    # this one slow response fails the whole sync (and the cron run). Retry
    # transient connect/read errors with a short backoff instead — the sync
    # is incremental, so a retry after a partial fetch is cheap.
    garth.client.sess = _build_session()
    garth.client.loads(token)
    _GARTH_CLIENT = garth.client
    return _GARTH_CLIENT


def _build_session() -> requests.Session:
    """Requests session with bounded retries for transient Garmin failures.

    connect=3 / read=2 retries (total capped at 3) with a short backoff;
    idempotent GETs only — writes (POST/DELETE) are never auto-retried, so
    a retried token refresh can't double-consume anything."""
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry

    session = requests.Session()
    retry = Retry(
        total=3,
        connect=3,
        read=2,
        backoff_factor=0.5,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=frozenset({"GET"}),
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


def _fetch_garmin_activities() -> list[dict]:
    """Fetch the full running activity list from Garmin (newest first).

    The list is cheap (~2 requests for ~170 activities). Detail fetching is
    the expensive part and is filtered elsewhere to only activities that
    don't yet have splits/polyline cached — that check doubles as the retry
    mechanism, so a previously-failed activity (even one older than the
    newest synced) is retried on every run until it succeeds.
    """
    client = _garmin_client()
    all_activities: list[dict] = []
    start = 0
    limit = 100

    while True:
        url = (
            f"/activitylist-service/activities/search/activities"
            f"?start={start}&limit={limit}&activityType=running"
        )
        batch = client.connectapi(url)
        if not batch:
            break
        all_activities.extend(batch)
        if len(batch) < limit:
            break
        start += limit
        time.sleep(0.5)

    return all_activities


def _garmin_to_activity(garmin_act: dict) -> dict:
    """Convert a Garmin activity list entry to our running.yml format."""
    activity_id = garmin_act["activityId"]
    start_gmt = garmin_act.get("startTimeGMT", "")
    start_local = garmin_act.get("startTimeLocal", "")

    # Parse timestamps
    def _parse_ts(raw: str) -> str:
        try:
            dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        except (ValueError, TypeError):
            return raw

    start_date = _parse_ts(start_gmt)
    start_date_local = _parse_ts(start_local) if start_local else start_date

    # moving_time from Garmin
    moving = float(garmin_act.get("movingDuration") or garmin_act.get("duration", 0))
    moving_h = int(moving // 3600)
    moving_m = int((moving % 3600) // 60)
    moving_s = int(moving % 60)
    moving_str = (
        f"{moving_h}:{moving_m:02d}:{moving_s:02d}" if moving_h else f"{moving_m}:{moving_s:02d}"
    )

    return {
        "run_id": activity_id,
        "name": garmin_act.get("activityName") or "Running",
        "distance": float(garmin_act.get("distance", 0)),
        "moving_time": moving_str,
        "type": "Run",
        "subtype": garmin_act.get("activityType", {}).get("typeKey", "running"),
        "start_date": start_date,
        "start_date_local": start_date_local,
        "location_country": garmin_act.get("locationName", "") or "",
        "average_heartrate": float(garmin_act["averageHR"])
        if garmin_act.get("averageHR")
        else None,
        "average_speed": float(garmin_act.get("averageSpeed", 0)),
        "elevation_gain": float(garmin_act.get("elevationGain", 0)),
        "source": "garmin_cn",
    }


def _fetch_splits_and_polyline(activity_id: int) -> dict | None:
    """Fetch splits + polyline for one activity; None on failure."""
    client = _garmin_client()
    try:
        # Get splits
        splits_result = client.connectapi(f"/activity-service/activity/{activity_id}/splits")
        lap_dtos = (splits_result or {}).get("lapDTOs") or []
        splits = []
        for lap in lap_dtos:
            km = round(float(lap.get("distance", 0)) / 1000, 2)
            lap_dur = float(lap.get("movingDuration") or lap.get("duration", 0))
            avg_speed = float(lap.get("averageMovingSpeed") or lap.get("averageSpeed", 0))
            pace = _pace_from_speed(avg_speed) if avg_speed > 0 else None
            hr = float(lap["averageHR"]) if lap.get("averageHR") else None
            splits.append(
                {
                    "km": km,
                    "duration": round(lap_dur),
                    "pace": pace,
                    "hr": hr,
                }
            )

        # Get polyline from details endpoint
        details = client.connectapi(
            f"/activity-service/activity/{activity_id}/details?maxChartSize=0&maxPolylineSize=4000"
        )
        # Garmin returns polyline as an array of {lat, lon} points, encode to Google Polyline
        polyline = ""
        if details:
            gp = details.get("geoPolylineDTO") or {}
            pts = gp.get("polyline") or []
            if pts:
                polyline = _encode_polyline([(p["lat"], p["lon"]) for p in pts])

        return {"splits": splits, "summary_polyline": polyline}
    except Exception as e:
        print(f"  ⚠️  details failed for {activity_id}: {e}", file=sys.stderr)
        return None


def _encode_polyline(coords: list[tuple[float, float]]) -> str:
    """Encode [(lat, lng), ...] to Google Polyline format."""
    result = []
    lat_prev, lng_prev = 0, 0
    for lat, lng in coords:
        lat5 = int(round(lat * 1e5))
        lng5 = int(round(lng * 1e5))
        dlat = lat5 - lat_prev
        dlng = lng5 - lng_prev
        lat_prev = lat5
        lng_prev = lng5
        for val in (dlat, dlng):
            sval = val << 1
            if val < 0:
                sval = ~sval
            while True:
                b = sval & 0x1F
                sval >>= 5
                if sval:
                    b |= 0x20
                result.append(chr(b + 63))
                if not sval:
                    break
    return "".join(result)


def _pace_from_speed(speed_mps: float) -> str:
    if speed_mps <= 0:
        return "—"
    sec_per_km = 1000 / speed_mps
    m, s = divmod(int(round(sec_per_km)), 60)
    return f"{m}:{s:02d}"


def _save_splits(activities: list[dict], details_map: dict[int, dict]):
    """Merge newly-fetched details into .running/splits.json (repairing partials)."""
    by_id = {a["run_id"]: a for a in _load_existing_splits()}
    for a in activities:
        rid = a["run_id"]
        det = details_map.get(rid)
        if not det:
            continue
        entry = by_id.get(rid)
        if entry is not None:
            # Repair partial entries (e.g. empty polyline from a prior failed run)
            if not entry.get("summary_polyline") or not entry.get("splits"):
                entry["splits"] = det["splits"]
                entry["summary_polyline"] = det["summary_polyline"]
            continue
        by_id[rid] = {
            "run_id": rid,
            "source": "garmin_cn",
            "splits": det["splits"],
            "summary_polyline": det["summary_polyline"],
        }
    _write_splits(list(by_id.values()))
    print(f"  wrote {CACHE_FILE} ({len(by_id)} activities)")


def _cached_detail_ids(activities: list[dict]) -> set[int]:
    """Run_ids in the given list that carry real details (splits or polyline)."""
    return {a["run_id"] for a in activities if a.get("summary_polyline") or a.get("splits")}


def _migrate_old_running_page_ids(
    yml_acts: list[dict], splits_acts: list[dict], garmin_runs: list[dict]
) -> dict[int, int]:
    """One-time remap of running_page-era run_ids to Garmin IDs.

    The first Garmin-backed sync merged new Garmin-ID activities on top of
    160 running_page-era activities (millisecond-epoch run_ids). Both ID
    spaces then coexist in running.yml / splits.json; since the Garmin list
    only knows Garmin IDs, the incremental cache check would re-fetch and
    duplicate every run. This remaps old entries to their Garmin ID by
    matching the start instant: first by minute-level timestamp (disambiguates
    multi-run days), then by date for unambiguous days. It never guesses on a
    key that maps to more than one Garmin activity.

    Returns the applied {old_id: garmin_id} remap (empty when nothing to do).
    """
    by_minute: dict[str, list[int]] = {}
    by_date: dict[str, list[int]] = {}
    for ga in garmin_runs:
        gmt = ga.get("startTimeGMT") or ""
        minute = _garmin_ts_key(gmt)
        if minute:
            by_minute.setdefault(minute, []).append(ga["activityId"])
        day = gmt[:10]
        if day:
            by_date.setdefault(day, []).append(ga["activityId"])

    remap: dict[int, int] = {}
    for e in [*yml_acts, *splits_acts]:
        rid = e.get("run_id")
        if not isinstance(rid, int) or rid < _OLD_ID_THRESHOLD:
            continue
        start = e.get("start_date") or ""
        candidates = by_minute.get(start[:16]) or by_date.get(start[:10]) or []
        if len(candidates) == 1:
            remap.setdefault(rid, candidates[0])

    if remap:
        for e in [*yml_acts, *splits_acts]:
            rid = e.get("run_id")
            if rid in remap:
                e["run_id"] = remap[rid]
    return remap


def _garmin_ts_key(raw: str) -> str:
    """Normalize a Garmin startTimeGMT to 'YYYY-MM-DD HH:MM'."""
    if not raw:
        return ""
    return raw.replace("T", " ")[:16]


def _load_existing_activities() -> list[dict]:
    """Activities currently in running.yml (empty list when missing/invalid)."""
    if not DATA_PATH.is_file():
        return []
    try:
        with open(DATA_PATH, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    except yaml.YAMLError:
        return []
    acts = data.get("activities") or []
    return acts if isinstance(acts, list) else []


def _load_existing_splits() -> list[dict]:
    """Activities currently in .running/splits.json (empty list when missing)."""
    if not CACHE_FILE.is_file():
        return []
    try:
        with open(CACHE_FILE, encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return []
    acts = data.get("activities") or []
    return acts if isinstance(acts, list) else []


def _write_running_yml(activities: list[dict]) -> None:
    """Write running.yml (header + synced_at + deduplicated activities)."""
    seen: set[int] = set()
    deduped = []
    for a in activities:
        a.setdefault("source", "garmin_cn")  # all data is Garmin CN now
        rid = a.get("run_id")
        if isinstance(rid, int) and rid in seen:
            continue
        if isinstance(rid, int):
            seen.add(rid)
        deduped.append(a)
    payload = {
        "synced_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "source": "garmin_cn",
        "activities": deduped,
    }
    DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    header = (
        "# Auto-generated by `scripts/sync_running.py` (`uv run poe sync-running`)\n"
        "# Do not edit by hand — re-run the command to refresh.\n"
    )
    body = yaml.safe_dump(payload, sort_keys=False, allow_unicode=True, default_flow_style=False)
    DATA_PATH.write_text(header + body, encoding="utf-8")


def _write_splits(activities: list[dict]) -> None:
    """Write .running/splits.json (version + synced_at + deduplicated activities)."""
    # Keep the entry with real details when ids collide (e.g. a remapped old
    # entry vs its Garmin twin).
    best: dict[int, dict] = {}
    for a in activities:
        rid = a.get("run_id")
        if not isinstance(rid, int):
            continue
        cur = best.get(rid)
        if cur is None or (not (cur.get("summary_polyline") or cur.get("splits"))):
            best[rid] = a
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": 1,
        "synced_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "activities": sorted(best.values(), key=lambda x: x["run_id"]),
    }
    CACHE_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> int:
    load_env_files()

    # ── fetch the full Garmin activity list (cheap index) ──
    print("Fetching Garmin activity list...")
    garmin_acts = _fetch_garmin_activities()
    runs = [
        a
        for a in garmin_acts
        if str(a.get("activityType", {}).get("typeKey", "")).lower() == "running"
    ]
    if not runs:
        print("No running activities found")
        return 0

    # ── load existing data + one-time id migration ──
    # The first Garmin-backed sync merged new Garmin-ID activities on top of
    # running_page-era entries (different ID space). Remap those by start date
    # so the cache check below only sees Garmin IDs — otherwise the next sync
    # would re-fetch and duplicate the whole history.
    yml_acts = _load_existing_activities()
    splits_acts = _load_existing_splits()
    remap = _migrate_old_running_page_ids(yml_acts, splits_acts, runs)
    if remap:
        _write_running_yml(yml_acts)
        _write_splits(splits_acts)
        print(f"migrated {len(remap)} running_page ids to Garmin ids")

    # Incremental: only fetch details for activities not yet cached. An
    # activity whose details fetch failed stays uncached, so it is retried
    # on every run regardless of where it sits in the list (fixes the
    # older-fails-while-newer-succeeds gap).
    cached_ids = _cached_detail_ids(splits_acts)
    to_process = [a for a in runs if a["activityId"] not in cached_ids]
    already = len(runs) - len(to_process)
    print(f"Running activities: {len(runs)} ({already} cached, {len(to_process)} to fetch)")

    if not to_process:
        print("All activities already have details — nothing to do")
        return 0

    # ── convert + fetch details ──
    activities = []
    details_map: dict[int, dict] = {}
    for idx, ga in enumerate(to_process, 1):
        a = _garmin_to_activity(ga)
        rid = a["run_id"]
        print(f"  [{idx}/{len(to_process)}] {rid} ({a['start_date'][:10]})")

        det = _fetch_splits_and_polyline(rid)
        if det is None:
            # Not cached -> retried next run (no cursor to advance past it)
            print(f"    ⚠️  {rid}: details fetch failed, will retry next sync")
            time.sleep(0.5)
            continue
        activities.append(a)
        details_map[rid] = det
        time.sleep(0.5)

    # ── merge new activities into running.yml ──
    existing_ids = {a["run_id"] for a in yml_acts}
    merged = [a for a in activities if a["run_id"] not in existing_ids] + yml_acts
    _write_running_yml(merged)
    print(f"  wrote {DATA_PATH} ({len(merged)} activities)")

    # ── save splits ──
    _save_splits(activities, details_map)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
