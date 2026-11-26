"""Build the template context documented in docs/templates.md (FR-48)."""

from __future__ import annotations

import datetime as dt
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from pentrep import __version__
from pentrep.cvss import Severity
from pentrep.loader import SNIFF_BYTES, sniff_image_type
from pentrep.models import Branding, Finding, Report
from pentrep.redact import RedactionSummary, format_summary
from pentrep.stats import Stats, compute_stats, finding_severity, sort_findings

UNREDACTED_BANNER: Final = "UNREDACTED DRAFT \N{EN DASH} DO NOT DISTRIBUTE"  # FR-36 wording
STATUS_LABELS: Final = {
    "open": "Open",
    "remediated": "Remediated",
    "risk_accepted": "Risk accepted",
}
IMAGE_TYPES: Final = {  # sniffed type -> (file extension, MIME type)
    "PNG": ("png", "image/png"),
    "JPEG": ("jpg", "image/jpeg"),
    "GIF": ("gif", "image/gif"),
    "WebP": ("webp", "image/webp"),
    "SVG": ("svg", "image/svg+xml"),
}


def _image_info(path: Path) -> tuple[str, str]:
    """``(extension, MIME type)`` of an image that the loader already validated."""
    with path.open("rb") as handle:
        kind = sniff_image_type(handle.read(SNIFF_BYTES))
    return IMAGE_TYPES[kind or "PNG"]


@dataclass(frozen=True)
class EvidenceView:
    """One evidence item, numbered within its finding."""

    number: int
    type: str
    caption: str
    content: str | None
    language: str | None
    image_path: Path | None
    asset_name: str | None  # file name used when the image is copied (Markdown output)
    mime: str | None


@dataclass(frozen=True)
class FindingView:
    """A finding with everything the templates display, precomputed."""

    id: str
    title: str
    anchor: str
    severity: Severity
    badge: str
    score: float | None
    score_text: str
    vector: str | None
    impact_score: float | None
    exploitability_score: float | None
    status: str
    status_label: str
    cwe: list[tuple[int, str]]
    affected_assets: list[str]
    description: str
    impact: str
    steps_to_reproduce: list[str]
    evidence: list[EvidenceView]
    remediation: str
    references: list[str]


@dataclass(frozen=True)
class BrandingView:
    """Branding with the logo resolved to a file."""

    company_name: str | None
    accent_color: str
    logo_path: Path | None
    logo_asset_name: str | None
    logo_mime: str | None


@dataclass(frozen=True)
class RedactionView:
    """Redaction state for the cover banner and Appendix B."""

    enabled: bool
    unredacted: bool
    banner: str
    counts: tuple[tuple[str, int], ...]
    values: int
    images_not_scanned: int
    lines: list[str]


def _evidence(finding: Finding, base_dir: Path) -> list[EvidenceView]:
    views = []
    for number, item in enumerate(finding.evidence, 1):
        if item.type == "image":
            path = (base_dir / item.path).resolve()
            ext, mime = _image_info(path)
            views.append(
                EvidenceView(
                    number,
                    "image",
                    item.caption,
                    None,
                    None,
                    path,
                    f"{finding.id}-{number}.{ext}",
                    mime,
                )
            )
        else:
            language = item.language if item.type == "text" else "http"
            views.append(
                EvidenceView(
                    number, item.type, item.caption, item.content, language, None, None, None
                )
            )
    return views


def _finding_view(finding: Finding, base_dir: Path) -> FindingView:
    severity = finding_severity(finding)
    cvss = finding.cvss
    return FindingView(
        id=finding.id,
        title=finding.title,
        anchor=f"finding-{finding.id.lower()}",
        severity=severity,
        badge=severity.label.lower(),
        score=cvss.base_score if cvss else None,
        score_text=f"{cvss.base_score:.1f}" if cvss else "N/A",
        vector=cvss.vector.canonical() if cvss else None,
        impact_score=cvss.impact if cvss else None,
        exploitability_score=cvss.exploitability if cvss else None,
        status=finding.status,
        status_label=STATUS_LABELS[finding.status],
        cwe=[(n, f"https://cwe.mitre.org/data/definitions/{n}.html") for n in finding.cwe],
        affected_assets=list(finding.affected_assets),
        description=finding.description,
        impact=finding.impact,
        steps_to_reproduce=list(finding.steps_to_reproduce),
        evidence=_evidence(finding, base_dir),
        remediation=finding.remediation,
        references=list(finding.references),
    )


def _branding_view(branding: Branding, base_dir: Path) -> BrandingView:
    if branding.logo is None:
        return BrandingView(branding.company_name, branding.accent_color, None, None, None)
    path = (base_dir / branding.logo).resolve()
    ext, mime = _image_info(path)
    return BrandingView(branding.company_name, branding.accent_color, path, f"logo.{ext}", mime)


def generated_at(report: Report) -> str:
    """``SOURCE_DATE_EPOCH`` as a UTC timestamp when set, else the report date (FR-49)."""
    epoch = os.environ.get("SOURCE_DATE_EPOCH", "").strip()
    if epoch.isdigit():
        moment = dt.datetime.fromtimestamp(int(epoch), tz=dt.UTC)
        return moment.strftime("%Y-%m-%dT%H:%M:%SZ")
    return report.engagement.report_date.isoformat()


def build_context(report: Report, summary: RedactionSummary, base_dir: Path) -> dict[str, object]:
    """The template context: ``engagement``, ``branding``, ``findings`` (sorted, FR-42),
    ``stats`` (FR-43), ``redaction``, ``generated_at`` and ``pentrep_version``.

    ``report`` must already be redacted; ``base_dir`` is the directory of findings.yaml.
    """
    stats: Stats = compute_stats(report.findings)
    redaction = RedactionView(
        enabled=summary.enabled,
        unredacted=not summary.enabled,
        banner=UNREDACTED_BANNER,
        counts=summary.counts,
        values=summary.values,
        images_not_scanned=summary.images_not_scanned,
        lines=format_summary(summary),
    )
    return {
        "engagement": report.engagement,
        "branding": _branding_view(report.branding, base_dir),
        "findings": [_finding_view(f, base_dir) for f in sort_findings(report.findings)],
        "stats": stats,
        "redaction": redaction,
        "generated_at": generated_at(report),
        "pentrep_version": __version__,
    }
