"""PDF output with WeasyPrint (FR-03, FR-46).

WeasyPrint is imported lazily: it is slow to import and needs system libraries (Pango, HarfBuzz)
that may be missing, in which case a :class:`RenderError` with an install hint is raised.
"""

from __future__ import annotations

import importlib
import logging
import re
import sys
from importlib import resources
from pathlib import Path
from types import ModuleType
from typing import Final
from urllib.parse import urlparse
from urllib.request import url2pathname

DOCKER_HINT: Final = (
    'or use the Docker image: docker run --rm -v "$PWD:/work" ghcr.io/rayhan212/pentrep '
    "build findings.yaml"
)
_INSTALL_HINTS: Final = {
    "linux": "install the libraries: sudo apt install libpango-1.0-0 libpangoft2-1.0-0 "
    "libharfbuzz0b (Debian/Ubuntu)",
    "darwin": "install the libraries: brew install pango",
}
_MISSING_LIBRARY: Final = re.compile(r"cannot load library '([^']+)'")
PAPER_SIZES: Final = {"a4": "A4", "letter": "letter"}


class RenderError(Exception):
    """A report could not be rendered; ``hint`` says how to fix it."""

    def __init__(self, message: str, hint: str) -> None:
        super().__init__(message)
        self.hint = hint


def install_hint(platform: str = sys.platform) -> str:
    """How to get WeasyPrint's system libraries on this OS, plus the Docker alternative."""
    for prefix, hint in _INSTALL_HINTS.items():
        if platform.startswith(prefix):
            return f"{hint}; {DOCKER_HINT}"
    return f"PDF output is supported on Linux and macOS; {DOCKER_HINT}"


def load_weasyprint() -> ModuleType:
    """Import WeasyPrint, turning a missing package or system library into a RenderError."""
    try:
        return importlib.import_module("weasyprint")
    except (ImportError, OSError) as exc:
        match = _MISSING_LIBRARY.search(str(exc))
        what = f"the system library {match.group(1)}" if match else "WeasyPrint"
        raise RenderError(
            f"PDF output is unavailable: cannot load {what}", install_hint()
        ) from None


def _theme_dir() -> Path:
    path = Path(str(resources.files("pentrep") / "themes" / "classic"))
    return path.resolve()


def render_pdf(html: str, paper: str = "a4") -> bytes:
    """Render report HTML to PDF with the bundled fonts. No network access (NFR-09).

    Only ``data:`` URIs and files inside the built-in theme (the fonts) may be loaded; anything
    else stops the rendering with a RenderError.
    """
    weasyprint = load_weasyprint()
    urls = importlib.import_module("weasyprint.urls")
    theme = _theme_dir()

    class LocalOnlyFetcher(urls.URLFetcher):  # type: ignore[misc,name-defined]  # untyped library
        """Allow data: URIs and the theme's own files; refuse everything else."""

        def fetch(self, url: str, headers: object = None) -> object:
            if url.startswith("data:"):
                return super().fetch(url, headers)
            if url.startswith("file:"):
                local = Path(url2pathname(urlparse(url).path)).resolve()
                if local.is_relative_to(theme):
                    return super().fetch(url, headers)
            raise urls.FatalURLFetchingError(f"external resource blocked: {url}")

    fonts_css = (theme / "fonts.css").read_text(encoding="utf-8")
    page_css = f"@page {{ size: {PAPER_SIZES[paper]}; }}"
    fetcher = LocalOnlyFetcher()
    base_url = theme.as_uri() + "/"
    logger = logging.getLogger("weasyprint")
    previous_propagate, previous_level = logger.propagate, logger.level
    logger.propagate = False  # keep CSS warnings off the console
    logger.setLevel(logging.ERROR)
    # @font-face rules only take effect with one FontConfiguration shared by CSS and write_pdf.
    font_config = importlib.import_module("weasyprint.text.fonts").FontConfiguration()
    try:
        document = weasyprint.HTML(string=html, base_url=base_url, url_fetcher=fetcher)
        stylesheet = weasyprint.CSS(
            string=fonts_css + "\n" + page_css,
            base_url=base_url,
            url_fetcher=fetcher,
            font_config=font_config,
        )
        data: bytes = document.write_pdf(stylesheets=[stylesheet], font_config=font_config)
    except urls.FatalURLFetchingError as exc:
        raise RenderError(
            f"PDF rendering stopped: {exc}",
            "templates must embed images as data: URIs (use image_src) and must not load "
            "external resources",
        ) from None
    finally:
        logger.propagate = previous_propagate
        logger.setLevel(previous_level)
    return data
