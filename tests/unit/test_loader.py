"""YAML loading and line/column mapping (FR-10, FR-12)."""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import pytest

from pentrep import loader
from pentrep.diagnostics import ErrorCode
from pentrep.loader import (
    MAX_ALIAS_EXPANSION,
    MAX_FILE_BYTES,
    LoadError,
    join_path,
    load_report,
    load_yaml,
    parse_yaml,
    validate_document,
)


def test_join_path() -> None:
    assert join_path("", "findings") == "findings"
    assert join_path("findings", 0) == "findings[0]"
    assert join_path("findings[0]", "id") == "findings[0].id"


def test_parses_plain_python_values() -> None:
    doc = parse_yaml("a: 1\nb: [x, 2026-11-02, 1.5, true, null, '3']\nc: {d: e}\n", file="f.yaml")
    assert doc.data == {
        "a": 1,
        "b": ["x", dt.date(2026, 11, 2), 1.5, True, None, "3"],
        "c": {"d": "e"},
    }


def test_yaml_1_2_semantics() -> None:
    doc = parse_yaml("a: yes\nb: no\nc: on\n", file="f.yaml")
    assert doc.data == {"a": "yes", "b": "no", "c": "on"}


def test_positions_are_one_based_for_keys_and_values() -> None:
    text = "engagement:\n  title: Hello\nfindings:\n  - id: PT-001\n    title:  Foo\n"
    doc = parse_yaml(text, file="f.yaml")
    assert doc.position("engagement.title") == (2, 10)
    assert doc.key_position("engagement.title") == (2, 3)
    assert doc.position("findings") == (4, 3)
    assert doc.position("findings[0]") == (4, 5)
    assert doc.position("findings[0].title") == (5, 13)
    assert doc.key_position("findings[0].title") == (5, 5)
    assert doc.position("") == (1, 1)


def test_position_falls_back_to_nearest_ancestor() -> None:
    doc = parse_yaml("engagement:\n  title: Hello\n", file="f.yaml")
    assert doc.position("engagement.client.name") == doc.position("engagement")
    assert doc.position("missing") == (1, 1)
    assert doc.key_position("engagement.nope") == doc.position("engagement")


def _load_error(text: str) -> LoadError:
    with pytest.raises(LoadError) as exc_info:
        parse_yaml(text, file="f.yaml")
    return exc_info.value


def test_syntax_error_is_e100_with_line_and_column() -> None:
    err = _load_error("a: 1\nb: [1, 2\nc: 3\n")
    diag = err.diagnostic
    assert diag.code is ErrorCode.E100
    assert diag.file == "f.yaml"
    assert diag.line >= 2
    assert diag.column >= 1
    assert "Traceback" not in diag.message


def test_mapping_values_error_position() -> None:
    diag = _load_error("a: 1\nb: c: d\n").diagnostic
    assert (diag.code, diag.line, diag.column) == (ErrorCode.E100, 2, 5)
    assert "mapping values are not allowed" in diag.message
    assert diag.hint is not None
    assert "indentation" in diag.hint


def test_python_object_tag_is_rejected() -> None:
    diag = _load_error("a: !!python/object:os.system x\n").diagnostic
    assert diag.code is ErrorCode.E100
    assert (diag.line, diag.column) == (1, 4)
    assert "python/object" in diag.message
    assert diag.path == "a"


@pytest.mark.parametrize("text", ["a: !custom x\n", "a: !!set {x}\n", "a: !!binary aGk=\n"])
def test_other_tags_are_rejected(text: str) -> None:
    assert _load_error(text).diagnostic.code is ErrorCode.E100


def test_duplicate_keys_are_rejected() -> None:
    diag = _load_error("a: 1\na: 2\n").diagnostic
    assert (diag.code, diag.line, diag.column) == (ErrorCode.E100, 2, 1)
    assert "duplicate key 'a'" in diag.message


def test_merge_keys_are_rejected() -> None:
    diag = _load_error("base: &b {x: 1}\nchild:\n  <<: *b\n").diagnostic
    assert diag.code is ErrorCode.E100
    assert "merge" in diag.message


def test_non_scalar_keys_are_rejected() -> None:
    assert _load_error("? [a, b]\n: 1\n").diagnostic.code is ErrorCode.E100


def test_small_aliases_are_allowed() -> None:
    doc = parse_yaml("a: &x [1, 2]\nb: *x\n", file="f.yaml")
    assert doc.data == {"a": [1, 2], "b": [1, 2]}


def test_billion_laughs_is_rejected() -> None:
    lines = ['a: &a ["lol","lol","lol","lol","lol","lol","lol","lol","lol"]']
    for prev, name in zip("abcdefgh", "bcdefghi", strict=True):
        lines.append(f"{name}: &{name} [{', '.join(['*' + prev] * 9)}]")
    diag = _load_error("\n".join(lines) + "\n").diagnostic
    assert diag.code is ErrorCode.E100
    assert str(MAX_ALIAS_EXPANSION) in diag.message


def test_alias_limit_boundary() -> None:
    items = ", ".join(["*x"] * MAX_ALIAS_EXPANSION)
    parse_yaml(f"a: &x 1\nb: [{items}]\n", file="f.yaml")  # exactly at the limit: allowed
    with pytest.raises(LoadError):
        parse_yaml(f"a: &x 1\nb: [{items}, *x]\n", file="f.yaml")


def test_empty_document_is_none() -> None:
    assert parse_yaml("", file="f.yaml").data is None


def test_multiple_documents_are_rejected() -> None:
    assert _load_error("a: 1\n---\nb: 2\n").diagnostic.code is ErrorCode.E100


def test_deep_nesting_is_rejected_without_crash() -> None:
    assert _load_error("[" * 5000 + "]" * 5000).diagnostic.code is ErrorCode.E100


def test_load_yaml_reads_file_and_uses_display_name(tmp_path: Path) -> None:
    path = tmp_path / "findings.yaml"
    path.write_text("a: 1\n", encoding="utf-8")
    assert load_yaml(path).data == {"a": 1}
    path.write_text("a: [\n", encoding="utf-8")
    with pytest.raises(LoadError) as exc_info:
        load_yaml(path, display="shown.yaml")
    assert exc_info.value.diagnostic.file == "shown.yaml"


def test_utf8_bom_is_accepted(tmp_path: Path) -> None:
    path = tmp_path / "f.yaml"
    path.write_bytes(b"\xef\xbb\xbfa: 1\n")
    assert load_yaml(path).data == {"a": 1}


def test_non_utf8_file_is_e100(tmp_path: Path) -> None:
    path = tmp_path / "f.yaml"
    path.write_bytes(b"a: \xff\xfe\n")
    with pytest.raises(LoadError) as exc_info:
        load_yaml(path)
    assert exc_info.value.diagnostic.code is ErrorCode.E100
    assert "UTF-8" in exc_info.value.diagnostic.message


def test_file_over_10_mb_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "big.yaml"
    path.write_bytes(b"#" * (MAX_FILE_BYTES + 1))
    with pytest.raises(LoadError) as exc_info:
        load_yaml(path)
    diag = exc_info.value.diagnostic
    assert diag.code is ErrorCode.E303
    assert "10 MB" in diag.message


def test_file_at_the_size_limit_is_read(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Scanning a real 10 MB file takes seconds, so the boundary is tested with a smaller limit.
    monkeypatch.setattr(loader, "MAX_FILE_BYTES", 64)
    path = tmp_path / "ok.yaml"
    path.write_bytes(b"a: 1\n" + b"#" * 59)
    assert load_yaml(path).data == {"a": 1}
    path.write_bytes(b"a: 1\n" + b"#" * 60)
    with pytest.raises(LoadError):
        load_yaml(path)


# --- Validation: Pydantic errors → diagnostics (M2.5) ----------------------------------------

VALID = """\
schema_version: 1
engagement:
  title: "Web App Test"
  client:
    name: "Acme Corp"
  testers:
    - name: "Alex"
  start_date: 2026-11-02
  end_date: 2026-11-13
  report_date: 2026-11-20
  scope:
    in_scope:
      - asset: "https://portal.acme.example"
        type: url
  methodology: "OWASP WSTG v4.2 grey-box assessment."
findings:
  - id: PT-001
    title: "SQL Injection in Login"
    cvss_vector: "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H"
    affected_assets: ["https://portal.acme.example/login"]
    description: "The username field is concatenated into SQL."
    impact: "An attacker can bypass authentication entirely."
    steps_to_reproduce: ["Send the request."]
    evidence:
      - type: text
        caption: "Response"
        content: "HTTP/1.1 200 OK"
    remediation: "Use parameterised queries for all database access."
"""


def _validate(text: str) -> list[tuple[str, str, int, int]]:
    result = validate_document(parse_yaml(text, file="f.yaml"))
    return [(d.code.value, d.path, d.line, d.column) for d in result.diagnostics]


def _messages(text: str) -> list[str]:
    return [d.message for d in validate_document(parse_yaml(text, file="f.yaml")).diagnostics]


def test_valid_document_has_no_diagnostics() -> None:
    result = validate_document(parse_yaml(VALID, file="f.yaml"))
    assert result.diagnostics == []
    assert result.report is not None
    assert result.report.findings[0].id == "PT-001"
    assert result.ok


def test_unknown_field_is_e101_at_the_key_with_did_you_mean() -> None:
    text = VALID.replace("    remediation:", "    remediaton:")
    assert _validate(text) == [
        ("E102", "findings[0].remediation", 17, 5),
        ("E101", "findings[0].remediaton", 28, 5),
    ]
    assert _messages(text)[1] == "unknown field 'remediaton'; did you mean 'remediation'?"


def test_unknown_field_without_close_match_has_no_suggestion() -> None:
    text = VALID.replace("  methodology:", "  zzzzzz: 1\n  methodology:")
    diag = validate_document(parse_yaml(text, file="f.yaml")).diagnostics[0]
    assert diag.message == "unknown field 'zzzzzz'"
    assert diag.hint is not None
    assert "methodology" in diag.hint


def test_missing_field_is_e102_at_the_parent() -> None:
    text = VALID.replace('    name: "Acme Corp"\n', '    contact: "Jane"\n')
    assert _validate(text) == [("E102", "engagement.client.name", 5, 5)]
    assert _messages(text) == ["missing required field 'name'"]


def test_wrong_type_is_e103_at_the_value() -> None:
    text = VALID.replace('  title: "Web App Test"', "  title: 12345")
    assert _validate(text) == [("E103", "engagement.title", 3, 10)]
    assert _messages(text) == ["input should be a valid string, got 12345"]


def test_pattern_error_is_e103() -> None:
    text = VALID.replace("  - id: PT-001", "  - id: pt-1")
    assert _validate(text) == [("E103", "findings[0].id", 17, 9)]


def test_literal_error_has_hint_with_choices() -> None:
    text = VALID.replace("        type: url", "        type: domain")
    diag = validate_document(parse_yaml(text, file="f.yaml")).diagnostics[0]
    assert (diag.code, diag.path, diag.line, diag.column) == (
        ErrorCode.E103,
        "engagement.scope.in_scope[0].type",
        14,
        15,
    )
    assert diag.hint is not None
    assert "'url'" in diag.hint
    assert "'mobile_app'" in diag.hint


def test_field_not_allowed_for_evidence_type_is_e103() -> None:
    text = VALID.replace(
        '        content: "HTTP/1.1 200 OK"', '        content: "x"\n        path: a.png'
    )
    assert _validate(text) == [("E103", "findings[0].evidence[0].path", 28, 9)]
    assert _messages(text) == ["field 'path' is not allowed for evidence type 'text'"]


def test_evidence_errors_drop_the_union_tag_from_the_path() -> None:
    text = VALID.replace('        caption: "Response"', '        caption: "R"')
    assert _validate(text) == [("E103", "findings[0].evidence[0].caption", 26, 18)]


def test_missing_evidence_type_is_e102() -> None:
    text = VALID.replace("      - type: text\n        caption:", "      - caption:")
    diag = validate_document(parse_yaml(text, file="f.yaml")).diagnostics[0]
    assert (diag.code, diag.path, diag.line) == (ErrorCode.E102, "findings[0].evidence[0].type", 25)
    assert diag.hint is not None
    assert "text, http, image" in diag.hint


def test_invalid_evidence_type_is_e103() -> None:
    text = VALID.replace("      - type: text", "      - type: video")
    assert _validate(text) == [("E103", "findings[0].evidence[0].type", 25, 15)]
    assert "'video'" in _messages(text)[0]


def test_custom_error_codes_are_kept() -> None:
    text = VALID.replace("  end_date: 2026-11-13", "  end_date: 2026-11-01")
    assert _validate(text) == [("E105", "engagement.end_date", 9, 13)]
    assert _messages(text) == ["end_date 2026-11-01 is before start_date 2026-11-02"]


def test_schema_version_is_e106() -> None:
    assert _validate(VALID.replace("schema_version: 1", "schema_version: 2")) == [
        ("E106", "schema_version", 1, 17)
    ]


def test_cross_checks_are_included() -> None:
    finding = VALID[VALID.index("  - id: PT-001") :]
    text = VALID + finding.replace(
        "    cvss_vector:", "    severity: informational\n    cvss_vector:"
    )
    assert _validate(text) == [
        ("E104", "findings[1].id", 29, 9),
        ("E206", "findings[1].severity", 31, 5),
    ]


def test_cross_check_and_model_errors_are_both_reported() -> None:
    finding = VALID[VALID.index("  - id: PT-001") :]
    text = VALID + finding.replace('    title: "SQL Injection in Login"', "    title: 1")
    codes = [c for c, *_ in _validate(text)]
    assert codes == ["E104", "E103"]


def test_three_independent_errors_are_all_reported_sorted_by_line() -> None:
    text = (
        VALID.replace("  - id: PT-001", "  - id: bad")
        .replace('  title: "Web App Test"', '  title: "Web"')
        .replace("    remediation:", "    remediaton:")
    )
    assert [(c, line) for c, _, line, _ in _validate(text)] == [
        ("E103", 3),
        ("E102", 17),  # missing 'remediation', reported at the finding (column 5)
        ("E103", 17),  # bad id (column 9)
        ("E101", 28),
    ]


def test_diagnostics_are_capped_at_100() -> None:
    bad_assets = "\n".join(f"      - asset: x{i}\n        type: nope" for i in range(150))
    text = VALID.replace(
        '      - asset: "https://portal.acme.example"\n        type: url', bad_assets
    )
    result = validate_document(parse_yaml(text, file="f.yaml"))
    assert len(result.diagnostics) == 100
    assert [d.line for d in result.diagnostics] == sorted(d.line for d in result.diagnostics)


def test_top_level_must_be_a_mapping() -> None:
    assert _validate("- a\n- b\n") == [("E103", "", 1, 1)]


def test_empty_file_is_reported() -> None:
    assert _validate("") == [("E103", "", 1, 1)]
    assert _messages("") == ["file is empty; expected a findings.yaml document"]


def test_load_report_turns_load_errors_into_diagnostics(tmp_path: Path) -> None:
    path = tmp_path / "findings.yaml"
    path.write_text("a: [\n", encoding="utf-8")
    result = load_report(path, display="findings.yaml")
    assert result.report is None
    assert [d.code for d in result.diagnostics] == [ErrorCode.E100]
    assert not result.ok


def test_load_report_on_valid_file(tmp_path: Path) -> None:
    path = tmp_path / "findings.yaml"
    path.write_text(VALID, encoding="utf-8")
    result = load_report(path)
    assert result.ok
    assert result.diagnostics == []


# --- Warnings W101, W102 (M2.7) ----------------------------------------------------------------


@pytest.mark.parametrize(
    "text", ["TODO: write this", "tbd", "Fixme later", "Lorem Ipsum dolor sit amet", "see (TBD)"]
)
def test_placeholder_text_is_w101(text: str) -> None:
    doc = VALID.replace(
        '"OWASP WSTG v4.2 grey-box assessment."', f'"OWASP WSTG v4.2 grey-box. {text}"'
    )
    result = validate_document(parse_yaml(doc, file="f.yaml"))
    assert [(d.code, d.path, d.line, d.column) for d in result.diagnostics] == [
        (ErrorCode.W101, "engagement.methodology", 15, 16)
    ]
    assert result.ok  # warnings do not fail validation
    assert result.report is not None
    assert result.warnings == result.diagnostics


@pytest.mark.parametrize("text", ["todos", "mastodon", "outbdound", "lorem", "Fixmeup"])
def test_placeholder_words_need_word_boundaries(text: str) -> None:
    doc = VALID.replace("Response", f"Response {text}")
    assert _validate(doc) == []


def test_placeholders_are_found_in_lists_and_nested_values() -> None:
    doc = VALID.replace('["Send the request."]', '["Send the request.", "TODO"]')
    assert _validate(doc) == [("W101", "findings[0].steps_to_reproduce[1]", 23, 47)]


def test_placeholder_in_a_key_is_not_reported() -> None:
    assert "W101" not in [c for c, *_ in _validate(VALID.replace("schema_version", "todo"))]


def test_finding_without_evidence_is_w102() -> None:
    start = VALID.index("    evidence:")
    end = VALID.index("    remediation:")
    doc = VALID[:start] + VALID[end:]
    assert _validate(doc) == [("W102", "findings[0]", 17, 5)]


def test_finding_with_empty_evidence_is_w102_at_the_list() -> None:
    start = VALID.index("    evidence:")
    end = VALID.index("    remediation:")
    doc = VALID[:start] + "    evidence: []\n" + VALID[end:]
    assert _validate(doc) == [("W102", "findings[0].evidence", 24, 15)]
    assert _messages(doc) == ["finding PT-001 has no evidence"]


def test_warnings_and_errors_together() -> None:
    doc = VALID.replace('  title: "Web App Test"', '  title: "TBD"')
    result = validate_document(parse_yaml(doc, file="f.yaml"))
    assert [d.code for d in result.diagnostics] == [ErrorCode.E103, ErrorCode.W101]
    assert result.errors == result.diagnostics[:1]
    assert not result.ok
