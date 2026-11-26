"""Pydantic models for findings.yaml (PRD §4.2.2)."""

from __future__ import annotations

import copy
import datetime as dt
from typing import Any

import pytest
from pydantic import BaseModel, ValidationError

from pentrep import models
from pentrep.models import (
    Asset,
    Branding,
    Client,
    Engagement,
    Finding,
    Report,
    Scope,
    cross_checks,
)

# Test data is free-form YAML-like input, so Any is the honest type here.
Data = dict[str, Any]


def _errors(model: type[BaseModel], data: object) -> list[tuple[str, tuple[int | str, ...]]]:
    """Return ``(error type, loc)`` pairs, or ``[]`` if ``data`` is valid."""
    try:
        model.model_validate(data)
    except ValidationError as exc:
        return [(e["type"], tuple(e["loc"])) for e in exc.errors()]
    return []


@pytest.fixture
def engagement() -> Data:
    return {
        "title": "Web App Test",
        "client": {"name": "Acme Corp", "contact": "Jane Doe"},
        "testers": [{"name": "Alex", "email": "alex@example-security.test", "role": "Lead"}],
        "start_date": dt.date(2026, 11, 2),
        "end_date": dt.date(2026, 11, 13),
        "report_date": dt.date(2026, 11, 20),
        "scope": {"in_scope": [{"asset": "https://portal.acme.example", "type": "url"}]},
        "methodology": "OWASP WSTG v4.2, grey-box, two accounts.",
    }


# --- Engagement ---------------------------------------------------------------------------


def test_valid_engagement_and_defaults(engagement: Data) -> None:
    eng = Engagement.model_validate(engagement)
    assert eng.report_version == "1.0"
    assert eng.classification == "CONFIDENTIAL"
    assert eng.executive_summary is None
    assert eng.scope.out_of_scope == []
    assert eng.client.contact == "Jane Doe"
    assert eng.testers[0].role == "Lead"


@pytest.mark.parametrize(
    ("model", "data"),
    [
        (Client, {"name": "Acme", "nmae": "x"}),
        (models.Tester, {"name": "Alex", "phone": "1"}),
        (Asset, {"asset": "a", "type": "url", "note": "x"}),
        (Scope, {"in_scope": [{"asset": "a", "type": "url"}], "extra": 1}),
        (Branding, {"logo_path": "x.png"}),
    ],
)
def test_unknown_fields_are_forbidden(model: type[BaseModel], data: Data) -> None:
    assert [t for t, _ in _errors(model, data)] == ["extra_forbidden"]


def test_engagement_forbids_unknown_fields(engagement: Data) -> None:
    engagement["titel"] = "x"
    assert _errors(Engagement, engagement) == [("extra_forbidden", ("titel",))]


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("title", "Test"),
        ("title", "x" * 151),
        ("title", 12345),
        ("report_version", "1"),
        ("report_version", "v1.0"),
        ("classification", "x" * 41),
        ("methodology", "too short"),
        ("executive_summary", 5),
        ("testers", []),
        ("testers", [{"name": "A"}] * 11),
        ("start_date", 20261102),
        ("start_date", "02/11/2026"),
    ],
)
def test_engagement_constraints(engagement: Data, field: str, value: object) -> None:
    engagement[field] = value
    errors = _errors(Engagement, engagement)
    assert errors
    assert all(loc[0] == field for _, loc in errors)


def test_title_bounds_are_inclusive(engagement: Data) -> None:
    for title in ("x" * 5, "x" * 150):
        engagement["title"] = title
        assert _errors(Engagement, engagement) == []


def test_dates_accept_iso_strings(engagement: Data) -> None:
    engagement["start_date"] = "2026-11-02"
    assert Engagement.model_validate(engagement).start_date == dt.date(2026, 11, 2)


def test_datetime_is_not_a_date(engagement: Data) -> None:
    engagement["start_date"] = dt.datetime(2026, 11, 2, 10, 0)
    assert _errors(Engagement, engagement)[0][1] == ("start_date",)


@pytest.mark.parametrize("missing", ["title", "client", "testers", "start_date", "scope"])
def test_required_engagement_fields(engagement: Data, missing: str) -> None:
    del engagement[missing]
    assert ("missing", (missing,)) in _errors(Engagement, engagement)


def test_end_date_before_start_date_is_e105(engagement: Data) -> None:
    engagement["end_date"] = dt.date(2026, 11, 1)
    assert _errors(Engagement, engagement) == [("E105", ("end_date",))]


def test_end_date_equal_to_start_date_is_valid(engagement: Data) -> None:
    engagement["end_date"] = engagement["start_date"]
    assert _errors(Engagement, engagement) == []


def test_e105_not_raised_when_start_date_is_invalid(engagement: Data) -> None:
    engagement["start_date"] = "nope"
    assert [loc for _, loc in _errors(Engagement, engagement)] == [("start_date",)]


def test_report_date_defaults_to_source_date_epoch(
    engagement: Data, monkeypatch: pytest.MonkeyPatch
) -> None:
    del engagement["report_date"]
    monkeypatch.setenv("SOURCE_DATE_EPOCH", "1785542400")  # 2026-08-01T00:00:00Z
    assert Engagement.model_validate(engagement).report_date == dt.date(2026, 8, 1)


def test_report_date_defaults_to_today(engagement: Data, monkeypatch: pytest.MonkeyPatch) -> None:
    del engagement["report_date"]
    monkeypatch.delenv("SOURCE_DATE_EPOCH", raising=False)
    assert Engagement.model_validate(engagement).report_date == dt.date.today()


def test_invalid_source_date_epoch_is_ignored(
    engagement: Data, monkeypatch: pytest.MonkeyPatch
) -> None:
    del engagement["report_date"]
    monkeypatch.setenv("SOURCE_DATE_EPOCH", "not-a-number")
    assert Engagement.model_validate(engagement).report_date == dt.date.today()


# --- Client, Tester, Asset, Scope ------------------------------------------------------------


@pytest.mark.parametrize(
    ("data", "loc"),
    [
        ({"name": ""}, ("name",)),
        ({"name": "x" * 101}, ("name",)),
        ({"name": "Acme", "contact": "x" * 151}, ("contact",)),
    ],
)
def test_client_constraints(data: Data, loc: tuple[str, ...]) -> None:
    assert [error_loc for _, error_loc in _errors(Client, data)] == [loc]


@pytest.mark.parametrize("email", ["not-an-email", "a@b", "a b@c.test", "@example.test"])
def test_tester_email_must_be_valid(email: str) -> None:
    assert _errors(models.Tester, {"name": "Alex", "email": email})[0][1] == ("email",)


def test_tester_email_is_optional() -> None:
    assert _errors(models.Tester, {"name": "Alex"}) == []


@pytest.mark.parametrize(
    "asset_type", ["url", "ip", "cidr", "hostname", "api", "mobile_app", "other"]
)
def test_asset_types(asset_type: str) -> None:
    assert _errors(Asset, {"asset": "x", "type": asset_type}) == []


def test_asset_type_must_be_known() -> None:
    assert _errors(Asset, {"asset": "x", "type": "domain"}) == [("literal_error", ("type",))]


def test_scope_needs_one_in_scope_asset() -> None:
    assert _errors(Scope, {"in_scope": []}) == [("too_short", ("in_scope",))]


# --- Branding ------------------------------------------------------------------------------


def test_branding_defaults() -> None:
    branding = Branding.model_validate({})
    assert branding.accent_color == "#1F4E79"
    assert branding.company_name is None
    assert branding.logo is None


@pytest.mark.parametrize(
    ("data", "loc"),
    [
        ({"accent_color": "1F4E79"}, ("accent_color",)),
        ({"accent_color": "#1F4E7"}, ("accent_color",)),
        ({"accent_color": "#GGGGGG"}, ("accent_color",)),
        ({"company_name": "x" * 81}, ("company_name",)),
        ({"logo": 5}, ("logo",)),
    ],
)
def test_branding_constraints(data: Data, loc: tuple[str, ...]) -> None:
    assert [error_loc for _, error_loc in _errors(Branding, data)] == [loc]


def test_models_do_not_mutate_input(engagement: Data) -> None:
    before = copy.deepcopy(engagement)
    Engagement.model_validate(engagement)
    assert engagement == before


# --- Finding & Evidence (M2.4) ----------------------------------------------------------------


@pytest.fixture
def finding() -> Data:
    return {
        "id": "PT-001",
        "title": "SQL Injection in Login",
        "cvss_vector": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H",
        "affected_assets": ["https://portal.acme.example/api/v1/login"],
        "description": "The username field is concatenated into SQL.",
        "impact": "An attacker can bypass authentication entirely.",
        "steps_to_reproduce": ["Send the request.", "Observe the session."],
        "evidence": [{"type": "text", "caption": "Response", "content": "HTTP/1.1 200 OK"}],
        "remediation": "Use parameterised queries for all database access.",
    }


def test_valid_finding_and_defaults(finding: Data) -> None:
    del finding["evidence"]
    parsed = Finding.model_validate(finding)
    assert parsed.status == "open"
    assert parsed.cwe == []
    assert parsed.evidence == []
    assert parsed.references == []
    assert parsed.severity is None


@pytest.mark.parametrize("finding_id", ["PT-001", "AB-1234", "ABCDE-999"])
def test_finding_id_pattern_accepts(finding: Data, finding_id: str) -> None:
    finding["id"] = finding_id
    assert _errors(Finding, finding) == []


@pytest.mark.parametrize(
    "finding_id", ["pt-001", "P-001", "ABCDEF-001", "PT-01", "PT-12345", "PT001"]
)
def test_finding_id_pattern_rejects(finding: Data, finding_id: str) -> None:
    finding["id"] = finding_id
    assert _errors(Finding, finding) == [("string_pattern_mismatch", ("id",))]


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("title", "SQLi"),
        ("title", "x" * 121),
        ("status", "fixed"),
        ("cwe", [0]),
        ("cwe", [10000]),
        ("cwe", ["89"]),
        ("affected_assets", []),
        ("affected_assets", [""]),
        ("description", "short"),
        ("impact", "short"),
        ("remediation", "short"),
        ("steps_to_reproduce", []),
        ("steps_to_reproduce", "Send the request."),
        ("evidence", [{"type": "text", "caption": "ok!", "content": "x"}] * 31),
        ("references", ["ftp://example.test/x"]),
        ("references", ["javascript:alert(1)"]),
        ("references", ["https://exa mple.test"]),
        ("cvss_vector", 9.8),
        ("cvss_vector", ""),
        ("severity", "high"),
    ],
)
def test_finding_constraints(finding: Data, field: str, value: object) -> None:
    finding[field] = value
    errors = _errors(Finding, finding)
    assert errors
    assert all(loc[0] == field for _, loc in errors)


@pytest.mark.parametrize("status", ["open", "remediated", "risk_accepted"])
def test_finding_statuses(finding: Data, status: str) -> None:
    finding["status"] = status
    assert _errors(Finding, finding) == []


def test_references_accept_http_and_https(finding: Data) -> None:
    finding["references"] = ["http://example.test/a", "https://owasp.org/x?y=1#z"]
    assert Finding.model_validate(finding).references == finding["references"]


def test_informational_finding_without_vector(finding: Data) -> None:
    del finding["cvss_vector"]
    finding["severity"] = "informational"
    assert Finding.model_validate(finding).severity == "informational"


@pytest.mark.parametrize(
    "evidence",
    [
        {"type": "text", "caption": "Log", "content": "x", "language": "bash"},
        {"type": "http", "caption": "Req", "content": "GET / HTTP/1.1"},
        {"type": "image", "caption": "Screenshot", "path": "evidence/a.png"},
    ],
)
def test_valid_evidence_types(finding: Data, evidence: Data) -> None:
    finding["evidence"] = [evidence]
    parsed = Finding.model_validate(finding)
    assert parsed.evidence[0].type == evidence["type"]


@pytest.mark.parametrize(
    ("evidence", "expected"),
    [
        ({"type": "image", "caption": "Shot", "path": "a.png", "content": "x"}, "content"),
        ({"type": "text", "caption": "Log", "content": "x", "path": "a.png"}, "path"),
        ({"type": "http", "caption": "Req", "content": "x", "language": "http"}, "language"),
    ],
)
def test_fields_not_allowed_for_evidence_type(finding: Data, evidence: Data, expected: str) -> None:
    finding["evidence"] = [evidence]
    errors = _errors(Finding, finding)
    assert errors == [("extra_forbidden", ("evidence", 0, evidence["type"], expected))]


@pytest.mark.parametrize(
    ("evidence", "error"),
    [
        ({"caption": "Log", "content": "x"}, "union_tag_not_found"),
        ({"type": "video", "caption": "Log", "content": "x"}, "union_tag_invalid"),
        ({"type": "text", "caption": "Lo", "content": "x"}, "string_too_short"),
        ({"type": "text", "caption": "Log"}, "missing"),
        ({"type": "image", "caption": "Shot"}, "missing"),
        ({"type": "text", "caption": "Log", "content": "x" * (200 * 1024 + 1)}, "string_too_long"),
    ],
)
def test_evidence_errors(finding: Data, evidence: Data, error: str) -> None:
    finding["evidence"] = [evidence]
    assert [t for t, _ in _errors(Finding, finding)] == [error]


# --- Report, schema_version (E106), Redaction ---------------------------------------------------


@pytest.fixture
def report(engagement: Data, finding: Data) -> Data:
    return {"schema_version": 1, "engagement": engagement, "findings": [finding]}


def test_valid_report_and_defaults(report: Data) -> None:
    parsed = Report.model_validate(report)
    assert parsed.branding.accent_color == "#1F4E79"
    assert parsed.redaction.enabled is True
    assert parsed.redaction.apply_to_all_text is False
    assert parsed.redaction.custom_patterns == []
    assert parsed.redaction.allowlist == []


@pytest.mark.parametrize("version", [2, 0, "1", True, 1.0])
def test_unsupported_schema_version_is_e106(report: Data, version: object) -> None:
    report["schema_version"] = version
    assert _errors(Report, report) == [("E106", ("schema_version",))]


def test_e106_message_names_supported_versions(report: Data) -> None:
    report["schema_version"] = 2
    with pytest.raises(ValidationError, match=r"supports schema_version: 1"):
        Report.model_validate(report)


@pytest.mark.parametrize("count", [0, 501])
def test_findings_count_limits(report: Data, count: int) -> None:
    report["findings"] = [report["findings"][0]] * count
    assert [loc for _, loc in _errors(Report, report)] == [("findings",)]


def test_redaction_structure(report: Data) -> None:
    report["redaction"] = {
        "enabled": False,
        "apply_to_all_text": True,
        "custom_patterns": [{"name": "ACME_ID", "regex": r"ACME-\d{6}"}],
        "allowlist": ["attacker@example-security.test"],
    }
    parsed = Report.model_validate(report)
    assert parsed.redaction.custom_patterns[0].name == "ACME_ID"


@pytest.mark.parametrize(
    "redaction",
    [
        {"enabled": "yes"},
        {"custom_patterns": [{"name": "X"}]},
        {"custom_patterns": [{"name": "AB", "regex": "x"}] * 51},
        {"allowlist": ["x"] * 201},
        {"allow_list": []},
    ],
)
def test_redaction_constraints(report: Data, redaction: Data) -> None:
    report["redaction"] = redaction
    assert all(loc[0] == "redaction" for _, loc in _errors(Report, report))
    assert _errors(Report, report)


# --- cross_checks: E104, E206 ----------------------------------------------------------------


def _issues(data: object) -> list[tuple[str, tuple[int | str, ...]]]:
    return [(i.code.value, i.loc) for i in cross_checks(data)]


def test_cross_checks_clean_report(report: Data) -> None:
    assert _issues(report) == []


def test_duplicate_ids_are_e104(report: Data, finding: Data) -> None:
    report["findings"] = [finding, {**finding, "id": "PT-002"}, finding, finding]
    assert _issues(report) == [("E104", ("findings", 2, "id")), ("E104", ("findings", 3, "id"))]
    assert "first used in findings[0]" in cross_checks(report)[0].message


def test_both_vector_and_severity_is_e206(report: Data, finding: Data) -> None:
    finding["severity"] = "informational"
    issues = cross_checks(report)
    assert [(i.code.value, i.loc, i.at_key) for i in issues] == [
        ("E206", ("findings", 0, "severity"), True)
    ]
    assert "both" in issues[0].message


def test_neither_vector_nor_severity_is_e206(report: Data, finding: Data) -> None:
    del finding["cvss_vector"]
    issues = cross_checks(report)
    assert _issues(report) == [("E206", ("findings", 0))]
    assert issues[0].hint


@pytest.mark.parametrize(
    "data",
    [None, [], {"findings": "x"}, {"findings": [1, None, {"id": ["x"], "cvss_vector": "v"}]}],
)
def test_cross_checks_tolerate_malformed_input(data: object) -> None:
    assert _issues(data) == []
