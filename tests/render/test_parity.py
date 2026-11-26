"""The same findings, scores and severities appear in HTML, Markdown and PDF (PRD §8.2)."""

from __future__ import annotations

import html as html_lib
import re
import shutil
from pathlib import Path

import pytest
from pypdf import PdfReader
from typer.testing import CliRunner

from pentrep.cli import app

FIXTURES = Path(__file__).parent.parent / "fixtures" / "valid"
Row = tuple[str, str, str, str]  # id, title, severity, score


def _from_html(text: str) -> set[Row]:
    pattern = (
        r"<h3>(?P<id>[A-Z]+-\d+): (?P<title>.+?)</h3>.*?"
        r'class="badge badge-\w+">(?P<sev>\w+)</span>.*?'
        r"<dt>CVSS 3\.1 score</dt><dd>(?P<score>[\d.]+|N/A)"
    )
    return {
        (m["id"], html_lib.unescape(m["title"]), m["sev"], m["score"])
        for m in re.finditer(pattern, text, flags=re.DOTALL)
    }


def _from_md(text: str) -> set[Row]:
    pattern = (
        r"^### (?P<id>[A-Z]+-\d+): (?P<title>.+)\n\n- \*\*Severity:\*\* "
        r"\*\*(?P<sev>\w+)(?: \((?P<score>[\d.]+)\))?\*\*"
    )
    return {
        (m["id"], m["title"].replace("\\", ""), m["sev"], m["score"] or "N/A")
        for m in re.finditer(pattern, text, flags=re.MULTILINE)
    }


def _from_pdf(path: Path) -> set[Row]:
    text = "\n".join(page.extract_text() for page in PdfReader(path).pages)
    pattern = (
        r"^(?P<id>[A-Z]+-\d+): (?P<title>.+)\nSeverity (?P<sev>\w+)\n"
        r"CVSS 3\.1 score (?P<score>[\d.]+|N/A)"
    )
    return {
        (m["id"], m["title"], m["sev"], m["score"])
        for m in re.finditer(pattern, text, flags=re.MULTILINE)
    }


@pytest.mark.pdf
@pytest.mark.parametrize("fixture", ["full.yaml", "minimal.yaml"])
def test_findings_are_identical_in_all_formats(tmp_path: Path, fixture: str) -> None:
    shutil.copytree(FIXTURES, tmp_path / "p")
    out = tmp_path / "out"
    result = CliRunner().invoke(app, ["build", str(tmp_path / "p" / fixture), "-o", str(out)])
    assert result.exit_code == 0, result.output
    html_rows = _from_html((out / "pentest-report.html").read_text("utf-8"))
    md_rows = _from_md((out / "pentest-report.md").read_text("utf-8"))
    pdf_rows = _from_pdf(out / "pentest-report.pdf")
    assert html_rows, "no findings parsed from HTML"
    assert html_rows == md_rows == pdf_rows


def test_parsers_agree_on_an_informational_finding() -> None:
    html = (
        '<h3>PT-009: Info only</h3><span class="badge badge-informational">Informational</span>'
        "<dt>CVSS 3.1 score</dt><dd>N/A (informational)</dd>"
    )
    md = "### PT-009: Info only\n\n- **Severity:** **Informational**\n"
    assert _from_html(html) == _from_md(md) == {("PT-009", "Info only", "Informational", "N/A")}
