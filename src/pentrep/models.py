"""Pydantic models for ``findings.yaml`` (PRD §4.2.2).

Models are strict (no type coercion) and forbid unknown keys. Custom rule violations are raised
as :class:`PydanticCustomError` whose ``type`` is the pentrep error code (for example ``E105``),
so the loader can map them to diagnostics.
"""

from __future__ import annotations

import datetime as dt
import os
from dataclasses import dataclass
from typing import Annotated, Final, Literal

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, ValidationInfo, field_validator
from pydantic_core import PydanticCustomError

from pentrep.diagnostics import ErrorCode

ISO_DATE_LENGTH: Final = len("YYYY-MM-DD")


def _parse_date(value: object) -> object:
    """Accept ``date`` objects and ``YYYY-MM-DD`` strings; reject date-times."""
    if isinstance(value, dt.datetime):
        raise ValueError("expected a date (YYYY-MM-DD), not a date and time")
    if isinstance(value, str) and len(value) == ISO_DATE_LENGTH:
        try:
            return dt.date.fromisoformat(value)
        except ValueError:
            return value
    return value


IsoDate = Annotated[dt.date, BeforeValidator(_parse_date)]


def default_report_date() -> dt.date:
    """Today, or the UTC date of ``SOURCE_DATE_EPOCH`` when it is set to an integer (FR-49)."""
    epoch = os.environ.get("SOURCE_DATE_EPOCH", "").strip()
    if epoch.isdigit():
        return dt.datetime.fromtimestamp(int(epoch), tz=dt.UTC).date()
    return dt.datetime.now(tz=dt.UTC).astimezone().date()


class StrictModel(BaseModel):
    """Base for all schema models: strict types, unknown keys forbidden, immutable."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


class Client(StrictModel):
    """The client the engagement was performed for."""

    name: str = Field(min_length=1, max_length=100)
    contact: str | None = Field(default=None, max_length=150)


class Tester(StrictModel):
    """A member of the testing team."""

    name: str = Field(min_length=1, max_length=100)
    email: str | None = Field(default=None, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$", max_length=254)
    role: str | None = Field(default=None, max_length=100)


AssetType = Literal["url", "ip", "cidr", "hostname", "api", "mobile_app", "other"]


class Asset(StrictModel):
    """An in-scope or out-of-scope target."""

    asset: str = Field(min_length=1, max_length=500)
    type: AssetType
    notes: str | None = Field(default=None, max_length=500)


class Scope(StrictModel):
    """What was (and was not) tested."""

    in_scope: list[Asset] = Field(min_length=1)
    out_of_scope: list[Asset] = Field(default_factory=list)


class Engagement(StrictModel):
    """Engagement metadata shown on the cover and in document control."""

    title: str = Field(min_length=5, max_length=150)
    client: Client
    testers: list[Tester] = Field(min_length=1, max_length=10)
    start_date: IsoDate
    end_date: IsoDate
    report_date: IsoDate = Field(default_factory=default_report_date)
    report_version: str = Field(default="1.0", pattern=r"^\d+\.\d+$")
    classification: str = Field(default="CONFIDENTIAL", min_length=1, max_length=40)
    scope: Scope
    methodology: str = Field(min_length=20)
    executive_summary: str | None = None

    @field_validator("end_date")
    @classmethod
    def _end_not_before_start(cls, end: dt.date, info: ValidationInfo) -> dt.date:
        start = info.data.get("start_date")
        if isinstance(start, dt.date) and end < start:
            raise PydanticCustomError(
                "E105",
                "end_date {end} is before start_date {start}",
                {"end": end.isoformat(), "start": start.isoformat()},
            )
        return end


class Branding(StrictModel):
    """Optional report branding."""

    company_name: str | None = Field(default=None, min_length=1, max_length=80)
    logo: str | None = Field(default=None, min_length=1)
    accent_color: str = Field(default="#1F4E79", pattern=r"^#[0-9A-Fa-f]{6}$")


NonEmptyStr = Annotated[str, Field(min_length=1)]
HttpUrlStr = Annotated[str, Field(pattern=r"^https?://[^\s/?#]+[^\s]*$", max_length=2000)]
CweId = Annotated[int, Field(ge=1, le=9999)]
MAX_EVIDENCE_CONTENT: Final = 200 * 1024


class _EvidenceBase(StrictModel):
    caption: str = Field(min_length=3, max_length=200)


class TextEvidence(_EvidenceBase):
    """Plain text or code evidence, rendered in a monospaced block."""

    type: Literal["text"]
    content: str = Field(min_length=1, max_length=MAX_EVIDENCE_CONTENT)
    language: str | None = Field(default=None, min_length=1, max_length=40)


class HttpEvidence(_EvidenceBase):
    """An HTTP request/response pair, rendered with HTTP highlighting."""

    type: Literal["http"]
    content: str = Field(min_length=1, max_length=MAX_EVIDENCE_CONTENT)


class ImageEvidence(_EvidenceBase):
    """A screenshot or other image, referenced by a path relative to findings.yaml."""

    type: Literal["image"]
    path: str = Field(min_length=1)


Evidence = Annotated[TextEvidence | HttpEvidence | ImageEvidence, Field(discriminator="type")]
EVIDENCE_TYPES: Final = (TextEvidence, HttpEvidence, ImageEvidence)


class Finding(StrictModel):
    """One vulnerability. The vector/severity rule (E206) is checked by :func:`cross_checks`."""

    id: str = Field(pattern=r"^[A-Z]{2,5}-\d{3,4}$")
    title: str = Field(min_length=5, max_length=120)
    cvss_vector: str | None = Field(default=None, min_length=1)
    severity: Literal["informational"] | None = None
    status: Literal["open", "remediated", "risk_accepted"] = "open"
    cwe: list[CweId] = Field(default_factory=list)
    affected_assets: list[NonEmptyStr] = Field(min_length=1)
    description: str = Field(min_length=20)
    impact: str = Field(min_length=20)
    steps_to_reproduce: list[NonEmptyStr] = Field(min_length=1)
    evidence: list[Evidence] = Field(default_factory=list, max_length=30)
    remediation: str = Field(min_length=20)
    references: list[HttpUrlStr] = Field(default_factory=list)


class CustomPattern(StrictModel):
    """A user-defined redaction pattern (name and regex are checked further in M4, E304)."""

    name: str = Field(min_length=1)
    regex: str = Field(min_length=1)


class Redaction(StrictModel):
    """Redaction settings (PRD §4.4)."""

    enabled: bool = True
    apply_to_all_text: bool = False
    custom_patterns: list[CustomPattern] = Field(default_factory=list, max_length=50)
    allowlist: list[str] = Field(default_factory=list, max_length=200)


SUPPORTED_SCHEMA_VERSIONS: Final = (1,)


class Report(StrictModel):
    """The whole ``findings.yaml`` document. Cross-item rules are in :func:`cross_checks`."""

    schema_version: Literal[1]
    engagement: Engagement
    branding: Branding = Field(default_factory=Branding)
    redaction: Redaction = Field(default_factory=Redaction)
    findings: list[Finding] = Field(min_length=1, max_length=500)

    @field_validator("schema_version", mode="before")
    @classmethod
    def _supported_version(cls, value: object) -> object:
        if type(value) is not int or value not in SUPPORTED_SCHEMA_VERSIONS:
            raise PydanticCustomError(
                "E106",
                "unsupported schema_version {value}; this pentrep release supports "
                "schema_version: {supported}",
                {"value": repr(value), "supported": ", ".join(map(str, SUPPORTED_SCHEMA_VERSIONS))},
            )
        return value


Loc = tuple[str | int, ...]


@dataclass(frozen=True)
class Issue:
    """A rule violation found outside Pydantic validation, located by ``loc``."""

    code: ErrorCode
    loc: Loc
    message: str
    hint: str | None = None
    at_key: bool = False  # point at the mapping key for ``loc`` rather than its value


def cross_checks(data: object) -> list[Issue]:
    """Check rules that span fields or items on raw data: duplicate ids (E104), E206.

    These run on the raw YAML data rather than inside the models, so they are reported even when
    other fields of the same finding are invalid. Malformed input is skipped silently: the
    models report it.
    """
    findings = data.get("findings") if isinstance(data, dict) else None
    if not isinstance(findings, list):
        return []
    issues: list[Issue] = []
    first_index: dict[str, int] = {}
    for index, item in enumerate(findings):
        if not isinstance(item, dict):
            continue
        finding_id = item.get("id")
        if isinstance(finding_id, str):
            if finding_id in first_index:
                issues.append(
                    Issue(
                        ErrorCode.E104,
                        ("findings", index, "id"),
                        f"duplicate finding id '{finding_id}' "
                        f"(first used in findings[{first_index[finding_id]}])",
                        hint="every finding needs a unique id, for example PT-001, PT-002",
                    )
                )
            else:
                first_index[finding_id] = index
        has_vector = "cvss_vector" in item
        has_severity = "severity" in item
        if has_vector and has_severity:
            issues.append(
                Issue(
                    ErrorCode.E206,
                    ("findings", index, "severity"),
                    "both 'cvss_vector' and 'severity' are set; use only one",
                    hint="'severity: informational' is only for findings without a CVSS vector",
                    at_key=True,
                )
            )
        elif not has_vector and not has_severity:
            issues.append(
                Issue(
                    ErrorCode.E206,
                    ("findings", index),
                    "finding needs either 'cvss_vector' or 'severity: informational'",
                    hint="add a CVSS 3.1 vector, e.g. "
                    "'CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H'",
                )
            )
    return issues


JSON_SCHEMA_DIALECT: Final = "https://json-schema.org/draft/2020-12/schema"


def json_schema() -> dict[str, object]:
    """JSON Schema (draft 2020-12) for findings.yaml, generated from :class:`Report` (FR-04)."""
    schema: dict[str, object] = {"$schema": JSON_SCHEMA_DIALECT}
    schema.update(Report.model_json_schema(mode="validation"))
    schema["title"] = "pentrep findings.yaml"  # replaces Pydantic's default title "Report"
    return schema
