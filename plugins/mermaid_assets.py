"""
Mermaid Assets Hook

Downloads mermaid JS locally during build (mirroring glightbox's approach
of bundling assets locally) and serves it from a China-fast CDN first,
falling back to the self-hosted copy if the CDN fails.

Why the CDN: GitHub Pages is slow from mainland China (the site's main
audience) — a ~3.2 MB mermaid.min.js can take 1+ minute to download
directly, while registry.npmmirror.com (Alibaba CDN) is fast. The local
file is kept as a built-in fallback (offline builds, CDN outage), so the
site never depends on the CDN being up.

Disable the CDN (pure self-hosting, old behaviour) by building with:
  MERMAID_CDN_URL="" uv run poe build
or point it at another mirror (template must contain {version}):
  MERMAID_CDN_URL="https://cdn.jsdelivr.net/npm/mermaid@{version}/dist/mermaid.min.js" \
    uv run poe build

Also injects defer (no async) on the mermaid <script> tag and moves it
into <head>, so it runs before DOMContentLoaded without blocking parse.

Usage in mkdocs.yml:
  hooks:
    - plugins/mermaid_assets.py
  plugins:
    - mermaid2:
        javascript: assets/javascripts/mermaid.min.js
"""

import json
import logging
import os
from urllib.parse import urlsplit

import requests
from bs4 import BeautifulSoup

log = logging.getLogger("mkdocs.plugins.mermaid_assets")

# Derive version from mermaid2's own default (single source of truth)
# Falls back to hardcoded value if mermaid2's internal API changes.
_MERMAID_JS_TAG = "mermaid.min.js"
VERSION_LOCK_FILE = ".mermaid-version"

# CDN template for the mermaid script. {version} is substituted with the
# locked mermaid version. registry.npmmirror.com (Alibaba) is fast in
# mainland China; jsdelivr is a slower-but-fine alternative. An empty
# string (MERMAID_CDN_URL="") disables the CDN entirely — the page then
# loads the self-hosted copy exactly as before.
MERMAID_CDN_URL = os.environ.get(
    "MERMAID_CDN_URL",
    "https://registry.npmmirror.com/mermaid/{version}/files/dist/mermaid.min.js",
).strip()


def _cdn_url(version):
    """Resolved CDN URL for mermaid.min.js, or None when the CDN is disabled."""
    if not MERMAID_CDN_URL:
        return None
    try:
        return MERMAID_CDN_URL.format(version=version)
    except (KeyError, ValueError, IndexError, AttributeError):
        # Malformed template (stray/missing braces) must not crash the
        # build — use it as-is; the browser-side onerror fallback still
        # covers us.
        log.warning("MERMAID_CDN_URL template is malformed: %r", MERMAID_CDN_URL)
        return MERMAID_CDN_URL


def _cdn_origin(url):
    """Scheme+netloc of a URL, or None when the URL has no usable origin."""
    parts = urlsplit(url)
    if parts.scheme and parts.netloc:
        return f"{parts.scheme}://{parts.netloc}"
    return None


def _get_mermaid_version(config=None):
    """Read mermaid version from mermaid2 plugin config, falling back to JAVASCRIPT_VERSION."""
    # Check if mkdocs config has a version override in the mermaid2 plugin
    if config and "plugins" in config:
        for plugin_name, plugin_cfg in config["plugins"].items():
            if plugin_name == "mermaid2" and hasattr(plugin_cfg, "config"):
                ver = plugin_cfg.config.get("version")
                if ver:
                    return ver
    try:
        from mermaid2.plugin import JAVASCRIPT_VERSION

        return JAVASCRIPT_VERSION
    except (ImportError, AttributeError):
        return "10.9.0"


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

    mermaid_version = _get_mermaid_version(config)

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
    """Make the mermaid script defer-only and load it from <head>.

    Material's own bundle.*.js contains a mermaid integration that, on
    DOMContentLoaded, checks `typeof mermaid == "undefined"` and only then
    dynamically fetches `https://unpkg.com/mermaid@11/dist/mermaid.min.js`.

    The plain `async` attribute (which wins over `defer` per the HTML spec)
    gives no ordering guarantee: the 2.8MB self-hosted bundle can still be
    downloading when Material's check runs, so Material falls back to the
    slow unpkg CDN (sometimes downloading the library twice).

    A `defer`-only script is guaranteed by the spec to execute before
    DOMContentLoaded, so `window.mermaid` always exists when Material's
    integration initializes and the unpkg fetch never fires. defer still
    downloads in parallel (no render blocking), and placing the tag in
    <head> starts that download as early as possible.
    """
    # Quick pre-filter using the src attribute pattern to avoid BS4 parsing
    # on pages without mermaid (mermaid2 only injects the script on pages
    # that have diagrams).
    # Check for mermaid script tag using basename match (works with any relative path)
    if _MERMAID_JS_TAG not in output:
        return output

    soup = BeautifulSoup(output, "html.parser")
    cdn_url = _cdn_url(_get_mermaid_version(config))
    for script in soup.find_all("script", src=True):
        # idempotency: skip a tag this hook already rewrote (src is already
        # the resolved CDN URL) — MkDocs normally calls on_post_page once per
        # page per build, but a re-processed output must not capture the CDN
        # URL as its "local" fallback
        if script["src"] and _MERMAID_JS_TAG in script["src"] and script["src"] != cdn_url:
            local_src = script["src"]  # page-relative path, correct at any depth
            script["defer"] = ""
            script.attrs.pop("async", None)
            if cdn_url:
                # Serve from the China-fast CDN first. If it fails, swap
                # back to the self-hosted copy (GitHub Pages) so rendering
                # still works without the CDN. Material's own unpkg fallback
                # remains as a final safety net.
                #
                # Timing assumption: the src swap keeps `defer` semantics,
                # so the local fallback is expected to execute before
                # DOMContentLoaded, which keeps Material's
                # `typeof mermaid == "undefined"` check from falling back to
                # unpkg (and downloading the library twice). The HTML spec
                # does not strictly guarantee defer ordering after a src
                # swap on a failed deferred script — in the worst case
                # (slow CDN failure + late local load) the unpkg fallback
                # fires and the library downloads twice. Diagrams still
                # render; this only degrades a CDN-outage scenario, never
                # the normal path.
                script["src"] = cdn_url
                # json.dumps emits a JS string literal with proper escaping
                # (paths are config-controlled, but keep the attribute
                # injection-proof anyway)
                script["onerror"] = "this.onerror=null;this.src=" + json.dumps(local_src)
            # move into <head> so the download starts in parallel with body
            # parsing (mermaid2 appends the tag at the end of <body>)
            if soup.head is not None:
                soup.head.append(script.extract())
            break

    if cdn_url and soup.head is not None:
        # warm up the TLS connection to the CDN origin while HTML parses;
        # place it after <meta charset> (never before it). A template
        # without a usable origin (e.g. scheme-less) gets no preconnect.
        origin = _cdn_origin(cdn_url)
        # idempotent: don't duplicate the hint if a previous pass already
        # inserted it for the same origin
        if origin and not soup.head.find("link", rel="preconnect", href=origin):
            link = soup.new_tag("link", rel="preconnect", href=origin)
            charset = soup.head.find("meta", charset=True)
            if charset is not None:
                charset.insert_after(link)
            else:
                soup.head.insert(0, link)

    return str(soup)
