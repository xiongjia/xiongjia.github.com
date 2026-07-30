"""Convert MkDocs Markdown articles to WeChat Official Account-compatible HTML.

Usage:
    uv run poe md2wechat <path-to-md-file>
    uv run poe md2wechat                          # interactive selection
    uv run poe md2wechat --preview-only           # print HTML, no clipboard
    uv run poe md2wechat --no-copy                # don't copy to clipboard
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import tempfile
import webbrowser
from pathlib import Path
from typing import Any

import frontmatter  # python-frontmatter
import pyperclip
import yaml
from markdown_it import MarkdownIt
from markdown_it.renderer import RendererHTML
from markdown_it.token import Token
from markdown_it.utils import EnvType, OptionsDict
from mdit_py_plugins.footnote import footnote_plugin

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ADMONITION_EMOJI = {
    "note": "📌",
    "info": "ℹ️",
    "tip": "💡",
    "success": "✅",
    "warning": "⚠️",
    "danger": "🚫",
    "error": "🚫",
    "bug": "🐛",
    "example": "📝",
    "quote": "💬",
    "question": "❓",
    "abstract": "📋",
}

# ---------------------------------------------------------------------------
# Preprocessors (run BEFORE markdown-it-py)
# ---------------------------------------------------------------------------


def _is_admonition_boundary(line: str) -> bool:
    """Check if a line terminates an admonition body."""
    stripped = line.lstrip()
    return (
        stripped == ""
        or stripped.startswith("#")
        or stripped.startswith("!!!")
        or stripped.startswith("???")
    )


def preprocess_admonition(text: str) -> str:
    """Convert MkDocs admonition to emoji + bold title + body text.

    Handles `!!! type "title"`, `!!! type`, `???`, `???+` variants.
    Supports both indented and non-indented body.
    Stops at blank line, heading, or another admonition.
    """
    result_lines = []
    i = 0
    lines = text.splitlines(keepends=True)

    while i < len(lines):
        line = lines[i]
        m = re.match(r'^([ \t]*)(?:!!!|\?\?\?\+?)\s+(\w+)(?:\s+"([^"]*)")?\s*$\n?', line)
        if m:
            type_ = m.group(2).lower()
            title = m.group(3) or type_.capitalize()
            prefix = ADMONITION_EMOJI.get(type_, "📌")

            # Capture body
            i += 1
            body_lines = []
            while i < len(lines) and not _is_admonition_boundary(lines[i]):
                body_lines.append(lines[i])
                i += 1

            body = "".join(body_lines).strip()
            body = re.sub(r"^[ \t]{4}", "", body, flags=re.MULTILINE)

            result_lines.append(
                f'<p style="margin:12px 0;"><strong>{prefix} {title}</strong><br>{body}</p>\n'
            )
        else:
            result_lines.append(line)
            i += 1

    return "".join(result_lines)


def preprocess_tabs(text: str) -> str:
    """Flatten MkDocs tab syntax.

    Removes `=== "TabName"` headers and unindents nested content.
    """
    text = re.sub(r'^=== "[^"]*"\s*$\n?', "", text, flags=re.MULTILINE)
    text = re.sub(r"^ {4}", "", text, flags=re.MULTILINE)
    return text


def preprocess_tasklist(text: str) -> str:
    """Replace tasklist markers with emoji and <br> for line breaks.

    Each item becomes ``✅ text`` or ``⬜ text`` on a separate line.
    """
    text = text.replace("- [x]", "✅")
    text = text.replace("- [X]", "✅")
    text = text.replace("- [ ]", "⬜")
    text = re.sub(r"(✅[^\n]*|⬜[^\n]*)\n(?=(?:✅|⬜))", r"\1<br>", text)
    return text


def preprocess_abbreviation(text: str) -> str:
    """Remove MkDocs abbreviation / definition syntax lines."""
    text = re.sub(r"^\*\[[^\]]+\]:\s*.*$\n?", "", text, flags=re.MULTILINE)
    return text


def preprocess_mkdocs_attrs(text: str) -> str:
    """Remove MkDocs attribute syntax like ``{:target=\"_blank\"}``."""
    return re.sub(r'{:target="[^"]*"}', "", text)


def preprocess(text: str) -> str:
    """Apply all preprocessors in the correct order.

    Admonition must come BEFORE tabs because preprocess_tabs() removes
    leading 4-space indent that admonition relies on for body detection.
    """
    text = preprocess_tasklist(text)
    text = preprocess_admonition(text)
    text = preprocess_tabs(text)
    text = preprocess_mkdocs_attrs(text)
    text = preprocess_abbreviation(text)
    return text


# ---------------------------------------------------------------------------
# Custom markdown-it-py Renderer
# ---------------------------------------------------------------------------


class WeChatRenderer(RendererHTML):
    """Custom renderer producing WeChat-compatible HTML."""

    def __init__(self, parser: MarkdownIt | None = None):
        super().__init__(parser)
        self._warnings: list[str] = []
        self._local_images: list[dict[str, Any]] = []
        self._external_links: list[str] = []
        self._has_mermaid = False
        self._has_drawio = False
        self._source_dir: str = ""

    def renderToken(  # noqa: N802 -- overriding RendererHTML.renderToken (camelCase from upstream)
        self,
        tokens: list[Token],
        idx: int,
        options: OptionsDict,
        env: EnvType,
    ) -> str:
        """Intercept token rendering to collect external links.

        Footnote tokens are handled by custom rules patched in
        ``build_md_engine()``, not here.
        """
        token = tokens[idx]

        if token.type == "link_open":
            href = token.attrs.get("href", "")
            if href.startswith(("http://", "https://")):
                self._external_links.append(href)

        return super().renderToken(tokens, idx, options, env)

    def fence(self, tokens: list[Token], idx: int, options: OptionsDict, env: EnvType) -> str:
        token = tokens[idx]
        info = token.info.strip()
        lang = info.split()[0] if info else ""

        # Mermaid: not renderable in WeChat
        if lang == "mermaid":
            self._has_mermaid = True
            return (
                '<p style="color:#999;font-style:italic;'
                "border:1px dashed #ccc;padding:10px;"
                'background:#fafafa;border-radius:4px;">'
                "📊 [Mermaid] Screenshot and upload</p>\n"
            )

        # WeChat cannot render code blocks cleanly. Show a placeholder
        # and let the author screenshot the original code.
        lang_label = f" [{lang}]" if lang else ""
        return (
            f'<p style="color:#999;font-style:italic;'
            f"border:1px dashed #ccc;padding:8px 12px;"
            f'background:#fafafa;">'
            f"📄 Code block{lang_label} — screenshot and upload"
            f"</p>\n"
        )

    def image(self, tokens: list[Token], idx: int, options: OptionsDict, env: EnvType) -> str:
        token = tokens[idx]
        src = token.attrs.get("src", "")
        alt = token.content or ""
        title = token.attrs.get("title", "")

        is_local = not src.startswith(("http://", "https://"))
        extra = f' title="{title}"' if title else ""

        if is_local:
            abs_path = os.path.normpath(os.path.join(self._source_dir, src))

            if src.endswith(".drawio"):
                self._has_drawio = True
                return (
                    '<p style="color:#999;font-style:italic;'
                    "border:1px dashed #ccc;padding:10px;"
                    'background:#fafafa;border-radius:4px;">'
                    f"📊 [Drawio: {alt}] Screenshot and upload</p>\n"
                )

            size_info = ""
            try:
                from PIL import Image

                img = Image.open(abs_path)
                size_info = f" ({img.width}x{img.height})"
            except Exception:
                pass

            self._local_images.append(
                {
                    "src": src,
                    "abs_path": abs_path,
                    "alt": alt,
                    "size": size_info,
                }
            )

            return (
                f'<p style="color:#999;font-style:italic;'
                f"border:1px dashed #ccc;padding:10px;"
                f'background:#fafafa;border-radius:4px;">'
                f"📷 [{alt}]{size_info}{extra}<br>"
                f"<small>Upload to WeChat media library, then replace src</small>"
                f"</p>\n"
            )

        self._warnings.append(
            f"🌐 Remote image: {src} (may have hotlink protection, upload to media library)"
        )
        return f'<img src="{src}" alt="{alt}"{extra} style="max-width:100%;height:auto;">\n'

    def get_warnings(self) -> list[str]:
        """Aggregate all warnings collected during rendering."""
        result: list[str] = []

        if self._local_images:
            result.append("📷 Upload these images to WeChat media library:")
            for img in self._local_images:
                result.append(f"   {img['src']}{img['size']}")

        if self._external_links:
            result.append("⚠️ External links (not clickable in WeChat):")
            for link in self._external_links:
                result.append(f"   - {link}")

        if self._has_mermaid:
            result.append("📊 Mermaid diagram — screenshot and upload")

        if self._has_drawio:
            result.append("📊 Drawio diagram — screenshot and upload")

        result.append("📝 Footnotes converted to end-of-list, check formatting")
        result.append("💡 Admonition blocks simplified to emoji + text")
        result.append("🔢 Code line numbers removed")

        return result


# ---------------------------------------------------------------------------
# Build markdown-it-py engine
# ---------------------------------------------------------------------------


def build_md_engine() -> MarkdownIt:
    """Create a configured markdown-it-py instance with WeChat renderer.

    Enables tables, strikethrough, and footnotes. Patches footnote render
    rules for WeChat (plain superscript, no backref links).
    """
    md = (
        MarkdownIt("commonmark", renderer_cls=WeChatRenderer)
        .enable("table")
        .enable("strikethrough")
        .use(footnote_plugin)
    )
    md.options["xhtmlOut"] = False

    # Patch footnote rules AFTER plugin registration
    r = md.renderer  # renderer attached to the md instance
    r.rules["footnote_ref"] = lambda tokens, idx, options, env: (
        f'<sup style="color:#448aff;">[{tokens[idx].meta.get("label", idx)}]</sup>'
    )
    r.rules["footnote_block_open"] = lambda tokens, idx, options, env: (
        '<hr style="border:none;border-top:1px solid #eee;'
        'margin:24px 0;">\n'
        '<ol style="font-size:14px;color:#666;padding-left:20px;">\n'
    )
    r.rules["footnote_block_close"] = lambda tokens, idx, options, env: "</ol>\n"
    r.rules["footnote_open"] = lambda tokens, idx, options, env: '<li style="margin:4px 0;">'
    r.rules["footnote_close"] = lambda tokens, idx, options, env: "</li>\n"
    r.rules["footnote_anchor"] = lambda tokens, idx, options, env: ""
    r.rules["footnote_caption"] = lambda tokens, idx, options, env: ""

    return md


# ---------------------------------------------------------------------------
# Core conversion
# ---------------------------------------------------------------------------


def convert_md_to_wechat(md_path: str) -> tuple[str, str, list[str]]:
    """Convert a Markdown file to WeChat-compatible HTML.

    Returns:
        Tuple of (full_html, body_only, warnings).
    """
    md_path = os.path.abspath(md_path)

    with open(md_path, "r", encoding="utf-8") as f:
        post = frontmatter.load(f)

    if post.get("draft", False):
        print(
            f"❌ {md_path} is a draft. Remove `draft: true` from frontmatter first.",
            file=sys.stderr,
        )
        sys.exit(1)

    title = post.get("title", os.path.basename(md_path))
    content = post.content

    # Strip MkDocs excerpt marker
    content = re.sub(r"<!-- more -->\s*", "", content)

    content = preprocess(content)

    md = build_md_engine()
    md.renderer._source_dir = os.path.dirname(md_path)

    html_body = md.render(content)
    warnings = md.renderer.get_warnings()

    html = (
        "<!DOCTYPE html>\n"
        '<html>\n<head>\n<meta charset="utf-8">\n'
        f"<title>{title}</title>\n"
        "</head>\n<body>\n"
        f"{html_body}\n"
        "</body>\n</html>"
    )

    body_only = _clean_for_wechat(html_body)
    return html, body_only, warnings


def _clean_for_wechat(html_body: str) -> str:
    """Clean rendered HTML for WeChat rich-text paste.

    - Remove footnote legacy wrappers
    - Remove redundant <p> wrapping block-level elements
    """
    body = html_body
    body = re.sub(r'<hr class="footnotes-sep">', "", body)
    body = re.sub(r'<section class="footnotes">', "", body)
    body = body.replace("</section>", "")
    body = re.sub(r"<p><(table|h[1-6]|ul|ol|hr)", r"<\1", body)
    body = re.sub(r"</(table|h[1-6]|ul|ol|hr)></p>", r"</\1>", body)
    return body.strip()


# ---------------------------------------------------------------------------
# Clipboard
# ---------------------------------------------------------------------------


def copy_rich_text(html_content: str) -> bool:
    """Copy HTML to clipboard as RTF (rich text).

    Uses macOS textutil + pbcopy. Returns True on success.
    """
    try:
        full_html = (
            "<!DOCTYPE html>\n"
            '<html><head><meta charset="utf-8"></head><body>\n'
            f"{html_content}\n"
            "</body></html>"
        )
        proc = subprocess.run(
            ["textutil", "-format", "html", "-convert", "rtf", "-stdin", "-stdout"],
            input=full_html.encode("utf-8"),
            capture_output=True,
            timeout=15,
        )
        if proc.returncode != 0:
            print(
                f"textutil failed (code {proc.returncode}): {proc.stderr.decode(errors='replace')}",
                file=sys.stderr,
            )
            return False
        subprocess.run(["pbcopy"], input=proc.stdout, timeout=5)
        return True
    except (OSError, subprocess.TimeoutExpired) as exc:
        print(f"copy_rich_text error: {exc}", file=sys.stderr)
        return False


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def find_published_posts() -> list[str]:
    """List published (non-draft) blog posts under docs/notes/posts/."""
    posts_dir = Path("docs/notes/posts/posts")
    if not posts_dir.exists():
        return []

    candidates = sorted(posts_dir.rglob("*.md"))
    published = []
    for p in candidates:
        try:
            post = frontmatter.load(str(p))
            if not post.get("draft", False):
                published.append(str(p))
        except (yaml.YAMLError, KeyError, OSError):
            pass
    return published


def interactive_select() -> str | None:
    """Let user choose a post interactively."""
    posts = find_published_posts()
    if not posts:
        print("No published posts found.", file=sys.stderr)
        return None

    print("Select a published post:")
    for i, path in enumerate(posts, 1):
        try:
            post = frontmatter.load(path)
            title = post.get("title", Path(path).stem)
            print(f"  {i:>3}. {title}")
            print(f"       {path}")
        except (yaml.YAMLError, KeyError, OSError):
            print(f"  {i:>3}. {path}")

    try:
        choice = input("\nEnter number (or file path): ").strip()
    except (EOFError, KeyboardInterrupt):
        print()
        return None

    if not choice:
        return None

    # Try as number
    try:
        idx = int(choice)
        if 1 <= idx <= len(posts):
            return posts[idx - 1]
    except ValueError:
        pass

    # Try as file path
    if os.path.isfile(choice):
        return choice

    print(f"Invalid choice: {choice}", file=sys.stderr)
    return None


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Convert MkDocs Markdown to WeChat Official Account HTML",
    )
    parser.add_argument(
        "path",
        nargs="?",
        default=None,
        help="Path to Markdown file (leave empty for interactive selection)",
    )
    parser.add_argument(
        "--preview-only",
        action="store_true",
        help="Print HTML to stdout, don't copy to clipboard",
    )
    parser.add_argument(
        "--no-copy",
        action="store_true",
        help="Don't copy to clipboard (still prints to stdout)",
    )
    parser.add_argument(
        "--raw",
        action="store_true",
        help="Copy raw HTML instead of rich text",
    )
    parser.add_argument(
        "--open",
        action="store_true",
        help="Open generated HTML in browser",
    )

    args = parser.parse_args()

    md_path = args.path
    if not md_path:
        md_path = interactive_select()
        if not md_path:
            sys.exit(1)

    if not os.path.isfile(md_path):
        print(f"File not found: {md_path}", file=sys.stderr)
        sys.exit(1)

    html, body_only, warnings = convert_md_to_wechat(md_path)

    # Print warnings
    if warnings:
        print("=" * 40, file=sys.stderr)
        for w in warnings:
            print(w, file=sys.stderr)
        print("=" * 40, file=sys.stderr)
        print(file=sys.stderr)

    if args.preview_only:
        print(body_only)
        return

    if not args.no_copy:
        if args.raw:
            try:
                pyperclip.copy(body_only)
                print("✅ HTML source copied to clipboard")
            except pyperclip.PyperclipException as e:
                print(f"⚠️ Clipboard copy failed: {e}", file=sys.stderr)
                print("--- HTML source ---")
                print(body_only)
        else:
            if copy_rich_text(body_only):
                print("✅ Rich text copied. Paste into WeChat editor (Ctrl+V / Cmd+V)")
            else:
                try:
                    pyperclip.copy(body_only)
                    print("⚠️ Rich text failed, HTML source copied instead.")
                except pyperclip.PyperclipException as e:
                    print(f"⚠️ Clipboard copy failed: {e}", file=sys.stderr)
                    print("--- HTML content (copy manually) ---")
                    print(body_only)
    else:
        print("--- WeChat-compatible HTML ---")
        print(body_only)

    if args.open:
        fd, tmp_path = tempfile.mkstemp(suffix=".html", prefix="md2wechat_")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(body_only)
        webbrowser.open(f"file://{tmp_path}")
        print(f"✅ Preview opened in browser: {tmp_path}")


if __name__ == "__main__":
    main()
