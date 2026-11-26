"""CVSS 3.1 base score calculator (PRD §4.3)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from pentrep.cvss import (
    CvssIssue,
    CvssVector,
    Severity,
    calculate,
    parse_vector,
    roundup,
    weights,
)
from pentrep.diagnostics import ErrorCode


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (4.02, 4.1),
        (4.00, 4.0),
        (4.000000000000001, 4.0),  # float noise must not round up (spec Appendix A)
        (0.0, 0.0),
        (0.01, 0.1),
        (4.1, 4.1),
        (4.10001, 4.2),
        (4.099999999999999, 4.1),
        (9.99, 10.0),
        (10.0, 10.0),
        (6.0067, 6.1),
    ],
)
def test_roundup(value: float, expected: float) -> None:
    assert roundup(value) == expected


def test_roundup_returns_one_decimal_values() -> None:
    for i in range(0, 1001):
        result = roundup(i / 100)
        assert result == round(result, 1)


# --- Parser (M3.2) ------------------------------------------------------------------------------

BASE = "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H"


def _codes(text: str) -> list[str]:
    return [issue.code.value for issue in parse_vector(text).issues]


def _only_issue(text: str) -> CvssIssue:
    issues = parse_vector(text).issues
    assert len(issues) == 1, issues
    return issues[0]


def test_parses_valid_vector() -> None:
    result = parse_vector(BASE)
    assert result.issues == ()
    assert result.vector is not None
    assert result.vector["AV"] == "N"
    assert result.vector["S"] == "U"
    assert result.vector.canonical() == BASE


def test_metrics_in_any_order_and_whitespace_trimmed() -> None:
    result = parse_vector("  CVSS:3.1/A:H/I:H/C:H/S:U/UI:N/PR:N/AC:L/AV:N \n")
    assert result.issues == ()
    assert result.vector is not None
    assert result.vector.canonical() == BASE


@pytest.mark.parametrize("text", ["AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H", "cvss:3.1/AV:N", ""])
def test_missing_prefix_is_e201(text: str) -> None:
    issue = _only_issue(text)
    assert issue.code is ErrorCode.E201
    assert issue.message == "vector must start with 'CVSS:3.1/'"
    assert issue.hint is not None
    assert "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H" in issue.hint


def test_cvss_3_0_prefix_gets_a_hint_to_change_it() -> None:
    issue = _only_issue(BASE.replace("CVSS:3.1/", "CVSS:3.0/"))
    assert issue.code is ErrorCode.E201
    assert issue.message == "CVSS version 3.0 is not supported"
    assert issue.hint == (
        "change the prefix to 'CVSS:3.1/'; the 3.0 and 3.1 base metrics are the same"
    )


@pytest.mark.parametrize("prefix", ["CVSS:4.0/", "CVSS:2/"])
def test_other_versions_are_e201(prefix: str) -> None:
    issue = _only_issue(BASE.replace("CVSS:3.1/", prefix))
    assert issue.code is ErrorCode.E201
    assert issue.message == f"unsupported CVSS version '{prefix[5:-1]}'"


def test_unknown_metric_is_e202() -> None:
    issue = _only_issue(BASE + "/XX:Y")
    assert issue.code is ErrorCode.E202
    assert issue.message == "unknown CVSS metric 'XX'"
    assert issue.hint == "base metrics are AV, AC, PR, UI, S, C, I, A"


def test_metric_names_are_case_sensitive() -> None:
    issue = _only_issue(BASE.replace("AV:N", "av:N"))
    assert issue.code is ErrorCode.E202  # and no E204: the missing AV is not reported twice
    assert issue.hint == "metric names are case-sensitive: did you mean 'AV'?"


@pytest.mark.parametrize("bad", ["/AVN", "//", "/"])
def test_malformed_segments_are_e202(bad: str) -> None:
    text = BASE.replace("/AV:N", bad + "/AV:N") if bad != "/" else BASE + "/"
    issues = parse_vector(text).issues
    assert [i.code for i in issues] == [ErrorCode.E202]
    assert "expected METRIC:VALUE" in issues[0].message


def test_invalid_value_is_e203_with_prd_hint() -> None:
    issue = _only_issue(BASE.replace("AV:N", "AV:X"))
    assert issue.code is ErrorCode.E203
    assert issue.message == "invalid value 'X' for metric 'AV'"
    assert issue.hint == "AV must be one of N (Network), A (Adjacent), L (Local), P (Physical)"


@pytest.mark.parametrize(
    ("metric", "hint"),
    [
        ("AC", "AC must be one of L (Low), H (High)"),
        ("PR", "PR must be one of N (None), L (Low), H (High)"),
        ("UI", "UI must be one of N (None), R (Required)"),
        ("S", "S must be one of U (Unchanged), C (Changed)"),
        ("C", "C must be one of H (High), L (Low), N (None)"),
        ("I", "I must be one of H (High), L (Low), N (None)"),
        ("A", "A must be one of H (High), L (Low), N (None)"),
    ],
)
def test_every_metric_has_a_value_hint(metric: str, hint: str) -> None:
    parts = [p if not p.startswith(f"{metric}:") else f"{metric}:z" for p in BASE.split("/")]
    issue = _only_issue("/".join(parts))
    assert (issue.code, issue.hint) == (ErrorCode.E203, hint)


def test_values_are_case_sensitive() -> None:
    assert _codes(BASE.replace("AV:N", "AV:n")) == ["E203"]


def test_missing_metrics_are_e204() -> None:
    issue = _only_issue("CVSS:3.1/AV:N/AC:L/PR:N/S:U/C:H/I:H/A:H")
    assert issue.code is ErrorCode.E204
    assert issue.message == "missing CVSS base metric 'UI'"
    assert issue.hint == "UI must be one of N (None), R (Required)"


def test_several_missing_metrics_are_one_e204() -> None:
    issue = _only_issue("CVSS:3.1/AV:N/AC:L")
    assert issue.code is ErrorCode.E204
    assert issue.message == "missing CVSS base metrics: PR, UI, S, C, I, A"
    assert issue.hint == "a base vector needs all of AV, AC, PR, UI, S, C, I and A"


def test_empty_vector_after_prefix_is_e204() -> None:
    assert _codes("CVSS:3.1/") == ["E204"]


def test_duplicate_metric_is_e205() -> None:
    issue = _only_issue(BASE + "/AV:L")
    assert issue.code is ErrorCode.E205
    assert issue.message == "duplicate CVSS metric 'AV'"
    assert issue.hint == "each metric may appear only once"


def test_all_errors_are_collected_in_order() -> None:
    text = "CVSS:3.1/AV:X/AC:L/AC:L/ZZ:1/S:U/C:H/I:H/A:H"
    assert _codes(text) == ["E203", "E205", "E202", "E204"]
    assert parse_vector(text).vector is None


def test_temporal_and_environmental_metrics_are_ignored_with_w201() -> None:
    result = parse_vector(BASE + "/E:P/RL:O/RC:C/CR:H/MAV:L/MS:C")
    assert result.vector is not None
    assert result.vector.canonical() == BASE
    assert [i.code for i in result.issues] == [ErrorCode.W201]
    issue = result.issues[0]
    assert issue.message == (
        "temporal/environmental metrics are ignored in v0.1: E, RL, RC, CR, MAV, MS"
    )
    assert issue.hint == "only the base score is calculated; remove them to silence this warning"


@pytest.mark.parametrize(
    "metric",
    ["E", "RL", "RC", "CR", "IR", "AR", "MAV", "MAC", "MPR", "MUI", "MS", "MC", "MI", "MA"],
)
def test_every_ignored_metric_is_recognised(metric: str) -> None:
    assert _codes(f"{BASE}/{metric}:X") == ["W201"]


def test_repeated_ignored_metric_is_listed_once() -> None:
    issue = _only_issue(BASE + "/E:P/E:F")
    assert issue.message.endswith(": E")


def test_warning_alongside_errors_keeps_vector_none() -> None:
    result = parse_vector(BASE.replace("AV:N", "AV:X") + "/E:P")
    assert [i.code.value for i in result.issues] == ["E203", "W201"]
    assert result.vector is None


# --- Scoring (M3.3) -----------------------------------------------------------------------------

PRD_REFERENCE = [
    ("AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H", 9.8),
    ("AV:N/AC:L/PR:N/UI:N/S:C/C:H/I:H/A:H", 10.0),
    ("AV:N/AC:L/PR:L/UI:N/S:C/C:H/I:H/A:H", 9.9),
    ("AV:N/AC:L/PR:L/UI:N/S:U/C:H/I:H/A:H", 8.8),
    ("AV:L/AC:L/PR:L/UI:N/S:U/C:H/I:H/A:H", 7.8),
    ("AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:N/A:N", 7.5),
    ("AV:N/AC:L/PR:L/UI:N/S:U/C:H/I:N/A:N", 6.5),
    ("AV:N/AC:L/PR:N/UI:R/S:C/C:L/I:L/A:N", 6.1),
    ("AV:N/AC:H/PR:N/UI:N/S:U/C:H/I:N/A:N", 5.9),
    ("AV:P/AC:L/PR:N/UI:N/S:U/C:L/I:N/A:N", 2.4),
    ("AV:N/AC:L/PR:N/UI:N/S:U/C:N/I:N/A:N", 0.0),
]


def _vector(body: str) -> CvssVector:
    result = parse_vector("CVSS:3.1/" + body)
    assert result.vector is not None, result.issues
    return result.vector


@pytest.mark.parametrize(("body", "expected"), PRD_REFERENCE)
def test_prd_reference_scores(body: str, expected: float) -> None:
    assert calculate(_vector(body)).base_score == expected


@pytest.mark.parametrize(
    ("scope", "pr", "weight"),
    [("U", "N", 0.85), ("U", "L", 0.62), ("U", "H", 0.27), ("C", "N", 0.85), ("C", "L", 0.68),
     ("C", "H", 0.50)],
)  # fmt: skip
def test_privileges_required_weight_depends_on_scope(scope: str, pr: str, weight: float) -> None:
    assert weights(_vector(f"AV:N/AC:L/PR:{pr}/UI:N/S:{scope}/C:H/I:H/A:H"))["PR"] == weight


def test_fixed_weights() -> None:
    w = weights(_vector("AV:P/AC:H/PR:N/UI:R/S:U/C:L/I:N/A:H"))
    assert w == {"AV": 0.20, "AC": 0.44, "PR": 0.85, "UI": 0.62, "C": 0.22, "I": 0.0, "A": 0.56}


def test_sub_scores_for_unchanged_scope() -> None:
    score = calculate(_vector("AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H"))
    assert score.iss == pytest.approx(1 - 0.44**3)
    assert score.impact == 5.9
    assert score.exploitability == 3.9


def test_sub_scores_use_normal_rounding_not_roundup() -> None:
    # NVD/FIRST show Impact 2.7 and Exploitability 2.8 for this vector; Roundup would give 2.8/2.9.
    score = calculate(_vector("AV:N/AC:L/PR:N/UI:R/S:C/C:L/I:L/A:N"))
    assert (score.base_score, score.impact, score.exploitability) == (6.1, 2.7, 2.8)


def test_changed_scope_impact_formula() -> None:
    score = calculate(_vector("AV:N/AC:L/PR:L/UI:N/S:C/C:H/I:H/A:H"))
    iss = 1 - 0.44**3
    assert score.impact_raw == pytest.approx(7.52 * (iss - 0.029) - 3.25 * (iss - 0.02) ** 15)


def test_no_impact_scores_zero_even_with_changed_scope() -> None:
    score = calculate(_vector("AV:N/AC:L/PR:N/UI:N/S:C/C:N/I:N/A:N"))
    assert score.impact_raw < 0
    assert score.base_score == 0.0
    assert score.impact == 0.0  # negative sub-score is shown as 0.0


def test_changed_scope_score_is_capped_at_10() -> None:
    assert calculate(_vector("AV:N/AC:L/PR:N/UI:N/S:C/C:H/I:H/A:H")).base_score == 10.0


def test_score_keeps_the_vector() -> None:
    vector = _vector("AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H")
    assert calculate(vector).vector is vector


# --- Severity (M3.4) ----------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("score", "severity"),
    [(0.0, Severity.NONE), (0.1, Severity.LOW), (3.9, Severity.LOW), (4.0, Severity.MEDIUM),
     (6.9, Severity.MEDIUM), (7.0, Severity.HIGH), (8.9, Severity.HIGH), (9.0, Severity.CRITICAL),
     (10.0, Severity.CRITICAL)],
)  # fmt: skip
def test_severity_bands(score: float, severity: Severity) -> None:
    assert Severity.from_score(score) is severity


@pytest.mark.parametrize("score", [-0.1, 10.1, float("nan")])
def test_severity_rejects_out_of_range_scores(score: float) -> None:
    with pytest.raises(ValueError, match=r"between 0\.0 and 10\.0"):
        Severity.from_score(score)


def test_severity_labels() -> None:
    assert [s.label for s in Severity] == [
        "None", "Informational", "Low", "Medium", "High", "Critical"
    ]  # fmt: skip
    assert str(Severity.CRITICAL) == "Critical"


def test_severity_ordering() -> None:
    assert Severity.NONE < Severity.LOW < Severity.MEDIUM < Severity.HIGH < Severity.CRITICAL
    assert Severity.INFORMATIONAL < Severity.LOW
    assert Severity.CRITICAL > Severity.HIGH
    assert Severity.HIGH >= Severity.HIGH
    assert Severity.LOW <= Severity.MEDIUM
    # None and Informational share the lowest rank: neither sorts above the other.
    assert not Severity.NONE < Severity.INFORMATIONAL
    assert not Severity.INFORMATIONAL < Severity.NONE
    assert Severity.NONE <= Severity.INFORMATIONAL
    assert Severity.INFORMATIONAL >= Severity.NONE
    assert Severity.NONE != Severity.INFORMATIONAL
    assert max([Severity.LOW, Severity.CRITICAL, Severity.MEDIUM]) is Severity.CRITICAL


@pytest.mark.parametrize("op", ["__lt__", "__le__", "__gt__", "__ge__"])
def test_severity_comparison_with_other_types_is_unsupported(op: str) -> None:
    assert getattr(Severity.LOW, op)(1) is NotImplemented
    with pytest.raises(TypeError):
        _ = Severity.LOW < 1  # type: ignore[operator]


@pytest.mark.parametrize(("body", "expected"), PRD_REFERENCE)
def test_score_severity_matches_band(body: str, expected: float) -> None:
    assert calculate(_vector(body)).severity is Severity.from_score(expected)


def test_prd_reference_severities() -> None:
    labels = [calculate(_vector(body)).severity.label for body, _ in PRD_REFERENCE]
    assert labels == ["Critical", "Critical", "Critical", "High", "High", "High", "Medium",
                      "Medium", "Medium", "Low", "None"]  # fmt: skip


# --- Reference vectors (M3.5) -------------------------------------------------------------------

REFERENCE_FILE = Path(__file__).parent.parent / "fixtures" / "cvss_vectors.json"
REFERENCE = json.loads(REFERENCE_FILE.read_text(encoding="utf-8"))["vectors"]


def test_reference_file_has_at_least_30_unique_vectors() -> None:
    vectors = [entry["vector"] for entry in REFERENCE]
    assert len(vectors) >= 30
    assert len(set(vectors)) == len(vectors)
    assert all(entry["source"] for entry in REFERENCE)


def test_reference_file_contains_the_prd_table() -> None:
    by_vector = {entry["vector"]: entry["base_score"] for entry in REFERENCE}
    for body, score in PRD_REFERENCE:
        assert by_vector["CVSS:3.1/" + body] == score


@pytest.mark.parametrize("entry", REFERENCE, ids=[e["vector"][9:] for e in REFERENCE])
def test_reference_vector(entry: dict[str, Any]) -> None:
    result = parse_vector(entry["vector"])
    assert result.issues == ()
    assert result.vector is not None
    score = calculate(result.vector)
    assert score.base_score == entry["base_score"]
    assert score.severity.label == entry["severity"]
