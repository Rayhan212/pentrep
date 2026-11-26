"""Exit code contract (FR-00c)."""

from __future__ import annotations

from pentrep.diagnostics import ExitCode


def test_exit_codes_match_prd() -> None:
    assert ExitCode.OK == 0
    assert ExitCode.VALIDATION_FAILED == 1
    assert ExitCode.USAGE_ERROR == 2
    assert ExitCode.RENDER_ERROR == 3
