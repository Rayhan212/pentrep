"""Command-line interface for pentrep."""

from __future__ import annotations

import json
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from importlib import resources
from pathlib import Path
from typing import Annotated, Final

import typer

from pentrep import __version__
from pentrep.diagnostics import ExitCode, format_json, format_text
from pentrep.loader import load_report
from pentrep.models import json_schema
from pentrep.stats import breakdown, compute_stats


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


CURRENT_DIR: Final = Path(".")
SCAFFOLD_FILES: Final = ("findings.yaml", "assets/logo.png", "evidence/pt-001-sqlmap.png")


def _fail(message: str, code: ExitCode) -> typer.Exit:
    """Print ``message`` to stderr and return an Exit to raise."""
    typer.echo(message, err=True)
    return typer.Exit(code)


@app.command()
def init(
    directory: Annotated[
        Path, typer.Argument(help="Directory to create the project in (created if missing).")
    ] = CURRENT_DIR,
    force: Annotated[
        bool, typer.Option("--force", help="Overwrite files that already exist.")
    ] = False,
) -> None:
    """Create an example findings.yaml with a logo and an evidence image (FR-01)."""
    targets = [directory / name for name in SCAFFOLD_FILES]
    conflicts = [t for t in targets if t.exists() or t.is_symlink()]
    if conflicts and not force:
        listing = "\n".join(f"  {c}" for c in conflicts)
        raise _fail(
            f"error: these files already exist (use --force to overwrite):\n{listing}",
            ExitCode.VALIDATION_FAILED,
        )
    scaffold = resources.files("pentrep") / "scaffold"
    try:
        for name, target in zip(SCAFFOLD_FILES, targets, strict=True):
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(scaffold.joinpath(name).read_bytes())
            typer.echo(f"Created {target}")
    except OSError as exc:
        raise _fail(f"error: cannot write to {directory}: {exc}", ExitCode.RENDER_ERROR) from None
    typer.echo(f"Next: pentrep validate {targets[0]}")


class OutputFormat(StrEnum):
    """Output formats for ``validate``."""

    TEXT = "text"
    JSON = "json"


def _count(n: int, noun: str) -> str:
    return f"{n} {noun}" if n == 1 else f"{n} {noun}s"


@app.command()
def validate(
    file: Annotated[
        Path,
        typer.Argument(
            help="The findings.yaml file to check.", exists=True, dir_okay=False, readable=True
        ),
    ],
    strict: Annotated[bool, typer.Option("--strict", help="Treat warnings as errors.")] = False,
    output_format: Annotated[
        OutputFormat,
        typer.Option("--format", help="Print diagnostics as text (stderr) or JSON (stdout)."),
    ] = OutputFormat.TEXT,
) -> None:
    """Check FILE against the schema and report every error and warning (FR-02)."""
    name = str(file)
    result = load_report(file, display=name)
    errors, warnings = len(result.errors), len(result.warnings)
    failed = bool(errors) or (strict and bool(warnings))
    if output_format is OutputFormat.JSON:
        typer.echo(format_json(result.diagnostics))
    else:
        for diagnostic in result.diagnostics:
            typer.echo(format_text(diagnostic), err=True)
        summary = f"{_count(errors, 'error')}, {_count(warnings, 'warning')}"
        if failed:
            note = " (--strict treats warnings as errors)" if not errors else ""
            typer.echo(f"✗ {name} is invalid: {summary}{note}", err=True)
        else:
            report_findings = result.report.findings if result.report else []
            findings = _count(len(report_findings), "finding")
            if report_findings:
                findings += f" ({breakdown(compute_stats(report_findings))})"
            typer.echo(f"✓ {name} is valid: {findings}, {_count(warnings, 'warning')}")
    if failed:
        raise typer.Exit(ExitCode.VALIDATION_FAILED)


@app.command()
def schema(
    output: Annotated[
        Path | None,
        typer.Option("--output", "-o", help="Write the schema to FILE instead of stdout."),
    ] = None,
) -> None:
    """Print the JSON Schema (draft 2020-12) for findings.yaml (FR-04)."""
    text = json.dumps(json_schema(), indent=2, ensure_ascii=False) + "\n"
    if output is None:
        typer.echo(text, nl=False)
        return
    try:
        output.write_text(text, encoding="utf-8")
    except OSError as exc:
        raise _fail(f"error: cannot write {output}: {exc}", ExitCode.RENDER_ERROR) from None
    typer.echo(f"Wrote {output}")


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
