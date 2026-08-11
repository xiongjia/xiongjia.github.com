"""Minimal GitHub REST API client (urllib, zero dependencies) for the local bot.

Reusable by other tooling (bot status pages, stale-PR cleanup, stats). Reads
the bot PAT from ``BOT_GH_TOKEN`` via ``shared.env.load_env_files()``
(git-ignored ``.env`` / ``.env.local``). See ``internal/bot-auto-pr-design.md``.

Notes:
- No ``gh`` dependency — gh is bound to a work account in the developer's
  environment, so everything goes through this client with the personal PAT.
- ``--auto-merge`` is implemented as wait → ready → merge in
  ``scripts/git_bot.py`` (REST has no reliable auto-merge toggle, so the bot
  polls checks itself and merges when green).
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from shared.env import load_env_files  # noqa: E402

API_BASE = "https://api.github.com"
DEFAULT_TIMEOUT = 900  # seconds to wait for checks
POLL_INTERVAL = 30


def _default_repo() -> str:
    """Parse ``owner/repo`` from the origin remote URL (constant fallback)."""
    try:
        out = subprocess.run(
            ["git", "config", "--get", "remote.origin.url"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        ).stdout.strip()
        m = re.search(r"[:/]([^/:]+)/([^/]+?)(?:\.git)?$", out)
        if m:
            return f"{m.group(1)}/{m.group(2)}"
    except Exception:
        pass
    return "xiongjia/xiongjia.github.com"


class GitHubError(RuntimeError):
    """Raised for non-2xx API responses; carries status + GitHub message."""

    def __init__(self, status: int, message: str, url: str):
        super().__init__(f"GitHub API {status} on {url}: {message}")
        self.status = status
        self.message = message
        self.url = url


class GitHubAPI:
    """Thin wrapper over the GitHub REST API, scoped to this repo."""

    def __init__(self, repo: str | None = None, token: str | None = None):
        load_env_files()
        self.repo = repo or _default_repo()
        self.owner, self.name = self.repo.split("/", 1)
        self.token = token or os.environ.get("BOT_GH_TOKEN", "")
        if not self.token:
            raise GitHubError(
                0,
                "BOT_GH_TOKEN is not set. Create a fine-grained PAT "
                "(Contents: write, Pull requests: write, Actions: read) and "
                "put it in .env — see internal/bot-auto-pr-design.md "
                "→ Credential Strategy",
                "init",
            )
        # bot-specific proxy (GitHub unreachable directly, e.g. mainland China)
        self.proxy = os.environ.get("BOT_HTTP_PROXY")
        self._opener = self._build_opener()

    def _build_opener(self) -> urllib.request.OpenerDirector:
        if self.proxy:
            handler = urllib.request.ProxyHandler({"http": self.proxy, "https": self.proxy})
            return urllib.request.build_opener(handler)
        return urllib.request.build_opener()

    # -- low level -----------------------------------------------------------

    def _request(self, method: str, path: str, payload: dict | None = None):
        url = f"{API_BASE}/repos/{self.repo}{path}"
        body = json.dumps(payload).encode("utf-8") if payload is not None else None
        req = urllib.request.Request(url, data=body, method=method)
        req.add_header("Authorization", f"Bearer {self.token}")
        req.add_header("Accept", "application/vnd.github+json")
        req.add_header("User-Agent", "xiongjia-bot")
        if body is not None:
            req.add_header("Content-Type", "application/json")
        try:
            with self._opener.open(req) as resp:
                raw = resp.read()
                return json.loads(raw) if raw else None
        except urllib.error.HTTPError as exc:
            message = str(exc)
            try:
                message = json.loads(exc.read()).get("message", message)
            except Exception:
                pass
            raise GitHubError(exc.code, message, url) from exc

    # -- pull requests -------------------------------------------------------

    def create_pr(
        self,
        head: str,
        base: str,
        title: str,
        body: str,
        draft: bool = True,
    ) -> tuple[int, str]:
        """Open a PR; returns ``(number, html_url)``."""
        data = self._request(
            "POST",
            "/pulls",
            {"head": head, "base": base, "title": title, "body": body, "draft": draft},
        )
        return data["number"], data["html_url"]

    def list_prs(self, state: str = "all", head: str | None = None) -> list[dict]:
        path = f"/pulls?state={state}&per_page=100"
        if head:
            path += f"&head={head}"
        return self._request("GET", path) or []

    def find_pr_by_head(self, branch: str) -> dict | None:
        prs = self.list_prs(state="all", head=f"{self.owner}:{branch}")
        return prs[0] if prs else None

    def close_pr(self, pull_number: int) -> None:
        self._request("PATCH", f"/pulls/{pull_number}", {"state": "closed"})

    def mark_ready(self, pull_number: int) -> None:
        self._request("PATCH", f"/pulls/{pull_number}", {"draft": False})

    def merge(self, pull_number: int, method: str = "squash") -> dict:
        return self._request("PUT", f"/pulls/{pull_number}/merge", {"merge_method": method})

    # -- checks ----------------------------------------------------------------

    def wait_checks(
        self,
        sha: str,
        timeout: int = DEFAULT_TIMEOUT,
        interval: int = POLL_INTERVAL,
    ) -> tuple[bool, list[str]]:
        """Poll check-runs for a commit until all complete.

        Returns ``(all_green, summary_lines)``; ``all_green`` is False on
        failure or timeout.
        """
        deadline = time.monotonic() + timeout
        attempts = 0
        while time.monotonic() < deadline:
            data = self._request("GET", f"/commits/{sha}/check-runs")
            runs = data.get("check_runs") or []
            if runs and all(r.get("status") == "completed" for r in runs):
                lines = [f"{r.get('name')}: {r.get('conclusion')}" for r in runs]
                ok = all(r.get("conclusion") in ("success", "neutral", "skipped") for r in runs)
                return ok, lines
            attempts += 1
            if attempts % 5 == 0:
                running = [f"{r.get('name')}: {r.get('status')}" for r in runs[:3]] or [
                    "no checks yet"
                ]
                print(f"⏳ still waiting after {attempts * interval}s — " + ", ".join(running))
            time.sleep(interval)
        return False, ["timed out waiting for check-runs"]


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="GitHub API smoke test")
    parser.add_argument("--whoami", action="store_true", help="print repo full name")
    args = parser.parse_args()
    api = GitHubAPI()
    if args.whoami:
        data = api._request("GET", "")
        print(data["full_name"])
