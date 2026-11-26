"""Golden tests over tests/fixtures: valid files pass, invalid files give the expected output."""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from pentrep.cli import app
from pentrep.diagnostics import ErrorCode
from pentrep.loader import load_report

FIXTURES = Path(__file__).parent.parent / "fixtures"
VALID = sorted((FIXTURES / "valid").glob("*.yaml"))
INVALID = sorted((FIXTURES / "invalid").glob("*.yaml"))


def _ids(paths: list[Path]) -> list[str]:
    return [p.stem for p in paths]


def test_fixture_directories_are_not_empty() -> None:
    assert {p.name for p in VALID} >= {"minimal.yaml", "full.yaml"}
    assert INVALID


@pytest.mark.parametrize("path", VALID, ids=_ids(VALID))
def test_valid_fixtures_have_no_diagnostics(path: Path) -> None:
    result = load_report(path)
    assert result.diagnostics == []
    assert result.report is not None


def validate_args(path: Path) -> list[str]:
    """``validate`` arguments for a fixture; warning fixtures need ``--strict`` to fail."""
    return ["validate", path.name, *(["--strict"] if path.stem.startswith("w") else [])]


@pytest.mark.parametrize("path", INVALID, ids=_ids(INVALID))
def test_invalid_fixture_matches_expected_stderr(
    path: Path, runner: CliRunner, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``validate`` exits 1 and its stderr equals the ``.expected.txt`` golden (NFR-05, NFR-06)."""
    monkeypatch.chdir(path.parent)
    result = runner.invoke(app, validate_args(path))
    assert result.exit_code == 1
    assert result.stdout == ""
    assert "Traceback" not in result.stderr
    assert result.stderr == path.with_suffix(".expected.txt").read_text(encoding="utf-8")


@pytest.mark.parametrize("path", INVALID, ids=_ids(INVALID))
def test_invalid_fixture_reports_the_code_in_its_name(path: Path) -> None:
    code = ErrorCode[path.stem.split("_", 1)[0].upper()]
    result = load_report(path, display=path.name)
    assert code in {d.code for d in result.diagnostics}
    if code.value.startswith("E"):
        assert not result.ok


def test_every_code_has_a_fixture() -> None:
    covered = {ErrorCode[p.stem.split("_", 1)[0].upper()] for p in INVALID}
    assert set(ErrorCode) <= covered


def test_every_invalid_fixture_has_an_expected_file() -> None:
    expected = {p.name.removesuffix(".expected.txt") for p in INVALID[0].parent.glob("*.txt")}
    assert expected == {p.stem for p in INVALID}
