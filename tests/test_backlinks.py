"""Unit tests for plugins.backlinks: link extraction, resolution, injection."""

from collections import UserDict
from types import SimpleNamespace

from mkdocs.structure.files import File, Files

import plugins.backlinks as bl

CFG = {
    "docs_dir": "docs",
    "extra": {
        "backlinks": {
            "enabled": True,
            "include": ["notes/**"],
            "exclude": ["notes/posts/**", "moments/**", "notes/_index_content.md"],
            "max_backlinks": 20,
            "graph": {
                "enabled": True,
                "depth": 1,
                "layout": "lr",
                "max_nodes": 60,
                "global_page": "notes/link-graph.md",
            },
        }
    },
}


def _file(src_uri: str, tmp_path):
    return File(src_uri, str(tmp_path), "site", use_directory_urls=True)


# --- config loading ---


def test_load_config_mutable_mapping_config():
    """Real MkDocs config is a UserDict (MutableMapping, not a dict) — custom
    `extra.backlinks` values must flow through (regression: previously the
    `isinstance(config, dict)` guard silently fell back to defaults)."""
    config = UserDict({"extra": {"backlinks": {"max_backlinks": "all"}}})
    cfg = bl._load_config(config)
    assert cfg["max_backlinks"] == "all"


def test_load_config_mutable_mapping_overrides():
    config = UserDict(
        {
            "extra": {
                "backlinks": {
                    "enabled": False,
                    "include": ["docs/**"],
                    "exclude": ["x/**"],
                    "graph": {"enabled": False, "depth": 3},
                }
            }
        }
    )
    cfg = bl._load_config(config)
    assert cfg["enabled"] is False
    assert cfg["include"] == ["docs/**"]
    assert cfg["exclude"] == ["x/**"]
    assert cfg["graph"]["enabled"] is False
    assert cfg["graph"]["depth"] == 3
    # untouched defaults still apply
    assert cfg["graph"]["layout"] == "lr"
    assert cfg["graph"]["max_nodes"] == 50


def test_load_config_defaults_when_no_extra():
    cfg = bl._load_config(UserDict({"extra": {}}))
    assert cfg["max_backlinks"] == 20
    assert cfg["enabled"] is True
    assert cfg["graph"]["global_page"] == "notes/link-graph.md"


def test_load_config_nested_nulls_and_depth_clamp():
    """Nested `graph: {depth: null}` must fall back to defaults (not crash), and
    `depth: 0` falls back to the default."""
    cfg = bl._load_config(UserDict({"extra": {"backlinks": {"graph": {"depth": None}}}}))
    assert cfg["graph"]["depth"] == 5  # default restored, no TypeError
    cfg = bl._load_config(UserDict({"extra": {"backlinks": {"graph": {"depth": 0}}}}))
    assert cfg["graph"]["depth"] == 5  # 0 is invalid -> default


# --- resolution ---


def test_resolve_relative_md():
    assert (
        bl._resolve_target("notes/collection/index.md", "./database.md")
        == "notes/collection/database.md"
    )


def test_resolve_parent_dir():
    assert (
        bl._resolve_target("notes/research/index.md", "../collection/database.md")
        == "notes/collection/database.md"
    )


def test_resolve_trailing_slash_to_index():
    assert (
        bl._resolve_target("notes/collection/index.md", "../research/") == "notes/research/index.md"
    )


def test_resolve_strips_fragment_and_query():
    assert bl._resolve_target("notes/a/b.md", "c.md#section") == "notes/a/c.md"
    assert bl._resolve_target("notes/a/b.md", "c.md?highlight=x") == "notes/a/c.md"


def test_resolve_skips_non_internal():
    for bad in (
        "https://example.com/x",
        "http://x/",
        "mailto:a@b.c",
        "/notes/",
        "#anchor",
        "data:image/png",
    ):
        assert bl._resolve_target("notes/a.md", bad) is None, bad


def test_resolve_skips_non_markdown():
    assert bl._resolve_target("notes/a.md", "external/x.js") is None
    # trailing-slash dir normalizes to index.md (resolved relative to the page)
    assert (
        bl._resolve_target("notes/a.md", "packages/core/src/types/")
        == "notes/packages/core/src/types/index.md"
    )


# --- extraction ---


def test_scan_page_edges_and_skips(tmp_path):
    docs = tmp_path / "docs"
    (docs / "notes").mkdir(parents=True)
    (docs / "notes" / "a.md").write_text(
        "text [B](./b.md) [ext](https://example.com) ![img](./img.png)\n"
        "```\n[Fake](./b.md)\n```\n`[code link](./b.md)`\n",
        encoding="utf-8",
    )
    (docs / "notes" / "b.md").write_text("body", encoding="utf-8")
    pages = {"notes/a.md": {}, "notes/b.md": {}}
    # image, external, fenced and code-spanned links are all skipped
    assert list(bl._scan_page(docs, "notes/a.md", pages)) == [("notes/a.md", "notes/b.md")]


def test_scan_page_expands_includes(tmp_path):
    docs = tmp_path / "docs"
    (docs / "notes").mkdir(parents=True)
    (docs / "notes" / "part.md").write_text("[B](./b.md)", encoding="utf-8")
    (docs / "notes" / "a.md").write_text("<!-- include: notes/part.md -->", encoding="utf-8")
    (docs / "notes" / "b.md").write_text("body", encoding="utf-8")
    pages = {"notes/a.md": {}, "notes/b.md": {}}
    assert list(bl._scan_page(docs, "notes/a.md", pages)) == [("notes/a.md", "notes/b.md")]


def test_scan_page_ignores_self_links(tmp_path):
    docs = tmp_path / "docs"
    (docs / "notes").mkdir(parents=True)
    (docs / "notes" / "a.md").write_text("[self](./a.md) [other](./b.md)", encoding="utf-8")
    (docs / "notes" / "b.md").write_text("body", encoding="utf-8")
    pages = {"notes/a.md": {}, "notes/b.md": {}}
    assert list(bl._scan_page(docs, "notes/a.md", pages)) == [("notes/a.md", "notes/b.md")]


# --- index building ---


def test_build_index_map_and_edges(tmp_path):
    docs = tmp_path / "docs"
    (docs / "notes" / "collection").mkdir(parents=True)
    (docs / "notes" / "research").mkdir(parents=True)
    (docs / "notes" / "collection" / "index.md").write_text(
        "---\ntitle: Collection\n---\n[Database](./database.md) [Research](../research/index.md)",
        encoding="utf-8",
    )
    (docs / "notes" / "collection" / "database.md").write_text(
        "---\ntitle: Database\n---\nbody", encoding="utf-8"
    )
    (docs / "notes" / "research" / "index.md").write_text(
        "---\ntitle: Research\n---\n[DB](../collection/database.md)", encoding="utf-8"
    )

    files = Files(
        [
            _file("notes/collection/index.md", tmp_path),
            _file("notes/collection/database.md", tmp_path),
            _file("notes/research/index.md", tmp_path),
        ]
    )
    pages, edges, backlinks = bl._build_index(files, docs, bl._load_config(CFG))
    assert set(pages) == {
        "notes/collection/index.md",
        "notes/collection/database.md",
        "notes/research/index.md",
    }
    assert pages["notes/collection/database.md"]["title"] == "Database"
    assert pages["notes/collection/database.md"]["section"] == "collection"
    assert edges == {
        ("notes/collection/index.md", "notes/collection/database.md"),
        ("notes/collection/index.md", "notes/research/index.md"),
        ("notes/research/index.md", "notes/collection/database.md"),
    }
    assert set(backlinks["notes/collection/database.md"]) == {
        "notes/collection/index.md",
        "notes/research/index.md",
    }


def test_build_index_applies_excludes(tmp_path):
    docs = tmp_path / "docs"
    (docs / "notes").mkdir(parents=True)
    (docs / "notes" / "ok.md").write_text("body", encoding="utf-8")
    (docs / "notes" / "_index_content.md").write_text("body", encoding="utf-8")
    (docs / "notes" / "posts").mkdir()
    (docs / "notes" / "posts" / "p.md").write_text("body", encoding="utf-8")

    files = Files(
        [
            _file("notes/ok.md", tmp_path),
            _file("notes/_index_content.md", tmp_path),
            _file("notes/posts/p.md", tmp_path),
        ]
    )
    pages, edges, _ = bl._build_index(files, docs, bl._load_config(CFG))
    assert set(pages) == {"notes/ok.md"}
    assert edges == set()


# --- injection ---


def _fake_page(src_uri: str):
    return SimpleNamespace(file=SimpleNamespace(src_uri=src_uri))


def test_nav_titles_section_index_rule():
    """With navigation.indexes, a section's first bare .md child inherits the
    section title (nav > frontmatter > stem resolution)."""
    config = {
        "nav": [
            "index.md",
            {"Notes": ["notes/index.md", {"Collection": ["notes/collection/index.md"]}]},
            {"Research": "notes/research/index.md"},
        ]
    }
    titles = bl._nav_titles(config)
    assert titles["notes/collection/index.md"] == "Collection"
    assert titles["notes/research/index.md"] == "Research"
    assert titles["index.md"] == "index"


def test_neighborhood_depth_and_cap(monkeypatch):
    # chain a -> b -> c (no file IO; drive _EDGES directly)
    monkeypatch.setattr(bl, "_EDGES", {("a", "b"), ("b", "c")})
    assert bl._neighborhood("a", depth=1, max_nodes=10) == {"a", "b"}
    assert bl._neighborhood("a", depth=2, max_nodes=10) == {"a", "b", "c"}
    # max_nodes caps growth
    assert bl._neighborhood("a", depth=2, max_nodes=2) == {"a", "b"}


def test_link_list_overflow(monkeypatch):
    monkeypatch.setattr(
        bl,
        "_PAGES",
        {
            "a.md": {"title": "A", "url": "a/", "section": "s"},
            "b.md": {"title": "B", "url": "b/", "section": "s"},
            "c.md": {"title": "C", "url": "c/", "section": "s"},
        },
    )
    out = bl._link_list("a.md", ["b.md", "c.md"], cap=1)
    assert "[B]" in out and "[C]" not in out
    assert "… and 1 more" in out
    # 'all' means no cap
    out = bl._link_list("a.md", ["b.md", "c.md"], cap="all")
    assert "[B]" in out and "[C]" in out and "more" not in out


def test_ml_escape():
    assert bl._ml_escape('a"b\\c') == 'a\\"b\\\\c'
    assert bl._ml_escape("plain 中文") == "plain 中文"
    # newlines must not break the mermaid block
    assert bl._ml_escape("a\nb\rc") == "a b c"


def test_mermaid_click_url():
    # pretty URLs (trailing slash) stay relative from the base dir
    assert bl._mermaid_click_url("notes/", "notes/collection/") == "collection/"
    assert bl._mermaid_click_url("notes/collection/database/", "notes/collection/ai/") == "../ai/"
    # non-pretty base (use_directory_urls=False) -> dirname + "/"
    assert bl._mermaid_click_url("notes/a", "notes/b") == "b"
    assert bl._mermaid_click_url("notes/a", "notes/collection/database/") == "collection/database/"
    # root-level pages: targets are already root-relative (no CWD-anchored path)
    assert bl._mermaid_click_url("/", "notes/collection/") == "notes/collection/"
    assert bl._mermaid_click_url("index.html", "notes/") == "notes/"


def test_rel_src():
    # source .md paths, resolved relative to the current page's directory
    assert bl._rel_src(
        "notes/tools/med-tracker.md", "notes/tools/coffee-flavor-wheel.md"
    ) == "coffee-flavor-wheel.md"
    # parent directory index from a leaf page
    assert bl._rel_src("notes/tools/med-tracker.md", "notes/tools/index.md") == "index.md"
    # cross-section link
    assert bl._rel_src(
        "notes/tools/med-tracker.md", "notes/collection/database.md"
    ) == "../collection/database.md"
    # from a section index page
    assert bl._rel_src(
        "notes/tools/index.md", "notes/collection/database.md"
    ) == "../collection/database.md"


def test_load_config_invalid_depth_falls_back(caplog):
    cfg = bl._load_config(UserDict({"extra": {"backlinks": {"graph": {"depth": "abc"}}}}))
    assert cfg["graph"]["depth"] == 5  # default restored, build does not crash
    assert "Invalid backlinks graph.depth" in caplog.text


def test_load_config_invalid_options_fall_back(caplog):
    cfg = bl._load_config(
        UserDict(
            {
                "extra": {
                    "backlinks": {
                        "max_backlinks": "abc",
                        "graph": {"max_nodes": 0, "layout": 123, "global_layout": ""},
                    }
                }
            }
        )
    )
    assert cfg["max_backlinks"] == 20
    assert cfg["graph"]["max_nodes"] == 50
    assert cfg["graph"]["layout"] == "lr"
    assert cfg["graph"]["global_layout"] == "lr"
    assert "max_backlinks" in caplog.text and "graph.max_nodes" in caplog.text


def test_load_config_non_mapping_falls_back(caplog):
    cfg = bl._load_config(UserDict({"extra": {"backlinks": True}}))
    assert cfg["enabled"] is True
    assert cfg["max_backlinks"] == 20
    assert "Invalid backlinks config" in caplog.text


def test_load_config_nested_graph_non_mapping_falls_back(caplog):
    for bad in ("oops", [1, 2], 123):
        cfg = bl._load_config(UserDict({"extra": {"backlinks": {"graph": bad}}}))
        assert cfg["graph"]["depth"] == 5  # defaults restored, no AttributeError
    assert "Invalid backlinks graph config" in caplog.text


def test_load_config_misc_option_robustness(caplog):
    # bool-as-int rejected, string layout stripped, non-bool enabled rejected
    cfg = bl._load_config(
        UserDict(
            {
                "extra": {
                    "backlinks": {
                        "enabled": "no",
                        "max_backlinks": True,
                        "graph": {"depth": True, "max_nodes": 2.5, "layout": "lr "},
                    }
                }
            }
        )
    )
    assert cfg["enabled"] is True  # string "no" invalid -> default True
    assert cfg["max_backlinks"] == 20  # bool rejected -> default
    assert cfg["graph"]["depth"] == 5  # bool rejected -> default
    assert cfg["graph"]["max_nodes"] == 50  # non-integral float rejected -> default
    assert cfg["graph"]["layout"] == "lr"  # stripped


def test_on_page_markdown_injects_backlinks(tmp_path):
    docs = tmp_path / "docs"
    (docs / "notes").mkdir(parents=True)
    (docs / "notes" / "a.md").write_text("[B](./b.md)", encoding="utf-8")
    (docs / "notes" / "b.md").write_text("---\ntitle: B\n---\nbody", encoding="utf-8")
    files = [_file("notes/a.md", tmp_path), _file("notes/b.md", tmp_path)]
    bl.on_files(Files(files), {**CFG, "docs_dir": str(docs)})

    out = bl.on_page_markdown("body", _fake_page("notes/b.md"), {**CFG, "docs_dir": str(docs)})
    assert '??? info "Backlinks (1)"' in out  # collapsible admonition, count in title
    assert "../a/" in out  # relative URL to the linking page (notes/b/ -> notes/a/)
    assert "mermaid" in out and "flowchart LR" in out  # neighborhood graph in the card
    assert out.startswith("body")


def test_on_page_markdown_injects_both_cards(tmp_path):
    docs = tmp_path / "docs"
    (docs / "notes").mkdir(parents=True)
    (docs / "notes" / "a.md").write_text("[B](./b.md)", encoding="utf-8")
    (docs / "notes" / "b.md").write_text("---\ntitle: B\n---\n[C](./c.md)", encoding="utf-8")
    (docs / "notes" / "c.md").write_text("body", encoding="utf-8")
    files = [
        _file("notes/a.md", tmp_path),
        _file("notes/b.md", tmp_path),
        _file("notes/c.md", tmp_path),
    ]
    bl.on_files(Files(files), {**CFG, "docs_dir": str(docs)})

    out = bl.on_page_markdown("body", _fake_page("notes/b.md"), {**CFG, "docs_dir": str(docs)})
    assert '??? info "Backlinks (1)"' in out  # incoming card
    assert '??? info "Links (1)"' in out  # outgoing card
    assert "c/" in out


def test_on_page_markdown_injects_forward_links(tmp_path):
    docs = tmp_path / "docs"
    (docs / "notes").mkdir(parents=True)
    (docs / "notes" / "a.md").write_text(
        "---\ntitle: A\n---\n[B](./b.md) [C](./c.md)", encoding="utf-8"
    )
    (docs / "notes" / "b.md").write_text("body", encoding="utf-8")
    (docs / "notes" / "c.md").write_text("body", encoding="utf-8")
    files = [
        _file("notes/a.md", tmp_path),
        _file("notes/b.md", tmp_path),
        _file("notes/c.md", tmp_path),
    ]
    bl.on_files(Files(files), {**CFG, "docs_dir": str(docs)})

    out = bl.on_page_markdown("body", _fake_page("notes/a.md"), {**CFG, "docs_dir": str(docs)})
    assert '??? info "Links (2)"' in out  # forward (outgoing) links card, collapsed
    assert "b/" in out and "c/" in out
    assert "mermaid" in out and "flowchart LR" in out  # neighborhood graph folded into card
    assert "Backlinks" not in out  # nothing links to a.md


def test_on_page_markdown_no_backlinks_unchanged(tmp_path):
    docs = tmp_path / "docs"
    (docs / "notes").mkdir(parents=True)
    (docs / "notes" / "a.md").write_text("no links", encoding="utf-8")
    files = [_file("notes/a.md", tmp_path)]
    bl.on_files(Files(files), {**CFG, "docs_dir": str(docs)})
    assert (
        bl.on_page_markdown("body", _fake_page("notes/a.md"), {**CFG, "docs_dir": str(docs)})
        == "body"
    )


def test_on_page_markdown_global_page_override(tmp_path):
    docs = tmp_path / "docs"
    (docs / "notes").mkdir(parents=True)
    (docs / "notes" / "a.md").write_text("[B](./b.md)", encoding="utf-8")
    (docs / "notes" / "b.md").write_text("body", encoding="utf-8")
    (docs / "notes" / "link-graph.md").write_text("placeholder", encoding="utf-8")
    files = [
        _file("notes/a.md", tmp_path),
        _file("notes/b.md", tmp_path),
        _file("notes/link-graph.md", tmp_path),
    ]
    bl.on_files(Files(files), {**CFG, "docs_dir": str(docs)})

    out = bl.on_page_markdown(
        "placeholder", _fake_page("notes/link-graph.md"), {**CFG, "docs_dir": str(docs)}
    )
    assert "mermaid" in out
    assert "flowchart LR" in out
    assert "direction LR" in out  # subgraphs LR -> portrait, avoids width-shrink
    assert 'subgraph s0["' in out  # section clusters rendered
    assert "click " in out


def test_graph_disabled_backlinks_only(tmp_path):
    """graph.enabled=false: backlinks card renders without the mermaid graph, and the
    global page falls through to normal injection (no topology page)."""
    docs = tmp_path / "docs"
    (docs / "notes").mkdir(parents=True)
    (docs / "notes" / "a.md").write_text("[B](./b.md)", encoding="utf-8")
    (docs / "notes" / "b.md").write_text("---\ntitle: B\n---\nbody", encoding="utf-8")
    (docs / "notes" / "link-graph.md").write_text("placeholder", encoding="utf-8")
    files = [
        _file("notes/a.md", tmp_path),
        _file("notes/b.md", tmp_path),
        _file("notes/link-graph.md", tmp_path),
    ]
    cfg = {
        **CFG,
        "docs_dir": str(docs),
        "extra": {
            "backlinks": {
                **CFG["extra"]["backlinks"],
                "graph": {**CFG["extra"]["backlinks"]["graph"], "enabled": False},
            }
        },
    }
    bl.on_files(Files(files), cfg)

    # backlinks card without the neighborhood graph
    out = bl.on_page_markdown("body", _fake_page("notes/b.md"), cfg)
    assert '??? info "Backlinks (1)"' in out
    assert "mermaid" not in out
    # global page with graph disabled: no topology override, stub page unchanged
    out = bl.on_page_markdown("placeholder", _fake_page("notes/link-graph.md"), cfg)
    assert out == "placeholder"
    assert "Overview of all pages" not in out


def test_max_backlinks_all_shows_everything(tmp_path):
    docs = tmp_path / "docs"
    (docs / "notes").mkdir(parents=True)
    (docs / "notes" / "a.md").write_text(
        "---\ntitle: A\n---\n[B](./b.md) [C](./c.md)", encoding="utf-8"
    )
    (docs / "notes" / "b.md").write_text("body", encoding="utf-8")
    (docs / "notes" / "c.md").write_text("body", encoding="utf-8")
    cfg = {
        "docs_dir": str(docs),
        "extra": {"backlinks": {"max_backlinks": "all", "graph": {"enabled": False}}},
    }
    files = [
        _file("notes/a.md", tmp_path),
        _file("notes/b.md", tmp_path),
        _file("notes/c.md", tmp_path),
    ]
    bl.on_files(Files(files), {**cfg, "docs_dir": str(docs)})

    out = bl.on_page_markdown("body", _fake_page("notes/b.md"), {**cfg, "docs_dir": str(docs)})
    assert '??? info "Backlinks (1)"' in out
    assert "[A]" in out
    assert "more" not in out  # 'all' cap -> no overflow line


def test_excluded_page_unchanged(tmp_path):
    docs = tmp_path / "docs"
    (docs / "notes").mkdir(parents=True)
    (docs / "notes" / "a.md").write_text("body", encoding="utf-8")
    cfg = {"docs_dir": str(docs), "extra": {"backlinks": {"include": ["other/**"]}}}
    files = [_file("notes/a.md", tmp_path)]  # not in scope
    bl.on_files(Files(files), {**cfg, "docs_dir": str(docs)})

    assert (
        bl.on_page_markdown("body", _fake_page("notes/a.md"), {**cfg, "docs_dir": str(docs)})
        == "body"
    )


def test_nav_title_beats_frontmatter(tmp_path):
    docs = tmp_path / "docs"
    (docs / "notes").mkdir(parents=True)
    (docs / "notes" / "a.md").write_text(
        "---\ntitle: From Frontmatter\n---\nbody", encoding="utf-8"
    )
    files = [_file("notes/a.md", tmp_path)]
    pages, _, _ = bl._build_index(
        Files(files), docs, bl._load_config(CFG), nav_titles={"notes/a.md": "From Nav"}
    )
    assert pages["notes/a.md"]["title"] == "From Nav"


def test_disabled_config_noop(tmp_path):
    docs = tmp_path / "docs"
    (docs / "notes").mkdir(parents=True)
    (docs / "notes" / "a.md").write_text("[B](./b.md)", encoding="utf-8")
    (docs / "notes" / "b.md").write_text("body", encoding="utf-8")
    cfg = {
        "docs_dir": str(docs),
        "extra": {
            "backlinks": {
                "enabled": False,
                "include": [],
                "exclude": [],
                "graph": {"enabled": False},
            }
        },
    }
    files = [_file("notes/a.md", tmp_path), _file("notes/b.md", tmp_path)]
    bl.on_files(Files(files), cfg)
    assert bl.on_page_markdown("body", _fake_page("notes/b.md"), cfg) == "body"
