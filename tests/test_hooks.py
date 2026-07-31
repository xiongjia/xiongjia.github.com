"""Integration tests for MkDocs hooks: draft_filter and snippet_include.

mermaid_assets is intentionally not covered here (mock-HTTP cost outweighs
value — see internal/plans/plugins-scripts-shared-module.md).
"""

from types import SimpleNamespace

import plugins.draft_filter as draft_filter
import plugins.snippet_include as snippet_include

# --- snippet_include ---


def _fake_page(src_uri: str):
    return SimpleNamespace(file=SimpleNamespace(src_uri=src_uri))


def test_snippet_include_valid(tmp_path):
    (tmp_path / "part.md").write_text("included content", encoding="utf-8")
    md = "before <!-- include: part.md --> after"
    out = snippet_include.on_page_markdown(md, _fake_page("page.md"), {"docs_dir": str(tmp_path)})
    assert out == "before included content after"


def test_snippet_include_missing(tmp_path):
    md = "a <!-- include: nope.md --> b"
    out = snippet_include.on_page_markdown(md, _fake_page("page.md"), {"docs_dir": str(tmp_path)})
    assert out == md  # marker left untouched


def test_snippet_include_path_traversal(tmp_path):
    """Traversal attempts must be left untouched, not read outside docs_dir."""
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.md").write_text("SECRET", encoding="utf-8")

    for attack in ("../outside/secret.md", "..%2Foutside%2Fsecret.md", "../../etc/passwd"):
        md = f"a <!-- include: {attack} --> b"
        out = snippet_include.on_page_markdown(
            md, _fake_page("page.md"), {"docs_dir": str(tmp_path)}
        )
        assert out == md, f"traversal '{attack}' must not resolve"
    assert "SECRET" not in out


# --- draft_filter ---


def test_draft_filter_has_draft_frontmatter(tmp_path):
    draft = tmp_path / "draft.md"
    draft.write_text("---\ntitle: x\ndraft: true\n---\nbody", encoding="utf-8")
    assert draft_filter._has_draft_frontmatter(str(draft))

    normal = tmp_path / "normal.md"
    normal.write_text("---\ntitle: x\n---\nbody", encoding="utf-8")
    assert not draft_filter._has_draft_frontmatter(str(normal))

    missing = tmp_path / "missing.md"
    assert not draft_filter._has_draft_frontmatter(str(missing))  # unreadable → False


def test_draft_filter_get_blog_dir_default():
    assert draft_filter._get_blog_dir({"plugins": {}}) == "notes/posts"


def test_draft_filter_get_blog_dir_from_config():
    blog = SimpleNamespace(config={"blog_dir": "blog"})
    config = {"plugins": {"blog": blog}}
    assert draft_filter._get_blog_dir(config) == "blog"


def test_draft_filter_on_files_excludes_drafts(tmp_path):
    from mkdocs.structure.files import File, Files

    src_dir = str(tmp_path)
    (tmp_path / "draft.md").write_text("---\ndraft: true\n---\nx", encoding="utf-8")
    (tmp_path / "ok.md").write_text("---\ntitle: ok\n---\nx", encoding="utf-8")

    files = Files(
        [
            File("draft.md", src_dir, "site", use_directory_urls=False),
            File("ok.md", src_dir, "site", use_directory_urls=False),
        ]
    )
    result = draft_filter.on_files(files, {"plugins": {}})
    assert [f.src_path for f in result] == ["ok.md"]
