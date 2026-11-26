"""Exit codes, diagnostic codes and diagnostic formatting shared by all pentrep commands."""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass
from enum import Enum, IntEnum, StrEnum
from typing import Final


class ExitCode(IntEnum):
    """Process exit codes (PRD FR-00c)."""

    OK = 0
    VALIDATION_FAILED = 1
    USAGE_ERROR = 2
    RENDER_ERROR = 3


class Level(StrEnum):
    """Severity of a diagnostic."""

    ERROR = "error"
    WARNING = "warning"


class ErrorCode(Enum):
    """Stable diagnostic codes (PRD §4.2.4). The value is the code, ``summary`` its meaning."""

    E100 = ("E100", "YAML syntax error")
    E101 = ("E101", "Unknown field")
    E102 = ("E102", "Missing required field")
    E103 = ("E103", "Wrong type, length or pattern; or a field not allowed for this evidence type")
    E104 = ("E104", "Duplicate finding id")
    E105 = ("E105", "end_date is before start_date")
    E106 = ("E106", "Unsupported schema_version")
    E206 = ("E206", "Both cvss_vector and severity given, or neither")
    E301 = ("E301", "Referenced file not found")
    E302 = ("E302", "Path resolves outside the project directory")
    E303 = ("E303", "Unsupported file type, or file too large")
    E304 = ("E304", "Invalid custom redaction regex, or invalid pattern name")
    W101 = ("W101", "Placeholder text found")
    W102 = ("W102", "Finding has no evidence")

    def __new__(cls, code: str, summary: str) -> ErrorCode:
        """Use the code string as the enum value and keep the summary alongside it."""
        obj = object.__new__(cls)
        obj._value_ = code
        obj.summary = summary
        return obj

    summary: str

    @property
    def level(self) -> Level:
        """``warning`` for W-codes, ``error`` otherwise."""
        return Level.WARNING if self.value.startswith("W") else Level.ERROR


@dataclass(frozen=True, order=False)
class Diagnostic:
    """One error or warning, located in a file (FR-12)."""

    code: ErrorCode
    message: str
    file: str
    line: int
    column: int
    path: str = ""
    hint: str | None = None

    @property
    def level(self) -> Level:
        """The diagnostic's severity, derived from its code."""
        return self.code.level


MAX_DIAGNOSTICS: Final = 100


def sort_and_cap(
    diagnostics: Iterable[Diagnostic], limit: int = MAX_DIAGNOSTICS
) -> list[Diagnostic]:
    """Drop exact duplicates, sort by position (then code and path) and keep at most ``limit``."""
    unique = set(diagnostics)
    ordered = sorted(unique, key=lambda d: (d.line, d.column, d.code.value, d.path, d.message))
    return ordered[:limit]


def format_text(diagnostic: Diagnostic) -> str:
    """Format one diagnostic in the PRD §4.2.4 text format (hint on a second line)."""
    d = diagnostic
    where = f"{d.path}: " if d.path else ""
    text = f"{d.file}:{d.line}:{d.column}: {d.level}[{d.code.value}] {where}{d.message}"
    if d.hint:
        text += f"\n  hint: {d.hint}"
    return text


def format_json(diagnostics: Iterable[Diagnostic]) -> str:
    """Format diagnostics as a JSON array (FR-02 ``--format json``)."""
    items = [
        {
            "code": d.code.value,
            "severity": d.level.value,
            "path": d.path,
            "line": d.line,
            "column": d.column,
            "message": d.message,
            "hint": d.hint,
        }
        for d in diagnostics
    ]
    return json.dumps(items, indent=2, ensure_ascii=False)


DIAGNOSTICS_JSON_SCHEMA: Final[dict[str, object]] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "pentrep validate --format json output",
    "type": "array",
    "items": {
        "type": "object",
        "additionalProperties": False,
        "required": ["code", "severity", "path", "line", "column", "message", "hint"],
        "properties": {
            "code": {"type": "string", "pattern": "^[EW][0-9]{3}$"},
            "severity": {"enum": ["error", "warning"]},
            "path": {"type": "string"},
            "line": {"type": "integer", "minimum": 1},
            "column": {"type": "integer", "minimum": 1},
            "message": {"type": "string", "minLength": 1},
            "hint": {"type": ["string", "null"]},
        },
    },
}
