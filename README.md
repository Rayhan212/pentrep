# pentrep

> Turn a `findings.yaml` file into a professional penetration test report — HTML, PDF and Markdown —
> with CVSS 3.1 scoring and PII redaction built in.

**Status:** early development (v0.1 in progress). HTML, Markdown and PDF reports work; packaging and
release come next.

## Usage

```bash
pentrep init my-test/                      # example findings.yaml + logo + evidence image
pentrep validate my-test/findings.yaml     # every error with file:line:col, code and hint
pentrep build my-test/findings.yaml               # report/pentest-report.{html,md,pdf}
pentrep schema -o findings.schema.json     # JSON Schema for editor completion
```

| Command | Flags |
|---|---|
| `pentrep init [DIR]` | `--force`: overwrite existing files |
| `pentrep validate FILE` | `--strict`: treat warnings as errors · `--format text\|json`: JSON goes to stdout |
| `pentrep build FILE` | `-f, --format html\|md\|pdf\|all` (repeatable) · `-o, --output-dir DIR` · `-n, --name NAME` · `--template-dir DIR` · `--paper a4\|letter` · `--no-redact` · `--strict` · `-q, --quiet` |
| `pentrep schema` | `-o, --output FILE`: write to a file instead of stdout |
| global | `--version`, `--debug` (show tracebacks), `--help` |

Exit codes: `0` success, `1` validation failed, `2` usage error, `3` I/O or rendering failure.

- File format: [docs/schema.md](docs/schema.md)
- Error codes: [docs/errors.md](docs/errors.md)
- Custom templates: [docs/templates.md](docs/templates.md)

Redaction is a safety net, not a guarantee: always review evidence before you share a report.

### PDF output

PDF rendering uses [WeasyPrint](https://weasyprint.org/), which needs the Pango and HarfBuzz system libraries:

| OS | Install |
|---|---|
| Debian / Ubuntu | `sudo apt install libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz0b` |
| macOS (Homebrew) | `brew install pango` (on Apple Silicon, also `export DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib`) |
| Other / Windows | Use the Docker image (coming with the v0.1.0 release) |

Without these libraries, `build` still writes the HTML and Markdown reports, then exits with code 3 and an
install hint. PDFs embed the bundled OFL fonts (Source Sans 3, Source Code Pro), so they look the same on every
machine.

- Product requirements: [docs/PRD.md](docs/PRD.md)
- Implementation plan & progress: [docs/PLAN.md](docs/PLAN.md)

## Development

```bash
uv sync
uv run pentrep --version
uv run pytest
```

## License

pentrep is released under the [MIT License](LICENSE).

The bundled fonts, Source Sans 3 and Source Code Pro by Adobe, are licensed under the SIL Open Font License,
Version 1.1. The licence text and both copyright notices are in
[`src/pentrep/themes/classic/fonts/OFL.txt`](src/pentrep/themes/classic/fonts/OFL.txt). It ships inside the wheel
next to the font files.
