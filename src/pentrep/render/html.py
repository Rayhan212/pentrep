"""Self-contained HTML report: inline CSS, images as data: URIs, no scripts (FR-45)."""

from __future__ import annotations

import base64
from pathlib import Path

from markupsafe import Markup

from pentrep.models import Report
from pentrep.redact import RedactionSummary
from pentrep.render import make_environment
from pentrep.render.context import build_context

TEMPLATE = "report.html.j2"


def data_uri(path: Path, mime: str, asset_name: str | None = None) -> str:
    """Embed a (validated, project-confined) image file as a ``data:`` URI."""
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{encoded}"


def render_html(
    report: Report, summary: RedactionSummary, base_dir: Path, template_dir: Path | None = None
) -> str:
    """Render the (already redacted) report as one self-contained HTML document."""
    env = make_environment(template_dir)
    if env.loader is None:  # pragma: no cover - make_environment always sets a loader
        raise RuntimeError("template loader missing")
    css, _, _ = env.loader.get_source(env, "style.css")
    safe_css = Markup(css)  # noqa: S704 - the theme's own stylesheet, not user input
    context = build_context(report, summary, base_dir)
    return env.get_template(TEMPLATE).render(**context, css=safe_css, image_src=data_uri)
