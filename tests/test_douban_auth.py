"""Tests for `shared/douban_auth.py` — cookie handling and the login gate.

No browser and no network: `probe_cdp` is exercised against a closed port and a
faked HTTP layer, `check_cookies` against a faked session. The security-relevant
behaviour (what gets redacted, what ends up in the cookie file, which cookie
domains are accepted) is what these tests pin down.
"""

from __future__ import annotations

import json
import os
import stat
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from shared import douban_auth as auth  # noqa: E402


@pytest.fixture()
def cookie_file(tmp_path, monkeypatch) -> Path:
    """Point the module at a temp cookie file and clear the env override."""
    path = tmp_path / "douban-cookies.json"
    monkeypatch.setenv(auth.COOKIES_FILE_ENV, str(path))
    monkeypatch.delenv(auth.COOKIE_ENV, raising=False)
    return path


class FakeResponse:
    def __init__(self, status_code: int, location: str = "", text: str = ""):
        self.status_code = status_code
        self.headers = {"location": location} if location else {}
        self.text = text


class FakeSession:
    def __init__(self, response: FakeResponse):
        self.response = response
        self.requested: list[str] = []

    def get(self, url, **_kwargs):
        self.requested.append(url)
        return self.response


# --- cookie sources ----------------------------------------------------------


def test_env_cookie_beats_the_file(cookie_file, monkeypatch):
    cookie_file.write_text(json.dumps({"cookie": "dbcl2=from-file"}), encoding="utf-8")
    monkeypatch.setenv(auth.COOKIE_ENV, "dbcl2=from-env")
    assert auth.load_cookie_header() == "dbcl2=from-env"


def test_save_and_reload_the_cookie_file(cookie_file):
    path = auth.save_cookie_header("dbcl2=2535429%3Aabc; bid=x", user_id="2535429")

    assert path == cookie_file
    payload = json.loads(cookie_file.read_text(encoding="utf-8"))
    assert payload["cookie"].startswith("dbcl2=")
    assert payload["user_id"] == "2535429"
    assert payload["captured_at"]  # ISO timestamp, never empty
    assert auth.load_cookie_header() == "dbcl2=2535429%3Aabc; bid=x"


def test_cookie_file_is_owner_only(cookie_file):
    auth.save_cookie_header("dbcl2=x")
    mode = stat.S_IMODE(os.stat(cookie_file).st_mode)
    assert mode == 0o600  # the file holds a live session token


def test_missing_cookie_file_is_none(cookie_file):
    assert auth.load_cookie_header() is None
    assert auth.cookie_source().endswith("(missing)")


def test_cookie_source_reports_the_env_variable(cookie_file, monkeypatch):
    monkeypatch.setenv(auth.COOKIE_ENV, "dbcl2=x")
    assert auth.cookie_source() == f"{auth.COOKIE_ENV} (env)"


# --- parsing / redaction -----------------------------------------------------


def test_mask_cookie_redacts_only_session_cookies():
    header = "dbcl2=secret-token; bid=abc; ck=nonce; ll=118282"
    masked = auth.mask_cookie(header)

    assert "secret-token" not in masked and "nonce" not in masked
    assert "dbcl2=***" in masked and "ck=***" in masked
    assert "bid=abc" in masked and "ll=118282" in masked
    assert auth.mask_cookie(None) == "<none>"


def test_cookie_pairs_keeps_values_containing_equals():
    pairs = auth.cookie_pairs('a=1; dbcl2="2535429:tok=0"; bad; flag=')
    assert pairs["a"] == "1"
    # the value keeps everything after the first "=" (quotes are stripped later)
    assert pairs["dbcl2"] == '"2535429:tok=0"'
    assert pairs["flag"] == ""
    assert "bad" not in pairs


def test_dbcl2_user_id_reads_the_numeric_prefix():
    assert auth.dbcl2_user_id("dbcl2=2535429%3Aabc") is None  # percent-encoded value
    assert auth.dbcl2_user_id('dbcl2="2535429:abc"') == "2535429"
    assert auth.dbcl2_user_id("dbcl2=lexiongjia:abc") is None  # vanity name, not an id
    assert auth.dbcl2_user_id("bid=x") is None


def test_format_cookie_header_prefers_the_shortest_path():
    # CDP returns cookies in an unspecified order and a site may keep the same
    # name on several paths: the session-wide cookie (path /) must win
    cookies = [
        {"name": "dbcl2", "value": "subject-scoped", "domain": ".douban.com", "path": "/subject/"},
        {"name": "dbcl2", "value": "session-wide", "domain": ".douban.com", "path": "/"},
        {"name": "bid", "value": "b", "domain": ".douban.com", "path": "/"},
        {"name": "ll", "value": "no-path", "domain": ".douban.com"},  # no path → widest
        {"name": "ck", "value": "scoped", "domain": ".douban.com", "path": "/subject/"},
        {"name": "", "value": "ignored", "domain": ".douban.com", "path": "/"},
    ]
    assert auth.format_cookie_header(cookies) == "bid=b; ck=scoped; dbcl2=session-wide; ll=no-path"
    # order does not matter
    assert auth.format_cookie_header(list(reversed(cookies))) == (
        "bid=b; ck=scoped; dbcl2=session-wide; ll=no-path"
    )


@pytest.mark.parametrize(
    "domain,expected",
    [
        ("douban.com", True),
        (".douban.com", True),
        ("movie.douban.com", True),
        ("DOUBAN.COM", True),
        ("douban.com.cn", False),  # different registrable domain
        ("notdouban.com", False),
        ("douban.com.evil.net", False),
        ("", False),
        (None, False),
    ],
)
def test_is_douban_domain_matches_only_douban(domain, expected):
    assert auth.is_douban_domain(domain) is expected


def test_login_cookies_present_needs_a_dbcl2_value():
    assert auth.login_cookies_present("dbcl2=2535429:abc; bid=x") is True
    assert auth.login_cookies_present("dbcl2=; bid=x") is False
    assert auth.login_cookies_present("bid=x") is False
    assert auth.login_cookies_present("") is False


# --- CDP probing (no browser involved) ---------------------------------------


def test_probe_cdp_returns_none_when_nothing_listens():
    assert auth.probe_cdp(1) is None  # port 1: connection refused → OSError


def test_probe_cdp_refuses_a_non_cdp_listener(monkeypatch):
    def not_json(*_args, **_kwargs):
        raise ValueError("not json")

    monkeypatch.setattr(auth, "_http_json", not_json)
    with pytest.raises(RuntimeError, match="does not speak CDP"):
        auth.probe_cdp(9222)


def test_probe_cdp_refuses_a_non_browser(monkeypatch):
    monkeypatch.setattr(
        auth, "_http_json", lambda *a, **k: {"Browser": "nginx/1.25", "Protocol-Version": "1.3"}
    )
    with pytest.raises(RuntimeError, match="not a Chromium-based browser"):
        auth.probe_cdp(9222)


def test_probe_cdp_accepts_edge(monkeypatch):
    payload = {"Browser": "Edg/154.0.0.0", "Protocol-Version": "1.3"}
    monkeypatch.setattr(auth, "_http_json", lambda *a, **k: dict(payload))
    assert auth.probe_cdp(9222) == payload


# --- login gate --------------------------------------------------------------


def test_check_cookies_without_a_header():
    status = auth.check_cookies(None)
    assert status.ok is False and status.reason == "no cookie"


def test_check_cookies_accepts_a_people_redirect(monkeypatch):
    # what a live valid session does (measured): 302 → /people/<id-or-vanity>/
    session = FakeSession(FakeResponse(302, location="https://www.douban.com/people/lexiongjia/"))
    monkeypatch.setattr(auth, "build_session", lambda _header: session)

    status = auth.check_cookies("dbcl2=2535429:abc; bid=x")

    assert status.ok is True
    # the numeric dbcl2 id wins over the vanity name in the redirect
    assert status.user_id == "2535429"
    assert session.requested == [auth.MINE_URL]  # never follows the redirect


def test_check_cookies_reads_the_id_from_the_redirect_when_the_cookie_is_missing(monkeypatch):
    session = FakeSession(FakeResponse(302, location="https://movie.douban.com/people/lex/"))
    monkeypatch.setattr(auth, "build_session", lambda _header: session)

    status = auth.check_cookies("bid=x")

    assert status.ok is True and status.user_id == "lex"


def test_check_cookies_rejects_the_anti_bot_gate(monkeypatch):
    """A missing/expired/bogus cookie answers exactly like no cookie (measured
    2026-09-27: 302 → sec.douban.com/b?r=…). The `dbcl2` cookie must not turn
    that into a false "valid session"."""
    gate = "https://sec.douban.com/b?r=https%3A%2F%2Fwww.douban.com%2Fmine%2F"
    monkeypatch.setattr(
        auth, "build_session", lambda _header: FakeSession(FakeResponse(302, location=gate))
    )

    status = auth.check_cookies('dbcl2="2535429:deadbeef"; bid=x')

    assert status.ok is False
    assert "anti-bot challenge" in status.reason


def test_check_cookies_rejects_an_expired_session(monkeypatch):
    monkeypatch.setattr(
        auth,
        "build_session",
        lambda _header: FakeSession(
            FakeResponse(302, location="https://accounts.douban.com/passport/login?redir=x")
        ),
    )

    status = auth.check_cookies("dbcl2=2535429:abc")

    assert status.ok is False and "expired" in status.reason


def test_check_cookies_rejects_an_unknown_redirect(monkeypatch):
    monkeypatch.setattr(
        auth,
        "build_session",
        lambda _header: FakeSession(FakeResponse(302, location="https://www.douban.com/")),
    )

    status = auth.check_cookies("dbcl2=2535429:abc")

    assert status.ok is False and "unexpected redirect" in status.reason


def test_check_cookies_treats_403_as_not_logged_in(monkeypatch):
    monkeypatch.setattr(auth, "build_session", lambda _header: FakeSession(FakeResponse(403)))
    status = auth.check_cookies("dbcl2=2535429:abc")
    assert status.ok is False and "not logged in" in status.reason


def test_check_cookies_accepts_a_rendered_profile_with_a_login_marker(monkeypatch):
    body = '<a href="https://www.douban.com/people/2535429/">我的豆瓣</a>'
    monkeypatch.setattr(
        auth, "build_session", lambda _header: FakeSession(FakeResponse(200, text=body))
    )
    status = auth.check_cookies("dbcl2=2535429:abc")
    assert status.ok is True and status.user_id == "2535429"


def test_check_cookies_rejects_a_render_without_a_login_marker(monkeypatch):
    # a 200 alone is not proof: an anonymous render must not read as logged in
    monkeypatch.setattr(
        auth,
        "build_session",
        lambda _header: FakeSession(FakeResponse(200, text="<html>豆瓣</html>")),
    )
    status = auth.check_cookies("dbcl2=2535429:abc")
    assert status.ok is False and "without a login marker" in status.reason


def test_check_cookies_rejects_a_render_without_a_dbcl2_id(monkeypatch):
    monkeypatch.setattr(
        auth, "build_session", lambda _header: FakeSession(FakeResponse(200, text="x"))
    )
    status = auth.check_cookies("bid=x")
    assert status.ok is False and "no dbcl2 id" in status.reason


# --- paths -------------------------------------------------------------------


def test_user_data_dir_defaults_to_the_isolated_profile(monkeypatch):
    monkeypatch.delenv("DOUBAN_USER_DATA_DIR", raising=False)
    assert auth.user_data_dir_path() == auth.DEFAULT_USER_DATA_DIR
    assert auth.user_data_dir_path("~/profile").name == "profile"


def test_cookies_file_path_honours_the_env_override(monkeypatch, tmp_path):
    monkeypatch.setenv(auth.COOKIES_FILE_ENV, str(tmp_path / "c.json"))
    assert auth.cookies_file_path() == tmp_path / "c.json"
    monkeypatch.delenv(auth.COOKIES_FILE_ENV)
    assert auth.cookies_file_path() == auth.DEFAULT_COOKIES_FILE
