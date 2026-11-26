"""GitHub-Flavored Markdown report (FR-47).

Templates are not autoescaped (Markdown is not HTML), so every value goes through a filter:
``md_inline`` for plain text, ``md_block`` for user Markdown, ``md_cell`` for table cells.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from pentrep.models import Report
from pentrep.redact import RedactionSummary
from pentrep.render import make_environment
from pentrep.render.context import build_context

TEMPLATE: Final = "report.md.j2"
ASSETS_DIR: Final = "assets"
_FENCE_LINE: Final = re.compile(r"^ {0,3}(`{3,}|~{3,})")
_ATX_HEADING: Final = re.compile(r"^ {0,3}#{1,6}(?:[ \t]+(.*?))?(?:[ \t]+#+)?[ \t]*$")
_SETEXT_UNDERLINE: Final = re.compile(r"^ {0,3}(?:=+|-+)[ \t]*$")
_INLINE_SPECIAL: Final = re.compile(r"([\\`*_\[\]<>|#])")
_DANGEROUS_SCHEME: Final = r"(?:javascript|vbscript|data|file):"
_INLINE_LINK: Final = re.compile(rf"\]\((\s*<?\s*)(?={_DANGEROUS_SCHEME})", re.IGNORECASE)
_LINK_DEFINITION: Final = re.compile(rf"^( {{0,3}})(\[[^\]]+\]:\s*<?\s*{_DANGEROUS_SCHEME})", re.I)


def _neutralise(segment: str) -> str:
    """Outside code: escape raw HTML and break links to dangerous schemes (shown as text)."""
    return _INLINE_LINK.sub(r"\\](\1", segment.replace("<", "&lt;"))


@dataclass(frozen=True)
class MarkdownReport:
    """The Markdown text and the images to copy: ``(source file, path relative to output)``."""

    text: str
    assets: list[tuple[Path, str]]


def slug(heading: str) -> str:
    """GitHub's heading anchor: lower case, punctuation removed, spaces become hyphens."""
    return re.sub(r"[^\w\- ]", "", heading.strip().lower()).replace(" ", "-")


def fence(content: str) -> str:
    """A backtick fence longer than any backtick run in ``content`` (at least three)."""
    longest = max((len(run) for run in re.findall(r"`+", content)), default=0)
    return "`" * max(3, longest + 1)


def _escape_inline_code_aware(line: str) -> str:
    """Escape ``<`` outside code spans (a code span ends at a backtick run of equal length)."""
    out: list[str] = []
    position = 0
    while position < len(line):
        tick = re.compile(r"`+").search(line, position)
        if tick is None:
            out.append(_neutralise(line[position:]))
            break
        out.append(_neutralise(line[position : tick.start()]))
        closing = re.compile(rf"(?<!`){tick.group()}(?!`)").search(line, tick.end())
        if closing is None:
            out.append(tick.group())
            position = tick.end()
            continue
        out.append(line[tick.start() : closing.end()])
        position = closing.end()
    return "".join(out)


def escape_html_outside_code(text: str) -> str:
    """Escape raw HTML and neutralise javascript:/data:/vbscript:/file: links in user Markdown
    (FR-13), keeping code spans and fenced blocks verbatim."""
    out: list[str] = []
    open_fence: str | None = None
    for line in text.split("\n"):
        match = _FENCE_LINE.match(line)
        if open_fence is not None:
            out.append(line)
            if (
                match
                and match.group(1)[0] == open_fence[0]
                and len(match.group(1)) >= len(open_fence)
            ):
                open_fence = None
        elif match:
            open_fence = match.group(1)
            out.append(line)
        else:
            out.append(_escape_inline_code_aware(_LINK_DEFINITION.sub(r"\1\\\2", line)))
    return "\n".join(out)


def _demote_headings(text: str) -> str:
    """Turn headings in user Markdown into bold lines, so the report keeps one ``#`` title."""
    lines = text.split("\n")
    out: list[str] = []
    open_fence: str | None = None
    for line in lines:
        match = _FENCE_LINE.match(line)
        if open_fence is not None or match:
            if open_fence is None and match:
                open_fence = match.group(1)
            elif match and match.group(1)[0] == (open_fence or " ")[0]:
                open_fence = None
            out.append(line)
            continue
        heading = _ATX_HEADING.match(line)
        if heading:
            out.append(f"**{(heading.group(1) or '').strip()}**")
        elif _SETEXT_UNDERLINE.match(line) and out and out[-1].strip() and "=" in line:
            out[-1] = f"**{out[-1].strip()}**"
        else:
            out.append(line)
    return "\n".join(out)


def md_block(text: str) -> str:
    """Filter: user Markdown, with raw HTML escaped and headings demoted."""
    return escape_html_outside_code(_demote_headings(text.strip()))


def md_inline(text: str) -> str:
    """Filter: plain text shown literally in Markdown (titles, names, captions)."""
    return _INLINE_SPECIAL.sub(r"\\\1", " ".join(str(text).split()))


def md_cell(text: str) -> str:
    """Filter: plain text inside a GFM table cell."""
    return md_inline(text)


def md_url(url: str) -> str:
    """Filter: a URL for an autolink, with characters that could end it percent-encoded."""
    for char, code in (("<", "%3C"), (">", "%3E"), (" ", "%20"), ("`", "%60")):
        url = url.replace(char, code)
    return url


def md_step(text: str) -> str:
    """Filter: a list item of user Markdown on one line."""
    return escape_html_outside_code(" ".join(text.split()))


def render_md(
    report: Report, summary: RedactionSummary, base_dir: Path, template_dir: Path | None = None
) -> MarkdownReport:
    """Render the (already redacted) report as GitHub-Flavored Markdown."""
    env = make_environment(template_dir)
    env.filters.update(
        md_block=md_block,
        md_inline=md_inline,
        md_cell=md_cell,
        md_step=md_step,
        md_url=md_url,
        slug=slug,
        fence=fence,
    )
    context = build_context(report, summary, base_dir)
    assets: list[tuple[Path, str]] = []

    def image_src(path: Path, mime: str, asset_name: str) -> str:
        relative = f"{ASSETS_DIR}/{asset_name}"
        if (path, relative) not in assets:
            assets.append((path, relative))
        return relative

    text = env.get_template(TEMPLATE).render(**context, image_src=image_src)
    return MarkdownReport(text, assets)
