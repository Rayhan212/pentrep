"""Exit codes, error codes and diagnostic formatting (FR-00c, FR-12, PRD §4.2.4)."""

from __future__ import annotations

import json

import pytest

from pentrep.diagnostics import (
    DIAGNOSTICS_JSON_SCHEMA,
    Diagnostic,
    ErrorCode,
    ExitCode,
    Level,
    format_json,
    format_text,
    sort_and_cap,
)


def test_exit_codes_match_prd() -> None:
    assert ExitCode.OK == 0
    assert ExitCode.VALIDATION_FAILED == 1
    assert ExitCode.USAGE_ERROR == 2
    assert ExitCode.RENDER_ERROR == 3


def test_error_codes_for_m2() -> None:
    expected = {
        "E100", "E101", "E102", "E103", "E104", "E105", "E106",
        "E206",
        "E301", "E302", "E303", "E304",
        "W101", "W102",
    }  # fmt: skip
    assert {code.value for code in ErrorCode} == expected


@pytest.mark.parametrize(
    ("code", "level"),
    [(ErrorCode.E100, Level.ERROR), (ErrorCode.E304, Level.ERROR), (ErrorCode.W102, Level.WARNING)],
)
def test_level_derives_from_code_prefix(code: ErrorCode, level: Level) -> None:
    assert code.level is level
    assert Diagnostic(code, "m", file="f.yaml", line=1, column=1).level is level


def test_every_code_has_a_summary() -> None:
    for code in ErrorCode:
        assert code.summary, code


def _diag(**overrides: object) -> Diagnostic:
    fields: dict[str, object] = {
        "code": ErrorCode.E103,
        "message": "invalid value 'X'",
        "file": "findings.yaml",
        "line": 57,
        "column": 18,
        "path": "findings[0].cvss_vector",
        "hint": None,
    }
    fields.update(overrides)
    return Diagnostic(**fields)  # type: ignore[arg-type]


def test_text_format_matches_prd() -> None:
    diag = _diag(hint="AV must be one of N (Network), A (Adjacent), L (Local), P (Physical)")
    assert format_text(diag) == (
        "findings.yaml:57:18: error[E103] findings[0].cvss_vector: invalid value 'X'\n"
        "  hint: AV must be one of N (Network), A (Adjacent), L (Local), P (Physical)"
    )


def test_text_format_without_hint_is_one_line() -> None:
    assert format_text(_diag()) == (
        "findings.yaml:57:18: error[E103] findings[0].cvss_vector: invalid value 'X'"
    )


def test_text_format_without_path_omits_it() -> None:
    diag = _diag(code=ErrorCode.E100, path="", message="mapping values are not allowed here")
    assert format_text(diag) == (
        "findings.yaml:57:18: error[E100] mapping values are not allowed here"
    )


def test_text_format_warning() -> None:
    diag = _diag(code=ErrorCode.W102, path="findings[1]", message="finding has no evidence")
    assert format_text(diag).startswith("findings.yaml:57:18: warning[W102] findings[1]: ")


def test_json_format_has_prd_keys_and_validates() -> None:
    jsonschema = pytest.importorskip("jsonschema")
    out = format_json([_diag(hint="h"), _diag(code=ErrorCode.W101, hint=None)])
    data = json.loads(out)
    assert data[0] == {
        "code": "E103",
        "severity": "error",
        "path": "findings[0].cvss_vector",
        "line": 57,
        "column": 18,
        "message": "invalid value 'X'",
        "hint": "h",
    }
    assert data[1]["severity"] == "warning"
    assert data[1]["hint"] is None
    jsonschema.validate(data, DIAGNOSTICS_JSON_SCHEMA)


def test_json_format_empty_list() -> None:
    assert json.loads(format_json([])) == []


def test_sort_and_cap_orders_by_line_then_column() -> None:
    diags = [_diag(line=9, column=1), _diag(line=2, column=5), _diag(line=2, column=1)]
    assert [(d.line, d.column) for d in sort_and_cap(diags)] == [(2, 1), (2, 5), (9, 1)]


def test_sort_and_cap_limits_to_100() -> None:
    diags = [_diag(line=n) for n in range(150, 0, -1)]
    capped = sort_and_cap(diags)
    assert len(capped) == 100
    assert capped[0].line == 1
    assert capped[-1].line == 100


def test_sort_and_cap_removes_exact_duplicates() -> None:
    assert len(sort_and_cap([_diag(), _diag()])) == 1
