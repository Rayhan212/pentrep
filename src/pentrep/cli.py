"""Command-line interface for pentrep."""

from __future__ import annotations

import sys
from collections.abc import Sequence
from dataclasses import dataclass

import typer

from pentrep import __version__
from pentrep.diagnostics import ExitCode


@dataclass
class _State:
    """Per-invocation global options."""

    debug: bool = False


_state = _State()

app = typer.Typer(
    name="pentrep",
    help="Turn findings.yaml into professional pentest reports (HTML, PDF, Markdown).",
    no_args_is_help=True,
    add_completion=False,
    pretty_exceptions_enable=False,
)


def _version_callback(value: bool) -> None:
    """Print the version and exit when --version is given."""
    if value:
        typer.echo(f"pentrep {__version__}")
        raise typer.Exit()


@app.callback()
def root(
    version: bool = typer.Option(
        False,
        "--version",
        callback=_version_callback,
        is_eager=True,
        help="Show the pentrep version and exit.",
    ),
    debug: bool = typer.Option(
        False, "--debug", help="Show full tracebacks for unexpected errors."
    ),
) -> None:
    """Turn findings.yaml into professional pentest reports (HTML, PDF, Markdown)."""
    _state.debug = debug


def run(cli_app: typer.Typer, argv: Sequence[str]) -> int:
    """Run ``cli_app`` with ``argv`` and return its exit code (FR-00c, FR-00d).

    Unexpected exceptions become exit code 3 with a one-line message, unless
    ``--debug`` was given, in which case they propagate with a full traceback.
    """
    _state.debug = False
    try:
        cli_app(args=list(argv), prog_name="pentrep")
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else ExitCode.OK
    except Exception as exc:
        if _state.debug:
            raise
        typer.echo(f"internal error: {exc} (re-run with --debug for details)", err=True)
        return ExitCode.RENDER_ERROR
    return ExitCode.OK  # pragma: no cover - Click's standalone mode always raises SystemExit


def main() -> None:
    """Console-script entry point."""
    sys.exit(run(app, sys.argv[1:]))
