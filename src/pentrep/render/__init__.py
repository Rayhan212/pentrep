"""Report rendering (HTML and Markdown; PDF from M6). Imported lazily by the CLI."""

from __future__ import annotations

from pathlib import Path

import jinja2
from markupsafe import Markup

from pentrep.render.highlight import highlight
from pentrep.render.markdown import render_markdown, render_markdown_inline

THEME_PACKAGE_PATH = "themes/classic"


def _markdown_inline_filter(text: str) -> Markup:
    """Jinja filter: one line of user Markdown (no paragraph wrapper) → safe HTML."""
    return Markup(render_markdown_inline(text))  # noqa: S704 - markdown-it escapes raw HTML


def _highlight_filter(content: str, language: str | None) -> Markup:
    """Jinja filter: evidence text → Pygments HTML with inline styles (content escaped)."""
    return Markup(highlight(content, language))  # noqa: S704 - Pygments escapes the content


def _markdown_filter(text: str) -> Markup:
    """Jinja filter: user Markdown → safe HTML (raw HTML is escaped by the renderer)."""
    return Markup(render_markdown(text))  # noqa: S704 - markdown-it escapes raw HTML (html=False)


def make_environment(template_dir: Path | None) -> jinja2.Environment:
    """A Jinja environment that searches ``template_dir`` first, then the built-in theme (FR-48).

    HTML templates (``*.html.j2``) are autoescaped and undefined variables raise. Values from
    findings.yaml are only ever passed as data, never compiled as templates (FR-13).
    """
    loaders: list[jinja2.BaseLoader] = []
    if template_dir is not None:
        if not template_dir.is_dir():
            raise NotADirectoryError(f"template directory not found: {template_dir}")
        loaders.append(jinja2.FileSystemLoader(template_dir))
    loaders.append(jinja2.PackageLoader("pentrep", THEME_PACKAGE_PATH))
    env = jinja2.Environment(
        loader=jinja2.ChoiceLoader(loaders),
        autoescape=jinja2.select_autoescape(enabled_extensions=("html", "html.j2")),
        undefined=jinja2.StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
        keep_trailing_newline=True,
    )
    env.filters["markdown"] = _markdown_filter
    env.filters["markdown_inline"] = _markdown_inline_filter
    env.filters["highlight"] = _highlight_filter
    return env
