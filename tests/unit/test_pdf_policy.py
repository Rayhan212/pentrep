"""pdf tests run when possible, skip locally without Pango, and fail in CI (M6.7)."""

from __future__ import annotations

from collections.abc import Callable

import pytest


@pytest.mark.parametrize(
    ("available", "required", "policy"),
    [(True, False, "run"), (True, True, "run"), (False, False, "skip"), (False, True, "fail")],
)
def test_pdf_policy(
    pdf_policy_function: Callable[[bool, bool], str], available: bool, required: bool, policy: str
) -> None:
    assert pdf_policy_function(available, required) == policy
