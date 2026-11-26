"""Markdown → HTML for user-written fields (FR-13).

Raw HTML is escaped, links are limited to http, https and mailto, images are not rendered (so no
external ``src`` can appear) and headings become bold paragraphs so they don't break the report's
heading structure (FR-45).
"""

from __future__ import annotations

from collections.abc import Sequence
from functools import cache
from typing import Final

from markdown_it import MarkdownIt
from markdown_it.renderer import RendererHTML
from markdown_it.token import Token
from markdown_it.utils import EnvType, OptionsDict

SAFE_SCHEMES: Final = ("http://", "https://", "mailto:")


def _validate_link(url: str) -> bool:
    return url.strip().lower().startswith(SAFE_SCHEMES)


def _heading_open(
    renderer: RendererHTML, tokens: Sequence[Token], idx: int, options: OptionsDict, env: EnvType
) -> str:
    return '<p class="md-heading"><strong>'


def _heading_close(
    renderer: RendererHTML, tokens: Sequence[Token], idx: int, options: OptionsDict, env: EnvType
) -> str:
    return "</strong></p>\n"


@cache
def _parser() -> MarkdownIt:
    md = MarkdownIt("commonmark", {"html": False, "linkify": False, "typographer": False})
    md.enable(["table", "strikethrough"])
    md.disable("image")
    md.validateLink = _validate_link  # type: ignore[method-assign]  # documented extension point
    md.add_render_rule("heading_open", _heading_open)
    md.add_render_rule("heading_close", _heading_close)
    return md


def render_markdown(text: str) -> str:
    """Render CommonMark + GFM tables/strikethrough to safe HTML."""
    html: str = _parser().render(text)
    return html


def render_markdown_inline(text: str) -> str:
    """Render one line of Markdown without a surrounding paragraph (list items, steps)."""
    html: str = _parser().renderInline(text)
    return html
