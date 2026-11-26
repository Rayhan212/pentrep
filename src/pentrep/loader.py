"""Load ``findings.yaml`` safely and keep the line/column of every node (FR-10, FR-12)."""

from __future__ import annotations

import difflib
import io
import re
from collections.abc import Iterator
from dataclasses import dataclass, field, replace
from pathlib import Path
from types import UnionType
from typing import Annotated, Final, Union, get_args, get_origin

from pydantic import BaseModel, ValidationError
from pydantic_core import ErrorDetails
from ruamel.yaml import YAML
from ruamel.yaml.error import MarkedYAMLError, YAMLError
from ruamel.yaml.nodes import MappingNode, Node, ScalarNode, SequenceNode

from pentrep.cvss import parse_vector
from pentrep.diagnostics import Diagnostic, ErrorCode, Level, sort_and_cap
from pentrep.models import EVIDENCE_TYPES, Issue, Report, cross_checks

MAX_FILE_BYTES: Final = 10 * 1024 * 1024
MAX_ALIAS_EXPANSION: Final = 1_000
MAX_DEPTH: Final = 100

_TAG_PREFIX: Final = "tag:yaml.org,2002:"
_SCALAR_TAGS: Final = frozenset(
    _TAG_PREFIX + name for name in ("str", "int", "float", "bool", "null", "timestamp")
)

# A plain YAML value: what json-like data from findings.yaml is made of.
Position = tuple[int, int]


class LoadError(Exception):
    """The YAML file could not be loaded; carries one diagnostic."""

    def __init__(self, diagnostic: Diagnostic) -> None:
        super().__init__(diagnostic.message)
        self.diagnostic = diagnostic


def join_path(parent: str, part: str | int) -> str:
    """Append a key or list index to a dotted path (``findings[0].id``)."""
    if isinstance(part, int):
        return f"{parent}[{part}]"
    return f"{parent}.{part}" if parent else part


def parent_path(path: str) -> str:
    """Return the dotted path one level up (``findings[0].id`` → ``findings[0]``)."""
    cut = max(path.rfind("."), path.rfind("["))
    return path[:cut] if cut > 0 else ""


@dataclass
class LoadedYaml:
    """Plain data loaded from YAML plus the position of every value and mapping key."""

    data: object
    file: str
    values: dict[str, Position] = field(default_factory=dict)
    keys: dict[str, Position] = field(default_factory=dict)

    def position(self, path: str) -> Position:
        """Line/column of the value at ``path``, or of its nearest existing ancestor."""
        while path not in self.values and path:
            path = parent_path(path)
        return self.values.get(path, (1, 1))

    def key_position(self, path: str) -> Position:
        """Line/column of the mapping key for ``path``; falls back like :meth:`position`."""
        return self.keys.get(path) or self.position(parent_path(path))


def _diag(
    file: str,
    message: str,
    pos: Position = (1, 1),
    path: str = "",
    code: ErrorCode = ErrorCode.E100,
) -> Diagnostic:
    return Diagnostic(code, message, file=file, line=pos[0], column=pos[1], path=path)


def _pos(node: Node) -> Position:
    return (node.start_mark.line + 1, node.start_mark.column + 1)


class _Builder:
    """Turn a composed node graph into plain Python data, recording positions.

    Only standard JSON-like tags are accepted, and alias expansion is bounded, so the
    result never contains arbitrary objects and a "billion laughs" file is rejected.
    """

    def __init__(self, yaml: YAML, doc: LoadedYaml) -> None:
        self._constructor = yaml.constructor
        self._doc = doc
        self._seen: set[int] = set()
        self._expanded = 0

    def build(self, node: Node, path: str, depth: int = 0) -> object:
        if id(node) in self._seen:
            self._expanded += 1
            if self._expanded > MAX_ALIAS_EXPANSION:
                raise self._error(
                    node, path, f"alias expansion exceeds {MAX_ALIAS_EXPANSION} nodes"
                )
        self._seen.add(id(node))
        if depth > MAX_DEPTH:
            raise self._error(node, path, f"nesting deeper than {MAX_DEPTH} levels")
        self._doc.values.setdefault(path, _pos(node))
        if isinstance(node, MappingNode):
            return self._mapping(node, path, depth)
        if isinstance(node, SequenceNode):
            return self._sequence(node, path, depth)
        return self._scalar(node, path)

    def _mapping(self, node: MappingNode, path: str, depth: int) -> dict[object, object]:
        if node.tag != _TAG_PREFIX + "map":
            raise self._unsupported_tag(node, path)
        result: dict[object, object] = {}
        for key_node, value_node in node.value:
            if key_node.tag == _TAG_PREFIX + "merge":
                raise self._error(key_node, path, "merge keys ('<<') are not supported")
            if not isinstance(key_node, ScalarNode):
                raise self._error(key_node, path, "mapping keys must be plain scalars")
            key = self._scalar(key_node, path)
            if not isinstance(key, str | int | float | bool):
                raise self._error(key_node, path, "mapping keys must be strings")
            if key in result:
                raise self._error(key_node, path, f"duplicate key '{key}'")
            child = join_path(path, str(key))
            self._doc.keys.setdefault(child, _pos(key_node))
            result[key] = self.build(value_node, child, depth + 1)
        return result

    def _sequence(self, node: SequenceNode, path: str, depth: int) -> list[object]:
        if node.tag != _TAG_PREFIX + "seq":
            raise self._unsupported_tag(node, path)
        return [
            self.build(item, join_path(path, i), depth + 1) for i, item in enumerate(node.value)
        ]

    def _scalar(self, node: Node, path: str) -> object:
        if node.tag not in _SCALAR_TAGS:
            raise self._unsupported_tag(node, path)
        return self._constructor.construct_object(node, deep=True)

    def _unsupported_tag(self, node: Node, path: str) -> LoadError:
        tag = str(node.tag).replace(_TAG_PREFIX, "!!")
        return self._error(node, path, f"unsupported YAML tag '{tag}'")

    def _error(self, node: Node, path: str, message: str) -> LoadError:
        return LoadError(_diag(self._doc.file, message, _pos(node), path))


def parse_yaml(text: str, file: str) -> LoadedYaml:
    """Parse YAML 1.2 ``text`` into plain data with positions; raise :class:`LoadError`."""
    yaml = YAML(typ="safe", pure=True)
    yaml.version = (1, 2)
    doc = LoadedYaml(data=None, file=file)
    try:
        node = yaml.compose(io.StringIO(text))
    except MarkedYAMLError as exc:
        mark = exc.problem_mark or exc.context_mark
        pos = (mark.line + 1, mark.column + 1) if mark else (1, 1)
        message = exc.problem or exc.context or "invalid YAML"
        if "expected a single document" in str(exc):
            message = "only one YAML document is allowed per file"
        diag = _diag(file, message, pos)
        hint = "check the indentation, quoting and brackets on this line and the one above"
        raise LoadError(replace(diag, hint=hint)) from None
    except YAMLError as exc:
        raise LoadError(_diag(file, f"invalid YAML: {exc}")) from None
    except RecursionError:
        raise LoadError(_diag(file, f"nesting deeper than {MAX_DEPTH} levels")) from None
    if node is not None:
        doc.data = _Builder(yaml, doc).build(node, "")
    return doc


def load_yaml(path: Path, display: str | None = None) -> LoadedYaml:
    """Read ``path`` (≤ 10 MB, UTF-8) and parse it; ``display`` is the name used in diagnostics."""
    file = display if display is not None else str(path)
    if path.stat().st_size > MAX_FILE_BYTES:
        raise LoadError(_diag(file, "file is larger than 10 MB", code=ErrorCode.E303))
    raw = path.read_bytes()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        line = raw[: exc.start].count(b"\n") + 1
        column = exc.start - (raw.rfind(b"\n", 0, exc.start) + 1) + 1
        raise LoadError(_diag(file, "file is not valid UTF-8", (line, column))) from None
    return parse_yaml(text, file)


# --- Referenced files (FR-14, E301-E303) ---------------------------------------------------------

LOGO_MAX_BYTES: Final = 2 * 1024 * 1024
IMAGE_MAX_BYTES: Final = 5 * 1024 * 1024
_SNIFF_BYTES: Final = 1024


def _sniff(head: bytes) -> str | None:
    """Detect an image type from its first bytes (the extension is not trusted)."""
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "PNG"
    if head.startswith(b"\xff\xd8\xff"):
        return "JPEG"
    if head.startswith((b"GIF87a", b"GIF89a")):
        return "GIF"
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "WebP"
    text = head.decode("utf-8", errors="ignore").lstrip("\ufeff \t\r\n").lower()
    if text.startswith("<") and "<svg" in text:
        return "SVG"
    return None


@dataclass(frozen=True)
class _FileRule:
    kinds: tuple[str, ...]
    max_bytes: int

    @property
    def kinds_text(self) -> str:
        return ", ".join(self.kinds[:-1]) + f" or {self.kinds[-1]}"


_LOGO_RULE: Final = _FileRule(("PNG", "JPEG", "SVG"), LOGO_MAX_BYTES)
_IMAGE_RULE: Final = _FileRule(("PNG", "JPEG", "GIF", "WebP"), IMAGE_MAX_BYTES)


def _referenced_files(data: object) -> list[tuple[str, str, _FileRule]]:
    """``(dotted path, file path, rule)`` for the logo and every image evidence item."""
    if not isinstance(data, dict):
        return []
    refs: list[tuple[str, str, _FileRule]] = []
    branding = data.get("branding")
    if isinstance(branding, dict) and isinstance(branding.get("logo"), str) and branding["logo"]:
        refs.append(("branding.logo", branding["logo"], _LOGO_RULE))
    findings = data.get("findings")
    for i, finding in enumerate(findings if isinstance(findings, list) else []):
        evidence = finding.get("evidence") if isinstance(finding, dict) else None
        for j, item in enumerate(evidence if isinstance(evidence, list) else []):
            if isinstance(item, dict) and item.get("type") == "image":
                ref = item.get("path")
                if isinstance(ref, str) and ref:
                    refs.append((f"findings[{i}].evidence[{j}].path", ref, _IMAGE_RULE))
    return refs


def _check_file(base_dir: Path, ref: str, rule: _FileRule) -> tuple[ErrorCode, str] | None:
    """Return ``(code, message)`` if the referenced file is unusable, else ``None``."""
    target = (base_dir / ref).resolve()  # resolves ".." and symlinks
    if not target.is_relative_to(base_dir):
        return ErrorCode.E302, f"path '{ref}' resolves outside the project directory"
    if not target.is_file():
        return ErrorCode.E301, f"file '{ref}' not found"
    size = target.stat().st_size
    if size > rule.max_bytes:
        limit = rule.max_bytes // (1024 * 1024)
        return ErrorCode.E303, f"file '{ref}' is larger than {limit} MB"
    with target.open("rb") as handle:
        kind = _sniff(handle.read(_SNIFF_BYTES))
    if kind not in rule.kinds:
        found = kind or "unknown"
        return ErrorCode.E303, (
            f"unsupported file type for '{ref}' (found {found}; expected {rule.kinds_text})"
        )
    return None


def check_files(doc: LoadedYaml, base_dir: Path) -> list[Diagnostic]:
    """Check the logo and image evidence: confinement (E302), existence (E301), type/size (E303)."""
    root = base_dir.resolve()
    diagnostics: list[Diagnostic] = []
    for path, ref, rule in _referenced_files(doc.data):
        problem = _check_file(root, ref, rule)
        if problem:
            line, column = doc.position(path)
            diagnostics.append(Diagnostic(problem[0], problem[1], doc.file, line, column, path))
    return diagnostics


# --- CVSS vectors (E201-E205, W201) --------------------------------------------------------------


def check_cvss(doc: LoadedYaml) -> list[Diagnostic]:
    """Report every issue in each finding's ``cvss_vector``, at the vector's position."""
    diagnostics: list[Diagnostic] = []
    findings = doc.data.get("findings") if isinstance(doc.data, dict) else None
    for index, finding in enumerate(findings if isinstance(findings, list) else []):
        vector = finding.get("cvss_vector") if isinstance(finding, dict) else None
        if not isinstance(vector, str) or not vector:
            continue  # wrong type or empty: the model reports E103
        path = f"findings[{index}].cvss_vector"
        line, column = doc.position(path)
        diagnostics.extend(
            Diagnostic(issue.code, issue.message, doc.file, line, column, path, issue.hint)
            for issue in parse_vector(vector).issues
        )
    return diagnostics


# --- Warnings (W101, W102) ------------------------------------------------------------------------

PLACEHOLDER_RE: Final = re.compile(r"\b(?:TODO|TBD|FIXME)\b|\blorem\s+ipsum\b", re.IGNORECASE)


def _strings(value: object, path: str) -> Iterator[tuple[str, str]]:
    """Yield ``(dotted path, text)`` for every string value (not key) in the data."""
    if isinstance(value, str):
        yield path, value
    elif isinstance(value, dict):
        for key, child in value.items():
            yield from _strings(child, join_path(path, str(key)))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from _strings(child, join_path(path, index))


def check_warnings(doc: LoadedYaml) -> list[Diagnostic]:
    """Placeholder text (W101) and findings without evidence (W102)."""
    diagnostics: list[Diagnostic] = []
    for path, text in _strings(doc.data, ""):
        match = PLACEHOLDER_RE.search(text)
        if match:
            line, column = doc.position(path)
            diagnostics.append(
                Diagnostic(
                    ErrorCode.W101,
                    f"placeholder text '{match.group(0)}' found",
                    doc.file,
                    line,
                    column,
                    path,
                    hint="replace it with real content before sending the report",
                )
            )
    findings = doc.data.get("findings") if isinstance(doc.data, dict) else None
    for index, finding in enumerate(findings if isinstance(findings, list) else []):
        if not isinstance(finding, dict) or finding.get("evidence"):
            continue
        path = f"findings[{index}]"
        if "evidence" in finding:
            path = join_path(path, "evidence")
        finding_id = finding.get("id")
        name = f"finding {finding_id}" if isinstance(finding_id, str) else "finding"
        line, column = doc.position(path)
        diagnostics.append(
            Diagnostic(ErrorCode.W102, f"{name} has no evidence", doc.file, line, column, path)
        )
    return diagnostics


# --- Validation ---------------------------------------------------------------------------------

SUGGESTION_CUTOFF: Final = 0.6
EVIDENCE_TYPE_NAMES: Final = "text, http, image"


@dataclass
class ValidationResult:
    """The outcome of validating a findings file: the report (if valid) and all diagnostics."""

    report: Report | None
    diagnostics: list[Diagnostic]

    @property
    def errors(self) -> list[Diagnostic]:
        """Error-level diagnostics."""
        return [d for d in self.diagnostics if d.level is Level.ERROR]

    @property
    def warnings(self) -> list[Diagnostic]:
        """Warning-level diagnostics."""
        return [d for d in self.diagnostics if d.level is Level.WARNING]

    @property
    def ok(self) -> bool:
        """True when there are no errors (warnings are allowed)."""
        return not self.errors


def _models_in(annotation: object) -> list[type[BaseModel]]:
    """The model classes an annotation refers to, looking through Annotated/Optional/list/Union."""
    origin = get_origin(annotation)
    if origin is Annotated:
        return _models_in(get_args(annotation)[0])
    if origin in (list, Union, UnionType):
        return [m for arg in get_args(annotation) for m in _models_in(arg)]
    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        return [annotation]
    return []


def _type_tag(model: type[BaseModel]) -> str | None:
    """The literal ``type`` value of a discriminated-union member, if it has one."""
    field_info = model.model_fields.get("type")
    if field_info is None:
        return None
    args = get_args(field_info.annotation)
    return args[0] if len(args) == 1 and isinstance(args[0], str) else None


def _resolve(loc: tuple[str | int, ...]) -> tuple[tuple[str | int, ...], list[type[BaseModel]]]:
    """Walk a Pydantic ``loc`` from :class:`Report`.

    Returns the location without discriminated-union tags (which don't exist in the YAML) and
    the model classes that the location's parent mapping may be.
    """
    clean: list[str | int] = []
    models: list[type[BaseModel]] = [Report]
    parents: list[type[BaseModel]] = []
    for part in loc:
        parents = models
        if isinstance(part, int):
            clean.append(part)
            continue
        tagged = [m for m in models if _type_tag(m) == part and part not in m.model_fields]
        if tagged:
            models = tagged
            continue
        clean.append(part)
        fields = [m.model_fields[part] for m in models if part in m.model_fields]
        models = [m for f in fields for m in _models_in(f.annotation)]
    return tuple(clean), parents


def _path(loc: tuple[str | int, ...]) -> str:
    path = ""
    for part in loc:
        path = join_path(path, part)
    return path


def _sentence(msg: str) -> str:
    return msg[:1].lower() + msg[1:]


def _from_pydantic(error: ErrorDetails, doc: LoadedYaml) -> Diagnostic:
    """Map one Pydantic error to a diagnostic with the YAML position (FR-11, FR-12)."""
    kind = error["type"]
    loc, parents = _resolve(tuple(error["loc"]))
    path = _path(loc)
    ctx = error.get("ctx", {})
    hint: str | None = None
    pos = doc.position(path)

    if kind in ErrorCode.__members__:
        code, message = ErrorCode[kind], error["msg"]
        hint = ctx.get("hint")
    elif kind == "extra_forbidden":
        key = str(loc[-1])
        allowed = sorted({name for m in parents for name in m.model_fields})
        pos = doc.key_position(path)
        other_types = [m for m in EVIDENCE_TYPES if key in m.model_fields and m not in parents]
        if other_types and all(m in EVIDENCE_TYPES for m in parents):
            code = ErrorCode.E103
            evidence_type = _type_tag(parents[0])
            message = f"field '{key}' is not allowed for evidence type '{evidence_type}'"
            hint = "use 'content' for text/http evidence and 'path' for image evidence"
        else:
            code = ErrorCode.E101
            message = f"unknown field '{key}'"
            close = difflib.get_close_matches(key, allowed, n=1, cutoff=SUGGESTION_CUTOFF)
            if close:
                message += f"; did you mean '{close[0]}'?"
            hint = "allowed fields: " + ", ".join(allowed)
    elif kind == "missing":
        code, message = ErrorCode.E102, f"missing required field '{loc[-1]}'"
    elif kind == "union_tag_not_found":
        path = join_path(path, "type")
        code, message = ErrorCode.E102, "missing required field 'type'"
        hint = f"evidence type must be one of: {EVIDENCE_TYPE_NAMES}"
    elif kind == "union_tag_invalid":
        path = join_path(path, "type")
        pos = doc.position(path)
        code, message = ErrorCode.E103, f"invalid evidence type {ctx.get('tag')!r}"
        hint = f"evidence type must be one of: {EVIDENCE_TYPE_NAMES}"
    elif not loc and kind == "model_type" and doc.data is None:
        code, message = ErrorCode.E103, "file is empty; expected a findings.yaml document"
    elif not loc and kind == "model_type":
        code, message = ErrorCode.E103, "the top level of the file must be a mapping"
    else:
        code, message = ErrorCode.E103, _sentence(error["msg"])
        if kind.endswith("_type") and isinstance(error["input"], str | int | float | bool):
            message += f", got {error['input']!r}"
        if kind == "literal_error":
            hint = f"allowed values: {ctx.get('expected')}"
    return Diagnostic(code, message, doc.file, pos[0], pos[1], path, hint)


def _from_issue(issue: Issue, doc: LoadedYaml) -> Diagnostic:
    path = _path(issue.loc)
    line, column = doc.key_position(path) if issue.at_key else doc.position(path)
    return Diagnostic(issue.code, issue.message, doc.file, line, column, path, issue.hint)


def validate_document(doc: LoadedYaml, base_dir: Path | None = None) -> ValidationResult:
    """Validate loaded YAML and collect every diagnostic (FR-02).

    Referenced files are checked only when ``base_dir`` (the findings file's directory) is given.
    """
    diagnostics = [_from_issue(issue, doc) for issue in cross_checks(doc.data)]
    if base_dir is not None:
        diagnostics.extend(check_files(doc, base_dir))
    diagnostics.extend(check_cvss(doc))
    diagnostics.extend(check_warnings(doc))
    report: Report | None = None
    try:
        report = Report.model_validate(doc.data)
    except ValidationError as exc:
        diagnostics.extend(_from_pydantic(error, doc) for error in exc.errors())
    result = ValidationResult(report, sort_and_cap(diagnostics))
    if not result.ok:
        result.report = None
    return result


def load_report(path: Path, display: str | None = None) -> ValidationResult:
    """Load and validate a findings file; loader failures become diagnostics."""
    try:
        doc = load_yaml(path, display)
    except LoadError as exc:
        return ValidationResult(None, [exc.diagnostic])
    return validate_document(doc, base_dir=path.parent)
