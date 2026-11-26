# pentrep

> Turn a `findings.yaml` file into a professional penetration test report — HTML, PDF and Markdown —
> with CVSS 3.1 scoring and PII redaction built in.

**Status:** early development (v0.1 in progress). HTML and Markdown reports work; PDF output arrives
in the next milestone.

## Usage

```bash
pentrep init my-test/                      # example findings.yaml + logo + evidence image
pentrep validate my-test/findings.yaml     # every error with file:line:col, code and hint
pentrep build my-test/findings.yaml -f html -f md   # report/pentest-report.{html,md}
pentrep schema -o findings.schema.json     # JSON Schema for editor completion
```

| Command | Flags |
|---|---|
| `pentrep init [DIR]` | `--force`: overwrite existing files |
| `pentrep validate FILE` | `--strict`: treat warnings as errors · `--format text\|json`: JSON goes to stdout |
| `pentrep build FILE` | `-f, --format html\|md\|pdf\|all` (repeatable) · `-o, --output-dir DIR` · `-n, --name NAME` · `--template-dir DIR` · `--no-redact` · `--strict` · `-q, --quiet` |
| `pentrep schema` | `-o, --output FILE`: write to a file instead of stdout |
| global | `--version`, `--debug` (show tracebacks), `--help` |

Exit codes: `0` success, `1` validation failed, `2` usage error, `3` I/O or rendering failure.

- File format: [docs/schema.md](docs/schema.md)
- Error codes: [docs/errors.md](docs/errors.md)
- Custom templates: [docs/templates.md](docs/templates.md)

Redaction is a safety net, not a guarantee: always review evidence before you share a report.

- Product requirements: [docs/PRD.md](docs/PRD.md)
- Implementation plan & progress: [docs/PLAN.md](docs/PLAN.md)

## Development

```bash
uv sync
uv run pentrep --version
uv run pytest
```

## License

[MIT](LICENSE)
