"""PDF output through WeasyPrint (FR-03, FR-46)."""

from __future__ import annotations

import io
import re
import subprocess
import sys
from pathlib import Path

import pytest
from pypdf import PdfReader

from pentrep.loader import load_report
from pentrep.redact import redact_report
from pentrep.render import pdf
from pentrep.render.html import render_html
from pentrep.render.pdf import RenderError, install_hint, load_weasyprint, render_pdf

FULL = Path(__file__).parent.parent / "fixtures" / "valid" / "full.yaml"


def _html() -> str:
    result = load_report(FULL)
    assert result.report is not None
    report, summary = redact_report(result.report)
    return render_html(report, summary, FULL.parent)


@pytest.mark.parametrize(
    ("platform", "expected"),
    [
        ("linux", "apt install"),
        ("darwin", "brew install pango"),
        ("win32", "Docker"),
    ],
)
def test_install_hint_per_os(platform: str, expected: str) -> None:
    hint = install_hint(platform)
    assert expected in hint
    assert "docker run" in hint  # the Docker alternative is always offered


def test_missing_python_package_raises_render_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "weasyprint", None)  # makes `import weasyprint` fail
    with pytest.raises(RenderError) as exc_info:
        load_weasyprint()
    assert "WeasyPrint" in str(exc_info.value)
    assert "docker run" in exc_info.value.hint


def test_missing_system_library_names_the_library(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail(name: str) -> object:
        raise OSError(
            "cannot load library 'libpango-1.0-0': libpango-1.0-0: cannot open shared object file"
        )

    monkeypatch.setattr(pdf.importlib, "import_module", fail)
    with pytest.raises(RenderError, match=r"libpango-1\.0-0"):
        load_weasyprint()


def test_import_is_lazy() -> None:
    """Importing the wrapper must not import WeasyPrint (keeps --help fast, NFR-04)."""
    code = "import sys, pentrep.render.pdf; print('weasyprint' in sys.modules)"
    result = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, check=True
    )
    assert result.stdout.strip() == "False"


@pytest.mark.pdf
def test_render_pdf_returns_a_pdf() -> None:
    data = render_pdf(_html(), paper="a4")
    assert data.startswith(b"%PDF-")
    assert data.rstrip().endswith(b"%%EOF")


@pytest.mark.pdf
def test_render_pdf_blocks_external_resources() -> None:
    html = _html().replace("</body>", '<img src="https://example.test/x.png"></body>')
    with pytest.raises(RenderError, match="external resource"):
        render_pdf(html, paper="a4")


def _fonts(data: bytes) -> set[str]:
    """Base font names used on any page (subset prefixes like ``ABCDEF+`` removed)."""
    names = set()
    for page in PdfReader(io.BytesIO(data)).pages:
        fonts = page["/Resources"].get("/Font", {})
        for font in fonts.values():
            names.add(str(font.get_object()["/BaseFont"]).split("+", 1)[-1])
    return names


@pytest.mark.pdf
def test_only_bundled_fonts_are_embedded() -> None:
    """Same fonts on every machine (FR-46): no system fonts may be used."""
    fonts = _fonts(render_pdf(_html(), paper="a4"))
    families = ("Source-Sans-3", "Source-Code-Pro")
    assert all(name.startswith(families) for name in fonts), fonts
    assert {f for f in families if any(name.startswith(f) for name in fonts)} == set(families)


# --- Structure (M6.5, PRD §8.2) ------------------------------------------------------------------


def _reader(paper: str = "a4", enabled: bool | None = None) -> PdfReader:
    result = load_report(FULL)
    assert result.report is not None
    report, summary = redact_report(result.report, enabled=enabled)
    return PdfReader(io.BytesIO(render_pdf(render_html(report, summary, FULL.parent), paper=paper)))


@pytest.fixture(scope="module")
def reader() -> PdfReader:
    return _reader()


def _pages(reader: PdfReader) -> list[str]:
    return [page.extract_text() for page in reader.pages]


def _outline_titles(items: list[object]) -> list[str]:
    titles: list[str] = []
    for item in items:
        if isinstance(item, list):
            titles += _outline_titles(item)
        else:
            titles.append(item.title)  # type: ignore[attr-defined]
    return titles


@pytest.mark.pdf
@pytest.mark.parametrize(("paper", "size"), [("a4", (595, 842)), ("letter", (612, 792))])
def test_page_size(paper: str, size: tuple[int, int]) -> None:
    for page in _reader(paper).pages:
        assert (float(page.mediabox.width), float(page.mediabox.height)) == pytest.approx(
            size, abs=1
        )


@pytest.mark.pdf
def test_every_finding_title_appears(reader: PdfReader) -> None:
    text = "\n".join(_pages(reader))
    assert "PT-001: SQL Injection in Login Endpoint" in text
    assert "PT-002: Reflected Cross-Site Scripting in Search" in text


@pytest.mark.pdf
def test_each_finding_starts_a_new_page(reader: PdfReader) -> None:
    for title in ("PT-001: SQL Injection", "PT-002: Reflected Cross-Site"):
        starts = [p for p in _pages(reader) if p.lstrip().startswith(title)]
        assert len(starts) == 1, title


@pytest.mark.pdf
def test_page_x_of_y_footer_and_header_on_every_page_but_the_cover(reader: PdfReader) -> None:
    pages = _pages(reader)
    total = len(pages)
    assert "Page 1 of" not in pages[0]
    for number, text in enumerate(pages[1:], start=2):
        assert f"Page {number} of {total}" in text, number
        assert "CONFIDENTIAL" in text, number


@pytest.mark.pdf
def test_toc_shows_page_numbers(reader: PdfReader) -> None:
    toc = next(p for p in _pages(reader) if "Table of contents" in p)
    assert re.search(r"Executive summary \.{5,}\s+\d+", toc)
    assert re.search(r"PT-001: SQL Injection in Login Endpoint \.{5,}\s+\d+", toc)


@pytest.mark.pdf
def test_bookmarks_for_every_h1_and_h2(reader: PdfReader) -> None:
    titles = _outline_titles(reader.outline)
    for heading in (
        "Web Application Penetration Test \N{EN DASH} Acme Customer Portal",
        "Document control", "Table of contents", "Executive summary", "Scope and methodology",
        "Findings summary", "Detailed findings", "Appendix A: CVSS 3.1 severity scale",
        "Appendix B: Redaction", "PT-001: SQL Injection in Login Endpoint",
    ):  # fmt: skip
        assert heading in titles, heading
    assert "Description" not in titles  # h4 has no bookmark


@pytest.mark.pdf
def test_unredacted_banner_in_every_page_header() -> None:
    pages = _pages(_reader(enabled=False))
    for text in pages[1:]:
        assert "UNREDACTED DRAFT \N{EN DASH} DO NOT DISTRIBUTE" in text


@pytest.mark.pdf
def test_long_evidence_lines_wrap_inside_the_page() -> None:
    """A long line without spaces (JSON, tokens) must wrap instead of running off the page."""
    reader = _reader()
    for number, page in enumerate(reader.pages, 1):
        width = float(page.mediabox.width)
        xs: list[float] = []

        def visit(text: str, cm: list[float], tm: list[float], *_: object) -> None:
            if text.strip():  # page x = text position transformed by the current matrix
                xs.append(cm[0] * tm[4] + cm[2] * tm[5] + cm[4])  # noqa: B023 - per page

        page.extract_text(visitor_text=visit)
        assert all(x < width - 40 for x in xs), (number, max(xs))
