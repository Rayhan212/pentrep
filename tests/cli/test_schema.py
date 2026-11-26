"""`pentrep schema [-o FILE]` (FR-04)."""

from __future__ import annotations

import datetime as dt
import json
from collections.abc import Callable
from pathlib import Path

import jsonschema
import pytest
from typer.testing import CliRunner

from pentrep.cli import app
from pentrep.loader import load_yaml

ROOT = Path(__file__).parent.parent.parent
FIXTURES = ROOT / "tests" / "fixtures"
# Fixtures whose only problems are expressible in JSON Schema (FR-04).
PURE_SCHEMA_ERRORS = sorted(
    p
    for prefix in ("e101", "e102", "e103", "e106")
    for p in (FIXTURES / "invalid").glob(f"{prefix}_*.yaml")
)


def _json_ready(value: object) -> object:
    """YAML dates become ISO strings, as they would be in a JSON document."""
    if isinstance(value, dt.date):
        return value.isoformat()
    if isinstance(value, dict):
        return {k: _json_ready(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_ready(v) for v in value]
    return value


@pytest.fixture(scope="module")
def schema() -> dict[str, object]:
    result = CliRunner().invoke(app, ["schema"])
    assert result.exit_code == 0
    data: dict[str, object] = json.loads(result.stdout)
    return data


def test_schema_is_valid_draft_2020_12(schema: dict[str, object]) -> None:
    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    jsonschema.Draft202012Validator.check_schema(schema)
    assert schema["type"] == "object"
    assert schema["additionalProperties"] is False


def test_schema_validates_the_init_scaffold(schema: dict[str, object]) -> None:
    data = load_yaml(ROOT / "src" / "pentrep" / "scaffold" / "findings.yaml").data
    jsonschema.validate(_json_ready(data), schema, cls=jsonschema.Draft202012Validator)


@pytest.mark.parametrize("name", ["minimal.yaml", "full.yaml"])
def test_schema_validates_valid_fixtures(schema: dict[str, object], name: str) -> None:
    data = load_yaml(FIXTURES / "valid" / name).data
    jsonschema.validate(_json_ready(data), schema, cls=jsonschema.Draft202012Validator)


def test_pure_schema_error_fixtures_exist() -> None:
    assert len(PURE_SCHEMA_ERRORS) >= 5


@pytest.mark.parametrize("path", PURE_SCHEMA_ERRORS, ids=[p.stem for p in PURE_SCHEMA_ERRORS])
def test_schema_rejects_schema_error_fixtures(schema: dict[str, object], path: Path) -> None:
    data = load_yaml(path).data
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(_json_ready(data), schema, cls=jsonschema.Draft202012Validator)


def test_schema_output_is_deterministic(runner: CliRunner) -> None:
    assert runner.invoke(app, ["schema"]).stdout == runner.invoke(app, ["schema"]).stdout


def test_output_file(runner: CliRunner, tmp_path: Path, schema: dict[str, object]) -> None:
    out = tmp_path / "schema.json"
    result = runner.invoke(app, ["schema", "-o", str(out)])
    assert result.exit_code == 0
    assert json.loads(out.read_text(encoding="utf-8")) == schema
    assert out.read_text(encoding="utf-8").endswith("}\n")
    assert "{" not in result.stdout  # the schema itself is not printed


def test_unwritable_output_exits_3(runner: CliRunner, tmp_path: Path) -> None:
    blocker = tmp_path / "file"
    blocker.write_text("x", encoding="utf-8")
    result = runner.invoke(app, ["schema", "--output", str(blocker / "schema.json")])
    assert result.exit_code == 3
    assert "cannot write" in result.stderr
    assert "Traceback" not in result.output


def test_help_lists_flags(runner: CliRunner, plain: Callable[[str], str]) -> None:
    result = runner.invoke(app, ["schema", "--help"])
    assert "--output" in plain(result.stdout)
    assert "-o" in plain(result.stdout)
