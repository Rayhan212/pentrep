"""Secret and PII redaction for evidence text (PRD §4.4).

Redaction is a safety net, not a guarantee: it is regex-based and can miss secrets.
"""

from __future__ import annotations

import ipaddress
import re
from collections.abc import Callable, Collection, Iterator, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:  # models imports this module, so only import it for type checking
    from pentrep.models import Redaction, Report

NAME_RE: Final = re.compile(r"^[A-Z][A-Z0-9_]{1,31}$")

Span = tuple[int, int]


def token(name: str) -> str:
    """The replacement text for a redacted value (FR-31)."""
    return f"[REDACTED:{name}]"


@dataclass(frozen=True)
class Pattern:
    """A named redaction rule. Lower ``priority`` numbers win on overlap (FR-32).

    If the regex has groups whose names start with ``value``, only the first one that took part
    in the match is redacted; otherwise (or if none took part) the whole match is. ``check`` can
    reject a candidate value (for example a Luhn check), and ``finder`` replaces the regex
    entirely for rules that a single regex cannot express.
    """

    name: str
    regex: re.Pattern[str]
    priority: int
    check: Callable[[str], bool] | None = None
    finder: Callable[[str], Iterator[Span]] | None = None

    def __post_init__(self) -> None:
        if not NAME_RE.match(self.name):
            raise ValueError(f"invalid pattern name {self.name!r}")

    def spans(self, text: str) -> Iterator[Span]:
        """Yield the ``(start, end)`` of every value this pattern would redact."""
        if self.finder is not None:
            yield from self.finder(text)
            return
        value_groups = [g for g in self.regex.groupindex if g.startswith("value")]
        for match in self.regex.finditer(text):
            # A value group that did not take part (another alternative matched) means the
            # whole match is redacted: when in doubt, hide more.
            group = next((g for g in value_groups if match.group(g) is not None), None)
            start, end = match.span(group) if group else match.span()
            if start == end:
                continue
            if self.check is not None and not self.check(text[start:end]):
                continue
            yield start, end


@dataclass(frozen=True)
class RedactedText:
    """Redacted text and the pattern name of each replaced value, in text order."""

    text: str
    names: tuple[str, ...]


@dataclass(frozen=True, order=True)
class _Candidate:
    priority: int
    start: int
    neg_length: int
    name: str
    keep: bool  # allowlisted: protects its characters but is neither replaced nor counted

    @property
    def end(self) -> int:
        return self.start - self.neg_length


def redact_text(
    text: str, patterns: Sequence[Pattern], allowlist: Collection[str] = ()
) -> RedactedText:
    """Replace every match with ``[REDACTED:NAME]`` (FR-31, FR-32, FR-34).

    Candidates are taken by priority, then earliest start, then longest; a candidate that
    overlaps an accepted one is dropped, so each character is redacted at most once. The result
    does not depend on the order of ``patterns``.
    """
    candidates = sorted(
        _Candidate(p.priority, start, start - end, p.name, text[start:end] in allowlist)
        for p in patterns
        for start, end in p.spans(text)
    )
    accepted: list[_Candidate] = []
    for cand in candidates:
        if all(cand.end <= other.start or cand.start >= other.end for other in accepted):
            accepted.append(cand)
    replaced = sorted((c for c in accepted if not c.keep), key=lambda c: c.start)
    parts: list[str] = []
    position = 0
    for cand in replaced:
        parts += [text[position : cand.start], token(cand.name)]
        position = cand.end
    parts.append(text[position:])
    return RedactedText("".join(parts), tuple(c.name for c in replaced))


# --- Built-in patterns (FR-32), in priority order ------------------------------------------------

_PRIVATE_KEY_RE: Final = re.compile(
    # An unterminated block (truncated output) is redacted to the end of the text.
    r"-----BEGIN (?:[A-Z0-9]+ )*PRIVATE KEY-----"
    r"(?:.*?-----END (?:[A-Z0-9]+ )*PRIVATE KEY-----|.*)",
    re.DOTALL,
)
_JWT_RE: Final = re.compile(
    r"(?<![A-Za-z0-9_-])eyJ[A-Za-z0-9_-]+\.eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]*"
)
_BEARER_RE: Final = re.compile(
    r"\bauthorization[ \t]*:[ \t]*(?:bearer|basic)[ \t]+(?P<value>[^\s'\"]+)", re.IGNORECASE
)
_COOKIE_LINE_RE: Final = re.compile(r"^[ \t]*(?:set-)?cookie[ \t]*:(?P<rest>[^\r\n]*)", re.I | re.M)
COOKIE_ATTRIBUTES: Final = frozenset(
    ("path", "domain", "expires", "max-age", "samesite", "httponly", "secure")
)


def _cookie_values(text: str) -> Iterator[Span]:
    """Values of ``name=value`` pairs on Cookie/Set-Cookie lines, keeping names and attributes."""
    for line in _COOKIE_LINE_RE.finditer(text):
        offset = line.start("rest")
        for part in re.finditer(r"[^;]+", line.group("rest")):
            name, sep, value = part.group().partition("=")
            if not sep or name.strip().lower() in COOKIE_ATTRIBUTES or not value.strip():
                continue
            value_start = offset + part.start() + len(name) + 1
            leading = len(value) - len(value.lstrip())
            yield value_start + leading, value_start + len(value.rstrip())


_AWS_KEY_RE: Final = re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b")
_SECRET_RE: Final = re.compile(
    r"(?<![A-Za-z0-9_])"  # "-" may precede the key, as in the header X-Api-Key
    r"(?:password|passwd|pwd|secret|api[_-]?key|access_token|refresh_token|client_secret)"
    r"[\"']?[ \t]*[:=][ \t]*"
    r"(?:\"(?P<value>[^\"\r\n]*)\"|'(?P<value2>[^'\r\n]*)'|(?P<value3>[^\s\"'&;,]+))",
    re.IGNORECASE,
)
_CARD_RE: Final = re.compile(r"(?<![\d-])(?:\d[ -]?){12,18}\d(?![\d-])")


def luhn_valid(digits: str) -> bool:
    """True if the digit string passes the Luhn checksum."""
    total = 0
    for position, char in enumerate(reversed(digits)):
        n = int(char)
        if position % 2:
            n = n * 2 - 9 if n > 4 else n * 2
        total += n
    return total % 10 == 0


def _is_card_number(candidate: str) -> bool:
    digits = re.sub(r"\D", "", candidate)
    return 13 <= len(digits) <= 19 and luhn_valid(digits)


_EMAIL_RE: Final = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_IPV4_RE: Final = re.compile(r"(?<![\d.])(?:\d{1,3}\.){3}\d{1,3}(?!\.?\d)")
PRIVATE_NETWORKS: Final = tuple(
    ipaddress.IPv4Network(net)
    for net in ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16", "169.254.0.0/16")
)


def _is_private_ip(candidate: str) -> bool:
    """True for RFC 1918 and link-local addresses (public, loopback and RFC 5737 are kept)."""
    try:
        address = ipaddress.IPv4Address(candidate)
    except ValueError:
        return False
    return any(address in network for network in PRIVATE_NETWORKS)


BUILTIN_PATTERNS: Final[tuple[Pattern, ...]] = (
    Pattern("PRIVATE_KEY", _PRIVATE_KEY_RE, 1),
    Pattern("JWT", _JWT_RE, 2),
    Pattern("BEARER", _BEARER_RE, 3),
    Pattern("COOKIE", _COOKIE_LINE_RE, 4, finder=_cookie_values),
    Pattern("AWS_KEY", _AWS_KEY_RE, 5),
    Pattern("SECRET", _SECRET_RE, 6),
    Pattern("CARD", _CARD_RE, 7, check=_is_card_number),
    Pattern("EMAIL", _EMAIL_RE, 8),
    Pattern("PRIVATE_IP", _IPV4_RE, 9, check=_is_private_ip),
)
BUILTIN_NAMES: Final = frozenset(p.name for p in BUILTIN_PATTERNS)


# --- Configured redaction (FR-33, FR-34) -------------------------------------------------------

CUSTOM_PRIORITY_START: Final = 100


def build_patterns(config: Redaction) -> tuple[Pattern, ...]:
    """Built-in patterns followed by the custom ones, which have lower priority (FR-33)."""
    custom = tuple(
        Pattern(item.name, re.compile(item.regex), CUSTOM_PRIORITY_START + index)
        for index, item in enumerate(config.custom_patterns)
    )
    return BUILTIN_PATTERNS + custom


class Redactor:
    """Redacts text with the patterns and allowlist from a ``redaction`` config."""

    def __init__(self, config: Redaction) -> None:
        self.patterns = build_patterns(config)
        self.allowlist = frozenset(config.allowlist)

    def redact(self, text: str) -> RedactedText:
        """Redact ``text``; allowlisted values are kept and not counted."""
        return redact_text(text, self.patterns, self.allowlist)


# --- Whole report (FR-30) ----------------------------------------------------------------------


@dataclass(frozen=True)
class RedactionSummary:
    """What was redacted: counts per pattern in order of first appearance (FR-35)."""

    enabled: bool
    counts: tuple[tuple[str, int], ...]
    findings: int  # findings with at least one redacted value
    images_not_scanned: int

    @property
    def values(self) -> int:
        """Total number of redacted values."""
        return sum(count for _, count in self.counts)


def redact_report(report: Report, enabled: bool | None = None) -> tuple[Report, RedactionSummary]:
    """Redact the fields listed in FR-30 and summarise what was replaced.

    Always: evidence ``content`` (text/http) and ``steps_to_reproduce``. With
    ``apply_to_all_text`` also ``description``, ``impact`` and ``remediation``. Metadata, titles,
    affected assets and references are never touched. ``enabled`` overrides the config
    (``--no-redact``). The input report is not modified.
    """
    config = report.redaction
    images = sum(1 for f in report.findings for e in f.evidence if e.type == "image")
    if not (config.enabled if enabled is None else enabled):
        return report, RedactionSummary(False, (), 0, images)
    redactor = Redactor(config)
    counts: dict[str, int] = {}
    affected = 0

    def scrub(text: str) -> str:
        result = redactor.redact(text)
        for name in result.names:
            counts[name] = counts.get(name, 0) + 1
        return result.text

    findings = []
    for finding in report.findings:
        before = sum(counts.values())
        update: dict[str, object] = {}
        if config.apply_to_all_text:
            update["description"] = scrub(finding.description)
            update["impact"] = scrub(finding.impact)
        update["steps_to_reproduce"] = [scrub(step) for step in finding.steps_to_reproduce]
        update["evidence"] = [
            item
            if item.type == "image"
            else item.model_copy(update={"content": scrub(item.content)})
            for item in finding.evidence
        ]
        if config.apply_to_all_text:
            update["remediation"] = scrub(finding.remediation)
        affected += sum(counts.values()) > before
        findings.append(finding.model_copy(update=update))
    redacted = report.model_copy(update={"findings": findings})
    return redacted, RedactionSummary(True, tuple(counts.items()), affected, images)


def _plural(n: int, noun: str) -> str:
    return f"{n} {noun}" if n == 1 else f"{n} {noun}s"


def format_summary(summary: RedactionSummary, preview: bool = False) -> list[str]:
    """Summary lines for the CLI (FR-35). Only pattern names and counts, never values.

    ``preview`` words it for ``validate``, which redacts nothing.
    """
    counts = ", ".join(f"{name}×{count}" for name, count in summary.counts)
    where = f"{_plural(summary.values, 'value')} in {_plural(summary.findings, 'finding')}"
    if not summary.enabled:
        if preview:
            return ["Redaction preview: redaction is disabled (redaction.enabled: false)"]
        return ["Redaction is disabled: the report is an UNREDACTED DRAFT"]
    if preview:
        lines = [
            f"Redaction preview: {where} would be redacted: {counts}"
            if summary.values
            else "Redaction preview: no values would be redacted"
        ]
    else:
        lines = [f"Redacted {where}: {counts}" if summary.values else "No values were redacted"]
    if summary.images_not_scanned:
        items = _plural(summary.images_not_scanned, "image evidence item")
        verb = "was" if summary.images_not_scanned == 1 else "were"
        lines.append(f"Note: {items} {verb} not scanned (image redaction is not supported in v0.1)")
    return lines
