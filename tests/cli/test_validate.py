"""`pentrep validate FILE [--strict] [--format text|json]` (FR-02)."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

import jsonschema
import pytest
from typer.testing import CliRunner

from pentrep.cli import app
from pentrep.diagnostics import DIAGNOSTICS_JSON_SCHEMA

FIXTURES = Path(__file__).parent.parent / "fixtures"
MINIMAL = FIXTURES / "valid" / "minimal.yaml"


@pytest.fixture
def project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A temp dir (the cwd) holding a copy of valid/minimal.yaml as findings.yaml."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "findings.yaml").write_text(MINIMAL.read_text(encoding="utf-8"), encoding="utf-8")
    return tmp_path


def _edit(project: Path, old: str, new: str) -> None:
    path = project / "findings.yaml"
    text = path.read_text(encoding="utf-8")
    assert old in text
    path.write_text(text.replace(old, new), encoding="utf-8")


def test_valid_file_prints_success_line(runner: CliRunner, project: Path) -> None:
    result = runner.invoke(app, ["validate", "findings.yaml"])
    assert result.exit_code == 0
    assert result.stdout == "✓ findings.yaml is valid: 1 finding (1 low), 0 warnings\n"
    assert result.stderr == ""


def test_full_example_counts_findings(runner: CliRunner) -> None:
    result = runner.invoke(app, ["validate", str(FIXTURES / "valid" / "full.yaml")])
    assert result.exit_code == 0
    assert result.stdout.endswith(
        "full.yaml is valid: 2 findings (1 critical, 1 medium), 0 warnings\n"
    )


def test_warnings_go_to_stderr_and_do_not_fail(runner: CliRunner, project: Path) -> None:
    _edit(project, '"Minimal Example Engagement"', '"Minimal Example Engagement TBD"')
    result = runner.invoke(app, ["validate", "findings.yaml"])
    assert result.exit_code == 0
    assert result.stdout == "✓ findings.yaml is valid: 1 finding (1 low), 1 warning\n"
    assert result.stderr.startswith("findings.yaml:5:10: warning[W101] engagement.title: ")


def test_strict_turns_warnings_into_failure(runner: CliRunner, project: Path) -> None:
    _edit(project, '"Minimal Example Engagement"', '"Minimal Example Engagement TBD"')
    result = runner.invoke(app, ["validate", "findings.yaml", "--strict"])
    assert result.exit_code == 1
    assert result.stdout == ""
    assert "warning[W101]" in result.stderr
    assert result.stderr.endswith(
        "✗ findings.yaml is invalid: 0 errors, 1 warning (--strict treats warnings as errors)\n"
    )


def test_errors_exit_1_with_all_diagnostics(runner: CliRunner, project: Path) -> None:
    _edit(project, '"Minimal Example Engagement"', '"Min"')
    _edit(project, "  - id: PT-001", "  - id: bad")
    result = runner.invoke(app, ["validate", "findings.yaml"])
    assert result.exit_code == 1
    assert result.stdout == ""
    lines = result.stderr.splitlines()
    assert lines[0].startswith("findings.yaml:5:10: error[E103] engagement.title: ")
    assert lines[1].startswith("findings.yaml:19:9: error[E103] findings[0].id: ")
    assert lines[-1] == "✗ findings.yaml is invalid: 2 errors, 0 warnings"
    assert "Traceback" not in result.output


def test_json_format_prints_only_json_to_stdout(runner: CliRunner, project: Path) -> None:
    _edit(project, '"Minimal Example Engagement"', '"TBD"')
    result = runner.invoke(app, ["validate", "findings.yaml", "--format", "json"])
    assert result.exit_code == 1
    assert result.stderr == ""
    data = json.loads(result.stdout)
    jsonschema.validate(data, DIAGNOSTICS_JSON_SCHEMA)
    assert [(d["code"], d["severity"], d["line"]) for d in data] == [
        ("E103", "error", 5),
        ("W101", "warning", 5),
    ]


def test_json_format_on_valid_file(runner: CliRunner, project: Path) -> None:
    result = runner.invoke(app, ["validate", "findings.yaml", "--format", "json"])
    assert result.exit_code == 0
    assert json.loads(result.stdout) == []


def test_json_format_with_strict_warning(runner: CliRunner, project: Path) -> None:
    _edit(project, '"Minimal Example Engagement"', '"Minimal Example Engagement TBD"')
    args = ["validate", "findings.yaml", "--format", "json"]
    assert runner.invoke(app, args).exit_code == 0
    assert runner.invoke(app, [*args, "--strict"]).exit_code == 1


def test_yaml_syntax_error_exits_1(runner: CliRunner, project: Path) -> None:
    (project / "findings.yaml").write_text("a: [\n", encoding="utf-8")
    result = runner.invoke(app, ["validate", "findings.yaml"])
    assert result.exit_code == 1
    assert "error[E100]" in result.stderr


@pytest.mark.parametrize(
    "args",
    [
        ["validate"],
        ["validate", "missing.yaml"],
        ["validate", "findings.yaml", "--format", "xml"],
        ["validate", "."],
    ],
)
def test_usage_errors_exit_2(runner: CliRunner, project: Path, args: list[str]) -> None:
    assert runner.invoke(app, args).exit_code == 2


def test_help_lists_every_flag(runner: CliRunner, plain: Callable[[str], str]) -> None:
    result = runner.invoke(app, ["validate", "--help"])
    assert result.exit_code == 0
    for flag in ("--strict", "--format", "--help"):
        assert flag in plain(result.stdout)


def test_examples_file_prints_severity_breakdown(runner: CliRunner) -> None:
    examples = Path(__file__).parent.parent.parent / "examples" / "findings.yaml"
    result = runner.invoke(app, ["validate", str(examples)])
    assert result.exit_code == 0
    assert "is valid: 2 findings (1 critical, 1 medium), 0 warnings" in result.stdout
