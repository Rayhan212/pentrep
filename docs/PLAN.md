# pentrep — Implementation Plan (v0.1)

Spec: [PRD.md](PRD.md) · Working rules: [../CLAUDE.md](../CLAUDE.md)

**How to use this file**
- Each task takes ≤ 1–2 hours. Do them in order; tick a task `[x]` only when it meets the Definition of Done in CLAUDE.md.
- `files:` lists the files a task is expected to create or change.
- Every milestone ends with a `verify:` task and leaves the tool in a runnable state (see "Runnable at the end").
- Dependencies listed in PRD §6 are pre-approved. They are added in the task that first needs them, never earlier.
  Any other dependency is marked **(needs approval)** and must be confirmed before that task starts.
- If scope changes, add a short `> note:` under the task. Don't silently rewrite the task.

---

## M1 — Skeleton, CLI & tooling (incl. CI)
Runnable at the end: `uv run pentrep --version`, `uv run pentrep --help`, CI green on push.

- [x] M1.1 Repo basics: `.gitignore` (`output/`, `report/`, `tmp/`, `.env*`, `.venv/`, `dist/`, `.coverage`, `htmlcov/`, `.mypy_cache/`), MIT licence, README stub, CHANGELOG with an `Unreleased` section
  files: `.gitignore`, `LICENSE`, `README.md`, `CHANGELOG.md`
- [x] M1.2 Check that the name `pentrep` is free on PyPI and GHCR (R-07) and record the result as a note here
  files: `docs/PLAN.md`
  > note (2026-11-26): PyPI and TestPyPI return 404 for `pentrep`, so the name is free. GHCR images live in the
  > owner's namespace (`ghcr.io/rayhan212/pentrep`), so they can't clash; the proxy blocked a direct GHCR check (403).
- [x] M1.3 `pyproject.toml`: hatchling, metadata, `requires-python = ">=3.11"`, `typer` runtime dep, `[project.scripts] pentrep = "pentrep.cli:main"`, dev dependency group (pytest, pytest-cov, ruff, mypy, pre-commit); generate `uv.lock`
  files: `pyproject.toml`, `uv.lock`
  > note: the entry point is `pentrep.cli:main` (a wrapper around the Typer `app`), so M1.6 can add
  > top-level error handling. Runtime deps are pinned below the next major version (`typer>=0.29.2,<1`).
- [x] M1.4 Tool config in `pyproject.toml`: ruff (rules `E,F,I,B,UP,S,SIM,RUF`, line length 100), mypy `strict = true`, pytest (`--strict-markers`, markers `pdf` and `perf`, `testpaths`), coverage (`branch = true`, `fail_under = 85`)
  files: `pyproject.toml`
- [x] M1.5 TDD: test that `--version` and `python -m pentrep --version` print `pentrep 0.1.0.dev0`; implement the Typer app, `__version__` and `__main__`
  files: `tests/cli/test_cli.py`, `tests/conftest.py`, `src/pentrep/__init__.py`, `src/pentrep/__main__.py`, `src/pentrep/cli.py`
- [x] M1.6 TDD: `ExitCode` enum (0/1/2/3), global `--debug` flag, internal-error handler that prints no traceback without `--debug` (FR-00c, FR-00d), and `NO_COLOR` / non-TTY colour handling (FR-00e)
  files: `src/pentrep/diagnostics.py`, `src/pentrep/cli.py`, `tests/cli/test_cli.py`
- [x] M1.7 Pre-commit hooks: ruff, ruff-format, mypy, check-yaml, end-of-file-fixer, detect-private-key
  files: `.pre-commit-config.yaml`
  > note: ruff and mypy run as `repo: local` hooks via `uv run --frozen`, so their versions come from `uv.lock`
  > (same as CI). Generic hooks come from `pre-commit/pre-commit-hooks` v6.0.0.
- [x] M1.8 CI workflow: uv setup; ruff, mypy and pytest with the coverage gate; matrix Python 3.11–3.14 × {ubuntu-22.04, ubuntu-24.04, macos-latest}; install Pango (apt / brew) now so the PDF jobs later need no CI changes
  files: `.github/workflows/ci.yml`
  > note: `libharfbuzz-subset0` doesn't exist on Ubuntu 22.04, so it's installed only when available (plus `libharfbuzz0b`).
  > Typer forces colour when `GITHUB_ACTIONS`/`FORCE_COLOR`/`PY_COLORS` is set, so CLI tests remove those vars.
- [x] M1.9 verify: `uv run ruff check . && uv run ruff format --check . && uv run mypy src && uv run pytest && uv run pentrep --version` all pass locally, and the CI run on GitHub is green for all matrix jobs
  > note (2026-11-26): passed locally (18 tests, 97.96 % coverage) and in CI run 45738160801 (13/13 jobs green).

## M2 — Schema, loader & `init` / `validate` / `schema`
Runnable at the end: `pentrep init`, then `pentrep validate` with file:line:col errors, and `pentrep schema`.

- [ ] M2.1 TDD: `ErrorCode` enum (E100–E106, E301–E304, W101, W102), `Diagnostic` dataclass, text formatter (PRD §4.2.4 format) and JSON formatter
  files: `src/pentrep/diagnostics.py`, `tests/unit/test_diagnostics.py`
- [ ] M2.2 TDD: YAML loader using ruamel.yaml safe mode: 10 MB limit, alias/anchor limit of 1,000 nodes, E100 with line/col, and a map from dotted path to (line, col) for every node. Add the `ruamel.yaml` dep
  files: `src/pentrep/loader.py`, `tests/unit/test_loader.py`, `pyproject.toml`, `uv.lock`
- [ ] M2.3 TDD: models part 1: `Engagement`, `Client`, `Tester`, `Asset`, `Scope`, `Branding`, all with `extra="forbid"`; date rule E105; `report_date` default from `SOURCE_DATE_EPOCH`. Add the `pydantic` dep
  files: `src/pentrep/models.py`, `tests/unit/test_models.py`, `pyproject.toml`, `uv.lock`
- [ ] M2.4 TDD: models part 2: `Finding` and `Evidence` (type-dependent fields, E103), `status`, `cwe`, `references`; `cvss_vector` / `severity` exclusivity (E206, vector checked only as a string for now); duplicate ids (E104); `schema_version` (E106)
  files: `src/pentrep/models.py`, `tests/unit/test_models.py`
- [ ] M2.5 TDD: map Pydantic errors to diagnostics (E101 with a difflib "did you mean" at ratio ≥ 0.6, E102, E103) with line/col from the loader map; collect all errors, sort by line, cap at 100
  files: `src/pentrep/loader.py`, `src/pentrep/diagnostics.py`, `tests/unit/test_loader.py`
- [ ] M2.6 TDD: file checks for `logo` and image evidence: path confinement including symlinks (E302), file exists (E301), type and size limits (E303)
  files: `src/pentrep/loader.py`, `tests/security/test_hardening.py`
- [ ] M2.7 TDD: warnings W101 (placeholder text) and W102 (finding without evidence)
  files: `src/pentrep/loader.py`, `tests/unit/test_loader.py`
- [ ] M2.8 Fixtures: `valid/minimal.yaml` and `valid/full.yaml`; one `invalid/<code>_<case>.yaml` per E1xx/E3xx/W1xx code with a matching `.expected.txt` (stderr golden); a parametrised test over all of them
  files: `tests/fixtures/valid/*`, `tests/fixtures/invalid/*`, `tests/unit/test_fixtures.py`
- [ ] M2.9 Security tests: a `!!python/object` tag is rejected, a billion-laughs file is rejected, and a `../` path gives E302
  files: `tests/security/test_hardening.py`
- [ ] M2.10 TDD: `pentrep init [DIR] [--force]` (FR-01) with the scaffold from PRD §4.2.3 and placeholder PNGs; mirror it into `examples/`
  files: `src/pentrep/scaffold/**`, `examples/**`, `src/pentrep/cli.py`, `tests/cli/test_init.py`
- [ ] M2.11 TDD: `pentrep validate FILE [--strict] [--format text|json]` (FR-02): exit codes 0/1, success line `✓ … valid: N findings, N warnings`
  files: `src/pentrep/cli.py`, `tests/cli/test_validate.py`
- [ ] M2.12 TDD: `pentrep schema [-o FILE]` (FR-04); test that the output validates the scaffold and rejects schema-error fixtures. Needs the dev dep `jsonschema` **(needs approval)**
  files: `src/pentrep/cli.py`, `tests/cli/test_schema.py`, `pyproject.toml`, `uv.lock`
- [ ] M2.13 Docs: `docs/errors.md` (every code with an example and fix), `docs/schema.md`, and the NFR-13 test that compares `docs/errors.md` with `ErrorCode`
  files: `docs/errors.md`, `docs/schema.md`, `tests/unit/test_docs.py`
- [ ] M2.14 verify: `uv run pytest && uv run pentrep init tmp/m2 && uv run pentrep validate tmp/m2/findings.yaml` (exit 0, "0 warnings") `&& ! uv run pentrep validate tests/fixtures/invalid/e101_unknown_field.yaml` (exit 1, shows file:line:col + "did you mean") `&& uv run pentrep schema > /dev/null`

## M3 — CVSS 3.1 calculator
Runnable at the end: `pentrep validate` scores each finding and prints the severity breakdown; invalid vectors produce E2xx errors with hints.

- [ ] M3.1 TDD: `roundup()` using the integer algorithm from spec Appendix A, with the edge cases 4.02, 4.00 and 4.000000000000001
  files: `src/pentrep/cvss.py`, `tests/unit/test_cvss.py`
- [ ] M3.2 TDD: vector parser: `CVSS:3.1/` prefix, metrics in any order, case-sensitive; E201–E205 with hints; temporal/environmental metrics trigger W201; `CvssVector.canonical()`. Add the E2xx/W201 codes
  files: `src/pentrep/cvss.py`, `src/pentrep/diagnostics.py`, `tests/unit/test_cvss.py`
- [ ] M3.3 TDD: weights (with PR adjusted when S:C), ISS, Impact, Exploitability, base score, and sub-scores rounded to one decimal
  files: `src/pentrep/cvss.py`, `tests/unit/test_cvss.py`
- [ ] M3.4 TDD: `Severity` enum with the bands and ordering (None/Informational < Low < … < Critical)
  files: `src/pentrep/cvss.py`, `tests/unit/test_cvss.py`
- [ ] M3.5 Reference vectors: build `cvss_vectors.json` with ≥ 30 vectors (the 11 from PRD §4.3 plus more) cross-checked with the official FIRST calculator; add a parametrised test
  files: `tests/fixtures/cvss_vectors.json`, `tests/unit/test_cvss.py`
- [ ] M3.6 Property tests with hypothesis (score range, one decimal, monotonic C/I/A, idempotent canonical form), 1,000 examples each. Add the `hypothesis` dev dep
  files: `tests/unit/test_cvss_properties.py`, `pyproject.toml`, `uv.lock`
- [ ] M3.7 Integration: a computed `Finding.cvss` field; CVSS diagnostics carry the vector's line/col; invalid fixtures `e201`–`e205` and `w201` with `.expected.txt`; update `docs/errors.md`
  files: `src/pentrep/models.py`, `src/pentrep/loader.py`, `tests/fixtures/invalid/*`, `docs/errors.md`
- [ ] M3.8 TDD: `stats.py` with finding order (FR-42), severity counts and overall risk (FR-43); `validate` success line gains `(1 critical, 1 medium)`
  files: `src/pentrep/stats.py`, `tests/unit/test_stats.py`, `src/pentrep/cli.py`, `tests/cli/test_validate.py`
- [ ] M3.9 verify: `uv run pytest --cov=pentrep.cvss --cov-branch --cov-fail-under=95 tests/unit/test_cvss*.py && uv run pentrep validate examples/findings.yaml` (prints "2 findings (1 critical, 1 medium)")

## M4 — PII redaction
Runnable at the end: `pentrep validate` checks redaction config (E304) and prints a redaction preview summary.

- [ ] M4.1 TDD: engine core: `Pattern` dataclass, priority and overlap resolution (each character redacted at most once), `value` group support, `[REDACTED:NAME]` token, deterministic output
  files: `src/pentrep/redact.py`, `tests/unit/test_redact.py`
- [ ] M4.2 TDD: built-in patterns `PRIVATE_KEY`, `JWT`, `BEARER`, `COOKIE` (keeping cookie names and attributes), each with a positive and a negative corpus of ≥ 5 samples
  files: `src/pentrep/redact.py`, `tests/fixtures/redaction/*`, `tests/unit/test_redact_patterns.py`
- [ ] M4.3 TDD: built-in patterns `AWS_KEY`, `SECRET` (query, form, JSON and header forms), `CARD` (with Luhn check), with corpora
  files: `src/pentrep/redact.py`, `tests/fixtures/redaction/*`, `tests/unit/test_redact_patterns.py`
- [ ] M4.4 TDD: built-in patterns `EMAIL` and `PRIVATE_IP` (confirmed with `ipaddress`; public, loopback and RFC 5737 ranges are kept), with corpora
  files: `src/pentrep/redact.py`, `tests/fixtures/redaction/*`, `tests/unit/test_redact_patterns.py`
- [ ] M4.5 TDD: `Redaction` config model (`enabled`, `apply_to_all_text`, `custom_patterns` ≤ 50, `allowlist` ≤ 200); E304 for a bad regex or name; custom patterns run after built-ins; allowlisted values are skipped and not counted
  files: `src/pentrep/models.py`, `src/pentrep/redact.py`, `tests/unit/test_redact.py`, `tests/fixtures/invalid/e304_*`
- [ ] M4.6 TDD: `redact_report(report) -> (report, RedactionSummary)` over the fields in FR-30, counting image evidence items that were not scanned
  files: `src/pentrep/redact.py`, `tests/unit/test_redact.py`
- [ ] M4.7 TDD: summary formatter (FR-35; never prints original values) and a `validate` "Redaction preview: …" line. Also update PRD FR-02 to describe this line
  files: `src/pentrep/redact.py`, `src/pentrep/cli.py`, `tests/cli/test_validate.py`, `docs/PRD.md`
- [ ] M4.8 Test the PRD §4.2.3 example: the redacted PT-001 and PT-002 evidence equals the expected text in the PRD exactly
  files: `tests/unit/test_redact_example.py`
- [ ] M4.9 Leak-test harness: fixture `valid/leaky.yaml` seeding 20 unique secrets, plus helper `assert_no_leaks(texts)`; apply it now to `validate` stdout/stderr and the `--debug` log
  files: `tests/fixtures/valid/leaky.yaml`, `tests/conftest.py`, `tests/security/test_leaks.py`
- [ ] M4.10 verify: `uv run pytest --cov=pentrep.redact --cov-branch --cov-fail-under=95 tests/unit/test_redact*.py tests/security && uv run pentrep validate examples/findings.yaml` (prints "Redaction preview: 6 values … SECRET×1, COOKIE×1, JWT×1, EMAIL×1, ACME_EMPLOYEE_ID×1, PRIVATE_IP×1")

## M5 — HTML & Markdown renderer (`classic` theme)
Runnable at the end: `pentrep build examples/findings.yaml -f html -f md` produces a redacted, self-contained report.

- [ ] M5.1 TDD: Markdown helper using markdown-it-py with `html=False`, GFM tables, and `javascript:`/`data:` links neutralised. Add the `markdown-it-py` dep
  files: `src/pentrep/render/markdown.py`, `tests/render/test_markdown_helper.py`, `pyproject.toml`, `uv.lock`
- [ ] M5.2 TDD: template context builder (`engagement`, `branding`, sorted `findings`, `stats`, `redaction`, `generated_at`, `pentrep_version`)
  files: `src/pentrep/render/context.py`, `tests/render/test_context.py`
- [ ] M5.3 TDD: Jinja environment with a `ChoiceLoader` (`--template-dir` first, then the built-in theme), autoescape for HTML and `StrictUndefined`. Add the `jinja2` dep
  files: `src/pentrep/render/__init__.py`, `tests/render/test_env.py`, `pyproject.toml`, `uv.lock`
- [ ] M5.4 HTML theme part 1: `report.html.j2`, partials for cover, document control, TOC and executive summary with the stats table; `style.css` with the accent colour variable and severity palette; contrast test (FR-44)
  files: `src/pentrep/themes/classic/**`, `tests/render/test_theme.py`
- [ ] M5.5 HTML theme part 2: scope & methodology, summary table, finding partial, evidence with Pygments inline CSS (HTTP lexer), appendices A/B, `UNREDACTED DRAFT` banner (FR-36). Add the `pygments` dep
  files: `src/pentrep/themes/classic/**`, `pyproject.toml`, `uv.lock`
- [ ] M5.6 TDD: HTML renderer that inlines CSS and turns images into `data:` URIs; tests for no `<script>`, no external `src`/`url()`, `lang="en"`, no skipped heading levels, captions used as alt text
  files: `src/pentrep/render/html.py`, `tests/render/test_html.py`
- [ ] M5.7 TDD: Markdown report with `report.md.j2`, images copied to `assets/<id>-<n>.<ext>`, automatic fence length, GFM tables, text severity badges
  files: `src/pentrep/themes/classic/report.md.j2`, `src/pentrep/render/md.py`, `tests/render/test_md.py`
- [ ] M5.8 TDD: `pentrep build` for html/md (FR-03): `-f`, `-o`, `-n`, `--template-dir`, `--no-redact`, `--strict`, `-q`; validation runs first; prints written paths, sizes and the redaction summary
  files: `src/pentrep/cli.py`, `tests/cli/test_build.py`
- [ ] M5.9 Golden files: `--update-golden` pytest option, `SOURCE_DATE_EPOCH` fixed, version string normalised; generate and review `report.html` and `report.md`
  files: `tests/conftest.py`, `tests/render/test_golden.py`, `tests/golden/report.html`, `tests/golden/report.md`
- [ ] M5.10 Security and leak tests on output: XSS in a description, `{{ 7*7 }}` and `{% %}` in a title rendered literally, `javascript:` link neutralised, no network access (add the `pytest-socket` dev dep), `assert_no_leaks` on HTML/MD built from `leaky.yaml`
  files: `tests/security/test_hardening.py`, `tests/security/test_leaks.py`, `pyproject.toml`, `uv.lock`
- [ ] M5.11 Template override test (override only `partials/cover.html.j2`; everything else stays golden-identical) and `docs/templates.md`
  files: `tests/render/test_override.py`, `tests/fixtures/templates/**`, `docs/templates.md`
- [ ] M5.12 verify: `uv run pytest && uv run pentrep build examples/findings.yaml -f html -f md -o tmp/m5` (exit 0; `tmp/m5/pentest-report.{html,md}` and `tmp/m5/assets/` exist; `grep -c "REDACTED" tmp/m5/pentest-report.html` ≥ 6); golden tests pass on ubuntu and macOS in CI

## M6 — PDF export
Runnable at the end: `pentrep build examples/findings.yaml` (default `-f all`) produces HTML, MD and PDF.

- [ ] M6.1 Decide the font (Q-06), bundle the OFL font and its licence, and add a wheel-size check script (≤ 2 MB, NFR-12)
  files: `src/pentrep/themes/classic/fonts/**`, `src/pentrep/themes/classic/style.css`, `tests/unit/test_package_size.py`
- [ ] M6.2 TDD: PDF wrapper with lazy WeasyPrint import and a dependency check that raises `RenderError` with OS-specific hints (apt, brew, Docker); test the missing-library case with a simulated import failure. Add the `weasyprint` dep
  files: `src/pentrep/render/pdf.py`, `tests/render/test_pdf.py`, `pyproject.toml`, `uv.lock`
- [ ] M6.3 Print CSS: `@page` A4/Letter, classification header, `Page X of Y` footer, no header on the cover, page break before each finding, TOC page numbers via `target-counter`, bookmarks for h1/h2
  files: `src/pentrep/themes/classic/style.css`, `src/pentrep/themes/classic/partials/*`
- [ ] M6.4 TDD: `build -f pdf` / `-f all` with `--paper`; on partial success, HTML and MD are written, then exit 3 with a hint and no traceback
  files: `src/pentrep/cli.py`, `tests/cli/test_build.py`
- [ ] M6.5 PDF structural tests (marker `pdf`) with pypdf: page size, finding titles in the text, one finding per page, footers, bookmarks. Add the `pypdf` dev dep
  files: `tests/render/test_pdf.py`, `pyproject.toml`, `uv.lock`
- [ ] M6.6 Content-parity test (same ids, titles, scores and severities in HTML, MD and PDF) and the PDF leak test on `leaky.yaml`
  files: `tests/render/test_parity.py`, `tests/security/test_leaks.py`
- [ ] M6.7 CI: set `PENTREP_REQUIRE_PDF=1` so a skipped `pdf` test fails in CI; check that PDF tests run on ubuntu and macOS
  files: `tests/conftest.py`, `.github/workflows/ci.yml`
- [ ] M6.8 verify: `uv run pytest -m pdf && uv run pentrep build examples/findings.yaml -o tmp/m6 && uv run pentrep build examples/findings.yaml -f pdf --paper letter -o tmp/m6-letter` (both exit 0, `tmp/m6/pentest-report.pdf` opens, and CI shows 0 skipped `pdf` tests)

## M7 — Sample report, packaging, Docker & release
Runnable at the end: `pipx install pentrep && pentrep init && pentrep build findings.yaml`, and `docker run … build findings.yaml`.

- [ ] M7.1 Perf benchmarks (NFR-01..04): a generator for 50 findings with 20 images, timing tests marked `perf`, a dedicated CI job, and a check that `--help` does not import `weasyprint`
  files: `tests/perf/test_benchmarks.py`, `tests/perf/conftest.py`, `.github/workflows/ci.yml`
- [ ] M7.2 Packaging smoke job: build the wheel, install it into a fresh venv, run `init` + `build -f all` in a temp dir, assert three non-empty files, check wheel size ≤ 2 MB
  files: `.github/workflows/ci.yml`
- [ ] M7.3 Dockerfile: `python:3.12-slim` with the Pango/HarfBuzz libs, non-root user, `WORKDIR /work`, `ENTRYPOINT ["pentrep"]`; `.dockerignore`; local check that the image is ≤ 400 MB
  files: `Dockerfile`, `.dockerignore`
- [ ] M7.4 Docker workflow: build, smoke test (`init` + `build`), push to GHCR on tags (`:<version>`, `:latest`)
  files: `.github/workflows/docker.yml`
- [ ] M7.5 GitHub Pages workflow: build the sample report from `examples/` (HTML + PDF) and publish it
  files: `.github/workflows/pages.yml`
- [ ] M7.6 Release workflow with PyPI Trusted Publishing: `v*-rc*` tags go to TestPyPI, `v*.*.*` tags go to PyPI. The trusted publisher must be configured on pypi.org and test.pypi.org by the repo owner (a manual step)
  files: `.github/workflows/release.yml`
- [ ] M7.7 README: quickstart (3 commands), WeasyPrint install matrix, Docker usage, cover and finding screenshots, links to the sample report, the "redaction is a safety net" notice, a link to `docs/errors.md`
  files: `README.md`, `docs/img/*`
- [ ] M7.8 Release candidate: bump to `0.1.0rc1`, update CHANGELOG, tag `v0.1.0-rc1`; in a clean `python:3.12` container run the TestPyPI `pipx install` → `init` → `build -f html -f md` (PRD M7 AC)
  files: `src/pentrep/__init__.py`, `CHANGELOG.md`
- [ ] M7.9 verify: `uv run pytest -m "perf or not perf"` green; `docker run --rm -v "$PWD/tmp/m7:/work" ghcr.io/<github-user>/pentrep:0.1.0rc1 init && docker run --rm -v "$PWD/tmp/m7:/work" ghcr.io/<github-user>/pentrep:0.1.0rc1 build findings.yaml` produces 3 files; the Pages site shows the sample report; then bump to `0.1.0`, tag `v0.1.0`, and confirm `pipx install pentrep` from PyPI works
