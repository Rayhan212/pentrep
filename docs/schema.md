# `findings.yaml` reference (schema_version 1)

`pentrep init` writes a complete example. `pentrep validate findings.yaml` checks a file against the rules
below, and `pentrep schema` prints them as a JSON Schema (draft 2020-12) for editors and CI. Error codes
are explained in [errors.md](errors.md).

## General rules

- The file is UTF-8 YAML 1.2 and at most 10 MB. Only plain mappings, lists, strings, numbers, booleans,
  `null` and dates are allowed. Custom tags, merge keys and duplicate keys are rejected (E100).
- Unknown keys are errors (E101). Types are not converted: `title: 12345` is an error, so write
  `title: "12345"` instead (E103).
- Dates are `YYYY-MM-DD`, written unquoted or quoted. Date-times are rejected.
- Relative paths (`branding.logo`, image evidence `path`) are resolved against the directory that contains
  `findings.yaml` and must stay inside it (E302).
- *Markdown* fields accept CommonMark plus GFM tables and fenced code. Raw HTML is escaped, not rendered.
- Placeholder text (`TODO`, `TBD`, `FIXME`, `lorem ipsum`) in any value is a warning (W101).

## Top level

| Key | Type | Required | Constraints / default |
|---|---|---|---|
| `schema_version` | int | yes | Must be `1` (E106) |
| `engagement` | object | yes | See [engagement](#engagement) |
| `branding` | object | no | See [branding](#branding) |
| `redaction` | object | no | See [redaction](#redaction) |
| `findings` | list | yes | 1–500 [findings](#findings) |

## `engagement`

| Key | Type | Required | Constraints / default |
|---|---|---|---|
| `title` | str | yes | 5–150 characters |
| `client` | object | yes | `name` (required, 1–100 chars), `contact` (≤ 150 chars) |
| `testers` | list | yes | 1–10 items: `name` (required, ≤ 100 chars), `email` (valid address), `role` (≤ 100 chars) |
| `start_date` | date | yes | |
| `end_date` | date | yes | ≥ `start_date` (E105) |
| `report_date` | date | no | Defaults to today, or the date of `SOURCE_DATE_EPOCH` (UTC) when it is set |
| `report_version` | str | no | `"1.0"`. Pattern `^\d+\.\d+$`, so quote it: `"1.0"` |
| `classification` | str | no | `"CONFIDENTIAL"`. ≤ 40 characters |
| `scope` | object | yes | `in_scope` (≥ 1 asset, required), `out_of_scope` (list of assets) |
| `methodology` | Markdown | yes | ≥ 20 characters |
| `executive_summary` | Markdown | no | If omitted, only the generated statistics are shown |

An **asset** is `{ asset: str, type: url | ip | cidr | hostname | api | mobile_app | other, notes: str }`.
`asset` and `type` are required.

## `branding`

| Key | Type | Required | Constraints / default |
|---|---|---|---|
| `company_name` | str | no | ≤ 80 characters. Shown on the cover and in the footer |
| `logo` | path | no | PNG, JPEG or SVG, ≤ 2 MB (E301–E303) |
| `accent_color` | str | no | `#RRGGBB`, default `#1F4E79` |

## `redaction`

Redaction is on by default. See [errors.md](errors.md#e304--invalid-custom-redaction-regex-or-invalid-pattern-name)
for pattern-name and regex rules.

| Key | Type | Required | Constraints / default |
|---|---|---|---|
| `enabled` | bool | no | `true` |
| `apply_to_all_text` | bool | no | `false` |
| `custom_patterns` | list | no | ≤ 50 items of `{ name, regex }`. `name`: `^[A-Z][A-Z0-9_]{1,31}$`, not a built-in name. `regex`: Python `re`; a `(?P<value>…)` group redacts only that part. Run after the built-in patterns (E304) |
| `allowlist` | list[str] | no | ≤ 200 exact strings that are never redacted |

## `findings`

| Key | Type | Required | Constraints / default |
|---|---|---|---|
| `id` | str | yes | `^[A-Z]{2,5}-\d{3,4}$` (for example `PT-001`), unique in the file (E104) |
| `title` | str | yes | 5–120 characters |
| `cvss_vector` | str | conditional | CVSS 3.1 base vector. Required unless `severity` is given (E206) |
| `severity` | str | conditional | Only `informational`, and only when `cvss_vector` is absent (E206) |
| `status` | str | no | `open` (default), `remediated` or `risk_accepted` |
| `cwe` | list[int] | no | Each 1–9999 |
| `affected_assets` | list[str] | yes | ≥ 1 non-empty item |
| `description` | Markdown | yes | ≥ 20 characters |
| `impact` | Markdown | yes | ≥ 20 characters |
| `steps_to_reproduce` | list[Markdown] | yes | ≥ 1 non-empty item, rendered as a numbered list |
| `evidence` | list | no | 0–30 [evidence items](#evidence). Missing or empty gives W102 |
| `remediation` | Markdown | yes | ≥ 20 characters |
| `references` | list[str] | no | `http://` or `https://` URLs only |

## Evidence

Each item has a `type` that decides which other keys are allowed. A key that belongs to a different type
is an error (E103).

| `type` | Keys |
|---|---|
| `text` | `caption` (3–200 chars, required), `content` (required, ≤ 200 KiB), `language` (optional hint such as `bash` or `json`) |
| `http` | `caption` (required), `content` (required, ≤ 200 KiB), shown with request/response highlighting |
| `image` | `caption` (required, used as alt text), `path` (required): PNG, JPEG, GIF or WebP, ≤ 5 MB |

```yaml
evidence:
  - type: http
    caption: "Login request with the payload"
    content: |
      POST /api/v1/login HTTP/1.1
      Host: portal.acme.example
  - type: image
    caption: "sqlmap enumerating tables"
    path: evidence/pt-001-sqlmap.png
```
