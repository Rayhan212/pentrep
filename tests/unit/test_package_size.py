"""Packaging: bundled OFL fonts and the wheel size limit (FR-46, NFR-12, NFR-14)."""

from __future__ import annotations

import shutil
import subprocess
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent.parent
FONTS = ROOT / "src" / "pentrep" / "themes" / "classic" / "fonts"
MAX_WHEEL_BYTES = 2 * 1024 * 1024
FONT_FILES = (
    "SourceSans3-Regular.ttf",
    "SourceSans3-It.ttf",
    "SourceSans3-Bold.ttf",
    "SourceCodePro-Regular.ttf",
)


@pytest.mark.parametrize("name", FONT_FILES)
def test_fonts_are_bundled_as_truetype(name: str) -> None:
    data = (FONTS / name).read_bytes()
    assert data[:4] in (b"\x00\x01\x00\x00", b"true", b"OTTO")


def test_ofl_licences_are_bundled() -> None:
    for name in ("OFL-SourceSans3.txt", "OFL-SourceCodePro.txt"):
        text = (FONTS / name).read_text("utf-8")
        assert "SIL OPEN FONT LICENSE VERSION 1.1" in text.upper()


def test_fonts_css_declares_every_bundled_font() -> None:
    css = (FONTS.parent / "fonts.css").read_text("utf-8")
    for name in FONT_FILES:
        assert f'url("fonts/{name}")' in css, name


def test_html_stylesheet_does_not_reference_font_files() -> None:
    """style.css is inlined into the HTML, which must not load external files (FR-45)."""
    assert "url(" not in (FONTS.parent / "style.css").read_text("utf-8")


def test_wheel_is_at_most_2_mb(tmp_path: Path) -> None:
    uv = shutil.which("uv")
    if uv is None:
        pytest.skip("uv is needed to build the wheel")
    subprocess.run(
        [uv, "build", "--wheel", "--out-dir", str(tmp_path), str(ROOT)],
        check=True,
        capture_output=True,
    )
    [wheel] = tmp_path.glob("*.whl")
    assert wheel.stat().st_size <= MAX_WHEEL_BYTES, wheel.stat().st_size
    names = zipfile.ZipFile(wheel).namelist()
    for name in FONT_FILES:
        assert f"pentrep/themes/classic/fonts/{name}" in names
