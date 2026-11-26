"""Property-based tests for CVSS 3.1 invariants (PRD §8.2), 1,000 examples each."""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from pentrep.cvss import BASE_METRICS, Severity, calculate, parse_vector

EXAMPLES = settings(max_examples=1_000, deadline=None)
IMPACT_ORDER = ("N", "L", "H")

metric_values = st.fixed_dictionaries(
    {metric: st.sampled_from(sorted(values)) for metric, values in BASE_METRICS.items()}
)


def _text(values: dict[str, str], order: list[str] | None = None) -> str:
    """Build a vector string; without ``order`` the metrics are in specification order."""
    return "CVSS:3.1/" + "/".join(f"{m}:{values[m]}" for m in order or list(BASE_METRICS))


def _score(values: dict[str, str]) -> float:
    vector = parse_vector(_text(values)).vector
    assert vector is not None
    return calculate(vector).base_score


@EXAMPLES
@given(metric_values)
def test_score_is_between_0_and_10(values: dict[str, str]) -> None:
    assert 0.0 <= _score(values) <= 10.0


@EXAMPLES
@given(metric_values)
def test_score_has_exactly_one_decimal(values: dict[str, str]) -> None:
    score = _score(values)
    assert f"{score:.1f}" == repr(score)


@EXAMPLES
@given(metric_values)
def test_severity_matches_its_band(values: dict[str, str]) -> None:
    vector = parse_vector(_text(values)).vector
    assert vector is not None
    result = calculate(vector)
    bands = {
        Severity.NONE: (0.0, 0.0),
        Severity.LOW: (0.1, 3.9),
        Severity.MEDIUM: (4.0, 6.9),
        Severity.HIGH: (7.0, 8.9),
        Severity.CRITICAL: (9.0, 10.0),
    }
    low, high = bands[result.severity]
    assert low <= result.base_score <= high


@EXAMPLES
@given(metric_values, st.sampled_from(("C", "I", "A")))
def test_raising_c_i_or_a_never_lowers_the_score(values: dict[str, str], metric: str) -> None:
    scores = [_score({**values, metric: level}) for level in IMPACT_ORDER]
    assert scores == sorted(scores)


@EXAMPLES
@given(metric_values, st.data())
def test_canonical_form_of_a_shuffled_vector_is_idempotent(
    values: dict[str, str], data: st.DataObject
) -> None:
    order = data.draw(st.permutations(list(values)))
    vector = parse_vector(_text(values, order)).vector
    assert vector is not None
    canonical = vector.canonical()
    assert canonical == _text(values)  # specification order
    again = parse_vector(canonical).vector
    assert again is not None
    assert again.canonical() == canonical
    assert calculate(again).base_score == calculate(vector).base_score
