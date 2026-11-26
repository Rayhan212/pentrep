"""`pentrep build FILE [options]` for HTML and Markdown (FR-03, FR-35, FR-36)."""

from __future__ import annotations

import shutil
from collections.abc import Callable
from pathlib import Path

import pytest
from typer.testing import CliRunner

from pentrep.cli import app

FIXTURES = Path(__file__).parent.parent / "fixtures"


@pytest.fixture
def project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A copy of the full example (with its images) as the current directory."""
    shutil.copytree(FIXTURES / "valid", tmp_path, dirs_exist_ok=True)
    (tmp_path / "findings.yaml").write_text(
        (FIXTURES / "valid" / "full.yaml").read_text("utf-8"), "utf-8"
    )
    monkeypatch.chdir(tmp_path)
    return tmp_path


def _build(runner: CliRunner, *args: str) -> object:
    return runner.invoke(app, ["build", "findings.yaml", *args])


def _edit(project: Path, old: str, new: str) -> None:
    path = project / "findings.yaml"
    text = path.read_text("utf-8")
    assert old in text
    path.write_text(text.replace(old, new), "utf-8")


def test_html_and_md_are_written_with_assets(runner: CliRunner, project: Path) -> None:
    result = runner.invoke(app, ["build", "findings.yaml", "-f", "html", "-f", "md"])
    assert result.exit_code == 0, result.output
    html = project / "report" / "pentest-report.html"
    md = project / "report" / "pentest-report.md"
    assert html.read_text("utf-8").startswith("<!DOCTYPE html>")
    assert md.read_text("utf-8").startswith("# Web Application Penetration Test")
    assets = project / "report" / "assets"
    assert (assets / "logo.png").read_bytes() == (project / "assets" / "logo.png").read_bytes()
    assert (assets / "PT-001-2.png").read_bytes() == (
        project / "evidence" / "pt-001-sqlmap.png"
    ).read_bytes()
    lines = result.stdout.splitlines()
    assert lines[0].startswith("Wrote report/pentest-report.html (")
    assert lines[0].endswith(" KB)")
    assert "Wrote report/pentest-report.md (" in result.stdout
    assert "Wrote report/assets/PT-001-2.png (" in result.stdout
    assert (
        "Redacted 6 values in 2 findings: SECRET×1, COOKIE×1, JWT×1, EMAIL×1, ACME_EMPLOYEE_ID×1, "
        "PRIVATE_IP×1"
    ) in result.stdout
    assert "Note: 1 image evidence item was not scanned" in result.stdout
    assert result.stderr == ""


def test_html_only_writes_no_assets(runner: CliRunner, project: Path) -> None:
    assert _build(runner, "-f", "html").exit_code == 0  # type: ignore[attr-defined]
    assert (project / "report" / "pentest-report.html").is_file()
    assert not (project / "report" / "pentest-report.md").exists()
    assert not (project / "report" / "assets").exists()


def test_output_dir_and_name(runner: CliRunner, project: Path) -> None:
    result = _build(runner, "-f", "md", "-o", "out/deep", "-n", "acme-2026.v1")
    assert result.exit_code == 0  # type: ignore[attr-defined]
    assert (project / "out" / "deep" / "acme-2026.v1.md").is_file()


@pytest.mark.parametrize("name", ["", "has space", "../escape", "a/b", "x" * 101])
def test_invalid_name_is_a_usage_error(runner: CliRunner, project: Path, name: str) -> None:
    assert _build(runner, "-f", "html", "-n", name).exit_code == 2  # type: ignore[attr-defined]


@pytest.mark.parametrize(
    "args", [["-f", "docx"], ["--template-dir", "missing"], ["--template-dir", "findings.yaml"]]
)
def test_other_usage_errors(runner: CliRunner, project: Path, args: list[str]) -> None:
    assert _build(runner, *args).exit_code == 2  # type: ignore[attr-defined]


def test_validation_errors_write_nothing(runner: CliRunner, project: Path) -> None:
    _edit(project, "id: PT-002", "id: bad")
    result = _build(runner, "-f", "html")
    assert result.exit_code == 1  # type: ignore[attr-defined]
    assert "error[E103]" in result.stderr  # type: ignore[attr-defined]
    assert not (project / "report").exists()


def test_strict_fails_on_warnings(runner: CliRunner, project: Path) -> None:
    _edit(project, '"Acme Corp"', '"Acme Corp TBD"')
    assert _build(runner, "-f", "html").exit_code == 0  # type: ignore[attr-defined]
    shutil.rmtree(project / "report")
    result = _build(runner, "-f", "html", "--strict")
    assert result.exit_code == 1  # type: ignore[attr-defined]
    assert "warning[W101]" in result.stderr  # type: ignore[attr-defined]
    assert not (project / "report").exists()


def test_quiet_prints_nothing_on_success(runner: CliRunner, project: Path) -> None:
    _edit(project, '"Acme Corp"', '"Acme Corp TBD"')  # a warning, which -q hides
    result = _build(runner, "-f", "html", "-f", "md", "-q")
    assert result.exit_code == 0  # type: ignore[attr-defined]
    assert result.output == ""  # type: ignore[attr-defined]
    assert (project / "report" / "pentest-report.md").is_file()


def test_quiet_still_prints_errors(runner: CliRunner, project: Path) -> None:
    _edit(project, "id: PT-002", "id: bad")
    result = _build(runner, "-f", "html", "-q")
    assert result.exit_code == 1  # type: ignore[attr-defined]
    assert "error[E103]" in result.stderr  # type: ignore[attr-defined]


def test_no_redact_marks_draft_and_warns(runner: CliRunner, project: Path) -> None:
    result = _build(runner, "-f", "html", "-f", "md", "--no-redact")
    assert result.exit_code == 0  # type: ignore[attr-defined]
    warning = "warning: redaction is disabled; the report is marked UNREDACTED DRAFT"
    assert warning in result.stderr  # type: ignore[attr-defined]
    html = (project / "report" / "pentest-report.html").read_text("utf-8")
    md = (project / "report" / "pentest-report.md").read_text("utf-8")
    assert "UNREDACTED DRAFT \N{EN DASH} DO NOT DISTRIBUTE" in html
    assert "UNREDACTED DRAFT \N{EN DASH} DO NOT DISTRIBUTE" in md
    assert "9f8e7d6c5b4a3921" in md  # really not redacted
    assert "Redaction is disabled" in result.stdout  # type: ignore[attr-defined]


def test_disabled_in_config_also_warns(runner: CliRunner, project: Path) -> None:
    _edit(project, "redaction:\n  enabled: true", "redaction:\n  enabled: false")
    result = _build(runner, "-f", "md")
    assert result.exit_code == 0  # type: ignore[attr-defined]
    assert "warning: redaction is disabled" in result.stderr  # type: ignore[attr-defined]


def test_template_dir_overrides_a_partial(runner: CliRunner, project: Path) -> None:
    templates = project / "templates" / "partials"
    templates.mkdir(parents=True)
    (templates / "cover.html.j2").write_text(
        '<header class="cover" id="cover"><h1>CUSTOM {{ engagement.title }}</h1></header>\n',
        "utf-8",
    )
    result = _build(runner, "-f", "html", "--template-dir", "templates")
    assert result.exit_code == 0, result.output  # type: ignore[attr-defined]
    html = (project / "report" / "pentest-report.html").read_text("utf-8")
    assert "<h1>CUSTOM Web Application" in html
    assert 'id="detailed-findings"' in html  # the rest still comes from the built-in theme


def test_broken_template_exits_3_without_traceback(runner: CliRunner, project: Path) -> None:
    templates = project / "templates" / "partials"
    templates.mkdir(parents=True)
    (templates / "cover.html.j2").write_text("{{ no_such_variable }}", "utf-8")
    result = _build(runner, "-f", "html", "--template-dir", "templates")
    assert result.exit_code == 3  # type: ignore[attr-defined]
    assert "template error" in result.stderr  # type: ignore[attr-defined]
    assert "no_such_variable" in result.stderr  # type: ignore[attr-defined]
    assert "Traceback" not in result.output  # type: ignore[attr-defined]


def test_unwritable_output_exits_3(runner: CliRunner, project: Path) -> None:
    (project / "blocker").write_text("x", "utf-8")
    result = _build(runner, "-f", "html", "-o", "blocker/out")
    assert result.exit_code == 3  # type: ignore[attr-defined]
    assert "cannot write" in result.stderr  # type: ignore[attr-defined]


@pytest.mark.parametrize("args", [[], ["-f", "all"], ["-f", "pdf", "-f", "html", "-f", "md"]])
def test_pdf_is_not_available_yet_but_other_formats_are_written(
    runner: CliRunner, project: Path, args: list[str]
) -> None:
    result = _build(runner, *args)
    assert result.exit_code == 3  # type: ignore[attr-defined]
    assert "PDF" in result.stderr  # type: ignore[attr-defined]
    assert (project / "report" / "pentest-report.html").is_file()
    assert (project / "report" / "pentest-report.md").is_file()


def test_help_lists_every_flag(runner: CliRunner, plain: Callable[[str], str]) -> None:
    text = plain(runner.invoke(app, ["build", "--help"]).stdout)
    for flag in ("--format", "-f", "--output-dir", "-o", "--name", "-n", "--template-dir",
                 "--no-redact", "--strict", "--quiet", "-q"):  # fmt: skip
        assert flag in text, flag
