"""Finding order, severity counts and overall risk (PRD FR-42, FR-43)."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final

from pentrep.cvss import Severity
from pentrep.models import Finding

# Count buckets in report order; None and Informational share one bucket (FR-43).
BUCKETS: Final = ("Critical", "High", "Medium", "Low", "Informational/None")
_BUCKET_OF: Final = {
    Severity.CRITICAL: "Critical",
    Severity.HIGH: "High",
    Severity.MEDIUM: "Medium",
    Severity.LOW: "Low",
    Severity.INFORMATIONAL: "Informational/None",
    Severity.NONE: "Informational/None",
}


def finding_severity(finding: Finding) -> Severity:
    """Informational for ``severity: informational``, else the CVSS severity band."""
    return finding.cvss.severity if finding.cvss else Severity.INFORMATIONAL


def _score(finding: Finding) -> float:
    return finding.cvss.base_score if finding.cvss else 0.0


def sort_findings(findings: Sequence[Finding]) -> list[Finding]:
    """Score descending, then id ascending; 0.0 and informational findings last (FR-42)."""
    return sorted(findings, key=lambda f: (_score(f) == 0.0, -_score(f), f.id))


@dataclass(frozen=True)
class Stats:
    """Severity counts per bucket (plus ``Total``) and the overall risk rating."""

    counts: dict[str, int]
    overall_risk: Severity


def compute_stats(findings: Sequence[Finding]) -> Stats:
    """Count findings per severity bucket and rate the overall risk (FR-43).

    Overall risk is the highest severity among ``open`` findings, or None if nothing is open.
    At the lowest rank, Informational wins over None.
    """
    counts = dict.fromkeys(BUCKETS, 0)
    for finding in findings:
        counts[_BUCKET_OF[finding_severity(finding)]] += 1
    counts["Total"] = len(findings)
    open_severities = [finding_severity(f) for f in findings if f.status == "open"]
    risk = max(open_severities, default=Severity.NONE)
    if risk.rank == 0 and Severity.INFORMATIONAL in open_severities:
        risk = Severity.INFORMATIONAL
    return Stats(counts, risk)


def breakdown(stats: Stats) -> str:
    """Non-zero bucket counts for the CLI, for example ``1 critical, 1 medium``."""
    parts = []
    for bucket in BUCKETS:
        if stats.counts[bucket]:
            label = "informational" if bucket == "Informational/None" else bucket.lower()
            parts.append(f"{stats.counts[bucket]} {label}")
    return ", ".join(parts)
