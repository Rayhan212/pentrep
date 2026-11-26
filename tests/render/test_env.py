"""Jinja environment: ChoiceLoader, autoescape for HTML, StrictUndefined (FR-13, FR-48)."""

from __future__ import annotations

from pathlib import Path

import jinja2
import pytest

from pentrep.render import make_environment


@pytest.fixture
def override(tmp_path: Path) -> Path:
    (tmp_path / "x.html.j2").write_text("<p>{{ value }}</p>", encoding="utf-8")
    (tmp_path / "x.md.j2").write_text("{{ value }}", encoding="utf-8")
    (tmp_path / "strict.html.j2").write_text("{{ missing }}", encoding="utf-8")
    (tmp_path / "data.html.j2").write_text("{{ title }}", encoding="utf-8")
    return tmp_path


def test_html_templates_are_autoescaped(override: Path) -> None:
    html = make_environment(override).get_template("x.html.j2").render(value="<script>x</script>")
    assert html == "<p>&lt;script&gt;x&lt;/script&gt;</p>"


def test_markdown_templates_are_not_autoescaped(override: Path) -> None:
    assert make_environment(override).get_template("x.md.j2").render(value="a<b") == "a<b"


def test_undefined_variables_raise(override: Path) -> None:
    with pytest.raises(jinja2.UndefinedError):
        make_environment(override).get_template("strict.html.j2").render()


def test_values_are_never_evaluated_as_templates(override: Path) -> None:
    template = make_environment(override).get_template("data.html.j2")
    assert template.render(title="{{ 7*7 }} {% if 1 %}x{% endif %}") == (
        "{{ 7*7 }} {% if 1 %}x{% endif %}"
    )


def test_builtin_theme_is_the_fallback() -> None:
    source, _, _ = make_environment(None).loader.get_source(  # type: ignore[union-attr]
        make_environment(None), "style.css"
    )
    assert "classic" in source


def test_template_dir_is_searched_first(tmp_path: Path) -> None:
    (tmp_path / "style.css").write_text("/* mine */", encoding="utf-8")
    env = make_environment(tmp_path)
    source, _, _ = env.loader.get_source(env, "style.css")  # type: ignore[union-attr]
    assert source == "/* mine */"


def test_missing_template_dir_is_an_error(tmp_path: Path) -> None:
    with pytest.raises(NotADirectoryError):
        make_environment(tmp_path / "nope")
