"""Sync running data from the deployed running_page site into the repo.

This repo does NOT sync running data itself (no Strava/Garmin access). The
running_page project syncs daily and deploys to GitHub Pages; this script
downloads the published result:

1. Fetch the deployed index page: https://xiongjia.github.io/running_page/
2. Discover the hashed asset `assets/activities-<hash>.js` in the HTML
   (it appears as `<link rel="modulepreload" href="...">`)
3. Fetch the bundle — it contains `JSON.parse('[...]')` — and unescape +
   parse the JS-string-escaped JSON array
4. Filter to `type == "Run"`, drop the heavy `summary_polyline` field, and
   write `docs/notes/health/data/running.yml` (activities + synced_at)

MkDocs macros read the local yaml only — builds/serves never touch the
network, and no local `running_page` clone is required.

Usage:
    uv run poe sync-running
"""

import json
import re
import sys
import urllib.request
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

import yaml

RUNNING_PAGE_URL = "https://xiongjia.github.io/running_page/"
# Deployed GitHub Pages origin — the asset URLs in the index HTML are
# root-relative ("/running_page/assets/...") and get joined to this origin.
_SITE_ORIGIN = "https://xiongjia.github.io"
DATA_PATH = "docs/notes/health/data/running.yml"
USER_AGENT = "sync_running/1.0 (https://xiongjia.github.com)"

# Asset referenced as <link rel="modulepreload" href="..."> (sometimes <script
# src="...">); the filename hash changes on every upstream data refresh.
_ASSET_RE = re.compile(r'(?:src|href)="([^"]*?/assets/(activities-[A-Za-z0-9_-]+\.js))"')
# Bundle body looks like: const e=JSON.parse('[...]');export{e as a};
# Greedy (.*) matches up to the LAST `');` in the bundle — safe as long as the
# payload is the final statement and no activity name contains a literal `');`.
_PAYLOAD_RE = re.compile(r"JSON\.parse\('(.*)'\);", re.DOTALL)

# JS single-quoted string escapes; unknown escapes drop the backslash (JS rule).
_JS_ESCAPES = {
    "n": "\n",
    "t": "\t",
    "r": "\r",
    "b": "\b",
    "f": "\f",
    "v": "\v",
    "0": "\0",
    "\\": "\\",
    "'": "'",
    '"': '"',
    "/": "/",
}


def _fetch(url: str, timeout: int = 30) -> str:
    """GET a URL and return its body as text (honors proxy env vars)."""
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", "replace")


def js_unescape(text: str) -> str:
    """Unescape a JS single-quoted string literal body to its raw value."""
    out = []
    i = 0
    n = len(text)
    while i < n:
        c = text[i]
        if c == "\\" and i + 1 < n:
            nxt = text[i + 1]
            if nxt == "u" and i + 5 < n:
                try:
                    out.append(chr(int(text[i + 2 : i + 6], 16)))
                    i += 6
                    continue
                except ValueError:
                    pass  # malformed \u — keep literal backslash below
            out.append(_JS_ESCAPES.get(nxt, nxt))
            i += 2
        else:
            out.append(c)
            i += 1
    return "".join(out)


def find_asset_url(html: str) -> str | None:
    """Return the absolute URL of the activities asset, or None if absent."""
    m = _ASSET_RE.search(html)
    if not m:
        return None
    path = m.group(1)
    if path.startswith("//"):
        # protocol-relative URL — refuse: it would be joined onto our origin
        # as a bogus path instead of resolving to an external host
        return None
    if path.startswith("http"):
        # only follow assets hosted on the expected origin — a tampered upstream
        # HTML must not make us fetch an arbitrary URL
        if urlparse(path).netloc != urlparse(_SITE_ORIGIN).netloc:
            return None
        return path
    if path.startswith("/"):
        return _SITE_ORIGIN + path
    return RUNNING_PAGE_URL + path


def extract_activities(bundle: str) -> list[dict]:
    """Extract + unescape the JSON.parse('...') payload from the bundle."""
    m = _PAYLOAD_RE.search(bundle)
    if not m:
        raise ValueError("activities payload not found in bundle JS")
    try:
        return json.loads(js_unescape(m.group(1)))
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid activities JSON: {exc}") from exc


def is_run(activity: dict) -> bool:
    """True for Run activities (deployed data uses mixed case: 'Run'/'cycling')."""
    return str(activity.get("type", "")).lower() == "run"


def drop_polyline(activity: dict) -> dict:
    """Return a copy of the activity without the heavy route polyline."""
    out = dict(activity)
    out.pop("summary_polyline", None)
    return out


def _load_existing_activities() -> list[dict]:
    """Activities currently stored in the data yaml (for idempotency check).

    NB: equality assumes upstream keeps a stable order for identical data
    (it sorts by start date), so re-ordered-but-equal payloads are treated
    as changed.
    """
    path = Path(DATA_PATH)
    if not path.is_file():
        return []
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return data.get("activities") or []


def main() -> None:
    try:
        html = _fetch(RUNNING_PAGE_URL)
        asset_url = find_asset_url(html)
        if not asset_url:
            print(f"Error: activities asset not found in {RUNNING_PAGE_URL}", file=sys.stderr)
            sys.exit(1)
        bundle = _fetch(asset_url)
        activities = extract_activities(bundle)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)
    except OSError as exc:
        print(f"Error: failed to fetch {RUNNING_PAGE_URL}: {exc}", file=sys.stderr)
        sys.exit(1)

    runs = [drop_polyline(a) for a in activities if is_run(a)]
    # upstream order is oldest-first — keep the yaml in that order; the macros
    # sort newest-first defensively

    if runs == _load_existing_activities():
        print(f"ℹ️  Data unchanged — {len(runs)} runs, nothing to write")
        print(f"   {DATA_PATH} is already up to date")
        return

    payload = {
        "synced_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "source": RUNNING_PAGE_URL,
        "activities": runs,
    }
    path = Path(DATA_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    header = (
        "# Auto-generated by `scripts/sync_running.py` (`uv run poe sync-running`)\n"
        "# Do not edit by hand — re-run the command to refresh.\n"
    )
    body = yaml.safe_dump(payload, sort_keys=False, allow_unicode=True, default_flow_style=False)
    path.write_text(header + body, encoding="utf-8")

    # upstream order is oldest-first: runs[0] is the oldest activity
    oldest = runs[0]["start_date"][:10] if runs else "—"
    newest = runs[-1]["start_date"][:10] if runs else "—"
    print(f"✅ Synced {len(runs)} runs to {DATA_PATH}")
    print(f"   range: {oldest} → {newest} | asset: {asset_url.rsplit('/', 1)[-1]}")
    print("   Run `uv run poe server` to preview")


if __name__ == "__main__":
    main()
