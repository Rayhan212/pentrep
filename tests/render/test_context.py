"""Template context (FR-42, FR-43, FR-48, FR-49)."""

from __future__ import annotations

from pathlib import Path

import pytest

from pentrep import __version__
from pentrep.cvss import Severity
from pentrep.loader import load_report
from pentrep.models import Report
from pentrep.redact import redact_report
from pentrep.render.context import build_context

FIXTURES = Path(__file__).parent.parent / "fixtures"
FULL = FIXTURES / "valid" / "full.yaml"


def _report(path: Path = FULL) -> Report:
    result = load_report(path)
    assert result.report is not None, result.diagnostics
    return result.report


def _context(report: Report | None = None, enabled: bool | None = None) -> dict[str, object]:
    report = report or _report()
    redacted, summary = redact_report(report, enabled=enabled)
    return build_context(redacted, summary, FULL.parent)


def test_context_has_the_documented_keys() -> None:
    assert set(_context()) == {
        "engagement", "branding", "findings", "stats", "redaction", "generated_at",
        "pentrep_version",
    }  # fmt: skip


def test_basic_values() -> None:
    ctx = _context()
    assert ctx["pentrep_version"] == __version__
    assert ctx["engagement"].title.startswith("Web Application Penetration Test")  # type: ignore[attr-defined]


def test_findings_are_sorted_views_with_scores() -> None:
    findings = _context()["findings"]
    assert [f.id for f in findings] == ["PT-001", "PT-002"]  # type: ignore[attr-defined]
    first = findings[0]  # type: ignore[index]
    assert first.anchor == "finding-pt-001"
    assert first.severity is Severity.CRITICAL
    assert first.badge == "critical"
    assert first.score_text == "9.8"
    assert first.vector == "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H"
    assert first.impact_score == 5.9
    assert first.exploitability_score == 3.9
    assert first.status_label == "Open"
    assert first.cwe == [(89, "https://cwe.mitre.org/data/definitions/89.html")]


def test_evidence_views_are_numbered_and_images_resolved() -> None:
    evidence = _context()["findings"][0].evidence  # type: ignore[index]
    assert [(e.number, e.type) for e in evidence] == [(1, "http"), (2, "image")]
    assert "[REDACTED:SECRET]" in evidence[0].content
    image = evidence[1]
    assert image.content is None
    assert image.image_path == (FULL.parent / "evidence" / "pt-001-sqlmap.png").resolve()
    assert image.asset_name == "PT-001-2.png"
    assert image.mime == "image/png"


def test_branding_logo_is_resolved() -> None:
    branding = _context()["branding"]
    assert branding.logo_path == (FULL.parent / "assets" / "logo.png").resolve()  # type: ignore[attr-defined]
    assert branding.logo_asset_name == "logo.png"  # type: ignore[attr-defined]
    assert branding.logo_mime == "image/png"  # type: ignore[attr-defined]
    assert branding.accent_color == "#1F4E79"  # type: ignore[attr-defined]


def test_redaction_context() -> None:
    redaction = _context()["redaction"]
    assert redaction.enabled is True  # type: ignore[attr-defined]
    assert redaction.unredacted is False  # type: ignore[attr-defined]
    assert redaction.counts == (  # type: ignore[attr-defined]
        ("SECRET", 1), ("COOKIE", 1), ("JWT", 1), ("EMAIL", 1), ("ACME_EMPLOYEE_ID", 1),
        ("PRIVATE_IP", 1),
    )  # fmt: skip
    assert redaction.lines[0].startswith("Redacted 6 values in 2 findings")  # type: ignore[attr-defined]
    unredacted = _context(enabled=False)["redaction"]
    assert unredacted.unredacted is True  # type: ignore[attr-defined]
    assert unredacted.banner == "UNREDACTED DRAFT \N{EN DASH} DO NOT DISTRIBUTE"  # type: ignore[attr-defined]


def test_generated_at_uses_report_date_or_source_date_epoch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("SOURCE_DATE_EPOCH", raising=False)
    assert _context()["generated_at"] == "2026-11-20"
    monkeypatch.setenv("SOURCE_DATE_EPOCH", "1785542400")
    assert _context()["generated_at"] == "2026-08-01T00:00:00Z"


def _with_statuses(statuses: list[str], informational: bool = False) -> Report:
    data = _report().model_dump(mode="json", exclude_computed_fields=True)
    data["findings"] = [
        {**data["findings"][i % 2], "id": f"PT-{i + 1:03d}", "status": status}
        for i, status in enumerate(statuses)
    ]
    if informational:
        for finding in data["findings"]:
            finding.pop("cvss_vector", None)
            finding["severity"] = "informational"
    return Report.model_validate(data)


@pytest.mark.parametrize(
    ("statuses", "informational", "counts", "risk"),
    [
        (["open", "open"], False, (1, 0, 1, 0, 0, 2), "Critical"),
        (["remediated", "remediated"], False, (1, 0, 1, 0, 0, 2), "None"),
        (["remediated", "open", "risk_accepted"], False, (2, 0, 1, 0, 0, 3), "Medium"),
        (["open", "open"], True, (0, 0, 0, 0, 2, 2), "Informational"),
    ],
    ids=["all-open", "all-remediated", "mixed", "informational-only"],
)
def test_stats_for_fr43_combinations(
    statuses: list[str], informational: bool, counts: tuple[int, ...], risk: str
) -> None:
    stats = _context(_with_statuses(statuses, informational))["stats"]
    assert tuple(stats.counts.values()) == counts  # type: ignore[attr-defined]
    assert stats.overall_risk.label == risk  # type: ignore[attr-defined]


def test_informational_finding_view() -> None:
    finding = _context(_with_statuses(["open"], informational=True))["findings"][0]  # type: ignore[index]
    assert finding.severity is Severity.INFORMATIONAL
    assert finding.score is None
    assert finding.score_text == "N/A"
    assert finding.vector is None
    assert finding.badge == "informational"
