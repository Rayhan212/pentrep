"""Syntax highlighting for evidence with Pygments, as inline styles (no JavaScript, FR-45).

Pygments ships no type hints and ``types-Pygments`` is not a project dependency, so its imports
are untyped; results are converted to ``str`` explicitly.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from functools import cache
from typing import Final

from pygments import format as pygments_format  # type: ignore[import-untyped]
from pygments.formatters import HtmlFormatter  # type: ignore[import-untyped]
from pygments.lexers import HttpLexer, TextLexer, get_lexer_by_name  # type: ignore[import-untyped]
from pygments.token import Error  # type: ignore[import-untyped]
from pygments.util import ClassNotFound  # type: ignore[import-untyped]

# A line that starts an HTTP message: a request line or a status line.
_MESSAGE_START: Final = re.compile(
    r"^(?:[A-Z]+ \S+ HTTP/\d(?:\.\d)?|HTTP/\d(?:\.\d)? \d{3}\b)", re.M
)

# Keep evidence verbatim: Pygments strips leading/trailing newlines and adds one by default.
VERBATIM: Final = {"stripnl": False, "ensurenl": False}

# Pygments tokens are (token type, text) pairs; the token type is an untyped Pygments object.
Tokens = list[tuple[object, str]]


@cache
def _formatter() -> object:
    return HtmlFormatter(noclasses=True, style="default")


def _tokens(lexer: object, text: str) -> Tokens:
    """Tokens from ``lexer``, or plain text if it reports errors (no red error boxes)."""
    tokens: Tokens = list(lexer.get_tokens(text))  # type: ignore[attr-defined]
    if any(token is Error for token, _ in tokens):
        return list(TextLexer(**VERBATIM).get_tokens(text))
    return tokens


def _http_messages(content: str) -> Iterator[str]:
    """Split pasted HTTP traffic into separate messages (request, response, ...)."""
    starts = [m.start() for m in _MESSAGE_START.finditer(content)]
    if not starts or starts[0] != 0:
        starts.insert(0, 0)
    for begin, end in zip(starts, [*starts[1:], len(content)], strict=True):
        yield content[begin:end]


def highlight(content: str, language: str | None) -> str:
    """Highlighted HTML for evidence text; Pygments escapes the content."""
    if language == "http":
        tokens = [
            t for part in _http_messages(content) for t in _tokens(HttpLexer(**VERBATIM), part)
        ]
    else:
        try:
            lexer = get_lexer_by_name(language, **VERBATIM) if language else TextLexer(**VERBATIM)
        except ClassNotFound:
            lexer = TextLexer(**VERBATIM)
        tokens = _tokens(lexer, content)
    return str(pygments_format(tokens, _formatter()))
