"""Exit codes and (from M2) diagnostics shared by all pentrep commands."""

from __future__ import annotations

from enum import IntEnum


class ExitCode(IntEnum):
    """Process exit codes (PRD FR-00c)."""

    OK = 0
    VALIDATION_FAILED = 1
    USAGE_ERROR = 2
    RENDER_ERROR = 3
