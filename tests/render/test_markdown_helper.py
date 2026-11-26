"""Markdown → HTML for user-written fields (FR-13, NFR-10)."""

from __future__ import annotations

import pytest

from pentrep.render.markdown import render_markdown


def test_commonmark_basics() -> None:
    html = render_markdown("Some **bold** and `code`.\n\n```bash\nls -la\n```\n")
    assert "<p>Some <strong>bold</strong> and <code>code</code>.</p>" in html
    assert '<pre><code class="language-bash">ls -la\n</code></pre>' in html


def test_raw_html_is_escaped_not_rendered() -> None:
    html = render_markdown('Hello <script>alert(1)</script> <img src=x onerror="alert(2)">')
    assert "<script>" not in html
    assert "<img" not in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html


def test_html_block_is_escaped() -> None:
    html = render_markdown('<div onclick="x()">\nhi\n</div>\n')
    assert "<div" not in html
    assert "&lt;div" in html


def test_gfm_table() -> None:
    html = render_markdown("| a | b |\n|---|---|\n| 1 | 2 |\n")
    assert "<table>" in html
    assert "<td>1</td>" in html


def test_strikethrough() -> None:
    assert "<s>old</s>" in render_markdown("~~old~~")


@pytest.mark.parametrize(
    "url",
    [
        "javascript:alert(1)",
        "JaVaScRiPt:alert(1)",
        "data:text/html;base64,PHNjcmlwdD4=",
        "vbscript:msgbox(1)",
        "file:///etc/passwd",
    ],
)
def test_dangerous_links_are_neutralised(url: str) -> None:
    html = render_markdown(f"[click]({url}) and <{url}>")
    assert "href" not in html
    assert "click" in html


@pytest.mark.parametrize(
    ("url", "href"),
    [
        ("https://owasp.org/x?a=1&b=2", "https://owasp.org/x?a=1&amp;b=2"),
        ("http://example.test/", "http://example.test/"),
        ("mailto:sec@example.test", "mailto:sec@example.test"),
    ],
)
def test_safe_links_are_kept(url: str, href: str) -> None:
    assert f'<a href="{href}">x</a>' in render_markdown(f"[x]({url})")


def test_images_are_not_rendered_so_no_external_src() -> None:
    html = render_markdown("![tracker](https://evil.test/pixel.png)")
    assert "<img" not in html
    assert "src=" not in html


def test_headings_are_demoted_to_bold_paragraphs() -> None:
    html = render_markdown("# Big\n\n## Smaller\n\nSetext\n===\n")
    assert "<h1" not in html
    assert "<h2" not in html
    assert '<p class="md-heading"><strong>Big</strong></p>' in html
    assert '<p class="md-heading"><strong>Setext</strong></p>' in html


def test_template_syntax_is_rendered_literally() -> None:
    html = render_markdown("{{ 7*7 }} and {% if true %}x{% endif %}")
    assert "{{ 7*7 }}" in html
    assert "{% if true %}" in html


def test_output_is_deterministic() -> None:
    text = "# T\n\n| a |\n|---|\n| [l](https://x.test) |\n"
    assert render_markdown(text) == render_markdown(text)
