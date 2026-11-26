"""The PRD §4.2.3 example redacts to exactly the text shown in the PRD (M4 acceptance criterion)."""

from __future__ import annotations

import re
from pathlib import Path

from pentrep.loader import load_report
from pentrep.models import HttpEvidence, Report, TextEvidence
from pentrep.redact import redact_report

ROOT = Path(__file__).parent.parent.parent
PRD = (ROOT / "docs" / "PRD.md").read_text(encoding="utf-8")
SECTION = PRD[PRD.index("#### 4.2.3") : PRD.index("#### 4.2.4")]


def _expected_pt001_lines() -> list[str]:
    block = SECTION.split("```text\n", 1)[1].split("```", 1)[0]
    return [line for line in block.splitlines() if line != "..."]


def _expected_pt002_line() -> str:
    match = re.search(r"The PT-002 evidence line renders as `([^`]+)`", SECTION)
    assert match
    return match.group(1)


def _report() -> Report:
    result = load_report(ROOT / "src" / "pentrep" / "scaffold" / "findings.yaml")
    assert result.report is not None
    return result.report


def _content(item: object) -> str:
    assert isinstance(item, HttpEvidence | TextEvidence)
    return item.content


def test_pt001_http_evidence_matches_the_prd_exactly() -> None:
    original = _content(_report().findings[0].evidence[0]).splitlines()
    redacted = _content(redact_report(_report())[0].findings[0].evidence[0]).splitlines()
    expected = _expected_pt001_lines()
    assert len(expected) == 3
    changed = [i for i, (a, b) in enumerate(zip(original, redacted, strict=True)) if a != b]
    # Exactly the three lines shown in the PRD change, and they read exactly as shown.
    assert [redacted[i] for i in changed] == expected


def test_pt002_evidence_line_matches_the_prd() -> None:
    redacted = _content(redact_report(_report())[0].findings[1].evidence[0]).splitlines()
    assert redacted[0] == _expected_pt002_line()
    assert redacted[1] == (
        '<div class="results">No results for <svg/onload=alert(document.domain)></div>'
    )


def test_allowlist_and_other_fields_in_the_example() -> None:
    redacted, summary = redact_report(_report())
    assert summary.counts == (
        ("SECRET", 1), ("COOKIE", 1), ("JWT", 1), ("EMAIL", 1), ("ACME_EMPLOYEE_ID", 1),
        ("PRIVATE_IP", 1),
    )  # fmt: skip
    assert summary.findings == 2
    assert summary.images_not_scanned == 1
    assert redacted.findings[0].steps_to_reproduce == _report().findings[0].steps_to_reproduce


def test_example_redaction_is_byte_identical_across_runs() -> None:
    first = redact_report(_report())[0].model_dump_json()
    assert all(redact_report(_report())[0].model_dump_json() == first for _ in range(3))
