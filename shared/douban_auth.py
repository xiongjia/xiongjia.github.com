"""Douban authentication — cookie store plus CDP-based cookie capture.

Douban's login page is protected by a slider CAPTCHA, so form login cannot be
automated: the only viable path is to reuse a real browser session. This module
drives a local Edge/Chrome over the Chrome DevTools Protocol (CDP) to:

1. bring the Douban page to the front so the developer can log in once,
2. read the ``.douban.com`` cookies out of the browser
   (``Storage.getCookies`` on the browser-level endpoint — ``Network.
   getAllCookies`` does not exist there),
3. store them in ``.cache/douban-cookies.json`` (mode 0600) for the sync script
   to use with plain ``requests``.

The browser is used **only** for login/cookie capture; every scrape runs over
``requests`` on the cookie header this module stores. Import safety:
``websocket-client`` is imported lazily inside the CDP call, so importing this
module never pulls in the browser stack (CI stays browser-free).

Precedence for stored credentials: ``DOUBAN_COOKIE`` (explicit fallback)
over ``DOUBAN_COOKIES_FILE`` (default ``.cache/douban-cookies.json``).
"""

from __future__ import annotations

import json
import os
import re
import stat
import subprocess
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

COOKIE_ENV = "DOUBAN_COOKIE"
COOKIES_FILE_ENV = "DOUBAN_COOKIES_FILE"
DEFAULT_COOKIES_FILE = REPO_ROOT / ".cache" / "douban-cookies.json"
DEFAULT_USER_DATA_DIR = REPO_ROOT / ".cache" / "film-tv" / "browser-profile"
LOGIN_LOG = REPO_ROOT / ".cache" / "film-tv" / "login.log"

DEFAULT_CDP_PORT = 9222

DOUBAN_ROOT = "https://www.douban.com"
MINE_URL = f"{DOUBAN_ROOT}/mine/"
LOGIN_URL = f"{DOUBAN_ROOT}/"

#: Douban's anti-bot gate (a 302 here means "challenged", never "logged in")
SEC_CHALLENGE_HOST = "sec.douban.com"

# `/mine/` is the login gate. Verified 2026-09-27: a valid session redirects to
# `/people/<id-or-vanity>/`, while a missing/expired/bogus cookie redirects to
# `https://sec.douban.com/b?r=…` (the anti-bot gate; `/people/` alone answers 404
# either way, and 403 is what an over-eager block returns)."
PEOPLE_URL_RE = re.compile(r"douban\.com/people/([A-Za-z0-9_-]+)")

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/154.0.0.0 Safari/537.36"
)

# values redacted in logs / error messages (`dbcl2` is the session token)
SENSITIVE_COOKIE_NAMES = frozenset({"dbcl2", "ck"})

BROWSER_BINARIES = {
    "edge": "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
    "chrome": "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
}
BROWSER_ORDER = ("edge", "chrome")


@dataclass
class CookieStatus:
    """Result of a credential probe against Douban."""

    ok: bool
    user_id: str | None = None
    reason: str = ""


def cookies_file_path() -> Path:
    """Cookie file location (``DOUBAN_COOKIES_FILE`` overrides the default)."""
    override = os.environ.get(COOKIES_FILE_ENV, "").strip()
    return Path(override).expanduser() if override else DEFAULT_COOKIES_FILE


def user_data_dir_path(override: str | Path | None = None) -> Path:
    """Browser profile directory (isolated: Chromium 136+ refuses CDP on the
    default profile, and this keeps the developer's daily profile untouched)."""
    return Path(override).expanduser() if override else DEFAULT_USER_DATA_DIR


def load_cookie_header() -> str | None:
    """Cookie header from ``DOUBAN_COOKIE`` or the cookie file; ``None`` if absent."""
    env_value = os.environ.get(COOKIE_ENV, "").strip()
    if env_value:
        return env_value
    path = cookies_file_path()
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    header = str(data.get("cookie", "")).strip()
    return header or None


def cookie_source() -> str:
    """Where the cookie would come from, for logs (never prints the value)."""
    if os.environ.get(COOKIE_ENV, "").strip():
        return f"{COOKIE_ENV} (env)"
    path = cookies_file_path()
    return str(path) if path.is_file() else f"{path} (missing)"


def _chmod_600(path: Path) -> None:
    """Best-effort 0600 — the file holds a live session token."""
    try:
        path.chmod(stat.S_IRUSR | stat.S_IWUSR)
    except OSError:
        pass


def save_cookie_header(header: str, *, user_id: str | None = None) -> Path:
    """Persist the cookie header (0600) next to its captured metadata."""
    path = cookies_file_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "cookie": header,
        "user_id": user_id,
        "captured_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
    }
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _chmod_600(tmp)
    tmp.replace(path)
    return path


def mask_cookie(header: str | None) -> str:
    """Redact session-bearing values so a cookie header can be printed."""
    if not header:
        return "<none>"
    parts = []
    for chunk in header.split(";"):
        name, _, value = chunk.strip().partition("=")
        if name in SENSITIVE_COOKIE_NAMES:
            parts.append(f"{name}=***")
        else:
            parts.append(f"{name}={value}")
    return "; ".join(parts)


def cookie_pairs(header: str) -> dict[str, str]:
    """Cookie name → value for the bits we care about (e.g. ``dbcl2``)."""
    pairs: dict[str, str] = {}
    for chunk in header.split(";"):
        name, sep, value = chunk.strip().partition("=")
        if sep and name:
            pairs[name] = value
    return pairs


def build_session(header: str):
    """``requests`` session carrying the Douban cookie header."""
    import requests

    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT, "Cookie": header})
    return session


def _user_id_from_url(url: str) -> str | None:
    """Extract the Douban user id (numeric or vanity name) from a people URL."""
    match = PEOPLE_URL_RE.search(url)
    return match.group(1) if match else None


def dbcl2_user_id(header: str) -> str | None:
    """Numeric Douban user id, read from the session cookie itself.

    ``dbcl2`` looks like ``"2535429:<token>"``; the numeric id doubles as the
    people-URL segment (``movie.douban.com/people/2535429/collect`` works), so
    the collection URL never depends on scraping a vanity name.
    """
    raw = cookie_pairs(header).get("dbcl2", "").strip().strip('"')
    user_id = raw.split(":", 1)[0].strip()
    return user_id if user_id.isdigit() else None


def check_cookies(header: str | None, *, timeout: float = 15.0) -> CookieStatus:
    """Probe ``/mine/`` and resolve the user id the sync script will use.

    Only a redirect that lands on ``/people/<id>`` (or a rendered ``/mine/``)
    proves a session: the ``dbcl2`` cookie is *not* evidence by itself, because
    an expired or bogus cookie gets the same response as no cookie at all — a
    302 to the anti-bot gate. The reported id prefers the numeric one from
    ``dbcl2`` (a stable people-URL segment) and falls back to the redirect.
    """
    if not header:
        return CookieStatus(False, reason="no cookie")

    import requests

    session = build_session(header)
    try:
        resp = session.get(MINE_URL, allow_redirects=False, timeout=timeout)
    except requests.RequestException as exc:
        return CookieStatus(False, reason=f"network error: {exc.__class__.__name__}")
    if resp.status_code in (301, 302, 303, 307, 308):
        location = resp.headers.get("location", "")
        user_id = _user_id_from_url(location)
        if SEC_CHALLENGE_HOST in location:
            return CookieStatus(
                False,
                reason="anti-bot challenge (sec.douban.com) — the cookie is expired, "
                "or this IP is rate limited; retry later",
            )
        if not user_id:
            if "accounts/login" in location or "passport/login" in location:
                return CookieStatus(False, reason="session expired (redirected to login)")
            return CookieStatus(False, reason=f"unexpected redirect to {location[:80]}")
        return CookieStatus(True, user_id=dbcl2_user_id(header) or user_id, reason="ok")
    if resp.status_code == 200:
        # `/mine/` rendered in place: accept only with positive evidence, because a
        # 200 alone could also be an anonymous render — a false "ok" here would
        # send the sync off with a dead session
        user_id = dbcl2_user_id(header)
        if not user_id:
            return CookieStatus(False, reason="HTTP 200 but the cookie carries no dbcl2 id")
        if f"/people/{user_id}/" in resp.text:
            return CookieStatus(True, user_id=user_id, reason="ok")
        return CookieStatus(
            False,
            reason="HTTP 200 without a login marker on /mine/ — treating it as not logged in",
        )
    if resp.status_code in (403, 404):
        return CookieStatus(
            False, reason=f"HTTP {resp.status_code} — not logged in (session expired)"
        )
    return CookieStatus(False, reason=f"HTTP {resp.status_code}")


# --- CDP plumbing -----------------------------------------------------------


def _http_json(url: str, *, timeout: float = 5.0):
    with urllib.request.urlopen(url, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def probe_cdp(port: int, *, timeout: float = 3.0) -> dict | None:
    """Return the ``/json/version`` payload if a browser is listening, else ``None``.

    Raises ``RuntimeError`` when the port answers but is *not* a browser: the
    caller must then stop instead of sending CDP requests to an unrelated local
    process.
    """
    try:
        payload = _http_json(f"http://127.0.0.1:{port}/json/version", timeout=timeout)
    except OSError:
        # connection refused / timed out: all OSError subclasses (URLError,
        # TimeoutError, ConnectionError), i.e. nothing is listening
        return None
    except ValueError:
        raise RuntimeError(
            f"port {port} answers HTTP but does not speak CDP — refusing to reuse it"
        ) from None
    browser = str(payload.get("Browser", ""))
    protocol = payload.get("Protocol-Version")
    if not (browser.startswith("Edg/") or browser.startswith("Chrome/")) or not protocol:
        raise RuntimeError(
            f"port {port} is not a Chromium-based browser (Browser={browser!r}, "
            f"Protocol-Version={protocol!r}) — refusing to reuse it"
        )
    return payload


def browser_binary(name: str) -> str:
    """Resolve a browser name (``edge`` / ``chrome`` / ``auto``) to a binary path."""
    names = BROWSER_ORDER if name == "auto" else (name,)
    for candidate in names:
        path = BROWSER_BINARIES.get(candidate, "")
        if path and Path(path).is_file():
            return path
    raise RuntimeError(
        f"no usable browser found for {name!r}: checked "
        + ", ".join(str(BROWSER_BINARIES[n]) for n in names)
    )


def launch_browser(
    binary: str,
    *,
    port: int,
    user_data_dir: Path,
    url: str = LOGIN_URL,
    log_path: Path | None = None,
) -> subprocess.Popen:
    """Start a headed browser with CDP enabled, in its own session.

    ``start_new_session=True`` keeps the browser alive after the script exits
    (by design — reuse it next time). stderr goes to a log file because macOS
    crashpad always writes an ``Operation not permitted`` warning that cannot be
    suppressed from the command line.
    """
    user_data_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_path or LOGIN_LOG
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log = open(log_path, "a", encoding="utf-8")  # noqa: SIM115 — dup'd into the child
    try:
        return subprocess.Popen(
            [
                binary,
                f"--remote-debugging-port={port}",
                f"--user-data-dir={user_data_dir}",
                "--no-first-run",
                "--no-default-browser-check",
                "--disable-crash-reporter",
                url,
            ],
            stdout=subprocess.DEVNULL,
            stderr=log,
            start_new_session=True,
        )
    finally:
        log.close()


def wait_for_cdp(port: int, *, timeout: float = 30.0, interval: float = 0.5) -> dict:
    """Poll ``/json/version`` until the freshly launched browser is ready."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        payload = probe_cdp(port, timeout=2.0)
        if payload:
            return payload
        time.sleep(interval)
    raise RuntimeError(f"browser did not expose CDP on port {port} within {timeout:.0f}s")


def cdp_call(ws_url: str, method: str, params: dict | None = None, *, timeout: float = 15.0):
    """One CDP request/response round trip (send ``method``, return ``result``)."""
    import websocket  # lazy: keeps the browser stack out of CI / build imports

    # Douban/browser reject a WebSocket upgrade that carries an Origin header
    # (403): suppress_origin is the documented switch for that.
    conn = websocket.create_connection(ws_url, timeout=timeout, suppress_origin=True)
    try:
        conn.send(json.dumps({"id": 1, "method": method, "params": params or {}}))
        while True:
            message = json.loads(conn.recv())
            if message.get("id") != 1:
                continue
            if "error" in message:
                raise RuntimeError(f"CDP {method} failed: {message['error']}")
            return message.get("result", {})
    finally:
        conn.close()


def _page_ws_url(port: int) -> str | None:
    """WebSocket URL of an existing page target, if any."""
    try:
        targets = _http_json(f"http://127.0.0.1:{port}/json/list", timeout=5.0)
    except (urllib.error.URLError, OSError, ValueError):
        return None
    for target in targets if isinstance(targets, list) else []:
        if target.get("type") == "page" and target.get("webSocketDebuggerUrl"):
            return str(target["webSocketDebuggerUrl"])
    return None


def show_login_page(
    port: int, *, new_tab: bool = False, version_payload: dict | None = None, url: str = LOGIN_URL
) -> None:
    """Bring the Douban login page up and focus it (best effort).

    ``new_tab=True`` (attaching to a browser the developer already has open)
    opens the page in a **new tab** so their current page is never navigated
    away; otherwise the browser we launched ourselves is just refocused (the URL
    was already its startup page).

    A failure here is not fatal (the window can be switched by hand), but a
    silent one would leave the login page hidden behind other windows.
    """
    try:
        payload = version_payload or probe_cdp(port)
        ws_url = None
        if new_tab and payload and payload.get("webSocketDebuggerUrl"):
            created = cdp_call(
                str(payload["webSocketDebuggerUrl"]), "Target.createTarget", {"url": url}
            )
            ws_url = _target_ws_url(port, str(created.get("targetId", "")))
        else:
            ws_url = _page_ws_url(port)
            if ws_url:
                cdp_call(ws_url, "Page.navigate", {"url": url})
        if ws_url:
            cdp_call(ws_url, "Page.bringToFront")
    except Exception as exc:  # noqa: BLE001 — window focus is advisory only
        print(f"warning: could not focus the login page: {exc}", file=sys.stderr)


def is_douban_domain(domain: str) -> bool:
    """Whether a cookie domain belongs to Douban (``douban.com`` or a subdomain).

    A plain substring test would also accept ``douban.com.cn`` or
    ``douban.com.evil.net`` — domains a third party can own and set cookies on —
    and those values would end up in the request header sent to Douban.
    """
    value = str(domain or "").strip().lower().lstrip(".")
    return value == "douban.com" or value.endswith(".douban.com")


def _target_ws_url(port: int, target_id: str) -> str | None:
    """WebSocket URL of one target by id (``/json/list``)."""
    try:
        targets = _http_json(f"http://127.0.0.1:{port}/json/list", timeout=5.0)
    except (OSError, ValueError):
        return None
    for target in targets if isinstance(targets, list) else []:
        if target.get("id") == target_id and target.get("webSocketDebuggerUrl"):
            return str(target["webSocketDebuggerUrl"])
    return None


def cdp_douban_cookies(port: int, *, version_payload: dict | None = None) -> str:
    """Read all browser cookies and return the Douban-only cookie header.

    Uses the browser-level endpoint (``Storage.getCookies``); the same endpoint
    has no ``Network.getAllCookies`` (``-32601``).
    """
    payload = version_payload or probe_cdp(port)
    if not payload:
        raise RuntimeError(f"no CDP endpoint on port {port}")
    ws_url = payload.get("webSocketDebuggerUrl")
    if not ws_url:
        raise RuntimeError("CDP /json/version has no webSocketDebuggerUrl")
    result = cdp_call(str(ws_url), "Storage.getCookies")
    cookies = [c for c in result.get("cookies", []) if is_douban_domain(c.get("domain", ""))]
    return format_cookie_header(cookies)


def format_cookie_header(cookies: list[dict]) -> str:
    """CDP cookie dicts → ``name=value; …`` header (stable order, one per name).

    ``Storage.getCookies`` returns cookies in no particular order and a site may
    keep the same name on several paths. The browser sends the most specific
    path first, so picking the **shortest** path (the session-wide cookie, e.g.
    ``/``) makes the choice deterministic instead of order-dependent.
    """
    chosen: dict[str, tuple[int, str]] = {}
    for cookie in cookies:
        name = str(cookie.get("name", ""))
        if not name:
            continue
        depth = len([part for part in str(cookie.get("path") or "").split("/") if part])
        if name not in chosen or depth < chosen[name][0]:
            chosen[name] = (depth, str(cookie.get("value", "")))
    # sorted by name: the header is rebuilt from scratch on every login, so a stable
    # order keeps the 0600 cookie file from churning when the browser reorders
    return "; ".join(f"{name}={chosen[name][1]}" for name in sorted(chosen))


def login_cookies_present(header: str) -> bool:
    """Whether the header carries the session cookies Douban sets on login."""
    pairs = cookie_pairs(header)
    return "dbcl2" in pairs and bool(pairs.get("dbcl2"))


# --- flows ------------------------------------------------------------------


def login_flow(
    *,
    browser: str = "auto",
    port: int = DEFAULT_CDP_PORT,
    user_data_dir: Path | None = None,
    close_browser: bool = False,
    poll_interval: float = 3.0,
    timeout: float | None = None,
) -> CookieStatus:
    """Capture cookies from a browser, waiting for a manual login.

    Attaches to an existing CDP browser when one is listening, otherwise starts
    one. The developer logs in (CAPTCHA/slider included) while this loops until
    the Douban session cookies appear; ``timeout=None`` waits indefinitely.
    """
    version = probe_cdp(port)
    attached = version is not None
    process: subprocess.Popen | None = None
    if attached:
        print(f"attaching to the browser already listening on 127.0.0.1:{port}")
        print(f"  {version.get('Browser')} (Protocol {version.get('Protocol-Version')})")
    else:
        binary = browser_binary(browser)
        profile = user_data_dir_path(user_data_dir)
        print(f"starting {binary} with CDP on 127.0.0.1:{port}")
        print(f"  profile: {profile}")
        process = launch_browser(binary, port=port, user_data_dir=profile)
        version = wait_for_cdp(port)
        print(f"stderr from the browser goes to {LOGIN_LOG}")

    show_login_page(port, new_tab=attached, version_payload=version)
    print()
    print(f"Please log in to Douban in the browser window ({LOGIN_URL}).")
    print("The CAPTCHA / slider must be solved by hand; this script only reads cookies.")
    print("Waiting for a logged-in session (Ctrl-C to abort) …")

    deadline = None if timeout is None else time.monotonic() + timeout
    try:
        while True:
            header = cdp_douban_cookies(port, version_payload=version)
            if login_cookies_present(header):
                status = check_cookies(header)
                if status.ok:
                    path = save_cookie_header(header, user_id=status.user_id)
                    if process and close_browser:
                        process.terminate()
                    return CookieStatus(True, user_id=status.user_id, reason=f"saved to {path}")
                print(f"  cookies not usable yet: {status.reason}", file=sys.stderr)
            if deadline is not None and time.monotonic() >= deadline:
                return CookieStatus(False, reason="timed out waiting for login")
            time.sleep(poll_interval)
    except KeyboardInterrupt:
        return CookieStatus(False, reason="aborted by user")
    except Exception:
        if process and close_browser:
            process.terminate()
        raise


def ensure_cookies(**kwargs) -> CookieStatus:
    """Validate stored cookies, falling back to the interactive login flow."""
    header = load_cookie_header()
    if header:
        status = check_cookies(header)
        if status.ok:
            return status
        print(f"stored Douban cookie is not usable: {status.reason}", file=sys.stderr)
    else:
        print("no stored Douban cookie found", file=sys.stderr)
    return login_flow(**kwargs)
