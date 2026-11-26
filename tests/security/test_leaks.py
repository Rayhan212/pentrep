"""No seeded secret reaches stdout, stderr or the --debug output (FR-37, M4.9)."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from pathlib import Path

import pytest
from pypdf import PdfReader
from typer.testing import CliRunner

from pentrep.cli import app
from pentrep.loader import load_report
from pentrep.redact import redact_report

Leak = Callable[[Iterable[str]], None]


def test_fixture_seeds_20_unique_secrets(
    leaky_project: Path, leaky_secrets: tuple[str, ...]
) -> None:
    text = leaky_project.read_text(encoding="utf-8")
    assert len(set(leaky_secrets)) == 20
    assert all(secret in text for secret in leaky_secrets)
    assert "PRIVATE KEY-----" in text


def test_assert_no_leaks_detects_a_leak(no_leaks: Leak) -> None:
    no_leaks(["nothing secret here"])
    with pytest.raises(AssertionError, match=r"#\[3\]"):
        no_leaks(["token leakyBearerToken0003"])


def test_every_seeded_secret_is_redacted(leaky_project: Path, no_leaks: Leak) -> None:
    result = load_report(leaky_project)
    assert result.report is not None
    redacted, summary = redact_report(result.report)
    no_leaks([redacted.model_dump_json()])
    # 20 unique secrets; leakycookie0005 and ACME-190019 each occur twice.
    assert summary.values == 22


@pytest.mark.parametrize(
    "args",
    [
        ["validate", "{file}"],
        ["validate", "{file}", "--strict"],
        ["validate", "{file}", "--format", "json"],
        ["--debug", "validate", "{file}"],
    ],
)
def test_validate_output_has_no_leaks(
    runner: CliRunner, leaky_project: Path, args: list[str], no_leaks: Leak
) -> None:
    result = runner.invoke(app, [a.replace("{file}", str(leaky_project)) for a in args])
    assert result.exit_code == 0, result.output
    no_leaks([result.stdout, result.stderr])


def test_validate_preview_counts_every_occurrence(runner: CliRunner, leaky_project: Path) -> None:
    result = runner.invoke(app, ["validate", str(leaky_project)])
    assert "Redaction preview: 22 values in 2 findings would be redacted" in result.stdout


def test_diagnostics_of_an_invalid_leaky_file_have_no_leaks(
    runner: CliRunner, leaky_project: Path, no_leaks: Leak
) -> None:
    text = leaky_project.read_text(encoding="utf-8")
    leaky_project.write_text(text.replace("id: LK-002", "id: bad"), "utf-8")
    result = runner.invoke(app, ["--debug", "validate", str(leaky_project)])
    assert result.exit_code == 1
    assert "error[E103]" in result.stderr
    no_leaks([result.stdout, result.stderr])


@pytest.mark.parametrize("debug", [[], ["--debug"]])
def test_built_reports_and_output_have_no_leaks(
    runner: CliRunner, leaky_project: Path, no_leaks: Leak, debug: list[str]
) -> None:
    out = leaky_project.parent / "out"
    result = runner.invoke(
        app, [*debug, "build", str(leaky_project), "-f", "html", "-f", "md", "-o", str(out)]
    )
    assert result.exit_code == 0, result.output
    files = [p.read_text("utf-8") for p in sorted(out.glob("*.*"))]
    assert len(files) == 2
    no_leaks([*files, result.stdout, result.stderr])
    assert "Redacted 22 values in 2 findings" in result.stdout


def test_no_redact_really_contains_the_secrets(
    runner: CliRunner, leaky_project: Path, leaky_secrets: tuple[str, ...]
) -> None:
    """Sanity check for the harness: without redaction the secrets do reach the output."""
    out = leaky_project.parent / "out"
    runner.invoke(app, ["build", str(leaky_project), "-f", "md", "-o", str(out), "--no-redact"])
    md = (out / "pentest-report.md").read_text("utf-8")
    assert sum(secret in md for secret in leaky_secrets) >= 18


@pytest.mark.pdf
def test_pdf_has_no_leaks(runner: CliRunner, leaky_project: Path, no_leaks: Leak) -> None:
    out = leaky_project.parent / "out"
    result = runner.invoke(app, ["--debug", "build", str(leaky_project), "-o", str(out)])
    assert result.exit_code == 0, result.output
    pdf_path = out / "pentest-report.pdf"
    text = "\n".join(page.extract_text() for page in PdfReader(pdf_path).pages)
    assert "[REDACTED:" in text  # extraction works, so an absent secret means it was redacted
    no_leaks([text, pdf_path.read_bytes().decode("latin-1"), result.stdout, result.stderr])
