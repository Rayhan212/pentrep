"""Self-contained, script-free HTML output (FR-45)."""

from __future__ import annotations

import itertools
import re
import shutil
from html.parser import HTMLParser
from pathlib import Path

import pytest

from pentrep.loader import load_report
from pentrep.redact import redact_report
from pentrep.render.html import render_html

FIXTURES = Path(__file__).parent.parent / "fixtures" / "valid"
SVG_LOGO = (
    b'<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10">'
    b'<rect width="10" height="10"/></svg>\n'
)


class _Collector(HTMLParser):
    """Collect tags, attributes and heading levels."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.tags: list[tuple[str, dict[str, str | None]]] = []
        self.headings: list[int] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.tags.append((tag, dict(attrs)))
        if re.fullmatch(r"h[1-6]", tag):
            self.headings.append(int(tag[1]))


def _render(path: Path) -> str:
    result = load_report(path)
    assert result.report is not None, result.diagnostics
    report, summary = redact_report(result.report)
    return render_html(report, summary, path.parent)


@pytest.fixture(params=["full.yaml", "minimal.yaml"])
def html(request: pytest.FixtureRequest) -> str:
    return _render(FIXTURES / request.param)


def _parse(html: str) -> _Collector:
    collector = _Collector()
    collector.feed(html)
    return collector


def test_no_script_elements_or_event_handlers(html: str) -> None:
    tags = _parse(html).tags
    assert all(tag != "script" for tag, _ in tags)
    assert not [(t, a) for t, attrs in tags for a in attrs if a.lower().startswith("on")]
    assert "javascript:" not in html.lower()


def test_html_lang_and_charset(html: str) -> None:
    assert html.startswith('<!DOCTYPE html>\n<html lang="en">')
    assert '<meta charset="utf-8">' in html


def test_css_is_inlined_without_external_stylesheets(html: str) -> None:
    tags = _parse(html).tags
    assert not [a for t, a in tags if t == "link"]
    assert "<style>" in html
    assert ".badge-critical" in html


def test_no_external_resources(html: str) -> None:
    for tag, attrs in _parse(html).tags:
        src = attrs.get("src")
        if src is not None:
            assert src.startswith("data:"), (tag, src[:40])
        if "href" in attrs:
            assert tag == "a", tag  # external URLs are allowed only in links
    assert not re.findall(r"url\((?!\s*['\"]?data:)", html)
    assert "@import" not in html


def test_headings_start_at_h1_and_never_skip_a_level(html: str) -> None:
    levels = _parse(html).headings
    assert levels[0] == 1
    assert levels.count(1) == 1
    for previous, current in itertools.pairwise(levels):
        assert current <= previous + 1, levels


def test_images_are_data_uris_with_captions_as_alt() -> None:
    html = _render(FIXTURES / "full.yaml")
    images = [attrs for tag, attrs in _parse(html).tags if tag == "img"]
    assert len(images) == 2  # logo + one image evidence
    assert all((a["src"] or "").startswith("data:image/png;base64,") for a in images)
    assert {a["alt"] for a in images} == {
        "Example Security Labs logo",
        "sqlmap enumerating database tables",
    }


def test_svg_logo_is_embedded_as_svg_data_uri(tmp_path: Path) -> None:
    shutil.copytree(FIXTURES, tmp_path / "p")
    (tmp_path / "p" / "assets" / "logo.svg").write_bytes(SVG_LOGO)
    path = tmp_path / "p" / "full.yaml"
    path.write_text(path.read_text("utf-8").replace("assets/logo.png", "assets/logo.svg"), "utf-8")
    assert 'src="data:image/svg+xml;base64,' in _render(path)


def test_output_is_deterministic() -> None:
    assert _render(FIXTURES / "full.yaml") == _render(FIXTURES / "full.yaml")
