# Diagnostic codes

`pentrep validate` (and later `pentrep build`) reports every problem in `findings.yaml` with a stable
code, its position and a dotted path to the field:

```text
FILE:LINE:COLUMN: LEVEL[CODE] PATH: MESSAGE
  hint: HINT
```

- Lines and columns start at 1.
- Errors (`E…`) make `validate` exit with code 1. Warnings (`W…`) don't, unless `--strict` is given.
- Up to 100 diagnostics are shown per run, sorted by line.
- `--format json` prints the same diagnostics as a JSON array with the keys `code`, `severity`, `path`,
  `line`, `column`, `message` and `hint`.

The field reference is in [schema.md](schema.md). The examples below come from the test fixtures in
`tests/fixtures/invalid/`.

## E100 — YAML syntax error

The file is not valid YAML 1.2, or it uses a YAML feature that pentrep rejects for safety. These features
are rejected: tags such as `!!python/object`, merge keys (`<<`), duplicate keys, more than one document,
more than 1,000 nodes expanded through aliases, nesting deeper than 100 levels, and files that are not
UTF-8.

**Example**

```text
e100_syntax_error.yaml:20:19: error[E100] expected <block end>, but found '<scalar>'
  hint: check the indentation, quoting and brackets on this line and the one above
```

**Fix** — The parser often notices the mistake one line late. Here the closing quote of `title` on
line 19 is missing. Check that quotes and brackets are balanced and that indentation uses spaces.
Remove any custom tags and anchors.

## E101 — Unknown field

A key that is not part of the schema. This is often a typo. If a known key is close enough, the message
suggests it.

**Example**

```text
e101_unknown_field.yaml:33:5: error[E101] findings[0].remediaton: unknown field 'remediaton'; did you mean 'remediation'?
  hint: allowed fields: affected_assets, cvss_vector, cwe, description, evidence, id, impact, references, remediation, severity, status, steps_to_reproduce, title
```

**Fix** — Rename the key to one of the allowed fields, or remove it.

## E102 — Missing required field

A required field is absent. The position is the start of the mapping that needs the field.

**Example**

```text
e102_missing_field.yaml:4:3: error[E102] engagement.methodology: missing required field 'methodology'
```

**Fix** — Add the field. The required fields are marked in [schema.md](schema.md).

## E103 — Wrong type, length or pattern

A value has the wrong type (for example a number where text is expected), is too short or too long, does
not match the required pattern, is not one of the allowed values, or is a field that this evidence type
does not allow.

**Example**

```text
e103_wrong_type.yaml:4:10: error[E103] engagement.title: input should be a valid string, got 12345
e103_evidence_field.yaml:30:9: error[E103] findings[0].evidence[0].content: field 'content' is not allowed for evidence type 'image'
  hint: use 'content' for text/http evidence and 'path' for image evidence
```

**Fix** — Change the value to match the constraint in [schema.md](schema.md). Quote values that YAML
would otherwise read as numbers or booleans. Text and `http` evidence use `content`, and `image` evidence
uses `path`.

## E104 — Duplicate finding id

Two findings have the same `id`.

**Example**

```text
e104_duplicate_id.yaml:34:9: error[E104] findings[1].id: duplicate finding id 'PT-001' (first used in findings[0])
  hint: every finding needs a unique id, for example PT-001, PT-002
```

**Fix** — Give each finding its own id.

## E105 — end_date is before start_date

**Example**

```text
e105_end_before_start.yaml:10:13: error[E105] engagement.end_date: end_date 2026-11-01 is before start_date 2026-11-02
```

**Fix** — Correct one of the dates. A one-day engagement uses the same date for both.

## E106 — Unsupported schema_version

`schema_version` is not a version this release of pentrep understands. Only the integer `1` is
supported.

**Example**

```text
e106_schema_version.yaml:1:17: error[E106] schema_version: unsupported schema_version 2; this pentrep release supports schema_version: 1
```

**Fix** — Set `schema_version: 1` (unquoted), or upgrade pentrep if the file was written for a newer
release.

## E201 — CVSS vector missing the CVSS:3.1/ prefix, or an unsupported version

`cvss_vector` must start with `CVSS:3.1/` (case-sensitive, after trimming spaces). CVSS 3.0 vectors get a
hint, because their base metrics are the same as in 3.1. CVSS 2 and 4 are not supported.

**Example**

```text
e201_cvss_3_0_prefix.yaml:20:18: error[E201] findings[0].cvss_vector: CVSS version 3.0 is not supported
  hint: change the prefix to 'CVSS:3.1/'; the 3.0 and 3.1 base metrics are the same
```

**Fix** — Use a CVSS 3.1 base vector, for example `CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H`.

## E202 — Unknown CVSS metric

A metric name that is not part of CVSS 3.1, a wrongly-cased name (`av` instead of `AV`), or a part that
is not in `METRIC:VALUE` form (including `//` or a trailing `/`).

**Example**

```text
e202_unknown_metric.yaml:20:18: error[E202] findings[0].cvss_vector: unknown CVSS metric 'av'
  hint: metric names are case-sensitive: did you mean 'AV'?
```

**Fix** — Use the base metric names `AV`, `AC`, `PR`, `UI`, `S`, `C`, `I` and `A`, in upper case.

## E203 — Invalid value for a CVSS metric

**Example**

```text
e203_invalid_value.yaml:20:18: error[E203] findings[0].cvss_vector: invalid value 'X' for metric 'AV'
  hint: AV must be one of N (Network), A (Adjacent), L (Local), P (Physical)
```

**Fix** — Use one of the values listed in the hint. Values are case-sensitive.

## E204 — Missing CVSS base metric(s)

All 8 base metrics must be present.

**Example**

```text
e204_missing_metric.yaml:20:18: error[E204] findings[0].cvss_vector: missing CVSS base metric 'UI'
  hint: UI must be one of N (None), R (Required)
```

**Fix** — Add the missing metrics. The easiest way is to copy the full vector from the FIRST CVSS 3.1
calculator.

## E205 — Duplicate CVSS metric

**Example**

```text
e205_duplicate_metric.yaml:20:18: error[E205] findings[0].cvss_vector: duplicate CVSS metric 'AV'
  hint: each metric may appear only once
```

**Fix** — Remove the extra occurrence, and keep the value you meant.

## E206 — Both cvss_vector and severity given, or neither

Every finding is scored with a CVSS 3.1 vector. Only an informational finding has no vector, and it is
marked with `severity: informational` instead.

**Example**

```text
e206_vector_and_severity.yaml:21:5: error[E206] findings[0].severity: both 'cvss_vector' and 'severity' are set; use only one
  hint: 'severity: informational' is only for findings without a CVSS vector
```

**Fix** — Keep `cvss_vector` and remove `severity`, or the other way round for an informational
finding. If neither is present, add one of them.

## E301 — Referenced file not found

The `branding.logo` file or an image evidence `path` does not exist, or it is not a regular file.

**Example**

```text
e301_file_not_found.yaml:30:15: error[E301] findings[0].evidence[0].path: file 'evidence/missing.png' not found
```

**Fix** — Relative paths are resolved against the directory that contains `findings.yaml`. Check the
spelling and the directory.

## E302 — Path resolves outside the project directory

A referenced file is outside the directory that contains `findings.yaml`. This also applies to paths
reached through `..`, an absolute path or a symlink. It is rejected so that a findings file can't embed
arbitrary files from your machine in a report.

**Example**

```text
e302_path_traversal.yaml:30:15: error[E302] findings[0].evidence[0].path: path '../valid/evidence/pt-001-sqlmap.png' resolves outside the project directory
```

**Fix** — Copy the file into the project directory (for example `evidence/`) and reference it there.

## E303 — Unsupported file type, or file too large

The file type is detected from the file's content, not its extension. The limits are:

| Field | Types | Max size |
|---|---|---|
| `branding.logo` | PNG, JPEG, SVG | 2 MB |
| image evidence `path` | PNG, JPEG, GIF, WebP | 5 MB |
| `findings.yaml` itself | YAML | 10 MB |

**Example**

```text
e303_unsupported_type.yaml:30:15: error[E303] findings[0].evidence[0].path: unsupported file type for 'evidence/not-an-image.png' (found unknown; expected PNG, JPEG, GIF or WebP)
```

**Fix** — Convert the image to a supported format, or shrink it (for example crop the screenshot or save
it as JPEG).

## E304 — Invalid custom redaction regex, or invalid pattern name

A `redaction.custom_patterns` entry has a `regex` that doesn't compile with Python's `re` module, or a
`name` that doesn't match `^[A-Z][A-Z0-9_]{1,31}$` or that is already used by a built-in pattern
(`PRIVATE_KEY`, `JWT`, `BEARER`, `COOKIE`, `AWS_KEY`, `SECRET`, `CARD`, `EMAIL`, `PRIVATE_IP`).

**Example**

```text
e304_bad_regex.yaml:20:14: error[E304] redaction.custom_patterns[0].regex: invalid regex: missing ), unterminated subpattern at position 5
  hint: use Python re syntax; a (?P<value>...) group redacts only that part
e304_bad_name.yaml:21:13: error[E304] redaction.custom_patterns[1].name: pattern name 'EMAIL' is already used by a built-in pattern
  hint: choose another name, for example ACME_EMAIL
```

**Fix** — Correct the regular expression, quoting it with single quotes in YAML so that backslashes are
kept. Rename the pattern to upper case with underscores, for example `ACME_EMPLOYEE_ID`.

## W101 — Placeholder text found

A text value contains `TODO`, `TBD`, `FIXME` or `lorem ipsum` (case-insensitive, whole words only).

**Example**

```text
w101_placeholder.yaml:23:18: warning[W101] findings[0].description: placeholder text 'TODO' found
  hint: replace it with real content before sending the report
```

**Fix** — Replace the placeholder with the real text. Use `--strict` in CI to make this an error.

## W102 — Finding has no evidence

A finding has no `evidence` key, or the list is empty.

**Example**

```text
w102_no_evidence.yaml:18:5: warning[W102] findings[0]: finding PT-001 has no evidence
```

**Fix** — Add at least one `text`, `http` or `image` evidence item, or accept the warning for findings
that really have none.

## W201 — Temporal/environmental CVSS metrics present

The vector contains temporal (`E`, `RL`, `RC`) or environmental (`CR`, `IR`, `AR`, `MAV`, `MAC`, `MPR`,
`MUI`, `MS`, `MC`, `MI`, `MA`) metrics. pentrep v0.1 calculates only the base score, so it ignores them
and leaves them out of the canonical vector shown in the report. Their values are not checked.

**Example**

```text
w201_temporal_metrics.yaml:20:18: warning[W201] findings[0].cvss_vector: temporal/environmental metrics are ignored in v0.1: E, RL
  hint: only the base score is calculated; remove them to silence this warning
```

**Fix** — Remove the extra metrics, or accept the warning.
