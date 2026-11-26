"""Redaction engine (PRD §4.4: FR-31, FR-32 overlap rules, FR-37 determinism)."""

from __future__ import annotations

import re

import pytest
from pydantic import ValidationError

from pentrep.models import Redaction as RedactionConfig
from pentrep.models import Report
from pentrep.redact import (
    BUILTIN_NAMES,
    BUILTIN_PATTERNS,
    Pattern,
    RedactionSummary,
    Redactor,
    build_patterns,
    format_summary,
    luhn_valid,
    redact_report,
    redact_text,
    token,
)


def _p(name: str, regex: str, priority: int) -> Pattern:
    return Pattern(name, re.compile(regex), priority)


def test_token_format() -> None:
    assert token("EMAIL") == "[REDACTED:EMAIL]"


def test_whole_match_is_replaced() -> None:
    result = redact_text("id 1234 and 5678", [_p("NUM", r"\d{4}", 1)])
    assert result.text == "id [REDACTED:NUM] and [REDACTED:NUM]"
    assert result.names == ("NUM", "NUM")


def test_value_group_replaces_only_the_value() -> None:
    result = redact_text("password=hunter2&x=1", [_p("SECRET", r"password=(?P<value>[^&]+)", 1)])
    assert result.text == "password=[REDACTED:SECRET]&x=1"


def test_alternative_value_groups() -> None:
    pattern = _p("SS", r"k=(?:\"(?P<value>[^\"]*)\"|(?P<value2>\w+))", 1)
    assert redact_text('k="a b" k=c', [pattern]).text == 'k="[REDACTED:SS]" k=[REDACTED:SS]'


def test_empty_or_missing_value_is_not_redacted() -> None:
    pattern = _p("SS", r"k=(?P<value>\w*)|zz", 1)
    result = redact_text("k= zz", [pattern])
    assert result.text == "k= [REDACTED:SS]"
    assert redact_text("", [_p("ANY", r".*", 1)]).names == ()


def test_check_function_filters_matches() -> None:
    even = Pattern("EVEN", re.compile(r"\d+"), 1, check=lambda v: int(v) % 2 == 0)
    assert redact_text("1 2 3 4", [even]).text == "1 [REDACTED:EVEN] 3 [REDACTED:EVEN]"


def test_finder_function_supplies_spans() -> None:
    finder = Pattern("XX", re.compile("unused"), 1, finder=lambda text: iter([(0, 2), (4, 5)]))
    assert redact_text("abcdef", [finder]).text == "[REDACTED:XX]cd[REDACTED:XX]f"


def test_higher_priority_wins_on_overlap() -> None:
    patterns = [_p("LOW", r"abc\w+", 2), _p("HIGH", r"cde", 1)]
    result = redact_text("abcdefg", patterns)
    assert result.text == "ab[REDACTED:HIGH]fg"
    assert result.names == ("HIGH",)


def test_equal_priority_earliest_then_longest_wins() -> None:
    patterns = [_p("AA", r"bcd", 1), _p("BB", r"abc", 1), _p("CC", r"abcde", 1)]
    assert redact_text("abcdef", patterns).text == "[REDACTED:CC]f"


def test_each_character_is_redacted_at_most_once() -> None:
    patterns = [_p("AA", r"\w+", 1), _p("BB", r"\w", 2)]
    result = redact_text("ab cd", patterns)
    assert result.text == "[REDACTED:AA] [REDACTED:AA]"
    assert result.text.count("REDACTED") == 2


def test_non_overlapping_matches_of_different_patterns_all_apply() -> None:
    patterns = [_p("BB", r"bb", 2), _p("AA", r"aa", 1)]
    result = redact_text("bb aa bb", patterns)
    assert result.text == "[REDACTED:BB] [REDACTED:AA] [REDACTED:BB]"
    assert result.names == ("BB", "AA", "BB")  # in text order


def test_allowlisted_value_is_kept_not_counted_and_protects_its_span() -> None:
    patterns = [_p("EMAIL", r"\S+@\S+", 1), _p("WORD", r"example", 2)]
    result = redact_text("a@example.test b@example.test", patterns, allowlist={"a@example.test"})
    assert result.text == "a@example.test [REDACTED:EMAIL]"
    assert result.names == ("EMAIL",)


def test_allowlist_compares_the_redacted_part_only() -> None:
    pattern = _p("SECRET", r"pw=(?P<value>\w+)", 1)
    assert redact_text("pw=demo pw=real", [pattern], allowlist={"demo"}).text == (
        "pw=demo pw=[REDACTED:SECRET]"
    )


def test_redaction_is_deterministic() -> None:
    patterns = [_p("AA", r"a+", 1), _p("BB", r"[ab]+", 1), _p("CC", r"b", 2)]
    text = "aab bba abab " * 50
    first = redact_text(text, patterns)
    assert all(redact_text(text, list(reversed(patterns))) == first for _ in range(5))


def test_redacting_twice_is_idempotent_for_tokens() -> None:
    patterns = [_p("NUM", r"\d+", 1)]
    once = redact_text("pin 1234", patterns).text
    assert redact_text(once, patterns).text == once


@pytest.mark.parametrize("bad", ["", "lower", "1ABC", "A", "A" * 33])
def test_pattern_names_are_validated(bad: str) -> None:
    with pytest.raises(ValueError, match="pattern name"):
        Pattern(bad, re.compile("x"), 1)


@pytest.mark.parametrize(
    ("number", "valid"),
    [("4111111111111111", True), ("4111111111111112", False), ("378282246310005", True),
     ("0000000000000", True), ("79927398713", True), ("79927398710", False)],
)  # fmt: skip
def test_luhn(number: str, valid: bool) -> None:
    assert luhn_valid(number) is valid


def test_builtin_patterns_are_in_prd_priority_order() -> None:
    assert [(p.name, p.priority) for p in BUILTIN_PATTERNS] == [
        ("PRIVATE_KEY", 1), ("JWT", 2), ("BEARER", 3), ("COOKIE", 4), ("AWS_KEY", 5),
        ("SECRET", 6), ("CARD", 7), ("EMAIL", 8), ("PRIVATE_IP", 9),
    ]  # fmt: skip


def test_secret_beats_email_on_overlap() -> None:
    text = "password=admin@acme.example"
    assert redact_text(text, BUILTIN_PATTERNS).text == "password=[REDACTED:SECRET]"


# --- Configuration: custom patterns, allowlist, E304 (M4.5) ---------------------------------------


def _config(**fields: object) -> RedactionConfig:
    return RedactionConfig.model_validate(fields)


def _e304(fields: dict[str, object]) -> list[tuple[str, tuple[int | str, ...]]]:
    with pytest.raises(ValidationError) as exc_info:
        RedactionConfig.model_validate(fields)
    return [(e["type"], tuple(e["loc"])) for e in exc_info.value.errors()]


@pytest.mark.parametrize("name", ["acme_id", "1ACME", "A", "A" * 33, "ACME-ID", ""])
def test_invalid_custom_pattern_name_is_e304(name: str) -> None:
    errors = _e304({"custom_patterns": [{"name": name, "regex": "x"}]})
    assert errors == [("E304", ("custom_patterns", 0, "name"))]


@pytest.mark.parametrize("name", sorted(BUILTIN_NAMES))
def test_custom_pattern_cannot_reuse_a_builtin_name(name: str) -> None:
    with pytest.raises(ValidationError, match="built-in"):
        RedactionConfig.model_validate({"custom_patterns": [{"name": name, "regex": "x"}]})


@pytest.mark.parametrize("regex", ["(", "[a-", "(?P<value>x", "*x"])
def test_invalid_regex_is_e304_with_the_re_error(regex: str) -> None:
    with pytest.raises(ValidationError) as exc_info:
        RedactionConfig.model_validate({"custom_patterns": [{"name": "ACME_ID", "regex": regex}]})
    [error] = exc_info.value.errors()
    assert (error["type"], error["loc"]) == ("E304", ("custom_patterns", 0, "regex"))
    assert str(error["msg"]).startswith("invalid regex: ")
    assert error["ctx"]["hint"]


def test_valid_names_and_limits() -> None:
    config = _config(
        custom_patterns=[{"name": "ACME_EMPLOYEE_ID", "regex": r"ACME-\d{6}"}] * 50,
        allowlist=["x"] * 200,
    )
    assert len(config.custom_patterns) == 50


def test_custom_patterns_run_after_builtins() -> None:
    patterns = build_patterns(_config(custom_patterns=[{"name": "DOMAIN", "regex": r"acme\.\w+"}]))
    assert [p.name for p in patterns[:9]] == [p.name for p in BUILTIN_PATTERNS]
    assert patterns[-1].name == "DOMAIN"
    assert patterns[-1].priority > max(p.priority for p in BUILTIN_PATTERNS)
    # The e-mail (built-in) wins over the overlapping custom match.
    assert redact_text("bob@acme.example and acme.test", patterns).text == (
        "[REDACTED:EMAIL] and [REDACTED:DOMAIN]"
    )


def test_custom_pattern_with_and_without_value_group() -> None:
    config = _config(
        custom_patterns=[
            {"name": "ACME_EMPLOYEE_ID", "regex": r"ACME-\d{6}"},
            {"name": "TICKET", "regex": r"ticket #(?P<value>\d+)"},
        ]
    )
    result = Redactor(config).redact("staff ACME-104233 opened ticket #4711")
    assert result.text == "staff [REDACTED:ACME_EMPLOYEE_ID] opened ticket #[REDACTED:TICKET]"


def test_custom_patterns_are_compiled_once_and_in_order() -> None:
    config = _config(
        custom_patterns=[{"name": "AA_X", "regex": "a"}, {"name": "BB_X", "regex": "b"}]
    )
    patterns = build_patterns(config)
    assert [p.name for p in patterns[9:]] == ["AA_X", "BB_X"]
    assert patterns[9].priority < patterns[10].priority


def test_allowlisted_values_are_kept_and_not_counted() -> None:
    config = _config(allowlist=["attacker@example-security.test"])
    result = Redactor(config).redact("from attacker@example-security.test to victim@acme.example")
    assert result.text == "from attacker@example-security.test to [REDACTED:EMAIL]"
    assert result.names == ("EMAIL",)


# --- redact_report (M4.6, FR-30) ---------------------------------------------------------------


def _report(redaction: dict[str, object] | None = None) -> Report:
    finding = {
        "id": "PT-001",
        "title": "Leaky finding title",
        "cvss_vector": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H",
        "affected_assets": ["https://admin@acme.example/login"],
        "description": "Contact admin@acme.example about this issue.",
        "impact": "Attackers reach 10.0.0.5 and every other host.",
        "steps_to_reproduce": ["Log in with password=hunter2", "Open the page."],
        "evidence": [
            {"type": "http", "caption": "Request", "content": "Cookie: sid=abc\n\nok"},
            {"type": "image", "caption": "Screenshot", "path": "evidence/a.png"},
            {"type": "text", "caption": "Log", "content": "user bob@acme.example"},
        ],
        "remediation": "Rotate the key AKIAIOSFODNN7EXAMPLE immediately.",
        "references": ["https://example.test/?email=a@acme.example"],
    }
    clean = {
        **finding,
        "id": "PT-002",
        "description": "A clean description without secrets.",
        "impact": "A clean impact statement, no secrets.",
        "steps_to_reproduce": ["Nothing secret."],
        "evidence": [],
        "remediation": "A clean remediation, no secrets here.",
    }
    data: dict[str, object] = {
        "schema_version": 1,
        "engagement": {
            "title": "Engagement for admin@acme.example",
            "client": {"name": "Acme"},
            "testers": [{"name": "Alex", "email": "alex@example.test"}],
            "start_date": "2026-11-02",
            "end_date": "2026-11-13",
            "scope": {"in_scope": [{"asset": "10.0.0.0", "type": "cidr"}]},
            "methodology": "Grey-box testing against 10.0.0.5 internal host.",
        },
        "findings": [finding, clean],
    }
    if redaction is not None:
        data["redaction"] = redaction
    return Report.model_validate(data)


def test_redacts_evidence_and_steps_by_default() -> None:
    redacted, summary = redact_report(_report())
    finding = redacted.findings[0]
    assert finding.steps_to_reproduce == [
        "Log in with password=[REDACTED:SECRET]",
        "Open the page.",
    ]
    assert finding.evidence[0].content == "Cookie: sid=[REDACTED:COOKIE]\n\nok"  # type: ignore[union-attr]
    assert finding.evidence[2].content == "user [REDACTED:EMAIL]"  # type: ignore[union-attr]
    # Not redacted unless apply_to_all_text is set:
    assert finding.description == "Contact admin@acme.example about this issue."
    assert finding.remediation.startswith("Rotate the key AKIA")
    assert summary.counts == (("SECRET", 1), ("COOKIE", 1), ("EMAIL", 1))
    assert summary.values == 3
    assert summary.findings == 1
    assert summary.images_not_scanned == 1
    assert summary.enabled is True


def test_never_redacts_metadata_titles_assets_or_references() -> None:
    report = _report({"apply_to_all_text": True})
    redacted, _ = redact_report(report)
    assert redacted.engagement == report.engagement
    assert redacted.findings[0].title == report.findings[0].title
    assert redacted.findings[0].affected_assets == report.findings[0].affected_assets
    assert redacted.findings[0].references == report.findings[0].references
    assert redacted.findings[0].evidence[0].caption == "Request"


def test_apply_to_all_text_covers_description_impact_and_remediation() -> None:
    redacted, summary = redact_report(_report({"apply_to_all_text": True}))
    finding = redacted.findings[0]
    assert finding.description == "Contact [REDACTED:EMAIL] about this issue."
    assert finding.impact == "Attackers reach [REDACTED:PRIVATE_IP] and every other host."
    assert finding.remediation == "Rotate the key [REDACTED:AWS_KEY] immediately."
    # counts follow the report order: description, impact, steps, evidence, remediation
    assert summary.counts == (
        ("EMAIL", 2), ("PRIVATE_IP", 1), ("SECRET", 1), ("COOKIE", 1), ("AWS_KEY", 1)
    )  # fmt: skip
    assert summary.values == 6


def test_disabled_redaction_returns_the_report_unchanged() -> None:
    report = _report({"enabled": False})
    redacted, summary = redact_report(report)
    assert redacted == report
    assert summary.enabled is False
    assert summary.values == 0
    assert summary.counts == ()


def test_enabled_can_be_overridden() -> None:
    report = _report()
    redacted, summary = redact_report(report, enabled=False)
    assert redacted == report
    assert not summary.enabled


def test_redact_report_does_not_change_the_input_and_is_deterministic() -> None:
    report = _report({"apply_to_all_text": True})
    before = report.model_dump()
    first = redact_report(report)
    assert report.model_dump() == before
    assert redact_report(report) == first
    assert redact_report(first[0])[0] == first[0]  # tokens are not redacted again


def test_redacted_report_keeps_cvss() -> None:
    redacted, _ = redact_report(_report())
    assert redacted.findings[0].cvss is not None
    assert redacted.findings[0].cvss.base_score == 9.8


# --- Summary text (M4.7, FR-35) ----------------------------------------------------------------


def _summary(
    counts: tuple[tuple[str, int], ...], findings: int, images: int = 0
) -> RedactionSummary:
    return RedactionSummary(True, counts, findings, images)


def test_summary_matches_fr35() -> None:
    summary = _summary(
        (("SECRET", 1), ("COOKIE", 1), ("JWT", 1), ("EMAIL", 1), ("ACME_EMPLOYEE_ID", 1),
         ("PRIVATE_IP", 1)),
        findings=2,
        images=1,
    )  # fmt: skip
    assert format_summary(summary) == [
        "Redacted 6 values in 2 findings: SECRET×1, COOKIE×1, JWT×1, EMAIL×1, "
        "ACME_EMPLOYEE_ID×1, PRIVATE_IP×1",
        "Note: 1 image evidence item was not scanned (image redaction is not supported in v0.1)",
    ]


def test_summary_singular_and_plural() -> None:
    assert format_summary(_summary((("EMAIL", 1),), findings=1)) == [
        "Redacted 1 value in 1 finding: EMAIL×1"
    ]
    assert format_summary(_summary((("EMAIL", 3),), findings=1, images=2))[1] == (
        "Note: 2 image evidence items were not scanned (image redaction is not supported in v0.1)"
    )


def test_summary_without_redactions() -> None:
    assert format_summary(_summary((), findings=0)) == ["No values were redacted"]


def test_summary_when_disabled() -> None:
    lines = format_summary(RedactionSummary(False, (), 0, 1))
    assert lines == ["Redaction is disabled: the report is an UNREDACTED DRAFT"]


def test_preview_wording() -> None:
    summary = _summary((("SECRET", 2), ("EMAIL", 1)), findings=1, images=1)
    assert format_summary(summary, preview=True) == [
        "Redaction preview: 3 values in 1 finding would be redacted: SECRET×2, EMAIL×1",
        "Note: 1 image evidence item was not scanned (image redaction is not supported in v0.1)",
    ]
    assert format_summary(_summary((), 0), preview=True) == [
        "Redaction preview: no values would be redacted"
    ]
    assert format_summary(RedactionSummary(False, (), 0, 0), preview=True) == [
        "Redaction preview: redaction is disabled (redaction.enabled: false)"
    ]


def test_summary_never_contains_original_values() -> None:
    _, summary = redact_report(_report({"apply_to_all_text": True}))
    text = "\n".join(format_summary(summary) + format_summary(summary, preview=True))
    for secret in ("hunter2", "abc", "acme.example", "10.0.0.5", "AKIAIOSFODNN7EXAMPLE"):
        assert secret not in text
