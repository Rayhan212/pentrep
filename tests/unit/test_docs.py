"""Documentation stays in sync with the code (NFR-13)."""

from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import Path

import pytest
from typer.testing import CliRunner

from pentrep.cli import app
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


def test_readme_has_the_m7_sections() -> None:
    """M7.7 / FR-62: quickstart, install matrix, Docker, screenshots, sample report, notices."""
    readme = (DOCS.parent / "README.md").read_text(encoding="utf-8")
    quickstart = readme[readme.index("## Quickstart") :].split("```bash\n", 1)[1].split("```", 1)[0]
    assert [line.split()[0] for line in quickstart.strip().splitlines()] == [
        "pipx", "pentrep", "pentrep"
    ]  # fmt: skip
    for text in (
        "libpango-1.0-0", "brew install pango",
        'docker run --rm -v "$PWD:/work" ghcr.io/rayhan212/pentrep',
        "](docs/img/cover.png)", "](docs/img/finding.png)",
        "https://rayhan212.github.io/pentrep/",
        "safety net", "(docs/errors.md)",
    ):  # fmt: skip
        assert text in readme, text
    for image in ("cover.png", "finding.png"):
        assert (DOCS / "img" / image).stat().st_size > 1000


def test_readme_lists_every_cli_flag(plain: Callable[[str], str]) -> None:
    """NFR-13: every CLI flag appears in --help and in the README."""
    readme = (DOCS.parent / "README.md").read_text(encoding="utf-8")
    runner = CliRunner()
    for command in ("init", "validate", "build", "schema"):
        help_text = plain(runner.invoke(app, [command, "--help"]).stdout)
        for flag in set(re.findall(r"(?<![\w-])--[a-z][a-z-]+", help_text)) - {"--help"}:
            assert f"`{flag}" in readme or f" {flag}" in readme, f"{command} {flag}"
