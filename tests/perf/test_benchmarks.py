"""Performance requirements NFR-01..NFR-04 (marked ``perf``; run in a dedicated CI job).

Each timing is the median of 5 runs of ``python -m pentrep`` in a subprocess, so interpreter
start-up and imports are included, as a user would experience them.
"""

from __future__ import annotations

import os
import statistics
import subprocess
import sys
import time
from pathlib import Path

import pytest

RUNS = 5
COLOUR_ENV = {"FORCE_COLOR", "NO_COLOR", "PY_COLORS", "GITHUB_ACTIONS"}


def _run(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    env = {k: v for k, v in os.environ.items() if k not in COLOUR_ENV}
    return subprocess.run(
        [sys.executable, "-m", "pentrep", *args],
        capture_output=True,
        text=True,
        check=False,
        cwd=cwd,
        env=env,
    )


def _median_seconds(*args: str, cwd: Path | None = None) -> float:
    times = []
    for _ in range(RUNS):
        start = time.perf_counter()
        result = _run(*args, cwd=cwd)
        times.append(time.perf_counter() - start)
        assert result.returncode == 0, result.stderr
    return statistics.median(times)


# --- Always-on checks (not timing) --------------------------------------------------------------


def test_benchmark_project_is_valid(bench_project: Path) -> None:
    images = sorted((bench_project / "evidence").glob("*.png"))
    assert len(images) == 20
    assert all(image.stat().st_size <= 500 * 1024 for image in images)
    result = _run("validate", str(bench_project / "findings.yaml"))
    assert result.returncode == 0, result.stderr
    assert "is valid: 50 findings (" in result.stdout
    assert result.stdout.split("\n", 1)[0].endswith(", 0 warnings")


def test_help_does_not_import_weasyprint_or_jinja() -> None:
    """NFR-04: heavy renderers are imported lazily, only by ``build``."""
    code = (
        "import sys\n"
        "from pentrep.cli import run, app\n"
        "run(app, ['--help'])\n"
        "print('weasyprint' in sys.modules, 'jinja2' in sys.modules)\n"
    )
    env = {k: v for k, v in os.environ.items() if k not in COLOUR_ENV}
    result = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, check=True, env=env
    )
    # Pygments is not checked: Rich (Typer's help renderer) imports it, not pentrep.
    assert result.stdout.strip().splitlines()[-1] == "False False"


# --- Timings (NFR-01..NFR-04) ------------------------------------------------------------------


@pytest.mark.perf
def test_nfr01_validate_50_findings_within_1s(bench_project: Path) -> None:
    seconds = _median_seconds("validate", str(bench_project / "findings.yaml"))
    assert seconds <= 1.0, f"median {seconds:.2f}s"


@pytest.mark.perf
def test_nfr02_build_html_and_md_within_3s(bench_project: Path, tmp_path: Path) -> None:
    seconds = _median_seconds(
        "build", str(bench_project / "findings.yaml"), "-f", "html", "-f", "md", "-q",
        "-o", str(tmp_path / "out"),
    )  # fmt: skip
    assert seconds <= 3.0, f"median {seconds:.2f}s"
    assert (tmp_path / "out" / "pentest-report.html").stat().st_size > 20 * 360 * 1024


@pytest.mark.perf
@pytest.mark.pdf
def test_nfr03_build_pdf_within_15s(bench_project: Path, tmp_path: Path) -> None:
    seconds = _median_seconds(
        "build", str(bench_project / "findings.yaml"), "-f", "pdf", "-q", "-o", str(tmp_path)
    )
    assert seconds <= 15.0, f"median {seconds:.2f}s"


@pytest.mark.perf
def test_nfr04_help_within_400ms() -> None:
    seconds = _median_seconds("--help")
    assert seconds <= 0.4, f"median {seconds:.3f}s"
