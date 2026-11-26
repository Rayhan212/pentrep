"""--template-dir overrides one partial and leaves the rest of the report unchanged (FR-48)."""

from __future__ import annotations

import dataclasses
import re
from pathlib import Path

import pytest

from pentrep import __version__
from pentrep.loader import load_report
from pentrep.redact import redact_report
from pentrep.render.context import BrandingView, EvidenceView, FindingView, RedactionView
from pentrep.render.html import render_html

ROOT = Path(__file__).parent.parent.parent
FULL = ROOT / "tests" / "fixtures" / "valid" / "full.yaml"
TEMPLATES = ROOT / "tests" / "fixtures" / "templates"
GOLDEN = ROOT / "tests" / "golden" / "report.html"
COVER = re.compile(r'<header class="cover" id="cover">.*?</header>\n', re.DOTALL)


def _render(template_dir: Path | None) -> str:
    result = load_report(FULL)
    assert result.report is not None
    report, summary = redact_report(result.report)
    return render_html(report, summary, FULL.parent, template_dir).replace(
        __version__, "<PENTREP_VERSION>"
    )


def test_overriding_the_cover_changes_only_the_cover(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SOURCE_DATE_EPOCH", "1795176000")  # same as the golden test
    html = _render(TEMPLATES)
    cover = COVER.search(html)
    assert cover is not None
    assert "Prepared for Acme Corp by Example Security Labs" in cover.group()
    golden = GOLDEN.read_text("utf-8")
    assert COVER.sub("", html) == COVER.sub("", golden)


def test_without_override_the_output_is_the_golden_file(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SOURCE_DATE_EPOCH", "1795176000")
    assert _render(None) == GOLDEN.read_text("utf-8")


def test_templates_md_documents_the_whole_context() -> None:
    doc = (ROOT / "docs" / "templates.md").read_text("utf-8")
    for key in ("engagement", "branding", "findings", "stats", "redaction", "generated_at",
                "pentrep_version", "css", "image_src"):  # fmt: skip
        assert f"`{key}`" in doc, key
    for view in (FindingView, EvidenceView, BrandingView, RedactionView):
        for field in dataclasses.fields(view):
            assert f"`{field.name}`" in doc, f"{view.__name__}.{field.name}"
    for name in ("markdown", "markdown_inline", "highlight", "md_block", "md_inline", "md_cell",
                 "md_step", "md_url", "slug", "fence"):  # fmt: skip
        assert f"`{name}`" in doc, name
    for partial in sorted((ROOT / "src/pentrep/themes/classic/partials").glob("*.j2")):
        assert f"`partials/{partial.name}`" in doc, partial.name
