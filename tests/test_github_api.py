"""Unit tests for shared/github_api.py — retry + idempotency (no network).

The HTTP layer is stubbed at ``_request_once`` / ``_request``; the real proxy
path (a flaky CONNECT that drops mid-request) is what the retries exist for,
and is only exercised end-to-end by the developer.
"""

import urllib.error
import urllib.request

import pytest

import shared.github_api as gi


@pytest.fixture()
def api(monkeypatch):
    monkeypatch.setattr(gi.time, "sleep", lambda _delay: None)  # skip real backoff
    monkeypatch.setattr(gi, "load_env_files", lambda: None)  # hermetic: no .env
    for key in ("BOT_HTTP_PROXY", "BOT_HTTP_DIRECT", "BOT_HTTP_TIMEOUT"):
        monkeypatch.delenv(key, raising=False)
    return gi.GitHubAPI(repo="owner/repo", token="fake")


# -- routes -------------------------------------------------------------------


def test_routes_default_to_direct_only(api):
    assert [name for name, _opener in api._routes] == ["direct"]


def test_routes_try_direct_before_proxy(api, monkeypatch):
    monkeypatch.setenv("BOT_HTTP_PROXY", "http://127.0.0.1:1095")
    api = gi.GitHubAPI(repo="owner/repo", token="fake")
    assert [name for name, _opener in api._routes] == ["direct", "proxy http://127.0.0.1:1095"]


def test_routes_proxy_only_when_direct_disabled(api, monkeypatch):
    monkeypatch.setenv("BOT_HTTP_PROXY", "http://127.0.0.1:1095")
    monkeypatch.setenv("BOT_HTTP_DIRECT", "0")
    api = gi.GitHubAPI(repo="owner/repo", token="fake")
    assert [name for name, _opener in api._routes] == ["proxy http://127.0.0.1:1095"]


def test_direct_route_ignores_env_proxy(api, monkeypatch):
    """git_bot exports BOT_HTTP_PROXY into HTTPS_PROXY for subprocesses; the
    direct route must not pick that up again."""
    monkeypatch.setenv("BOT_HTTP_PROXY", "http://127.0.0.1:1095")
    monkeypatch.setenv("HTTPS_PROXY", "http://127.0.0.1:1095")
    api = gi.GitHubAPI(repo="owner/repo", token="fake")
    direct, proxied = api._routes[0][1], api._routes[1][1]

    def proxy_handlers(opener):
        """Handlers that would route a request through a proxy."""
        return [
            h
            for h in opener.handlers
            if isinstance(h, urllib.request.ProxyHandler) and getattr(h, "proxies", None)
        ]

    assert proxy_handlers(direct) == []
    assert proxy_handlers(proxied)[0].proxies == {
        "http": "http://127.0.0.1:1095",
        "https": "http://127.0.0.1:1095",
    }


def test_timeout_reads_env(api, monkeypatch):
    monkeypatch.setenv("BOT_HTTP_TIMEOUT", "7")
    api = gi.GitHubAPI(repo="owner/repo", token="fake")
    assert api.timeout == 7.0


# -- transport-level retry ----------------------------------------------------


def test_request_retries_transient_then_succeeds(api, monkeypatch):
    calls = []

    def fake_once(opener, method, path, payload=None):
        calls.append(method)
        if len(calls) == 1:
            # what the 2026-10-30 runs died on: the connection drops mid-request
            raise urllib.error.URLError(
                "<urlopen error [SSL: UNEXPECTED_EOF_WHILE_READING] EOF occurred>"
            )
        return {"ok": True}

    monkeypatch.setattr(api, "_request_once", fake_once)
    assert api._request("GET", "/pulls") == {"ok": True}
    assert len(calls) == 2


def test_request_retries_unwrapped_connection_reset(api, monkeypatch):
    calls = []

    def fake_once(opener, method, path, payload=None):
        calls.append(method)
        if len(calls) == 1:
            raise ConnectionResetError("Remote end closed connection without response")
        return {"ok": True}

    monkeypatch.setattr(api, "_request_once", fake_once)
    assert api._request("POST", "/pulls", {}) == {"ok": True}
    assert len(calls) == 2


def test_request_gives_up_after_last_attempt(api, monkeypatch):
    calls = []

    def fake_once(*args, **kwargs):
        calls.append(1)
        raise TimeoutError("read timed out")

    monkeypatch.setattr(api, "_request_once", fake_once)
    with pytest.raises(TimeoutError):
        api._request("GET", "/pulls")
    assert len(calls) == len(gi.RETRY_BACKOFF) + 1


def test_request_does_not_retry_http_errors(api, monkeypatch):
    calls = []

    def fake_once(*args, **kwargs):
        calls.append(1)
        raise gi.GitHubError(404, "Not Found", "https://api.github.com/x")

    monkeypatch.setattr(api, "_request_once", fake_once)
    with pytest.raises(gi.GitHubError):
        api._request("GET", "/pulls")
    assert len(calls) == 1


# -- direct → proxy fallback --------------------------------------------------


def test_request_falls_back_to_proxy_after_direct_route_dies(api, monkeypatch):
    monkeypatch.setenv("BOT_HTTP_PROXY", "http://127.0.0.1:1095")
    api = gi.GitHubAPI(repo="owner/repo", token="fake")
    seen = []

    def fake_once(opener, method, path, payload=None):
        route = "direct" if opener is api._routes[0][1] else "proxy"
        seen.append(route)
        if route == "direct":
            raise urllib.error.URLError("connection refused")
        return {"ok": True}

    monkeypatch.setattr(api, "_request_once", fake_once)
    assert api._request("GET", "") == {"ok": True}
    # every direct attempt first, then the proxy wins
    assert seen == ["direct"] * (len(gi.RETRY_BACKOFF) + 1) + ["proxy"]


def test_request_uses_only_direct_when_it_works(api, monkeypatch):
    monkeypatch.setenv("BOT_HTTP_PROXY", "http://127.0.0.1:1095")
    api = gi.GitHubAPI(repo="owner/repo", token="fake")
    seen = []

    def fake_once(opener, method, path, payload=None):
        seen.append("direct" if opener is api._routes[0][1] else "proxy")
        return {"ok": True}

    monkeypatch.setattr(api, "_request_once", fake_once)
    assert api._request("GET", "") == {"ok": True}
    assert seen == ["direct"]


def test_request_raises_last_error_when_all_routes_fail(api, monkeypatch):
    monkeypatch.setenv("BOT_HTTP_PROXY", "http://127.0.0.1:1095")
    api = gi.GitHubAPI(repo="owner/repo", token="fake")
    calls = []

    def fake_once(opener, method, path, payload=None):
        calls.append(opener)
        raise TimeoutError("read timed out")

    monkeypatch.setattr(api, "_request_once", fake_once)
    with pytest.raises(TimeoutError):
        api._request("GET", "")
    assert len(calls) == 2 * (len(gi.RETRY_BACKOFF) + 1)


# -- create_pr ----------------------------------------------------------------


def test_create_pr_returns_number_and_url(api, monkeypatch):
    monkeypatch.setattr(api, "_request", lambda *a, **k: {"number": 7, "html_url": "https://x/7"})
    assert api.create_pr("bot/weight/1", "main", "t", "b") == (7, "https://x/7")


def test_create_pr_reuses_pr_when_head_already_exists(api, monkeypatch):
    """Replayed POST after a dropped response: GitHub answers 422, the PR exists."""

    def fake_request(*args, **kwargs):
        raise gi.GitHubError(422, "A pull request already exists for owner:bot/weight/1.", "u")

    monkeypatch.setattr(api, "_request", fake_request)
    monkeypatch.setattr(
        api, "find_pr_by_head", lambda head: {"number": 9, "html_url": "https://x/9"}
    )
    assert api.create_pr("bot/weight/1", "main", "t", "b") == (9, "https://x/9")


def test_create_pr_reraises_422_without_existing_pr(api, monkeypatch):
    """422 for another reason (no commits between branches) must still fail."""

    def fake_request(*args, **kwargs):
        raise gi.GitHubError(422, "No commits between main and bot/weight/1", "u")

    monkeypatch.setattr(api, "_request", fake_request)
    monkeypatch.setattr(api, "find_pr_by_head", lambda head: None)
    with pytest.raises(gi.GitHubError):
        api.create_pr("bot/weight/1", "main", "t", "b")


def test_create_pr_does_not_look_up_on_other_errors(api, monkeypatch):
    looked_up = []

    def fake_request(*args, **kwargs):
        raise gi.GitHubError(401, "Bad credentials", "u")

    monkeypatch.setattr(api, "_request", fake_request)
    monkeypatch.setattr(api, "find_pr_by_head", lambda head: looked_up.append(head) or None)
    with pytest.raises(gi.GitHubError):
        api.create_pr("bot/weight/1", "main", "t", "b")
    assert looked_up == []


# -- merge --------------------------------------------------------------------


def test_merge_reports_already_merged_pr(api, monkeypatch):
    def fake_request(method, path, payload=None):
        if method == "PUT":
            raise gi.GitHubError(405, "Pull Request is not mergeable", "u")
        return {"number": 5, "merged": True, "html_url": "https://x/5"}

    monkeypatch.setattr(api, "_request", fake_request)
    assert api.merge(5)["merged"] is True


def test_merge_reraises_when_pr_not_merged(api, monkeypatch):
    def fake_request(method, path, payload=None):
        if method == "PUT":
            raise gi.GitHubError(405, "Pull request is not mergeable", "u")
        return {"number": 5, "merged": False}

    monkeypatch.setattr(api, "_request", fake_request)
    with pytest.raises(gi.GitHubError):
        api.merge(5)
