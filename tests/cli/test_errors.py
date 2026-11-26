"""Global error handling (FR-00c, FR-00d) and colour handling (FR-00e)."""

from __future__ import annotations

import os
import re
import subprocess
import sys

import pytest
import typer

from pentrep import cli
from pentrep.diagnostics import ExitCode

ANSI_SGR = re.compile(r"\x1b\[([0-9;]*)m")


def _has_colour(text: str) -> bool:
    """True if ``text`` contains an ANSI colour code (bold/dim are not colour, per no-color.org)."""
    for match in ANSI_SGR.finditer(text):
        params = [int(p) for p in match.group(1).split(";") if p]
        if any(30 <= p <= 49 or 90 <= p <= 107 for p in params):
            return True
    return False


@pytest.fixture
def crashing_app() -> typer.Typer:
    """An app with pentrep's root callback and a command that raises."""
    test_app = typer.Typer(pretty_exceptions_enable=False)
    test_app.callback()(cli.root)

    @test_app.command()
    def boom() -> None:
        raise RuntimeError("kaboom")

    @test_app.command()
    def ok() -> None:
        typer.echo("fine")

    return test_app


def test_success_returns_zero(crashing_app: typer.Typer) -> None:
    assert cli.run(crashing_app, ["ok"]) == ExitCode.OK


def test_internal_error_without_debug_has_no_traceback(
    crashing_app: typer.Typer, capsys: pytest.CaptureFixture[str]
) -> None:
    code = cli.run(crashing_app, ["boom"])
    captured = capsys.readouterr()
    assert code == ExitCode.RENDER_ERROR
    assert captured.err.strip() == "internal error: kaboom (re-run with --debug for details)"
    assert "Traceback" not in captured.err
    assert captured.out == ""


def test_internal_error_with_debug_reraises(crashing_app: typer.Typer) -> None:
    with pytest.raises(RuntimeError, match="kaboom"):
        cli.run(crashing_app, ["--debug", "boom"])


def test_debug_flag_does_not_leak_between_runs(
    crashing_app: typer.Typer, capsys: pytest.CaptureFixture[str]
) -> None:
    cli.run(crashing_app, ["--debug", "ok"])
    assert cli.run(crashing_app, ["boom"]) == ExitCode.RENDER_ERROR
    assert "internal error" in capsys.readouterr().err


@pytest.mark.parametrize("argv", [["--no-such-flag"], ["no-such-command"]])
def test_usage_errors_exit_2(crashing_app: typer.Typer, argv: list[str]) -> None:
    assert cli.run(crashing_app, argv) == ExitCode.USAGE_ERROR


def test_real_app_usage_error_exit_2() -> None:
    assert cli.run(cli.app, ["--no-such-flag"]) == ExitCode.USAGE_ERROR


def test_help_mentions_debug_flag() -> None:
    proc = _pentrep("--help")
    assert "--debug" in proc.stdout


def test_no_colour_when_not_a_tty() -> None:
    proc = _pentrep("--help")
    assert proc.returncode == 0
    assert "\x1b[" not in proc.stdout  # no ANSI escapes at all when piped


def test_force_color_produces_colour() -> None:
    """Sanity check: the colour detector actually sees colour when it is forced."""
    proc = _pentrep("--no-such-flag", env={"FORCE_COLOR": "1"})
    assert _has_colour(proc.stdout + proc.stderr)


def test_no_color_env_wins_over_force_color() -> None:
    proc = _pentrep("--no-such-flag", env={"FORCE_COLOR": "1", "NO_COLOR": "1"})
    assert proc.returncode == ExitCode.USAGE_ERROR
    assert not _has_colour(proc.stdout + proc.stderr)


def _pentrep(*args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    """Run ``python -m pentrep`` in a subprocess (stdout/stderr are pipes, not a TTY)."""
    full_env = {k: v for k, v in os.environ.items() if k not in {"FORCE_COLOR", "NO_COLOR"}}
    full_env.update(env or {})
    return subprocess.run(
        [sys.executable, "-m", "pentrep", *args],
        capture_output=True,
        text=True,
        check=False,
        env=full_env,
    )
