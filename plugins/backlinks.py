"""Backlinks & Link Topology Hook

Builds a bidirectional link index (Backlinks) and optional Mermaid topology graphs:

- **Pass A (`on_files`)** — after draft filtering, build a page map from the final
  ``config.files`` and pre-scan raw markdown to extract internal links. This is a
  single source of truth for all downstream features, and is rebuilt on every
  build (hooks are plain modules; state must not leak across ``serve`` rebuilds).
- **Pass B (`on_page_markdown`)** — pure injection: a "Backlinks" section listing
  every page that links to the current one, plus a per-page neighborhood Mermaid
  graph and the site-wide topology page (``notes/link-graph.md``).

Why pre-scan instead of accumulating during render: MkDocs renders pages in a
single sequential pass with no deferred injection point, and per-page backlinks
depend on the *complete* edge set (a page processed later may link to an earlier
one). See internal/plans/mkdocs-backlinks-topology.md for the full design.

Usage in mkdocs.yml:
    hooks:
      - plugins/backlinks.py
    extra:
      backlinks:
        enabled: true
        include: ["notes/**"]        # gitignore-style globs relative to docs_dir
        exclude: ["notes/posts/**", "moments/**", "notes/_index_content.md"]
        max_backlinks: 20            # cap per page, "all" for unlimited
        graph:
          enabled: true
          depth: 5                   # neighborhood depth for per-page graph
          layout: "lr"               # per-page graph direction
          global_layout: "lr"        # global page: main+subgraph LR -> portrait, no shrink
          max_nodes: 50              # safety cap for huge sections
          global_page: "notes/link-graph.md"
"""

import logging
import os
import posixpath
import re
import sys
from collections.abc import MutableMapping
from pathlib import Path

# bootstrap repo root so `shared/` is importable regardless of how this runs
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pathspec import PathSpec

from shared.frontmatter import parse_frontmatter
from shared.io import resolve_within, safe_read

log = logging.getLogger("mkdocs.hooks.backlinks")

_INCLUDE_PATTERN = re.compile(r"<!--\s*include:\s*(.+?)\s*-->")
# Inline links [text](target), skipping images ![alt](target). Targets must not
# contain whitespace or `)`; an optional title in parens is allowed.
_LINK_PATTERN = re.compile(r"(?<!!)\[[^\]]*\]\(([^)\s]+)(?:\s+[^)]*)?\)")
_FENCE_PATTERN = re.compile(r"```.*?```", re.S)
_CODE_SPAN_PATTERN = re.compile(r"`[^`\n]*`")

_DEFAULT_CONFIG = {
    "enabled": True,
    "include": ["notes/**"],
    "exclude": ["notes/posts/**", "moments/**", "notes/_index_content.md"],
    "max_backlinks": 20,
    "graph": {
        "enabled": True,
        "depth": 5,
        "layout": "lr",
        # global page: main LR + subgraph LR -> portrait (clusters stacked top-down),
        # narrow enough that Material's width-fit does not shrink it unreadably
        "global_layout": "lr",
        "max_nodes": 50,
        "global_page": "notes/link-graph.md",
    },
}

# Module-level state, rebuilt every build in `on_files` (hooks are plain modules).
_PAGES: dict[str, dict] = {}  # src_uri -> {"title", "url", "section"}
_EDGES: set[tuple[str, str]] = set()  # (source src_uri, target src_uri)
_BACKLINKS: dict[str, list[str]] = {}  # target src_uri -> [source src_uri]


# --------------------------------------------------------------------------
# Config
# --------------------------------------------------------------------------


def _coerce_int(value, default: int, name: str) -> int:
    """Coerce a positive int config option; fall back (with a warning) on bad values."""
    original = value
    if isinstance(value, bool) or (isinstance(value, float) and not value.is_integer()):
        # bool is an int subclass; non-integral floats would truncate silently
        value = None
    try:
        value = int(value)
        if value < 1:
            raise ValueError
        return value
    except (TypeError, ValueError):
        log.warning("Invalid backlinks %s %r, using default %d", name, original, default)
        return default


def _coerce_str(value, default: str, name: str) -> str:
    """Coerce a non-empty str config option; fall back (with a warning) on bad values."""
    if isinstance(value, str) and value.strip():
        return value.strip()
    log.warning("Invalid backlinks %s %r, using default %r", name, value, default)
    return default


def _load_config(config) -> dict:
    """Merge `extra.backlinks` from mkdocs.yml over the defaults (deep merge).

    The real MkDocs config is a `UserDict` subclass (a `MutableMapping`, not a
    plain `dict`), so accept any mapping — a `dict` check would silently ignore
    `extra.backlinks` at build time. Malformed values fall back to defaults with
    a warning instead of crashing the build.
    """
    if isinstance(config, MutableMapping):
        user = config.get("extra", {}).get("backlinks", {})
    else:
        user = {}
    if not isinstance(user, MutableMapping):
        log.warning("Invalid backlinks config %r, using defaults", user)
        user = {}
    cfg = {**_DEFAULT_CONFIG, **{k: v for k, v in user.items() if v is not None}}
    # nested `graph` value must also be a mapping (same robustness as `backlinks`)
    graph_value = cfg.get("graph", {})
    if not isinstance(graph_value, MutableMapping):
        log.warning("Invalid backlinks graph config %r, using defaults", graph_value)
        graph_value = {}
    graph_user = {k: v for k, v in graph_value.items() if v is not None}
    graph = {**_DEFAULT_CONFIG["graph"], **graph_user}

    # validate options: a bad value must not crash the build
    if not isinstance(cfg["enabled"], bool):
        log.warning("Invalid backlinks enabled %r, using default %r", cfg["enabled"], True)
        cfg["enabled"] = True
    graph["depth"] = _coerce_int(graph["depth"], _DEFAULT_CONFIG["graph"]["depth"], "graph.depth")
    graph["max_nodes"] = _coerce_int(
        graph["max_nodes"], _DEFAULT_CONFIG["graph"]["max_nodes"], "graph.max_nodes"
    )
    graph["layout"] = _coerce_str(
        graph["layout"], _DEFAULT_CONFIG["graph"]["layout"], "graph.layout"
    )
    graph["global_layout"] = _coerce_str(
        graph["global_layout"], _DEFAULT_CONFIG["graph"]["global_layout"], "graph.global_layout"
    )
    if cfg["max_backlinks"] != "all":
        cfg["max_backlinks"] = _coerce_int(
            cfg["max_backlinks"], _DEFAULT_CONFIG["max_backlinks"], "max_backlinks"
        )
    cfg["graph"] = graph
    return cfg


def _in_scope(src_uri: str, include_spec, exclude_spec) -> bool:
    """Apply include/exclude gitignore-style globs (relative to docs_dir)."""
    if include_spec and not include_spec.match_file(src_uri):
        return False
    if exclude_spec and exclude_spec.match_file(src_uri):
        return False
    return True


# --------------------------------------------------------------------------
# Pass A: page map + edge pre-scan
# --------------------------------------------------------------------------


def _read(docs_dir, rel_uri):
    return safe_read(Path(docs_dir) / rel_uri)


def _title_of(src_uri: str, docs_dir) -> str:
    meta, _ = parse_frontmatter(_read(docs_dir, src_uri) or "") or (None, "")
    return str((meta or {}).get("title") or src_uri)


def _nav_titles(config) -> dict[str, str]:
    """Display titles from `nav` (nav title wins over frontmatter in MkDocs).

    Handles the `navigation.indexes` convention: a section's first bare `.md`
    child is the section index page and inherits the section title.
    """

    titles: dict[str, str] = {}

    def walk(items):
        for item in items or []:
            if isinstance(item, str):
                if item.endswith(".md"):
                    titles.setdefault(item, Path(item).stem)
            elif isinstance(item, dict):
                for title, value in item.items():
                    if isinstance(value, str) and value.endswith(".md"):
                        titles.setdefault(value, str(title))
                    elif isinstance(value, list):
                        if value and isinstance(value[0], str) and value[0].endswith(".md"):
                            titles.setdefault(value[0], str(title))
                        walk(value)

    walk(config.get("nav"))
    return titles


def _section_of(src_uri: str) -> str:
    """First path segment below docs root, e.g. notes/collection/x.md -> collection."""
    parts = src_uri.split("/")
    return parts[1] if len(parts) > 2 else "root"


def _expand_includes(text: str, docs_dir) -> str:
    """Expand `<!-- include: path -->` markers (mirrors snippet_include.py)."""

    def _replace(match):
        rel = match.group(1).strip()
        abs_path = resolve_within(docs_dir, rel)
        if abs_path is None:
            log.warning(
                "Snippet include path '%s' resolved outside docs_dir, skipping.",
                rel,
            )
            return match.group(0)
        if not os.path.isfile(abs_path):
            log.warning(
                "Snippet include file not found: %s (resolved: %s)",
                rel,
                abs_path,
            )
            return match.group(0)
        content = safe_read(abs_path)
        if content is None:
            log.warning("Snippet include unreadable: %s", rel)
            return match.group(0)
        return content

    return _INCLUDE_PATTERN.sub(_replace, text)


def _resolve_target(src_uri: str, target: str):
    """Resolve a raw link target to a normalized src_uri, or None if not internal."""
    t = target.strip()
    if not t or t.startswith(("#", "/")) or "://" in t or "mailto:" in t:
        return None
    # strip fragment / query
    t = t.split("#", 1)[0].split("?", 1)[0].strip()
    if not t:
        return None
    if t.endswith("/"):
        t += "index.md"
    if not t.endswith(".md"):
        return None
    return posixpath.normpath(posixpath.join(posixpath.dirname(src_uri), t))


def _scan_page(docs_dir, src_uri: str, pages: dict):
    """Yield (source, target) edges found in one page's raw markdown."""
    text = _read(docs_dir, src_uri)
    if text is None:
        return
    text = _expand_includes(text, docs_dir)
    text = _FENCE_PATTERN.sub("", text)
    text = _CODE_SPAN_PATTERN.sub("", text)
    for raw in _LINK_PATTERN.findall(text):
        target = _resolve_target(src_uri, raw)
        if target and target in pages and target != src_uri:
            yield (src_uri, target)


def _build_index(files, docs_dir, cfg, nav_titles=None):
    include_spec = PathSpec.from_lines("gitignore", cfg["include"]) if cfg["include"] else None
    exclude_spec = PathSpec.from_lines("gitignore", cfg["exclude"]) if cfg["exclude"] else None
    pages = {}
    for f in files:
        if not f.is_documentation_page():
            continue
        if not f.src_uri.endswith(".md"):
            continue
        if not _in_scope(f.src_uri, include_spec, exclude_spec):
            continue
        nav_title = (nav_titles or {}).get(f.src_uri)
        frontmatter_title = _title_of(f.src_uri, docs_dir)
        # nav title wins, then frontmatter title, then the filename stem
        title = (
            nav_title
            or (frontmatter_title if frontmatter_title != f.src_uri else None)
            or Path(f.src_uri).stem
        )
        pages[f.src_uri] = {
            "title": str(title),
            "url": f.url,
            "section": _section_of(f.src_uri),
        }
    edges = set()
    for src in pages:
        edges.update(_scan_page(docs_dir, src, pages))
    backlinks: dict[str, list[str]] = {}
    for source, target in edges:
        backlinks.setdefault(target, []).append(source)
    return pages, edges, backlinks


def on_files(files, config, **kwargs):
    """Pass A: build the page map + edge set from the final file collection."""
    cfg = _load_config(config)
    if not cfg["enabled"]:
        return files

    global _PAGES, _EDGES, _BACKLINKS
    _PAGES, _EDGES, _BACKLINKS = _build_index(files, config["docs_dir"], cfg, _nav_titles(config))
    log.info("backlinks: %d pages, %d edges", len(_PAGES), len(_EDGES))
    return files


# --------------------------------------------------------------------------
# Pass B: injection
# --------------------------------------------------------------------------


def _mermaid_click_url(from_url: str, to_url: str) -> str:
    """Relative URL from one page to another, for Mermaid `click` directives.

    Both URLs are MkDocs pretty URLs (e.g. ``notes/tools/med-tracker/``) that
    the browser must resolve at runtime, so directory paths keep their trailing
    slash. Distinct from `_rel_src`, which produces source-`.md` paths for
    markdown links that MkDocs validates and rewrites.
    """
    if from_url in ("", "/"):
        # root-level page: target URLs are already root-relative
        return to_url
    if from_url.endswith("/"):
        base = from_url
    else:
        dirname = posixpath.dirname(from_url)
        base = dirname + "/" if dirname else ""
    rel = posixpath.relpath(to_url, base)
    if to_url.endswith("/") and not rel.endswith("/"):
        rel += "/"
    return rel


def _backlinks_items(src_uri: str, cfg: dict) -> str:
    """Markdown list of incoming links; empty string when none."""
    sources = sorted(
        _BACKLINKS.get(src_uri, ()),
        key=lambda s: (_PAGES[s]["section"], _PAGES[s]["title"]),
    )
    return _link_list(page_src_uri=src_uri, targets=sources, cap=cfg["max_backlinks"])


def _forward_targets(src_uri: str) -> list[str]:
    """Outgoing link targets of a page, sorted by section then title."""
    return sorted(
        (t for s, t in _EDGES if s == src_uri),
        key=lambda t: (_PAGES[t]["section"], _PAGES[t]["title"]),
    )


def _rel_src(from_src: str, to_src: str) -> str:
    """Relative path from one page's source `.md` file to another."""
    return posixpath.relpath(to_src, posixpath.dirname(from_src))


def _link_list(page_src_uri: str, targets, cap) -> str:
    """Markdown bullet list of page links, capped, ``... and N more`` overflow.

    `page_src_uri` is the current page's source `.md` path; links are rendered
    as relative source paths (e.g. ``../collection/database.md``) so MkDocs can
    validate them and rewrite them to pretty URLs at build time.
    """
    if not targets:
        return ""
    if cap == "all" or len(targets) <= cap:
        shown, extra = targets, 0
    else:
        shown, extra = targets[:cap], len(targets) - cap
    lines = [f"- [{_PAGES[t]['title']}]({_rel_src(page_src_uri, t)})" for t in shown]
    if extra:
        lines.append(f"- … and {extra} more")
    return "\n".join(lines)


def _card(title: str, lines) -> str:
    """A collapsed admonition (`??? info`) with 4-space indented content."""
    return f'??? info "{title}"\n' + "\n".join("    " + line for line in lines)


def _neighborhood(start: str, depth: int, max_nodes: int) -> set[str]:
    """Undirected BFS over edges from `start`, capped at max_nodes (exact)."""
    nodes = {start}
    frontier = {start}
    for _ in range(max(1, depth)):
        nxt = set()
        for u in frontier:
            for a, b in _EDGES:
                if a == u:
                    nxt.add(b)
                elif b == u:
                    nxt.add(a)
        frontier = nxt - nodes
        if not frontier:
            break
        room = max_nodes - len(nodes)
        if room <= 0:
            break
        if len(frontier) > room:
            # deterministic truncation keeps the cap exact
            frontier = set(sorted(frontier)[:room])
        nodes |= frontier
        if len(nodes) >= max_nodes:
            break
    return nodes


def _ml_escape(text: str) -> str:
    """Escape a string for use inside a quoted Mermaid label/tooltip."""
    return text.replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ").replace("\r", " ")


def _mermaid_block(layout: str, node_srcs, edge_pairs, base_url: str, clusters=None) -> str:
    """Render a mermaid flowchart with clickable nodes; empty string if nothing."""
    if not node_srcs:
        return ""
    ids = {s: f"n{i}" for i, s in enumerate(sorted(node_srcs))}
    lines = [f"flowchart {layout.upper()}"]

    if clusters:
        for idx, section in enumerate(sorted(clusters)):
            members = sorted(clusters[section])
            label = _ml_escape(section)
            lines.append(f'  subgraph s{idx}["{label}"]')
            lines.append(f"    direction {layout.upper()}")
            for s in members:
                lines.append(f'    {ids[s]}["{_ml_escape(_PAGES[s]["title"])}"]')
            lines.append("  end")
    else:
        for s in sorted(node_srcs):
            lines.append(f'  {ids[s]}["{_ml_escape(_PAGES[s]["title"])}"]')
    for a, b in sorted(edge_pairs):
        if a in ids and b in ids:
            lines.append(f"  {ids[a]} --> {ids[b]}")

    for s in sorted(node_srcs):
        title = _ml_escape(_PAGES[s]["title"])
        url = _mermaid_click_url(base_url, _PAGES[s]["url"])
        lines.append(f'  click {ids[s]} "{url}" "{title}"')
    return "```mermaid\n" + "\n".join(lines) + "\n```"


def _neighborhood_section(src_uri: str, cfg: dict) -> str:
    g = cfg["graph"]
    nodes = _neighborhood(src_uri, g["depth"], g["max_nodes"])
    # a graph with only the current page adds nothing
    if len(nodes) < 2:
        return ""
    edges_in = {(a, b) for (a, b) in _EDGES if a in nodes and b in nodes}
    return _mermaid_block(g["layout"], nodes, edges_in, _PAGES[src_uri]["url"])


def _global_section(cfg: dict) -> str:
    g = cfg["graph"]
    global_page = g["global_page"]
    node_srcs = set(_PAGES) - {global_page}
    if not node_srcs:
        return ""
    clusters: dict[str, list[str]] = {}
    for s in sorted(node_srcs):
        clusters.setdefault(_PAGES[s]["section"], []).append(s)
    edges_in = {(a, b) for (a, b) in _EDGES if a in node_srcs and b in node_srcs}
    base = _PAGES[global_page]["url"] if global_page in _PAGES else "notes/link-graph/"
    return _mermaid_block(
        g.get("global_layout", "lr"), node_srcs, edges_in, base, clusters=clusters
    )


def on_page_markdown(markdown, page, config, **kwargs):
    """Pass B: override the global page, append backlinks + neighborhood graph."""
    cfg = _load_config(config)
    if not cfg["enabled"]:
        return markdown

    src_uri = page.file.src_uri
    if cfg["graph"]["enabled"] and src_uri == cfg["graph"]["global_page"]:
        graph = _global_section(cfg)
        body = [
            "Overview of all pages and their link relationships, generated by a",
            "MkDocs plugin at build time.",
            "",
            graph,
            "",
        ]
        return "\n".join(body)

    if src_uri not in _PAGES:
        return markdown

    backlinks = _backlinks_items(src_uri, cfg)
    fwd_targets = _forward_targets(src_uri)
    forward = _link_list(
        page_src_uri=src_uri, targets=fwd_targets, cap=cfg["max_backlinks"]
    )
    graph = _neighborhood_section(src_uri, cfg) if cfg["graph"]["enabled"] else ""

    blocks = []
    if backlinks:
        # collapsed card: incoming list + neighborhood graph
        inner = backlinks.splitlines()
        if graph:
            inner += ["", *graph.splitlines()]
        blocks.append(_card(f"Backlinks ({len(_BACKLINKS.get(src_uri, ()))})", inner))
        if forward:
            blocks.append(_card(f"Links ({len(fwd_targets)})", forward.splitlines()))
    elif forward or graph:
        # no backlinks: fold outgoing list + graph into one collapsed card
        inner = forward.splitlines() if forward else []
        if graph:
            if inner:
                inner.append("")
            inner += graph.splitlines()
        blocks.append(_card(f"Links ({len(fwd_targets)})", inner))

    if not blocks:
        return markdown
    return markdown.rstrip() + "\n\n" + "\n\n".join(blocks) + "\n"
