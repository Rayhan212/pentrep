"""GitHub-Flavored Markdown report (FR-47)."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from pentrep.loader import load_report
from pentrep.models import Report
from pentrep.redact import redact_report
from pentrep.render.md import (
    MarkdownReport,
    escape_html_outside_code,
    fence,
    md_block,
    render_md,
    slug,
)

FULL = Path(__file__).parent.parent / "fixtures" / "valid" / "full.yaml"


def _report() -> Report:
    result = load_report(FULL)
    assert result.report is not None
    return result.report


def _render(report: Report | None = None, enabled: bool | None = None) -> MarkdownReport:
    redacted, summary = redact_report(report or _report(), enabled=enabled)
    return render_md(redacted, summary, FULL.parent)


def _outside_fences(text: str) -> list[str]:
    lines, inside, marker = [], False, ""
    for line in text.splitlines():
        match = re.match(r"^(`{3,}|~{3,})", line)
        if match and (not inside or line.strip() == marker):
            inside, marker = (not inside), match.group(1)
            continue
        if not inside:
            lines.append(line)
    return lines


def _with(**changes: object) -> Report:
    data = _report().model_dump(mode="json", exclude_computed_fields=True)
    data["findings"][0].update(changes)
    return Report.model_validate(data)


def test_one_h1_and_sections_in_fr40_order() -> None:
    lines = _outside_fences(_render().text)
    assert [line for line in lines if line.startswith("# ")] == [
        "# Web Application Penetration Test \N{EN DASH} Acme Customer Portal"
    ]
    sections = [line[3:] for line in lines if line.startswith("## ")]
    assert sections == [
        "Document control", "Table of contents", "Executive summary", "Scope and methodology",
        "Findings summary", "Detailed findings", "Appendix A: CVSS 3.1 severity scale",
        "Appendix B: Redaction",
    ]  # fmt: skip
    findings = [line for line in lines if line.startswith("### PT-")]
    assert findings == [
        "### PT-001: SQL Injection in Login Endpoint",
        "### PT-002: Reflected Cross-Site Scripting in Search",
    ]
    assert not [line for line in lines if line.startswith("####")]


def test_severity_as_text_and_gfm_tables() -> None:
    text = _render().text
    assert "**Critical (9.8)**" in text
    assert "**Medium (6.1)**" in text
    assert (
        "| [PT-001](#pt-001-sql-injection-in-login-endpoint) | SQL Injection in Login Endpoint "
        "| **Critical (9.8)** | Open |" in text
    )
    assert "| Critical | 1 |" in text
    assert "| Total | 2 |" in text
    assert "Overall risk: **Critical**" in text


def test_toc_anchors_match_github_slugs() -> None:
    text = _render().text
    assert "- [Executive summary](#executive-summary)" in text
    assert "(#appendix-a-cvss-31-severity-scale)" in text
    assert (
        "  - [PT-002: Reflected Cross-Site Scripting in Search]"
        "(#pt-002-reflected-cross-site-scripting-in-search)" in text
    )


@pytest.mark.parametrize(
    ("heading", "anchor"),
    [
        ("PT-001: SQL Injection", "pt-001-sql-injection"),
        ("Appendix B: Redaction", "appendix-b-redaction"),
        ("Café & Co_ok", "café--co_ok"),
    ],
)
def test_slug(heading: str, anchor: str) -> None:
    assert slug(heading) == anchor


def test_images_are_copied_assets_with_relative_paths() -> None:
    report = _render()
    assert "![sqlmap enumerating database tables](assets/PT-001-2.png)" in report.text
    assert "![Example Security Labs logo](assets/logo.png)" in report.text
    assert report.assets == [
        ((FULL.parent / "assets" / "logo.png").resolve(), "assets/logo.png"),
        ((FULL.parent / "evidence" / "pt-001-sqlmap.png").resolve(), "assets/PT-001-2.png"),
    ]


def test_evidence_uses_fences_with_language_and_is_redacted() -> None:
    text = _render().text
    assert "**Evidence 1: Boolean-based payload returns an admin session**\n\n```http\n" in text
    assert '{"username":"admin\' OR \'1\'=\'1\' -- ","password":"[REDACTED:SECRET]"}' in text
    assert "```html\nX-Backend-Host: [REDACTED:PRIVATE_IP]\n" in text


@pytest.mark.parametrize(
    ("content", "expected"),
    [("plain", "```"), ("has ``` inside", "````"), ("````` five", "``````"), ("`one`", "```")],
)
def test_fence_is_longer_than_any_backtick_run(content: str, expected: str) -> None:
    assert fence(content) == expected


def test_evidence_containing_a_fence_stays_inside_its_block() -> None:
    report = _with(evidence=[{"type": "text", "caption": "Has fence", "content": "a\n```\nb\n"}])
    assert "````\na\n```\nb\n````" in _render(report).text


def test_raw_html_is_escaped_outside_code() -> None:
    assert escape_html_outside_code("x <script>a</script> `<b>` y") == (
        "x &lt;script>a&lt;/script> `<b>` y"
    )
    assert escape_html_outside_code("```\n<keep>\n```\n<no>") == "```\n<keep>\n```\n&lt;no>"
    assert escape_html_outside_code("``a ` <b>`` <c>") == "``a ` <b>`` &lt;c>"


def test_user_markdown_headings_are_demoted() -> None:
    report = _with(description="# Heading one\n\nText here.\n\nSetext\n===\n\nMore text follows.")
    text = _render(report).text
    assert "**Heading one**" in text
    assert "**Setext**" in text
    assert "# Heading one" not in text


def test_steps_keep_inline_code_and_escape_html() -> None:
    text = _render().text
    assert "1. Log in as any user." in text
    assert (
        "2. Open `https://portal.acme.example/search?q=<svg/onload=alert(document.domain)>`."
        in text
    )


def test_table_cells_escape_pipes_and_newlines() -> None:
    report = _with(title="Pipe | in title")
    assert "| Pipe \\| in title |" in _render(report).text


def test_unredacted_banner_under_title_and_every_section() -> None:
    text = _render(enabled=False).text
    banner = "> **UNREDACTED DRAFT \N{EN DASH} DO NOT DISTRIBUTE**"
    assert text.count(banner) == 1 + text.count("\n## ")
    assert "UNREDACTED" not in _render().text


def test_markdown_output_is_deterministic() -> None:
    assert _render() == _render()


def test_no_double_blank_lines_after_headings() -> None:
    for enabled in (None, False):
        text = _render(enabled=enabled).text
        assert not re.search(r"^#{1,3} .*\n\n\n", text, flags=re.MULTILINE)


def test_reference_urls_cannot_inject_html() -> None:
    report = _with(references=["https://example.test/?q=<img/src=x/onerror=alert(1)>"])
    text = _render(report).text
    assert "<img" not in text
    assert "- <https://example.test/?q=%3Cimg" in text


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("[x](javascript:alert(1))", "[x\\](javascript:alert(1))"),
        ("[x]( JavaScript:alert(1))", "[x\\]( JavaScript:alert(1))"),
        ("[x](data:text/html,hi)", "[x\\](data:text/html,hi)"),
        ("[x](vbscript:msgbox)", "[x\\](vbscript:msgbox)"),
        ("[ref]: javascript:alert(1)", "\\[ref]: javascript:alert(1)"),
        ("[ok](https://example.test/)", "[ok](https://example.test/)"),
        ("`[code](javascript:x)`", "`[code](javascript:x)`"),
    ],
)
def test_dangerous_markdown_links_are_neutralised(text: str, expected: str) -> None:
    assert md_block(text) == expected
