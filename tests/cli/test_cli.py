"""CLI entry-point tests (FR-00a, FR-00b)."""

from __future__ import annotations

import re
import runpy
import subprocess
import sys

import pytest
from typer.testing import CliRunner

from pentrep import __version__
from pentrep.cli import app, main


def test_version_flag_prints_name_and_version(runner: CliRunner) -> None:
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert result.stdout.strip() == f"pentrep {__version__}"


def test_version_is_dev_version_for_m1() -> None:
    assert __version__ == "0.1.0.dev0"


def test_python_dash_m_matches_console_script() -> None:
    proc = subprocess.run(
        [sys.executable, "-m", "pentrep", "--version"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0
    assert proc.stdout.strip() == f"pentrep {__version__}"


def test_help_lists_global_options(runner: CliRunner) -> None:
    result = runner.invoke(app, ["--help"])
    # Typer may force colour in-process (e.g. GITHUB_ACTIONS is set), so compare plain text.
    text = re.sub(r"\x1b\[[0-9;]*m", "", result.stdout)
    assert result.exit_code == 0
    assert "--version" in text
    assert "--debug" in text
    assert "--help" in text


def test_main_exits_with_run_code(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(sys, "argv", ["pentrep", "--version"])
    with pytest.raises(SystemExit) as exc_info:
        main()
    assert exc_info.value.code == 0
    assert capsys.readouterr().out.strip() == f"pentrep {__version__}"


def test_dunder_main_runs_cli(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "argv", ["pentrep", "--version"])
    with pytest.raises(SystemExit) as exc_info:
        runpy.run_module("pentrep", run_name="__main__")
    assert exc_info.value.code == 0
