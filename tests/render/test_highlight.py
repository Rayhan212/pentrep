"""Evidence highlighting keeps the text verbatim (PRD §4.2.2 "rendered verbatim")."""

from __future__ import annotations

import html
import re

import pytest

from pentrep.render.highlight import highlight

REQUEST = 'POST /login HTTP/1.1\nHost: a.example\nContent-Type: application/json\n\n{"a":1}\n'
RESPONSE = 'HTTP/1.1 200 OK\nContent-Type: application/json\n\n{"ok":true}\n'


def _text(rendered: str) -> str:
    """The text inside the <pre> block, without markup."""
    match = re.search(r"<pre[^>]*>(.*?)</pre>", rendered, flags=re.DOTALL)
    assert match, rendered
    return html.unescape(re.sub(r"<[^>]+>", "", match.group(1)))


@pytest.mark.parametrize(
    ("content", "language"),
    [
        (REQUEST + "\n" + RESPONSE, "http"),
        (REQUEST, "http"),
        ("\n\nleading and trailing blank lines\n\n\n", "http"),
        ("GET / HTTP/1.1\nHost: x\n\n", "http"),
        ("no trailing newline", "bash"),
        ("  indented\n\tand tabbed\n\n", "python"),
        ("<svg/onload=alert(1)>\n", "html"),
        ("plain text\n\n", None),
        ("text in an unknown language", "no-such-language"),
    ],
)
def test_highlighted_text_equals_the_evidence(content: str, language: str | None) -> None:
    rendered = highlight(content, language)
    # Pygments' <pre> holds the text; it may add one trailing newline and nothing else.
    assert _text(rendered).removesuffix("\n") == content.removesuffix("\n")


def test_http_request_and_response_are_both_highlighted() -> None:
    rendered = highlight(REQUEST + "\n" + RESPONSE, "http")
    assert rendered.count('font-weight: bold">HTTP</span>') == 2  # both start lines are lexed


def test_markup_in_evidence_is_escaped() -> None:
    rendered = highlight("<script>alert(1)</script>", "html")
    assert "<script>" not in rendered
