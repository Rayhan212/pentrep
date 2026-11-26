"""Built-in redaction patterns against positive and negative corpora (FR-32, PRD §8.2)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from pentrep.redact import BUILTIN_PATTERNS, redact_text

CORPORA = Path(__file__).parent.parent / "fixtures" / "redaction"
# Written with a placeholder so the detect-private-key pre-commit hook does not flag the corpus.
PLACEHOLDERS = {"<<PRIVATE KEY>>": "PRIVATE KEY"}


def _expand(text: str) -> str:
    for placeholder, value in PLACEHOLDERS.items():
        text = text.replace(placeholder, value)
    return text


def _corpus(name: str) -> dict[str, Any]:
    data: dict[str, Any] = json.loads((CORPORA / f"{name}.json").read_text(encoding="utf-8"))
    return data


NAMES = sorted(p.stem for p in CORPORA.glob("*.json"))
POSITIVE = [(n, i, s) for n in NAMES for i, s in enumerate(_corpus(n)["positive"])]
NEGATIVE = [(n, i, s) for n in NAMES for i, s in enumerate(_corpus(n)["negative"])]


def test_every_builtin_pattern_has_a_corpus() -> None:
    assert set(NAMES) == {p.name.lower() for p in BUILTIN_PATTERNS}  # one corpus per built-in


@pytest.mark.parametrize("name", NAMES)
def test_each_corpus_has_at_least_5_samples_per_side(name: str) -> None:
    corpus = _corpus(name)
    assert len(corpus["positive"]) >= 5
    assert len(corpus["negative"]) >= 5


@pytest.mark.parametrize("name", NAMES)
def test_corpus_belongs_to_a_builtin_pattern(name: str) -> None:
    assert name.upper() in {p.name for p in BUILTIN_PATTERNS}


@pytest.mark.parametrize(
    ("name", "index", "sample"), POSITIVE, ids=[f"{n}+{i}" for n, i, _ in POSITIVE]
)
def test_positive_sample_is_redacted(name: str, index: int, sample: dict[str, str]) -> None:
    result = redact_text(_expand(sample["text"]), BUILTIN_PATTERNS)
    assert result.text == _expand(sample["expected"])
    assert set(result.names) == {name.upper()}


@pytest.mark.parametrize(
    ("name", "index", "text"), NEGATIVE, ids=[f"{n}-{i}" for n, i, _ in NEGATIVE]
)
def test_negative_sample_is_unchanged(name: str, index: int, text: str) -> None:
    expanded = _expand(text)
    result = redact_text(expanded, BUILTIN_PATTERNS)
    assert result.text == expanded
    assert result.names == ()
