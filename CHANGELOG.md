# Changelog

All notable changes to this project are documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Project skeleton: `pentrep` CLI with `--version`, `--help` and `--debug`.
- Tooling: uv, ruff, mypy (strict), pytest with coverage gate, pre-commit, GitHub Actions CI.
- `findings.yaml` schema v1 as Pydantic models, with safe YAML loading (no custom tags, alias-expansion
  limit, 10 MB limit) and a line/column for every value.
- `pentrep init [DIR] [--force]` creates an example project.
- `pentrep validate FILE [--strict] [--format text|json]` reports every error and warning with
  `file:line:col`, a stable code (E100–E106, E206, E301–E303, W101, W102) and a hint.
- `pentrep schema [-o FILE]` prints the JSON Schema (draft 2020-12).
- Docs: `docs/errors.md` and `docs/schema.md`.
- CVSS 3.1 base-score calculator (`pentrep.cvss`): vector parser with E201–E205 errors and W201 for
  ignored temporal/environmental metrics, canonical vectors, Roundup from spec Appendix A, sub-scores and
  severity bands. Checked against FIRST's published CVSS v3.1 examples and with property-based tests.
- `Finding.cvss` computed field; `stats` module with finding order, severity counts and overall risk.
- `validate` success line shows the severity breakdown, e.g. `2 findings (1 critical, 1 medium)`.
- Redaction engine (`pentrep.redact`): 9 built-in patterns (PRIVATE_KEY, JWT, BEARER, COOKIE, AWS_KEY,
  SECRET, CARD with Luhn, EMAIL, PRIVATE_IP), with priority/overlap rules, custom patterns with optional
  `value` groups (E304 for a bad name or regex), and an allowlist. Output is deterministic.
- `validate` prints a redaction preview with counts per pattern (never the values).
- `pentrep build FILE` with `-f html|md`, `-o`, `-n`, `--template-dir`, `--no-redact`, `--strict` and `-q`:
  a self-contained HTML report (inline CSS, `data:` images, no scripts, Pygments highlighting) and a GFM
  Markdown report with copied image assets, both from the `classic` theme. Output is deterministic and covered
  by golden files.
- Docs: `docs/templates.md` (template context, filters and partials for `--template-dir`).
- PDF output (`-f pdf`, part of the default `-f all`) with WeasyPrint: A4 or Letter (`--paper`), a
  classification header, `Page X of Y` footers, TOC page numbers, bookmarks and a new page per finding. It embeds
  only the bundled OFL fonts (Source Sans 3, Source Code Pro) and loads no external resources. If WeasyPrint's
  libraries are missing, the other formats are still written and the CLI exits 3 with an install hint.
