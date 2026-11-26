"""CVSS 3.1 base score calculator (FIRST specification, PRD §4.3). No third-party CVSS code."""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum
from typing import Final

from pentrep.diagnostics import ErrorCode, Level


def roundup(value: float) -> float:
    """Round up to one decimal using the integer algorithm from spec Appendix A.

    Working on ``round(value * 100000)`` removes floating-point noise, so 4.000000000000001
    rounds to 4.0 instead of 4.1.
    """
    integer = round(value * 100_000)
    if integer % 10_000 == 0:
        return integer / 100_000
    return (math.floor(integer / 10_000) + 1) / 10


# --- Vector parsing (FR-21) ---------------------------------------------------------------------

PREFIX: Final = "CVSS:3.1/"
EXAMPLE_VECTOR: Final = "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H"

_IMPACT_VALUES: Final = {"H": "High", "L": "Low", "N": "None"}
# Base metrics in specification order, each with its values (in spec order) and their names.
BASE_METRICS: Final[dict[str, dict[str, str]]] = {
    "AV": {"N": "Network", "A": "Adjacent", "L": "Local", "P": "Physical"},
    "AC": {"L": "Low", "H": "High"},
    "PR": {"N": "None", "L": "Low", "H": "High"},
    "UI": {"N": "None", "R": "Required"},
    "S": {"U": "Unchanged", "C": "Changed"},
    "C": _IMPACT_VALUES,
    "I": _IMPACT_VALUES,
    "A": _IMPACT_VALUES,
}
IGNORED_METRICS: Final = frozenset(
    ("E", "RL", "RC", "CR", "IR", "AR", "MAV", "MAC", "MPR", "MUI", "MS", "MC", "MI", "MA")
)
_BASE_LIST: Final = ", ".join(BASE_METRICS)


def _values_hint(metric: str) -> str:
    choices = ", ".join(f"{code} ({name})" for code, name in BASE_METRICS[metric].items())
    return f"{metric} must be one of {choices}"


@dataclass(frozen=True)
class CvssIssue:
    """A problem found while parsing a vector: an E2xx error or the W201 warning."""

    code: ErrorCode
    message: str
    hint: str | None = None


@dataclass(frozen=True)
class CvssVector:
    """A valid CVSS 3.1 base vector: one value for each of the 8 base metrics."""

    values: tuple[tuple[str, str], ...]  # (metric, value) in specification order

    def __getitem__(self, metric: str) -> str:
        """The value of a base metric, for example ``vector["AV"] == "N"``."""
        return dict(self.values)[metric]

    def canonical(self) -> str:
        """The vector with metrics in specification order and ignored metrics removed (FR-25)."""
        return PREFIX + "/".join(f"{metric}:{value}" for metric, value in self.values)


@dataclass(frozen=True)
class ParseResult:
    """The parsed vector (``None`` if there is any error) and every issue found."""

    vector: CvssVector | None
    issues: tuple[CvssIssue, ...]


def _prefix_issue(text: str) -> CvssIssue | None:
    if text.startswith(PREFIX):
        return None
    version = text.split("/", 1)[0].removeprefix("CVSS:") if text.startswith("CVSS:") else None
    if version == "3.0":
        return CvssIssue(
            ErrorCode.E201,
            "CVSS version 3.0 is not supported",
            "change the prefix to 'CVSS:3.1/'; the 3.0 and 3.1 base metrics are the same",
        )
    if version is not None:
        return CvssIssue(
            ErrorCode.E201,
            f"unsupported CVSS version '{version}'",
            f"only CVSS 3.1 vectors are supported, for example {EXAMPLE_VECTOR}",
        )
    return CvssIssue(
        ErrorCode.E201, f"vector must start with '{PREFIX}'", f"for example {EXAMPLE_VECTOR}"
    )


def parse_vector(text: str) -> ParseResult:
    """Parse a CVSS 3.1 vector, collecting every E201-E205 error and the W201 warning (FR-21)."""
    text = text.strip()
    prefix_issue = _prefix_issue(text)
    if prefix_issue:
        return ParseResult(None, (prefix_issue,))
    issues: list[CvssIssue] = []
    found: dict[str, str] = {}
    accounted: set[str] = set()  # base metrics present (even with a bad value or wrong case)
    ignored: list[str] = []
    rest = text[len(PREFIX) :]
    reported_empty = False
    for segment in rest.split("/") if rest else []:
        metric, sep, value = segment.partition(":")
        if not sep or not metric:
            if segment or not reported_empty:
                shown = f"'{segment}'" if segment else "empty metric (double or trailing '/')"
                issues.append(
                    CvssIssue(
                        ErrorCode.E202,
                        f"malformed metric {shown}; expected METRIC:VALUE",
                        f"base metrics are {_BASE_LIST}",
                    )
                )
                reported_empty = reported_empty or not segment
            continue
        if metric in IGNORED_METRICS:
            if metric not in ignored:
                ignored.append(metric)
        elif metric not in BASE_METRICS:
            hint = f"base metrics are {_BASE_LIST}"
            if metric.upper() in BASE_METRICS:
                hint = f"metric names are case-sensitive: did you mean '{metric.upper()}'?"
                accounted.add(metric.upper())
            issues.append(CvssIssue(ErrorCode.E202, f"unknown CVSS metric '{metric}'", hint))
        elif metric in accounted:
            issues.append(
                CvssIssue(
                    ErrorCode.E205,
                    f"duplicate CVSS metric '{metric}'",
                    "each metric may appear only once",
                )
            )
        else:
            accounted.add(metric)
            if value in BASE_METRICS[metric]:
                found[metric] = value
            else:
                issues.append(
                    CvssIssue(
                        ErrorCode.E203,
                        f"invalid value '{value}' for metric '{metric}'",
                        _values_hint(metric),
                    )
                )
    missing = [m for m in BASE_METRICS if m not in accounted]
    if len(missing) == 1:
        issues.append(
            CvssIssue(
                ErrorCode.E204, f"missing CVSS base metric '{missing[0]}'", _values_hint(missing[0])
            )
        )
    elif missing:
        issues.append(
            CvssIssue(
                ErrorCode.E204,
                f"missing CVSS base metrics: {', '.join(missing)}",
                "a base vector needs all of AV, AC, PR, UI, S, C, I and A",
            )
        )
    if ignored:
        issues.append(
            CvssIssue(
                ErrorCode.W201,
                f"temporal/environmental metrics are ignored in v0.1: {', '.join(ignored)}",
                "only the base score is calculated; remove them to silence this warning",
            )
        )
    has_error = any(i.code.level is Level.ERROR for i in issues)
    vector = None if has_error else CvssVector(tuple((m, found[m]) for m in BASE_METRICS))
    return ParseResult(vector, tuple(issues))


# --- Severity (FR-24) ---------------------------------------------------------------------------


class Severity(Enum):
    """Qualitative severity. None and Informational share the lowest rank."""

    NONE = ("None", 0)
    INFORMATIONAL = ("Informational", 0)
    LOW = ("Low", 1)
    MEDIUM = ("Medium", 2)
    HIGH = ("High", 3)
    CRITICAL = ("Critical", 4)

    def __init__(self, label: str, rank: int) -> None:
        self.label = label
        self.rank = rank

    def __str__(self) -> str:
        return self.label

    @classmethod
    def from_score(cls, score: float) -> Severity:
        """The severity band of a base score (0.0 is None)."""
        if not 0.0 <= score <= 10.0:
            raise ValueError(f"CVSS score must be between 0.0 and 10.0, got {score}")
        if score == 0.0:
            return cls.NONE
        if score < 4.0:
            return cls.LOW
        if score < 7.0:
            return cls.MEDIUM
        if score < 9.0:
            return cls.HIGH
        return cls.CRITICAL

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, Severity):
            return NotImplemented
        return self.rank < other.rank

    def __le__(self, other: object) -> bool:
        if not isinstance(other, Severity):
            return NotImplemented
        return self.rank <= other.rank

    def __gt__(self, other: object) -> bool:
        if not isinstance(other, Severity):
            return NotImplemented
        return self.rank > other.rank

    def __ge__(self, other: object) -> bool:
        if not isinstance(other, Severity):
            return NotImplemented
        return self.rank >= other.rank


# --- Scoring (FR-22, FR-23) ---------------------------------------------------------------------

_WEIGHTS: Final[dict[str, dict[str, float]]] = {
    "AV": {"N": 0.85, "A": 0.62, "L": 0.55, "P": 0.20},
    "AC": {"L": 0.77, "H": 0.44},
    "PR": {"N": 0.85, "L": 0.62, "H": 0.27},
    "UI": {"N": 0.85, "R": 0.62},
    "C": {"H": 0.56, "L": 0.22, "N": 0.0},
    "I": {"H": 0.56, "L": 0.22, "N": 0.0},
    "A": {"H": 0.56, "L": 0.22, "N": 0.0},
}
_PR_CHANGED_SCOPE: Final = {"N": 0.85, "L": 0.68, "H": 0.50}
SCOPE_COEFFICIENT: Final = 1.08


def weights(vector: CvssVector) -> dict[str, float]:
    """Numeric weight of each metric except S. PR depends on scope (FR-22)."""
    result = {metric: table[vector[metric]] for metric, table in _WEIGHTS.items()}
    if vector["S"] == "C":
        result["PR"] = _PR_CHANGED_SCOPE[vector["PR"]]
    return result


def round_one_decimal(value: float) -> float:
    """Round half up to one decimal (for sub-scores), ignoring float noise like Roundup does."""
    integer = round(value * 100_000)
    return math.floor((integer + 5_000) / 10_000) / 10


@dataclass(frozen=True)
class CvssScore:
    """The base score and sub-scores of a vector (FR-23, FR-25)."""

    vector: CvssVector
    base_score: float
    iss: float
    impact_raw: float
    exploitability_raw: float

    @property
    def severity(self) -> Severity:
        """Severity band of the base score."""
        return Severity.from_score(self.base_score)

    @property
    def impact(self) -> float:
        """Impact sub-score, one decimal; a negative value is shown as 0.0."""
        return round_one_decimal(max(self.impact_raw, 0.0))

    @property
    def exploitability(self) -> float:
        """Exploitability sub-score, one decimal."""
        return round_one_decimal(self.exploitability_raw)


def calculate(vector: CvssVector) -> CvssScore:
    """Compute the CVSS 3.1 base score with the equations of spec Section 7.1."""
    w = weights(vector)
    iss = 1 - (1 - w["C"]) * (1 - w["I"]) * (1 - w["A"])
    changed = vector["S"] == "C"
    impact = 7.52 * (iss - 0.029) - 3.25 * (iss - 0.02) ** 15 if changed else 6.42 * iss
    exploitability = 8.22 * w["AV"] * w["AC"] * w["PR"] * w["UI"]
    if impact <= 0:
        base = 0.0
    elif changed:
        base = roundup(min(SCOPE_COEFFICIENT * (impact + exploitability), 10))
    else:
        base = roundup(min(impact + exploitability, 10))
    return CvssScore(vector, base, iss, impact, exploitability)
