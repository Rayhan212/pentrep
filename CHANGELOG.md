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
