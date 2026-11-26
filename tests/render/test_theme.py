"""Classic theme: cover, document control, TOC, executive summary, colours (FR-40 to FR-44)."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from pentrep.loader import load_report
from pentrep.redact import redact_report
from pentrep.render.html import render_html

ROOT = Path(__file__).parent.parent.parent
THEME = ROOT / "src" / "pentrep" / "themes" / "classic"
FULL = ROOT / "tests" / "fixtures" / "valid" / "full.yaml"
SEVERITY_COLOURS = {  # FR-44
    "critical": "#7B1FA2",
    "high": "#C62828",
    "medium": "#E65100",
    "low": "#2E7D32",
    "informational": "#455A64",
    "none": "#455A64",
}


def _html(enabled: bool | None = None) -> str:
    result = load_report(FULL)
    assert result.report is not None
    report, summary = redact_report(result.report, enabled=enabled)
    return render_html(report, summary, FULL.parent)


def _luminance(hex_colour: str) -> float:
    channels = [int(hex_colour[i : i + 2], 16) / 255 for i in (1, 3, 5)]
    linear = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def _contrast(a: str, b: str) -> float:
    high, low = sorted((_luminance(a), _luminance(b)), reverse=True)
    return (high + 0.05) / (low + 0.05)


def _badge_rules() -> dict[str, tuple[str, str]]:
    css = (THEME / "style.css").read_text(encoding="utf-8")
    rules = re.findall(
        r"\.badge-(\w+)\s*\{\s*background:\s*(#[0-9A-Fa-f]{6});\s*color:\s*(#[0-9A-Fa-f]{6});", css
    )
    return {name: (bg.upper(), fg.upper()) for name, bg, fg in rules}


def test_theme_files_exist() -> None:
    for name in (
        "report.html.j2",
        "style.css",
        "partials/cover.html.j2",
        "partials/document_control.html.j2",
        "partials/toc.html.j2",
        "partials/executive_summary.html.j2",
    ):
        assert (THEME / name).is_file(), name


def test_badges_use_the_fr44_colours() -> None:
    rules = _badge_rules()
    assert {name: bg for name, (bg, _) in rules.items()} == SEVERITY_COLOURS


@pytest.mark.parametrize("severity", sorted(SEVERITY_COLOURS))
def test_badge_text_contrast_is_at_least_4_5(severity: str) -> None:
    background, text = _badge_rules()[severity]
    assert _contrast(background, text) >= 4.5, (severity, _contrast(background, text))


def test_contrast_helper_matches_wcag_examples() -> None:
    assert _contrast("#FFFFFF", "#000000") == pytest.approx(21.0)
    assert _contrast("#777777", "#FFFFFF") == pytest.approx(4.48, abs=0.01)


def test_accent_colour_is_a_css_variable() -> None:
    css = (THEME / "style.css").read_text(encoding="utf-8")
    assert "var(--accent)" in css
    assert "--accent: #1F4E79;" in _html()


def test_print_stylesheet_is_included() -> None:
    assert "@media print" in _html()


def test_cover() -> None:
    html = _html()
    cover = html[html.index('<header class="cover"') : html.index("</header>")]
    for text in (
        "<h1>Web Application Penetration Test \N{EN DASH} Acme Customer Portal</h1>",
        "Acme Corp",
        "2026-11-20",
        "Version 1.0",
        "CONFIDENTIAL",
        "Example Security Labs",
        'alt="Example Security Labs logo"',
    ):
        assert text in cover, text


def test_document_control() -> None:
    html = _html()
    section = html[html.index('id="document-control"') :]
    section = section[: section.index("</section>")]
    for text in ("1.0", "2026-11-20", "CONFIDENTIAL", "2026-11-02", "2026-11-13", "Alex Tester",
                 "Lead Penetration Tester", "alex@example-security.test"):  # fmt: skip
        assert text in section, text


def test_toc_links_to_every_section_and_finding() -> None:
    html = _html()
    toc = html[html.index('id="table-of-contents"') :]
    toc = toc[: toc.index("</section>")]
    for anchor in ("#executive-summary", "#scope-and-methodology", "#findings-summary",
                   "#detailed-findings", "#finding-pt-001", "#finding-pt-002", "#appendix-a",
                   "#appendix-b"):  # fmt: skip
        assert f'href="{anchor}"' in toc, anchor


def test_executive_summary_with_statistics() -> None:
    html = _html()
    section = html[html.index('id="executive-summary"') :]
    section = section[: section.index("</section>")]
    assert "allows an unauthenticated attacker to take over any account" in section
    for row in (
        ("Critical", "1"), ("High", "0"), ("Medium", "1"), ("Low", "0"),
        ("Informational/None", "0"), ("Total", "2"),
    ):  # fmt: skip
        assert re.search(rf"<th scope=\"row\">{row[0]}</th>\s*<td>{row[1]}</td>", section), row
    assert re.search(
        r"Overall risk:\s*<span class=\"badge badge-critical\">Critical</span>", section
    )


def test_no_banner_when_redacted_and_banner_everywhere_when_not() -> None:
    assert "UNREDACTED DRAFT" not in _html()
    html = _html(enabled=False)
    banners = html.count(
        '<p class="draft-banner">UNREDACTED DRAFT \N{EN DASH} DO NOT DISTRIBUTE</p>'
    )
    assert banners >= 1 + html.count("<h2")  # the cover and every section header


# --- Theme part 2 (M5.5) ----------------------------------------------------------------------


def _section(html: str, section_id: str) -> str:
    part = html[html.index(f'id="{section_id}"') :]
    return part[: part.index("</section>")]


def _finding(html: str, anchor: str) -> str:
    part = html[html.index(f'id="{anchor}"') :]
    return part[: part.index("</article>")]


def test_sections_are_in_fr40_order() -> None:
    html = _html()
    ids = ["cover", "document-control", "table-of-contents", "executive-summary",
           "scope-and-methodology", "findings-summary", "detailed-findings", "appendix-a",
           "appendix-b"]  # fmt: skip
    positions = [html.index(f'id="{i}"') for i in ids]
    assert positions == sorted(positions)


def test_scope_and_methodology() -> None:
    section = _section(_html(), "scope-and-methodology")
    assert "<td>https://portal.acme.example</td>" in section
    assert "<td>203.0.113.10</td><td>ip</td><td>Production API host</td>" in section
    assert "Out of scope" in section
    assert "<td>https://status.acme.example</td>" in section
    assert "<strong>OWASP Web Security Testing Guide v4.2</strong>" in section


def test_findings_summary_table_in_fr42_order() -> None:
    section = _section(_html(), "findings-summary")
    rows = re.findall(r'<tr><td><a href="#(finding-pt-\d+)">', section)
    assert rows == ["finding-pt-001", "finding-pt-002"]
    assert (
        '<span class="badge badge-critical">Critical</span></td><td>9.8</td><td>Open</td>'
        in section
    )
    assert '<span class="badge badge-medium">Medium</span></td><td>6.1</td><td>Open</td>' in section


def test_detailed_finding() -> None:
    finding = _finding(_html(), "finding-pt-001")
    for text in (
        "<h3>PT-001: SQL Injection in Login Endpoint</h3>",
        '<span class="badge badge-critical">Critical</span>',
        "<dd>9.8 (Impact 5.9, Exploitability 3.9)</dd>",
        "<dd><code>CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H</code></dd>",
        "<dd>Open</dd>",
        '<a href="https://cwe.mitre.org/data/definitions/89.html">CWE-89</a>',
        "<li>https://portal.acme.example/api/v1/login</li>",
        "<h4>Description</h4>",
        "<code>username</code>",
        "<h4>Impact</h4>",
        "<h4>Steps to reproduce</h4>",
        "<h4>Evidence</h4>",
        "<figcaption>Evidence 1: Boolean-based payload returns an admin session</figcaption>",
        "<figcaption>Evidence 2: sqlmap enumerating database tables</figcaption>",
        '<img src="data:image/png;base64,',
        'alt="sqlmap enumerating database tables"',
        "<h4>Remediation</h4>",
        "<h4>References</h4>",
        '<a href="https://owasp.org/www-community/attacks/SQL_Injection">',
    ):
        assert text in finding, text
    assert re.search(r"<ol>\s*<li>Send the request shown in Evidence 1", finding)


def test_evidence_is_highlighted_with_inline_styles_and_redacted() -> None:
    finding = _finding(_html(), "finding-pt-001")
    assert '<div class="highlight"' in finding
    assert "<span style=" in finding
    assert "[REDACTED:SECRET]" in finding
    assert "9f8e7d6c5b4a3921" not in finding


def test_text_evidence_markup_is_escaped() -> None:
    finding = _finding(_html(), "finding-pt-002")
    assert "<svg/onload" not in finding
    assert "svg/onload" in finding  # shown as text inside the highlighted block
    assert "[REDACTED:PRIVATE_IP]" in finding


def test_appendix_a_severity_scale() -> None:
    section = _section(_html(), "appendix-a")
    dash = " \N{EN DASH} "
    for label, scores in (
        ("None", "0.0"),
        ("Low", f"0.1{dash}3.9"),
        ("Medium", f"4.0{dash}6.9"),
        ("High", f"7.0{dash}8.9"),
        ("Critical", f"9.0{dash}10.0"),
    ):
        assert (
            f'<span class="badge badge-{label.lower()}">{label}</span></td><td>{scores}' in section
        )


def test_appendix_b_redaction_counts() -> None:
    section = _section(_html(), "appendix-b")
    assert "<tr><td>SECRET</td><td>1</td></tr>" in section
    assert "<tr><td>ACME_EMPLOYEE_ID</td><td>1</td></tr>" in section
    assert "Note: 1 image evidence item was not scanned" in section
    unredacted = _section(_html(enabled=False), "appendix-b")
    assert "was not redacted" in unredacted
    assert "<table" not in unredacted
