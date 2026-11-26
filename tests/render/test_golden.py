"""Golden-file tests for the HTML and Markdown reports (PRD §8.2, FR-49).

Regenerate with ``uv run pytest tests/render/test_golden.py --update-golden`` and review the diff.
"""

from __future__ import annotations

import difflib
from pathlib import Path

import pytest

from pentrep import __version__
from pentrep.loader import load_report
from pentrep.redact import redact_report
from pentrep.render.html import render_html
from pentrep.render.md import render_md

ROOT = Path(__file__).parent.parent
FULL = ROOT / "fixtures" / "valid" / "full.yaml"
GOLDEN = ROOT / "golden"
SOURCE_DATE_EPOCH = "1795176000"  # 2026-11-20T12:00:00Z
VERSION_PLACEHOLDER = "<PENTREP_VERSION>"


def _render(kind: str) -> str:
    result = load_report(FULL)
    assert result.report is not None
    report, summary = redact_report(result.report)
    if kind == "html":
        text = render_html(report, summary, FULL.parent)
    else:
        text = render_md(report, summary, FULL.parent).text
    return text.replace(__version__, VERSION_PLACEHOLDER)


@pytest.mark.parametrize("kind", ["html", "md"])
def test_report_matches_golden_file(
    kind: str, update_golden: bool, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SOURCE_DATE_EPOCH", SOURCE_DATE_EPOCH)
    golden = GOLDEN / f"report.{kind}"
    actual = _render(kind)
    if update_golden:
        golden.write_bytes(actual.encode("utf-8"))
        pytest.skip(f"updated {golden.name}")
    expected = golden.read_bytes().decode("utf-8")
    if actual != expected:
        diff = difflib.unified_diff(
            expected.splitlines(), actual.splitlines(), "golden", "actual", lineterm=""
        )
        pytest.fail(f"report.{kind} differs from the golden file:\n" + "\n".join(list(diff)[:200]))


def test_version_is_normalised() -> None:
    assert VERSION_PLACEHOLDER in _render("md")
    assert __version__ not in _render("md")
