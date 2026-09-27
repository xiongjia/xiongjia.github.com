"""Capture (or validate) the Douban login cookie via CDP.

`poe sync-film-tv` needs a logged-in Douban session; this script is the login
half of the pair and can also be used standalone. It attaches to an existing
browser that was started with a remote debugging port, or launches Edge/Chrome
in an isolated profile, brings the Douban page to the front, and reads the
``.douban.com`` cookies once the developer has logged in (CAPTCHA/slider by
hand — Douban cannot be logged into programmatically).

Usage:
    uv run poe film-tv-login               # capture (attaches or launches)
    uv run poe film-tv-login --check       # validate the stored cookie only
    uv run poe film-tv-login --force       # re-capture even if the cookie works
    uv run poe film-tv-login --manual      # paste a cookie string by hand
    uv run poe film-tv-login --close-browser
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shared.douban_auth import (  # noqa: E402
    DEFAULT_CDP_PORT,
    check_cookies,
    cookie_source,
    ensure_cookies,
    load_cookie_header,
    login_cookies_present,
    login_flow,
    mask_cookie,
    save_cookie_header,
    user_data_dir_path,
)
from shared.env import load_env_files  # noqa: E402


def _print_status(status) -> None:
    if status.ok:
        who = f"user {status.user_id}" if status.user_id else "user id unknown"
        print(f"OK: Douban session valid ({who}) — {status.reason}")
    else:
        print(f"FAILED: {status.reason}", file=sys.stderr)


def _manual_flow() -> int:
    print("Paste the cookie header (DevTools → Network → any douban.com request →")
    print("Request Headers → Cookie), then press Enter. 'dbcl2=' must be present.")
    try:
        header = input("cookie> ").strip()
    except (EOFError, KeyboardInterrupt):
        print("aborted", file=sys.stderr)
        return 1
    if not login_cookies_present(header):
        print("error: that string has no 'dbcl2' value — not a logged-in session", file=sys.stderr)
        return 1
    status = check_cookies(header)
    _print_status(status)
    if not status.ok:
        return 1
    path = save_cookie_header(header, user_id=status.user_id)
    print(f"saved to {path}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Capture or validate the Douban cookie used by poe sync-film-tv",
    )
    parser.add_argument("--check", action="store_true", help="only validate the stored cookie")
    parser.add_argument(
        "--force", action="store_true", help="re-capture even if the cookie is valid"
    )
    parser.add_argument(
        "--manual", action="store_true", help="paste a cookie string instead of CDP"
    )
    parser.add_argument(
        "--browser",
        choices=("edge", "chrome", "auto"),
        default="auto",
        help="browser to launch when none is listening (default: auto = edge, then chrome)",
    )
    parser.add_argument(
        "--cdp-port",
        type=int,
        default=DEFAULT_CDP_PORT,
        help=f"CDP port on 127.0.0.1 (default {DEFAULT_CDP_PORT})",
    )
    parser.add_argument(
        "--user-data-dir",
        default="",
        help="browser profile dir (default: the isolated .cache profile)",
    )
    parser.add_argument(
        "--close-browser",
        action="store_true",
        help="close the browser this script started once cookies are captured",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=None,
        help="give up waiting for the manual login after N seconds (default: wait)",
    )
    args = parser.parse_args()

    load_env_files()

    if args.check:
        header = load_cookie_header()
        print(f"cookie source: {cookie_source()}")
        print(f"cookie: {mask_cookie(header)}")
        status = check_cookies(header)
        _print_status(status)
        return 0 if status.ok else 1

    if args.manual:
        return _manual_flow()

    if not args.force:
        header = load_cookie_header()
        if header:
            status = check_cookies(header)
            if status.ok:
                who = f"user {status.user_id}" if status.user_id else "user id unknown"
                print(
                    f"stored cookie is still valid ({who}) — nothing to do (--force to re-capture)"
                )
                return 0
            print(f"stored cookie rejected: {status.reason}", file=sys.stderr)

    # --force re-captures from the browser even when the stored cookie still
    # validates; the default path reuses a working cookie and never opens one.
    flow = login_flow if args.force else ensure_cookies
    status = flow(
        browser=args.browser,
        port=args.cdp_port,
        user_data_dir=user_data_dir_path(args.user_data_dir),
        close_browser=args.close_browser,
        timeout=args.timeout,
    )
    _print_status(status)
    return 0 if status.ok else 1


if __name__ == "__main__":
    sys.exit(main())
