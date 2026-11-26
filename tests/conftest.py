"""Shared pytest fixtures for pentrep."""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable
from pathlib import Path

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


# --- Leak testing (M4.9) -------------------------------------------------------------------------

FIXTURES = Path(__file__).parent / "fixtures"
# The 20 fake secrets seeded in tests/fixtures/valid/leaky.yaml.
LEAKY_SECRETS = (
    "MIIEowIBAAKCAQEAleakyKEYbody0001",
    "eyJhbGciOiJIUzI1NiJ9.eyJsZWFreSI6MX0.bGVha3lzaWc",
    "leakyBearerToken0003",
    "bGVha3k6YmFzaWMwMDA0",
    "leakycookie0005",
    "leakycookie0006",
    "AKIALEAKYKEY00000007",
    "leakyPassword0008",
    "leakyApiKey0009",
    "leakyClientSecret0010",
    "leakyAccessToken0011",
    "4111111111111111",
    "5555 5555 5555 4444",
    "leaky.person14@acme.example",
    "victim15@corp.example",
    "10.14.15.16",
    "192.168.17.17",
    "172.18.0.18",
    "ACME-190019",
    "leakyRefresh0020",
)


def assert_no_leaks(texts: Iterable[str]) -> None:
    """Fail if any seeded secret appears in any of ``texts`` (stdout, stderr, files, logs)."""
    combined = "\n".join(texts)
    leaked = [i for i, secret in enumerate(LEAKY_SECRETS, 1) if secret in combined]
    assert not leaked, f"seeded secrets leaked: #{leaked}"


@pytest.fixture
def leaky_project(tmp_path: Path) -> Path:
    """A copy of valid/leaky.yaml as ``findings.yaml`` with the private-key placeholder expanded."""
    text = (FIXTURES / "valid" / "leaky.yaml").read_text(encoding="utf-8")
    path = tmp_path / "findings.yaml"
    path.write_text(text.replace("<<PRIVATE KEY>>", "PRIVATE KEY"), encoding="utf-8")
    return path


@pytest.fixture
def no_leaks() -> Callable[[Iterable[str]], None]:
    """The :func:`assert_no_leaks` helper, as a fixture (test modules don't import conftest)."""
    return assert_no_leaks


@pytest.fixture
def leaky_secrets() -> tuple[str, ...]:
    """The 20 fake secrets seeded in valid/leaky.yaml."""
    return LEAKY_SECRETS


# --- Golden files (M5.9) ----------------------------------------------------------------------


def pytest_addoption(parser: pytest.Parser) -> None:
    """``--update-golden`` rewrites tests/golden/* instead of comparing against them."""
    parser.addoption(
        "--update-golden",
        action="store_true",
        default=False,
        help="Regenerate golden files in tests/golden/ (review the diff before committing).",
    )


@pytest.fixture
def update_golden(request: pytest.FixtureRequest) -> bool:
    """True when pytest runs with ``--update-golden``."""
    return bool(request.config.getoption("--update-golden"))
