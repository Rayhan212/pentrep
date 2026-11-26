"""Documentation stays in sync with the code (NFR-13)."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from pentrep.diagnostics import ErrorCode

DOCS = Path(__file__).parent.parent.parent / "docs"
HEADING = re.compile(r"^## ([EW]\d{3}) — (.+)$", re.MULTILINE)


def _sections() -> dict[str, str]:
    text = (DOCS / "errors.md").read_text(encoding="utf-8")
    matches = list(HEADING.finditer(text))
    return {
        m.group(1): text[m.end() : matches[i + 1].start() if i + 1 < len(matches) else len(text)]
        for i, m in enumerate(matches)
    }


def test_errors_md_lists_exactly_the_error_codes() -> None:
    assert sorted(_sections()) == sorted(code.value for code in ErrorCode)


def test_errors_md_headings_are_in_code_order() -> None:
    codes = [m.group(1) for m in HEADING.finditer((DOCS / "errors.md").read_text("utf-8"))]
    assert codes == sorted(codes, key=lambda c: (c[0] == "W", c))


@pytest.mark.parametrize("code", [c.value for c in ErrorCode])
def test_each_code_has_example_and_fix(code: str) -> None:
    section = _sections()[code]
    assert "**Example**" in section, code
    assert f"[{code}]" in section, f"{code}: the example output should show the code"
    assert "**Fix**" in section, code


def test_schema_md_mentions_every_top_level_and_engagement_field() -> None:
    from pentrep.models import Engagement, Finding, Report

    text = (DOCS / "schema.md").read_text(encoding="utf-8")
    for model in (Report, Engagement, Finding):
        for name in model.model_fields:
            assert f"`{name}`" in text, f"{model.__name__}.{name} missing from docs/schema.md"


def test_errors_md_examples_match_the_fixture_goldens() -> None:
    """Example lines quoted from a fixture must equal that fixture's real output."""
    invalid = DOCS.parent / "tests" / "fixtures" / "invalid"
    text = (DOCS / "errors.md").read_text(encoding="utf-8")
    example = re.compile(r"^([ew]\d{3}_[a-z0-9_]+)\.yaml:\d+:\d+: .*$", re.MULTILINE)
    assert len(example.findall(text)) >= 12
    for match in example.finditer(text):
        golden = (invalid / f"{match.group(1)}.expected.txt").read_text(encoding="utf-8")
        assert match.group(0) in golden.splitlines(), match.group(0)
