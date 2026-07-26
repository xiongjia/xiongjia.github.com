"""
Mermaid Assets Hook

Downloads mermaid JS locally during build (mirroring glightbox's approach
of bundling assets locally). Removes CDN dependency for faster page loads.
Also injects async/defer on the mermaid <script> tag for non-blocking load.

Usage in mkdocs.yml:
  hooks:
    - plugins/mermaid_assets.py
  plugins:
    - mermaid2:
        javascript: assets/javascripts/mermaid.min.js
"""

import logging
import os

from bs4 import BeautifulSoup
import requests

log = logging.getLogger("mkdocs.plugins.mermaid_assets")

# Derive version from mermaid2's own default (single source of truth)
# Falls back to hardcoded value if mermaid2's internal API changes.
_MERMAID_JS_TAG = "mermaid.min.js"
VERSION_LOCK_FILE = ".mermaid-version"


def _get_mermaid_version():
    try:
        from mermaid2.plugin import JAVASCRIPT_VERSION

        return JAVASCRIPT_VERSION
    except (ImportError, AttributeError):
        return "10.4.0"


def on_pre_build(config, **kwargs):
    """Download self-contained mermaid UMD bundle to docs/assets/javascripts/."""
    docs_dir = config["docs_dir"]
    assets_dir = os.path.join(docs_dir, "assets", "javascripts")
    os.makedirs(assets_dir, exist_ok=True)

    mermaid_js_path = os.path.join(assets_dir, "mermaid.min.js")
    version_lock_path = os.path.join(docs_dir, VERSION_LOCK_FILE)

    # Check cache
    cached_version = None
    if os.path.exists(version_lock_path):
        with open(version_lock_path) as f:
            cached_version = f.read().strip()

    mermaid_version = _get_mermaid_version()

    if cached_version == mermaid_version and os.path.exists(mermaid_js_path):
        log.info(
            "mermaid v%s already cached locally at %s",
            mermaid_version,
            mermaid_js_path,
        )
        return

    # Download self-contained UMD bundle (not the ESM wrapper which has relative imports)
    url = f"https://unpkg.com/mermaid@{mermaid_version}/dist/mermaid.min.js"
    log.info("Downloading mermaid v%s from %s ...", mermaid_version, url)
    try:
        resp = requests.get(url, timeout=60)
        resp.raise_for_status()
        with open(mermaid_js_path, "wb") as f:
            f.write(resp.content)
        with open(version_lock_path, "w") as f:
            f.write(mermaid_version)
        log.info(
            "Downloaded mermaid JS (%.1f KB) to %s",
            len(resp.content) / 1024,
            mermaid_js_path,
        )
    except Exception as exc:
        log.warning("Failed to download mermaid JS: %s.", exc)
        # Create stub file to satisfy mermaid2's url_exists check.
        # Without a valid JS bundle, diagrams simply won't render
        # (graceful degradation instead of build crash).
        if not os.path.exists(mermaid_js_path):
            with open(mermaid_js_path, "w") as f:
                f.write("// download failed, mermaid unavailable")


def on_post_page(output, page, config, **kwargs):
    """Add async+defer to the mermaid <script> tag for non-blocking load.

    The 2.8MB mermaid bundle should not block rendering. The original ESM
    import (type="module") had implicit defer; the UMD script tag does not,
    so we inject the attributes here.
    """
    # Quick pre-filter using the src attribute pattern to avoid BS4 parsing
    # on pages without mermaid (mermaid2 only injects the script on pages
    # that have diagrams).
    mermaid_src = f"src=\"{_MERMAID_JS_TAG}\""
    if mermaid_src not in output:
        return output

    soup = BeautifulSoup(output, "html.parser")
    for script in soup.find_all("script", src=True):
        if _MERMAID_JS_TAG in script["src"]:
            script["async"] = ""
            script["defer"] = ""
            break

    return str(soup)
