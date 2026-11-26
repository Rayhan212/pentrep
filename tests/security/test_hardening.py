"""Security hardening: path confinement and referenced-file checks (FR-14, NFR-10)."""

from __future__ import annotations

import os
import re
import shutil
import time
from pathlib import Path

import pytest
from typer.testing import CliRunner

from pentrep.cli import app
from pentrep.diagnostics import ErrorCode
from pentrep.loader import IMAGE_MAX_BYTES, LOGO_MAX_BYTES, ValidationResult, load_report

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 32
GIF = b"GIF89a" + b"\x00" * 32
WEBP = b"RIFF\x00\x00\x00\x00WEBPVP8 " + b"\x00" * 32
SVG = b'<?xml version="1.0"?>\n<svg xmlns="http://www.w3.org/2000/svg"/>\n'

TEMPLATE = """\
schema_version: 1
engagement:
  title: "Web App Test"
  client: {{name: "Acme Corp"}}
  testers: [{{name: "Alex"}}]
  start_date: 2026-11-02
  end_date: 2026-11-13
  scope:
    in_scope: [{{asset: "https://portal.acme.example", type: url}}]
  methodology: "OWASP WSTG v4.2 grey-box assessment."
branding:
  logo: {logo}
findings:
  - id: PT-001
    title: "SQL Injection in Login"
    cvss_vector: "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H"
    affected_assets: ["https://portal.acme.example/login"]
    description: "The username field is concatenated into SQL."
    impact: "An attacker can bypass authentication entirely."
    steps_to_reproduce: ["Send the request."]
    evidence:
      - type: image
        caption: "Screenshot"
        path: {image}
    remediation: "Use parameterised queries for all database access."
"""
LOGO_LINE, IMAGE_LINE = 12, 24


@pytest.fixture
def project(tmp_path: Path) -> Path:
    root = tmp_path / "project"
    (root / "assets").mkdir(parents=True)
    (root / "evidence").mkdir()
    (root / "assets" / "logo.png").write_bytes(PNG)
    (root / "evidence" / "shot.png").write_bytes(PNG)
    return root


def _check(
    project: Path, logo: str = "assets/logo.png", image: str = "evidence/shot.png"
) -> tuple[list[tuple[ErrorCode, str, int]], ValidationResult]:
    path = project / "findings.yaml"
    path.write_text(TEMPLATE.format(logo=logo, image=image), encoding="utf-8")
    result = load_report(path, display="findings.yaml")
    return [(d.code, d.path, d.line) for d in result.diagnostics], result


def test_valid_files_pass(project: Path) -> None:
    diags, result = _check(project)
    assert diags == []
    assert result.report is not None


@pytest.mark.parametrize(
    ("name", "data"), [("logo.jpg", JPEG), ("logo.svg", SVG), ("logo.png", PNG)]
)
def test_logo_types(project: Path, name: str, data: bytes) -> None:
    (project / "assets" / name).write_bytes(data)
    assert _check(project, logo=f"assets/{name}")[0] == []


@pytest.mark.parametrize(
    ("name", "data"), [("a.png", PNG), ("a.jpg", JPEG), ("a.gif", GIF), ("a.webp", WEBP)]
)
def test_image_evidence_types(project: Path, name: str, data: bytes) -> None:
    (project / "evidence" / name).write_bytes(data)
    assert _check(project, image=f"evidence/{name}")[0] == []


def test_missing_files_are_e301(project: Path) -> None:
    diags, _ = _check(project, logo="assets/nope.png", image="evidence/nope.png")
    assert diags == [
        (ErrorCode.E301, "branding.logo", LOGO_LINE),
        (ErrorCode.E301, "findings[0].evidence[0].path", IMAGE_LINE),
    ]


def test_directory_is_not_a_file(project: Path) -> None:
    assert _check(project, image="evidence")[0] == [
        (ErrorCode.E301, "findings[0].evidence[0].path", IMAGE_LINE)
    ]


def test_dot_dot_path_is_e302(project: Path) -> None:
    (project.parent / "secret.png").write_bytes(PNG)
    diags, result = _check(project, image="../secret.png")
    assert diags == [(ErrorCode.E302, "findings[0].evidence[0].path", IMAGE_LINE)]
    assert "outside" in result.diagnostics[0].message


def test_absolute_path_outside_is_e302(project: Path) -> None:
    outside = project.parent / "outside.png"
    outside.write_bytes(PNG)
    assert _check(project, logo=str(outside))[0] == [(ErrorCode.E302, "branding.logo", LOGO_LINE)]


def test_absolute_path_inside_is_allowed(project: Path) -> None:
    assert _check(project, logo=str(project / "assets" / "logo.png"))[0] == []


@pytest.mark.skipif(not hasattr(os, "symlink"), reason="needs symlinks")
def test_symlink_escaping_the_project_is_e302(project: Path) -> None:
    outside = project.parent / "outside.png"
    outside.write_bytes(PNG)
    (project / "evidence" / "link.png").symlink_to(outside)
    assert _check(project, image="evidence/link.png")[0] == [
        (ErrorCode.E302, "findings[0].evidence[0].path", IMAGE_LINE)
    ]


@pytest.mark.skipif(not hasattr(os, "symlink"), reason="needs symlinks")
def test_symlink_inside_the_project_is_allowed(project: Path) -> None:
    (project / "evidence" / "link.png").symlink_to(project / "evidence" / "shot.png")
    assert _check(project, image="evidence/link.png")[0] == []


def test_wrong_logo_type_is_e303(project: Path) -> None:
    (project / "assets" / "logo.gif").write_bytes(GIF)  # GIF is allowed for evidence only
    diags, result = _check(project, logo="assets/logo.gif")
    assert diags == [(ErrorCode.E303, "branding.logo", LOGO_LINE)]
    assert "PNG, JPEG or SVG" in result.diagnostics[0].message


def test_content_type_is_sniffed_not_taken_from_extension(project: Path) -> None:
    (project / "evidence" / "fake.png").write_bytes(b"MZ\x90\x00 not an image")
    assert _check(project, image="evidence/fake.png")[0] == [
        (ErrorCode.E303, "findings[0].evidence[0].path", IMAGE_LINE)
    ]


def test_too_large_files_are_e303(project: Path) -> None:
    (project / "assets" / "big.png").write_bytes(PNG + b"\x00" * LOGO_MAX_BYTES)
    (project / "evidence" / "big.png").write_bytes(PNG + b"\x00" * IMAGE_MAX_BYTES)
    diags, result = _check(project, logo="assets/big.png", image="evidence/big.png")
    assert diags == [
        (ErrorCode.E303, "branding.logo", LOGO_LINE),
        (ErrorCode.E303, "findings[0].evidence[0].path", IMAGE_LINE),
    ]
    assert "2 MB" in result.diagnostics[0].message
    assert "5 MB" in result.diagnostics[1].message


def test_files_at_the_size_limit_are_allowed(project: Path) -> None:
    (project / "assets" / "max.png").write_bytes(PNG + b"\x00" * (LOGO_MAX_BYTES - len(PNG)))
    assert _check(project, logo="assets/max.png")[0] == []


def test_file_checks_run_even_when_other_fields_are_invalid(project: Path) -> None:
    path = project / "findings.yaml"
    text = TEMPLATE.format(logo="assets/nope.png", image="evidence/shot.png")
    path.write_text(text.replace('"Web App Test"', '"Web"'), encoding="utf-8")
    codes = [d.code for d in load_report(path).diagnostics]
    assert codes == [ErrorCode.E103, ErrorCode.E301]


# --- Unsafe YAML (M2.9, NFR-10) -----------------------------------------------------------------


@pytest.mark.parametrize(
    "tag",
    [
        "!!python/object/apply:os.system",
        "!!python/object/new:os.system",
        "!!python/name:os.system",
        "!!python/object:pathlib.Path",
    ],
)
@pytest.mark.parametrize("form", ["sequence", "scalar", "mapping"])
def test_python_tags_are_rejected_and_never_executed(project: Path, tag: str, form: str) -> None:
    marker = project / "pwned"
    value = {
        "sequence": f'["touch {marker}"]',
        "scalar": f'"touch {marker}"',
        "mapping": f'{{args: ["touch {marker}"]}}',
    }[form]
    path = project / "findings.yaml"
    text = TEMPLATE.format(logo="assets/logo.png", image="evidence/shot.png")
    path.write_text(
        text.replace('  methodology: "', f'  methodology: {tag} {value}\n  x: "'),
        encoding="utf-8",
    )
    result = load_report(path, display="findings.yaml")
    assert [(d.code, d.path, d.line) for d in result.diagnostics] == [
        (ErrorCode.E100, "engagement.methodology", 10)
    ]
    assert "unsupported YAML tag" in result.diagnostics[0].message
    assert result.report is None
    assert not marker.exists()


def test_billion_laughs_file_is_rejected_quickly(tmp_path: Path) -> None:
    lines = ['lol0: &lol0 "lol"']
    for level in range(1, 10):
        refs = ", ".join([f"*lol{level - 1}"] * 10)
        lines.append(f"lol{level}: &lol{level} [{refs}]")
    lines.append("schema_version: *lol9")
    path = tmp_path / "findings.yaml"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    start = time.perf_counter()
    result = load_report(path)
    assert time.perf_counter() - start < 2.0
    assert [d.code for d in result.diagnostics] == [ErrorCode.E100]
    assert "alias expansion exceeds 1000 nodes" in result.diagnostics[0].message


@pytest.mark.parametrize(
    "ref", ["../outside.png", "assets/../../outside.png", "evidence/../../../outside.png"]
)
def test_dot_dot_paths_escaping_the_project_are_e302(project: Path, ref: str) -> None:
    (project.parent / "outside.png").write_bytes(PNG)
    diags, _ = _check(project, logo=ref, image=ref)
    assert [code for code, _, _ in diags] == [ErrorCode.E302, ErrorCode.E302]


def test_dot_dot_path_staying_inside_is_allowed(project: Path) -> None:
    assert _check(project, image="assets/../evidence/shot.png")[0] == []


# --- Rendered output (M5.10, NFR-09, NFR-10) ---------------------------------------------------

FULL_FIXTURE = Path(__file__).parent.parent / "fixtures" / "valid"


@pytest.fixture
def hostile_project(tmp_path: Path) -> Path:
    """The full example with XSS, template syntax and a javascript: link in user fields."""
    shutil.copytree(FULL_FIXTURE, tmp_path, dirs_exist_ok=True)
    text = (FULL_FIXTURE / "full.yaml").read_text("utf-8")
    replacements = {
        'title: "SQL Injection in Login Endpoint"': (
            'title: "SQLi {{ 7*7 }} {% if 1 %}X{% endif %}"'
        ),
        "      The `username` field": (
            "      <script>alert('desc')</script> <img src=x onerror=alert(1)>\n"
            "      [click me](javascript:alert(document.cookie)) and {{ config }}.\n"
            "      The `username` field"
        ),
        'company_name: "Example Security Labs"': 'company_name: "Labs <b>{{ 7*7 }}</b>"',
    }
    for old, new in replacements.items():
        assert old in text, old
        text = text.replace(old, new)
    (tmp_path / "findings.yaml").write_text(text, "utf-8")
    return tmp_path


def _build_outputs(project: Path) -> tuple[str, str]:
    result = CliRunner().invoke(
        app,
        [
            "build",
            str(project / "findings.yaml"),
            "-f",
            "html",
            "-f",
            "md",
            "-o",
            str(project / "out"),
        ],
    )
    assert result.exit_code == 0, result.output
    html = (project / "out" / "pentest-report.html").read_text("utf-8")
    md = (project / "out" / "pentest-report.md").read_text("utf-8")
    return html, md


def test_xss_in_description_is_escaped(hostile_project: Path) -> None:
    html, md = _build_outputs(hostile_project)
    assert "<script>" not in html
    assert "<img src=x" not in html
    assert "&lt;script&gt;alert('desc')&lt;/script&gt;" in html
    assert "<script>" not in md
    assert "&lt;script>alert('desc')&lt;/script>" in md


def test_template_syntax_in_values_is_rendered_literally(hostile_project: Path) -> None:
    html, md = _build_outputs(hostile_project)
    assert "SQLi {{ 7*7 }} {% if 1 %}X{% endif %}" in html
    assert "SQLi 49" not in html  # {{ 7*7 }} was not evaluated
    assert "Labs <b>49" not in html
    assert "{{ config }}" in html
    assert "Labs &lt;b&gt;{{ 7*7 }}&lt;/b&gt;" in html
    assert "SQLi {{ 7\\*7 }} {% if 1 %}X{% endif %}" in md


def test_javascript_link_is_neutralised(hostile_project: Path) -> None:
    html, md = _build_outputs(hostile_project)
    # The rejected link is shown as plain text, never as a clickable href.
    assert not re.search(r"href\s*=\s*[\"']?\s*javascript:", html, flags=re.IGNORECASE)
    assert "[click me](javascript:alert(document.cookie))" in html
    assert "[click me\\](javascript:" in md  # Markdown: the link syntax is broken on purpose


def test_build_makes_no_network_connections(hostile_project: Path, socket_disabled: None) -> None:
    import socket

    with pytest.warns(UserWarning), pytest.raises(Exception, match="tried to use socket"):
        socket.socket()  # the guard is active
    html, _ = _build_outputs(hostile_project)  # any connection attempt would raise
    assert "<!DOCTYPE html>" in html
