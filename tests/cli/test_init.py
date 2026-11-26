"""`pentrep init [DIR] [--force]` (FR-01)."""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from pentrep.cli import app
from pentrep.loader import load_report

ROOT = Path(__file__).parent.parent.parent
SCAFFOLD = ROOT / "src" / "pentrep" / "scaffold"
FILES = ("findings.yaml", "assets/logo.png", "evidence/pt-001-sqlmap.png")


def test_init_creates_the_three_files(runner: CliRunner, tmp_path: Path) -> None:
    target = tmp_path / "new" / "project"
    result = runner.invoke(app, ["init", str(target)])
    assert result.exit_code == 0, result.output
    for name in FILES:
        assert (target / name).read_bytes() == (SCAFFOLD / name).read_bytes()
        assert str(target / name) in result.stdout
    assert f"pentrep validate {target / 'findings.yaml'}" in result.stdout


def test_init_defaults_to_current_directory(
    runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["init"])
    assert result.exit_code == 0, result.output
    assert all((tmp_path / name).is_file() for name in FILES)


def test_generated_file_validates_with_no_diagnostics(runner: CliRunner, tmp_path: Path) -> None:
    runner.invoke(app, ["init", str(tmp_path)])
    result = load_report(tmp_path / "findings.yaml")
    assert result.diagnostics == []
    assert result.report is not None
    assert [f.id for f in result.report.findings] == ["PT-001", "PT-002"]


def test_second_run_exits_1_and_lists_conflicts(runner: CliRunner, tmp_path: Path) -> None:
    runner.invoke(app, ["init", str(tmp_path)])
    (tmp_path / "findings.yaml").write_text("mine", encoding="utf-8")
    result = runner.invoke(app, ["init", str(tmp_path)])
    assert result.exit_code == 1
    for name in FILES:
        assert str(tmp_path / name) in result.stderr
    assert "--force" in result.stderr
    assert result.stdout == ""
    assert (tmp_path / "findings.yaml").read_text(encoding="utf-8") == "mine"


def test_partial_conflict_writes_nothing(runner: CliRunner, tmp_path: Path) -> None:
    (tmp_path / "assets").mkdir()
    (tmp_path / "assets" / "logo.png").write_bytes(b"my logo")
    result = runner.invoke(app, ["init", str(tmp_path)])
    assert result.exit_code == 1
    assert str(tmp_path / "assets" / "logo.png") in result.stderr
    assert str(tmp_path / "findings.yaml") not in result.stderr
    assert not (tmp_path / "findings.yaml").exists()
    assert (tmp_path / "assets" / "logo.png").read_bytes() == b"my logo"


def test_force_overwrites(runner: CliRunner, tmp_path: Path) -> None:
    runner.invoke(app, ["init", str(tmp_path)])
    (tmp_path / "findings.yaml").write_text("mine", encoding="utf-8")
    result = runner.invoke(app, ["init", str(tmp_path), "--force"])
    assert result.exit_code == 0, result.output
    assert (tmp_path / "findings.yaml").read_bytes() == (SCAFFOLD / "findings.yaml").read_bytes()


def test_unwritable_target_exits_3_without_traceback(runner: CliRunner, tmp_path: Path) -> None:
    blocker = tmp_path / "file"
    blocker.write_text("x", encoding="utf-8")
    result = runner.invoke(app, ["init", str(blocker / "sub")])
    assert result.exit_code == 3
    assert "cannot write" in result.stderr
    assert "Traceback" not in result.output


def test_help_lists_flags(runner: CliRunner) -> None:
    result = runner.invoke(app, ["init", "--help"])
    assert result.exit_code == 0
    assert "--force" in result.stdout


def test_examples_mirror_the_scaffold() -> None:
    for name in FILES:
        assert (ROOT / "examples" / name).read_bytes() == (SCAFFOLD / name).read_bytes(), name


def test_scaffold_matches_the_prd_example() -> None:
    prd = (ROOT / "docs" / "PRD.md").read_text(encoding="utf-8")
    section = prd[prd.index("#### 4.2.3") : prd.index("#### 4.2.4")]
    example = section.split("```yaml\n", 1)[1].split("```", 1)[0]
    assert (SCAFFOLD / "findings.yaml").read_text(encoding="utf-8") == example
