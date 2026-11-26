"""Finding order (FR-42), severity counts and overall risk (FR-43)."""

from __future__ import annotations

from typing import Any

import pytest

from pentrep.cvss import Severity
from pentrep.models import Finding
from pentrep.stats import breakdown, compute_stats, finding_severity, sort_findings

VECTORS = {
    "critical": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H",  # 9.8
    "critical10": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:C/C:H/I:H/A:H",  # 10.0
    "high": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:N/A:N",  # 7.5
    "medium": "CVSS:3.1/AV:N/AC:L/PR:N/UI:R/S:C/C:L/I:L/A:N",  # 6.1
    "low": "CVSS:3.1/AV:P/AC:L/PR:N/UI:N/S:U/C:L/I:N/A:N",  # 2.4
    "none": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:N/I:N/A:N",  # 0.0
}


def _finding(finding_id: str, level: str, status: str = "open") -> Finding:
    data: dict[str, Any] = {
        "id": finding_id,
        "title": "Some finding title",
        "status": status,
        "affected_assets": ["https://app.example.test"],
        "description": "A description that is long enough.",
        "impact": "An impact that is long enough too.",
        "steps_to_reproduce": ["Do the thing."],
        "remediation": "A remediation that is long enough.",
    }
    if level == "informational":
        data["severity"] = "informational"
    else:
        data["cvss_vector"] = VECTORS[level]
    return Finding.model_validate(data)


def test_finding_severity() -> None:
    assert finding_severity(_finding("PT-001", "critical")) is Severity.CRITICAL
    assert finding_severity(_finding("PT-001", "none")) is Severity.NONE
    assert finding_severity(_finding("PT-001", "informational")) is Severity.INFORMATIONAL


def test_sort_by_score_descending_then_id_with_zero_and_informational_last() -> None:
    findings = [
        _finding("PT-007", "informational"),
        _finding("PT-002", "medium"),
        _finding("PT-006", "none"),
        _finding("PT-004", "critical"),
        _finding("PT-003", "critical"),
        _finding("PT-005", "low"),
        _finding("PT-009", "critical10"),
        _finding("PT-001", "informational"),
    ]
    assert [f.id for f in sort_findings(findings)] == [
        "PT-009", "PT-003", "PT-004", "PT-002", "PT-005", "PT-001", "PT-006", "PT-007"
    ]  # fmt: skip


def test_sort_does_not_change_the_input() -> None:
    findings = [_finding("PT-002", "low"), _finding("PT-001", "high")]
    sort_findings(findings)
    assert [f.id for f in findings] == ["PT-002", "PT-001"]


def test_counts_per_severity() -> None:
    stats = compute_stats(
        [
            _finding("PT-001", "critical"),
            _finding("PT-002", "critical10"),
            _finding("PT-003", "high"),
            _finding("PT-004", "medium"),
            _finding("PT-005", "none"),
            _finding("PT-006", "informational"),
        ]
    )
    assert stats.counts == {
        "Critical": 2, "High": 1, "Medium": 1, "Low": 0, "Informational/None": 2, "Total": 6
    }  # fmt: skip


def test_overall_risk_is_highest_open_severity() -> None:
    stats = compute_stats(
        [
            _finding("PT-001", "critical", status="remediated"),
            _finding("PT-002", "high", status="risk_accepted"),
            _finding("PT-003", "medium"),
            _finding("PT-004", "low"),
        ]
    )
    assert stats.overall_risk is Severity.MEDIUM


def test_overall_risk_is_none_when_nothing_is_open() -> None:
    stats = compute_stats([_finding("PT-001", "critical", status="remediated")])
    assert stats.overall_risk is Severity.NONE


@pytest.mark.parametrize(
    ("levels", "expected"),
    [
        (["informational"], Severity.INFORMATIONAL),
        (["none"], Severity.NONE),
        (["none", "informational"], Severity.INFORMATIONAL),
    ],
)
def test_overall_risk_at_the_lowest_rank(levels: list[str], expected: Severity) -> None:
    findings = [_finding(f"PT-00{i}", level) for i, level in enumerate(levels, 1)]
    assert compute_stats(findings).overall_risk is expected


@pytest.mark.parametrize(
    ("levels", "text"),
    [
        (["critical", "medium"], "1 critical, 1 medium"),
        (["low", "critical", "critical10", "high"], "2 critical, 1 high, 1 low"),
        (["none", "informational"], "2 informational"),
        (["medium"], "1 medium"),
    ],
)
def test_breakdown_text(levels: list[str], text: str) -> None:
    findings = [_finding(f"PT-00{i}", level) for i, level in enumerate(levels, 1)]
    assert breakdown(compute_stats(findings)) == text
