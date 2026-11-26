"""Shared pytest fixtures for pentrep."""

from __future__ import annotations

import re
from collections.abc import Callable

import pytest
from typer.testing import CliRunner


@pytest.fixture
def runner() -> CliRunner:
    """Return a Typer CLI runner."""
    return CliRunner()


ANSI_ESCAPE = re.compile(r"\x1b\[[0-9;]*m")


@pytest.fixture
def plain() -> Callable[[str], str]:
    """Strip ANSI colour codes; Typer forces colour when GITHUB_ACTIONS/FORCE_COLOR is set."""
    return lambda text: ANSI_ESCAPE.sub("", text)
