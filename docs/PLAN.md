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

- [x] M2.1 TDD: `ErrorCode` enum (E100–E106, E301–E304, W101, W102), `Diagnostic` dataclass, text formatter (PRD §4.2.4 format) and JSON formatter
  files: `src/pentrep/diagnostics.py`, `tests/unit/test_diagnostics.py`
  > note: `E206` is also in the enum now, because M2.4 emits it. The JSON-format test validates against
  > `DIAGNOSTICS_JSON_SCHEMA`, so the approved `jsonschema` dev dep was added here instead of in M2.12.
- [x] M2.2 TDD: YAML loader using ruamel.yaml safe mode: 10 MB limit, alias/anchor limit of 1,000 nodes, E100 with line/col, and a map from dotted path to (line, col) for every node. Add the `ruamel.yaml` dep
  files: `src/pentrep/loader.py`, `tests/unit/test_loader.py`, `pyproject.toml`, `uv.lock`
  > note: nodes are composed with ruamel.yaml and turned into plain data by pentrep itself, so only
  > standard tags (str/int/float/bool/null/timestamp, map, seq) are accepted; merge keys, duplicate keys and
  > nesting deeper than 100 levels are E100. A file over 10 MB is E303 (file too large), not E100.
- [x] M2.3 TDD: models part 1: `Engagement`, `Client`, `Tester`, `Asset`, `Scope`, `Branding`, all with `extra="forbid"`; date rule E105; `report_date` default from `SOURCE_DATE_EPOCH`. Add the `pydantic` dep
  files: `src/pentrep/models.py`, `tests/unit/test_models.py`, `pyproject.toml`, `uv.lock`
  > note: models are strict (no type coercion) and frozen. Dates accept YAML dates or `YYYY-MM-DD` strings;
  > date-times are rejected. Tester `email` is checked with a simple pattern, because pydantic `EmailStr` needs
  > the unapproved `email-validator` dep. A `SOURCE_DATE_EPOCH` that is not an integer is ignored.
- [x] M2.4 TDD: models part 2: `Finding` and `Evidence` (type-dependent fields, E103), `status`, `cwe`, `references`; `cvss_vector` / `severity` exclusivity (E206, vector checked only as a string for now); duplicate ids (E104); `schema_version` (E106)
  files: `src/pentrep/models.py`, `tests/unit/test_models.py`
  > note: E104 and E206 are checked on the raw data by `models.cross_checks()`, so they are reported
  > even when other fields of the same finding are invalid. Evidence is a discriminated union on `type`.
  > A structural `Redaction` model (fields and list limits only) is added now so the scaffold validates;
  > name/regex checks (E304) stay in M4.5.
- [x] M2.5 TDD: map Pydantic errors to diagnostics (E101 with a difflib "did you mean" at ratio ≥ 0.6, E102, E103) with line/col from the loader map; collect all errors, sort by line, cap at 100
  files: `src/pentrep/loader.py`, `src/pentrep/diagnostics.py`, `tests/unit/test_loader.py`
  > note: the mapping lives in `loader.py` (`validate_document`, `load_report`); `diagnostics.py` got
  > `sort_and_cap` in M2.1. E101 also carries a hint listing the allowed fields. A field that belongs to another
  > evidence type (`content` on an image) is E103, not E101. Pydantic errors whose type is an `ErrorCode`
  > name (E105, E106) keep that code.
- [x] M2.6 TDD: file checks for `logo` and image evidence: path confinement including symlinks (E302), file exists (E301), type and size limits (E303)
  files: `src/pentrep/loader.py`, `tests/security/test_hardening.py`
  > note: file types are detected from the first bytes (magic numbers), not the extension. Checks run on
  > the raw data, so they are reported alongside schema errors.
- [x] M2.7 TDD: warnings W101 (placeholder text) and W102 (finding without evidence)
  files: `src/pentrep/loader.py`, `tests/unit/test_loader.py`
  > note: W101 scans every string value (not keys) with word boundaries; one warning per value. W102 points
  > at `evidence: []` when it is present, else at the finding.
- [x] M2.8 Fixtures: `valid/minimal.yaml` and `valid/full.yaml`; one `invalid/<code>_<case>.yaml` per E1xx/E3xx/W1xx code with a matching `.expected.txt` (stderr golden); a parametrised test over all of them
  files: `tests/fixtures/valid/*`, `tests/fixtures/invalid/*`, `tests/unit/test_fixtures.py`
  > note: goldens hold the diagnostic lines from `format_text`; M2.11 switches the test to real `validate`
  > stderr. An `e206` fixture is included as well. E304 fixtures come in M4.5. W1xx fixtures exit 1 only
  > with `--strict`. Placeholder PNGs are generated with the stdlib (no new deps).
- [x] M2.9 Security tests: a `!!python/object` tag is rejected, a billion-laughs file is rejected, and a `../` path gives E302
  files: `tests/security/test_hardening.py`
  > note: the behaviour already existed (M2.2, M2.6), so these end-to-end tests passed on the first
  > run. Instead, a mutation check showed that removing the tag filter or the alias limit makes them fail (or hang).
- [x] M2.10 TDD: `pentrep init [DIR] [--force]` (FR-01) with the scaffold from PRD §4.2.3 and placeholder PNGs; mirror it into `examples/`
  files: `src/pentrep/scaffold/**`, `examples/**`, `src/pentrep/cli.py`, `tests/cli/test_init.py`
  > note: the scaffold `findings.yaml` is the PRD §4.2.3 example byte for byte (a test checks this).
  > Conflicts exit 1 and nothing is written. A write failure exits 3. The wheel includes `pentrep/scaffold/**`.
- [x] M2.11 TDD: `pentrep validate FILE [--strict] [--format text|json]` (FR-02): exit codes 0/1, success line `✓ … valid: N findings, N warnings`
  files: `src/pentrep/cli.py`, `tests/cli/test_validate.py`
  > note: text mode writes diagnostics and a `✗ FILE is invalid: N errors, M warnings` summary to stderr;
  > the `✓` success line goes to stdout. The fixture goldens (M2.8) now hold real `validate` stderr. A missing
  > FILE, a directory, or a bad `--format` is a usage error (exit 2).
- [x] M2.12 TDD: `pentrep schema [-o FILE]` (FR-04); test that the output validates the scaffold and rejects schema-error fixtures. Needs the dev dep `jsonschema` **(needs approval)**
  files: `src/pentrep/cli.py`, `tests/cli/test_schema.py`, `pyproject.toml`, `uv.lock`
  > note: the user approved `jsonschema` on 2026-11-26 (added in M2.1). "Pure schema error" fixtures are
  > `e101_*`, `e102_*`, `e103_*` and `e106_*`. The rules E104/E105/E206/E3xx cannot be written in JSON Schema.
  > `-o FILE` prints `Wrote FILE`.
- [x] M2.13 Docs: `docs/errors.md` (every code with an example and fix), `docs/schema.md`, and the NFR-13 test that compares `docs/errors.md` with `ErrorCode`
  files: `docs/errors.md`, `docs/schema.md`, `tests/unit/test_docs.py`
  > note: there is also a test that every example line in `errors.md` quoted from a fixture matches
  > that fixture's golden, and the README now has a usage section. E304 is documented ahead of M4.
- [x] M2.14 verify: `uv run pytest && uv run pentrep init tmp/m2 && uv run pentrep validate tmp/m2/findings.yaml` (exit 0, "0 warnings") `&& ! uv run pentrep validate tests/fixtures/invalid/e101_unknown_field.yaml` (exit 1, shows file:line:col + "did you mean") `&& uv run pentrep schema > /dev/null`
  > note: (2026-11-26): passed locally: 346 tests, 98.94 % coverage. `init` and `validate` exit 0 with
  > "2 findings, 0 warnings"; the e101 fixture exits 1 and shows file:line:col plus "did you mean"; `schema`
  > exits 0. CI has not run yet because the branch is not pushed.
  > note (2026-11-26, later): CI run 45743559897 on `m3-cvss` (which includes M2) is green, 13/13 jobs.
  > The first run failed only because three `--help` tests did not strip ANSI colour (fixed in 5885dc1).

## M3 — CVSS 3.1 calculator
Runnable at the end: `pentrep validate` scores each finding and prints the severity breakdown; invalid vectors produce E2xx errors with hints.

- [x] M3.1 TDD: `roundup()` using the integer algorithm from spec Appendix A, with the edge cases 4.02, 4.00 and 4.000000000000001
  files: `src/pentrep/cvss.py`, `tests/unit/test_cvss.py`
- [x] M3.2 TDD: vector parser: `CVSS:3.1/` prefix, metrics in any order, case-sensitive; E201–E205 with hints; temporal/environmental metrics trigger W201; `CvssVector.canonical()`. Add the E2xx/W201 codes
  files: `src/pentrep/cvss.py`, `src/pentrep/diagnostics.py`, `tests/unit/test_cvss.py`
  > note: the parser collects every issue in a vector instead of stopping at the first. A wrongly-cased
  > base metric (`av`) is a single E202 with a "did you mean" hint, not E202 plus E204. Malformed parts (`AVN`,
  > `//`, a trailing `/`) are E202. Values of ignored metrics are not checked. `docs/errors.md` got the new codes
  > now, because the M2.13 sync test requires them; the examples are replaced with fixture output in M3.7.
- [x] M3.3 TDD: weights (with PR adjusted when S:C), ISS, Impact, Exploitability, base score, and sub-scores rounded to one decimal
  files: `src/pentrep/cvss.py`, `tests/unit/test_cvss.py`
  > note: the FIRST library (`cvsscalc31.js`) returns raw sub-scores. pentrep rounds Impact and
  > Exploitability half up to one decimal, the same way NVD shows them (6.1 XSS vector → 2.7 / 2.8), not with
  > Roundup. A negative Impact (S:C with C/I/A:N) is shown as 0.0.
- [x] M3.4 TDD: `Severity` enum with the bands and ordering (None/Informational < Low < … < Critical)
  files: `src/pentrep/cvss.py`, `tests/unit/test_cvss.py`
  > note: `Severity.NONE` and `Severity.INFORMATIONAL` have the same rank (neither is `<` the other)
  > but stay different members. `from_score` rejects scores outside 0.0–10.0.
- [x] M3.5 Reference vectors: build `cvss_vectors.json` with ≥ 30 vectors (the 11 from PRD §4.3 plus more) cross-checked with the official FIRST calculator; add a parametrised test
  files: `tests/fixtures/cvss_vectors.json`, `tests/unit/test_cvss.py`
  > note: 32 unique vectors. 25 come from FIRST's official "CVSS v3.1 Examples" page (28 examples,
  > read as data; every published score matches). The 7 vectors that are only in the PRD table (10.0, 8.8 PR:L,
  > 7.8 AV:L/PR:L, 6.5, 5.9, 2.4, 0.0) are marked "not cross-checked with the FIRST calculator": running FIRST's
  > `cvsscalc31.js` locally was blocked by the session's permission policy, and the user chose (2026-11-26) to
  > keep them with this note. They can be confirmed in the FIRST web calculator later.
- [x] M3.6 Property tests with hypothesis (score range, one decimal, monotonic C/I/A, idempotent canonical form), 1,000 examples each. Add the `hypothesis` dev dep
  files: `tests/unit/test_cvss_properties.py`, `pyproject.toml`, `uv.lock`
  > note: example order is not guaranteed by `fixed_dictionaries`, so the test builds vectors in
  > specification order explicitly. Mutation check: setting the C:H weight to 0.10 makes the monotonicity property fail.
- [x] M3.7 Integration: a computed `Finding.cvss` field; CVSS diagnostics carry the vector's line/col; invalid fixtures `e201`–`e205` and `w201` with `.expected.txt`; update `docs/errors.md`
  files: `src/pentrep/models.py`, `src/pentrep/loader.py`, `tests/fixtures/invalid/*`, `docs/errors.md`
  > note: `Finding.cvss` is a Pydantic `computed_field`. The loader reports every issue in a vector
  > (including W201) at the vector's position; the model validator raises only the first error, and that
  > duplicate is removed. The fixture-coverage test now requires a fixture for every code except E304.
- [x] M3.8 TDD: `stats.py` with finding order (FR-42), severity counts and overall risk (FR-43); `validate` success line gains `(1 critical, 1 medium)`
  files: `src/pentrep/stats.py`, `tests/unit/test_stats.py`, `src/pentrep/cli.py`, `tests/cli/test_validate.py`
  > note: the Informational/None bucket is shown as `N informational` in the CLI breakdown. If the only
  > open findings are 0.0 or informational, the overall risk is Informational when any of them is informational,
  > else None.
- [x] M3.9 verify: `uv run pytest --cov=pentrep.cvss --cov-branch --cov-fail-under=95 tests/unit/test_cvss*.py && uv run pentrep validate examples/findings.yaml` (prints "2 findings (1 critical, 1 medium)")
  > note: (2026-11-26): passed locally. `cvss.py` has 100 % line and branch coverage (149 CVSS tests);
  > the full suite is 539 tests at 98.9 % overall coverage. `validate examples/findings.yaml` prints
  > "2 findings (1 critical, 1 medium), 0 warnings". CI has not run yet because the branch is not pushed.
  > note (2026-11-26, later): CI run 45743559897 is green, 13/13 jobs.

## M4 — PII redaction
Runnable at the end: `pentrep validate` checks redaction config (E304) and prints a redaction preview summary.

- [x] M4.1 TDD: engine core: `Pattern` dataclass, priority and overlap resolution (each character redacted at most once), `value` group support, `[REDACTED:NAME]` token, deterministic output
  files: `src/pentrep/redact.py`, `tests/unit/test_redact.py`
  > note: a `Pattern` can have several groups whose names start with `value` (the first one that took part
  > is redacted; if none did, the whole match is), a `check` function, or a `finder` for rules a single regex
  > cannot express. An allowlisted match still claims its characters, so a lower-priority pattern can't redact
  > part of it.
- [x] M4.2 TDD: built-in patterns `PRIVATE_KEY`, `JWT`, `BEARER`, `COOKIE` (keeping cookie names and attributes), each with a positive and a negative corpus of ≥ 5 samples
  files: `src/pentrep/redact.py`, `tests/fixtures/redaction/*`, `tests/unit/test_redact_patterns.py`
  > note: corpora are JSON files (`tests/fixtures/redaction/<pattern>.json`) where each positive sample has
  > its exact expected output. The private-key corpus uses a `<<PRIVATE KEY>>` placeholder that the test expands,
  > so the `detect-private-key` hook stays enabled. An unterminated private-key block is redacted to the end of
  > the text. COOKIE also redacts every pair on a `Cookie:` line, keeping only the listed attributes.
- [x] M4.3 TDD: built-in patterns `AWS_KEY`, `SECRET` (query, form, JSON and header forms), `CARD` (with Luhn check), with corpora
  files: `src/pentrep/redact.py`, `tests/fixtures/redaction/*`, `tests/unit/test_redact_patterns.py`
  > note: SECRET has three value forms: double-quoted, single-quoted, and bare up to `& ; , " '` or
  > whitespace. The separator must be on the same line. `-` may come before a key (`X-Api-Key`), but `_` may not
  > (`my_password`). CARD accepts single spaces or hyphens between digits and needs 13–19 digits plus a valid
  > Luhn checksum.
- [x] M4.4 TDD: built-in patterns `EMAIL` and `PRIVATE_IP` (confirmed with `ipaddress`; public, loopback and RFC 5737 ranges are kept), with corpora
  files: `src/pentrep/redact.py`, `tests/fixtures/redaction/*`, `tests/unit/test_redact_patterns.py`
  > note: PRIVATE_IP matches dotted quads with boundaries (so `10.2.3.4.5` is skipped) and keeps only
  > addresses that `ipaddress` places in 10/8, 172.16/12, 192.168/16 or 169.254/16. All 9 built-ins now have a
  > corpus, and a test checks that there is exactly one corpus per built-in.
- [x] M4.5 TDD: `Redaction` config model (`enabled`, `apply_to_all_text`, `custom_patterns` ≤ 50, `allowlist` ≤ 200); E304 for a bad regex or name; custom patterns run after built-ins; allowlisted values are skipped and not counted
  files: `src/pentrep/models.py`, `src/pentrep/redact.py`, `tests/unit/test_redact.py`, `tests/fixtures/invalid/e304_*`
  > note: E304 is raised by validators on `CustomPattern` (name: pattern, or a clash with a built-in name;
  > regex: `re.compile`), located at the field. Custom patterns get priority 100+ (after all built-ins).
  > `Redactor(config)` bundles the patterns and the allowlist. Every code now has an invalid fixture.
- [x] M4.6 TDD: `redact_report(report) -> (report, RedactionSummary)` over the fields in FR-30, counting image evidence items that were not scanned
  files: `src/pentrep/redact.py`, `tests/unit/test_redact.py`
  > note: counts are kept in order of first appearance, scanning findings in file order and fields in report
  > order (description, impact, steps, evidence, remediation). That gives the PRD example order SECRET, COOKIE, JWT,
  > EMAIL, ACME_EMPLOYEE_ID, PRIVATE_IP. An `enabled` argument overrides the config for `--no-redact` (M5).
- [x] M4.7 TDD: summary formatter (FR-35; never prints original values) and a `validate` "Redaction preview: …" line. Also update PRD FR-02 to describe this line
  files: `src/pentrep/redact.py`, `src/pentrep/cli.py`, `tests/cli/test_validate.py`, `docs/PRD.md`
  > note: the preview goes to stdout after the `✓` line, in text mode only and only when the file is
  > valid. PRD FR-02 now describes it. The ruff config allows `×` as a confusable character (`allowed-confusables`),
  > because FR-35 prescribes it; RUF001 stays on for everything else.
- [x] M4.8 Test the PRD §4.2.3 example: the redacted PT-001 and PT-002 evidence equals the expected text in the PRD exactly
  files: `tests/unit/test_redact_example.py`
  > note: a test-only task: it passed on the first run. The expected lines are read from the PRD itself, and
  > the test also checks that only those three lines of the PT-001 evidence change.
- [x] M4.9 Leak-test harness: fixture `valid/leaky.yaml` seeding 20 unique secrets, plus helper `assert_no_leaks(texts)`; apply it now to `validate` stdout/stderr and the `--debug` log
  files: `tests/fixtures/valid/leaky.yaml`, `tests/conftest.py`, `tests/security/test_leaks.py`
  > note: `leaky.yaml` writes its private key with a `<<PRIVATE KEY>>` placeholder, which the `leaky_project`
  > fixture expands. `assert_no_leaks` is also available as the `no_leaks` fixture. The tests cover `validate` in
  > text, `--strict`, JSON and `--debug` mode, plus the diagnostics of an invalid leaky file. The preview counts 22
  > values: 20 unique secrets, two of which occur twice.
- [x] M4.10 verify: `uv run pytest --cov=pentrep.redact --cov-branch --cov-fail-under=95 tests/unit/test_redact*.py tests/security && uv run pentrep validate examples/findings.yaml` (prints "Redaction preview: 6 values … SECRET×1, COOKIE×1, JWT×1, EMAIL×1, ACME_EMPLOYEE_ID×1, PRIVATE_IP×1")
  > note: (2026-11-26): passed locally. `redact.py` has 100 % line and branch coverage (231 tests in the
  > verify subset); the full suite is 741 tests at 99 % overall coverage. `validate examples/findings.yaml` prints the
  > expected preview line. CI runs after the push.
  > note (2026-11-26, later): CI run 45744658677 on `m4-redaction` is green, 13/13 jobs.

## M5 — HTML & Markdown renderer (`classic` theme)
Runnable at the end: `pentrep build examples/findings.yaml -f html -f md` produces a redacted, self-contained report.

- [x] M5.1 TDD: Markdown helper using markdown-it-py with `html=False`, GFM tables, and `javascript:`/`data:` links neutralised. Add the `markdown-it-py` dep
  files: `src/pentrep/render/markdown.py`, `tests/render/test_markdown_helper.py`, `pyproject.toml`, `uv.lock`
  > note: links are allowed only for http, https and mailto (anything else is shown as text). Markdown images
  > are not rendered, so user Markdown can never add an external `src` (FR-45). Headings in user Markdown become
  > bold paragraphs, so they cannot break the report's h1→h2→h3 structure.
- [x] M5.2 TDD: template context builder (`engagement`, `branding`, sorted `findings`, `stats`, `redaction`, `generated_at`, `pentrep_version`)
  files: `src/pentrep/render/context.py`, `tests/render/test_context.py`
  > note: the context holds view objects (`FindingView`, `EvidenceView`, `BrandingView`, `RedactionView`) with
  > display values precomputed (badge class, score text, canonical vector, sub-scores, CWE links, image asset
  > names and MIME types). `generated_at` is `SOURCE_DATE_EPOCH` as UTC when set, else the report date, so the
  > output stays deterministic. The four FR-43 combinations are tested.
- [x] M5.3 TDD: Jinja environment with a `ChoiceLoader` (`--template-dir` first, then the built-in theme), autoescape for HTML and `StrictUndefined`. Add the `jinja2` dep
  files: `src/pentrep/render/__init__.py`, `tests/render/test_env.py`, `pyproject.toml`, `uv.lock`
  > note: the built-in theme is loaded with `PackageLoader("pentrep", "themes/classic")`. `style.css` also goes
  > through the loader, so it can be overridden too. A missing `--template-dir` raises `NotADirectoryError`, which
  > the CLI reports as a usage error in M5.8.
- [x] M5.4 HTML theme part 1: `report.html.j2`, partials for cover, document control, TOC and executive summary with the stats table; `style.css` with the accent colour variable and severity palette; contrast test (FR-44)
  files: `src/pentrep/themes/classic/**`, `tests/render/test_theme.py`
  > note: a basic `render_html` was written here so the theme could be tested; its own checks (FR-45) are in
  > M5.6. Badge text colours: white on Critical/High/Low/Informational and black on Medium, because white on
  > #E65100 is only 3.8:1. The contrast test computes WCAG ratios from `style.css`. The FR-40 order test moved to
  > M5.5, which adds the remaining sections.
- [x] M5.5 HTML theme part 2: scope & methodology, summary table, finding partial, evidence with Pygments inline CSS (HTTP lexer), appendices A/B, `UNREDACTED DRAFT` banner (FR-36). Add the `pygments` dep
  files: `src/pentrep/themes/classic/**`, `pyproject.toml`, `uv.lock`
  > note: Pygments is type-checked with the `types-Pygments` dev dependency (approved and added on 2026-11-26,
  > after M6). Pasted HTTP traffic is split into messages at each request or status line,
  > so a request plus its response is highlighted instead of falling back to plain text. A part that still lexes
  > with errors is shown as plain text. Steps use inline Markdown inside `<li>`.
- [x] M5.6 TDD: HTML renderer that inlines CSS and turns images into `data:` URIs; tests for no `<script>`, no external `src`/`url()`, `lang="en"`, no skipped heading levels, captions used as alt text
  files: `src/pentrep/render/html.py`, `tests/render/test_html.py`
  > note: the renderer itself was written in M5.4, so these FR-45 tests passed on the first run. A mutation
  > check (the finding title changed from `h3` to `h4`, which skips a level after `h2`) makes the heading test fail. The tests parse the output with `html.parser`:
  > every `src` must be a `data:` URI, `href` may only appear on `<a>`, and there must be no `<link>`, `url()`
  > or `@import`, no `on*` attributes and no `<script>`.
- [x] M5.7 TDD: Markdown report with `report.md.j2`, images copied to `assets/<id>-<n>.<ext>`, automatic fence length, GFM tables, text severity badges
  files: `src/pentrep/themes/classic/report.md.j2`, `src/pentrep/render/md.py`, `tests/render/test_md.py`
  > note: `render_md` returns the text and a list of images to copy (`assets/<finding-id>-<n>.<ext>`, the
  > logo as `assets/logo.<ext>`); the CLI copies them. Every value goes through a filter: `md_inline`/`md_cell`
  > backslash-escape Markdown punctuation, `md_block` escapes raw HTML outside code spans and fences and turns user
  > headings into bold lines (the report keeps one `#` title), and `md_url` percent-encodes `<`, `>`, spaces and
  > backticks. TOC links use GitHub heading slugs. Finding subsections are bold labels, not `####`.
- [x] M5.8 TDD: `pentrep build` for html/md (FR-03): `-f`, `-o`, `-n`, `--template-dir`, `--no-redact`, `--strict`, `-q`; validation runs first; prints written paths, sizes and the redaction summary
  files: `src/pentrep/cli.py`, `tests/cli/test_build.py`
  > note: `jinja2` and the renderers are imported inside `build`, so `--help` stays fast (NFR-04). Everything
  > is rendered before anything is written, so a template error (exit 3) leaves no half-written report. Written
  > paths are printed with `/` on every OS. The FR-36 warning is printed even with `-q`, because it is
  > safety-relevant. Until M6, requesting `pdf` (including the default `all`) writes HTML and Markdown, then exits
  > 3 with "PDF output is not implemented yet".
- [x] M5.9 Golden files: `--update-golden` pytest option, `SOURCE_DATE_EPOCH` fixed, version string normalised; generate and review `report.html` and `report.md`
  files: `tests/conftest.py`, `tests/render/test_golden.py`, `tests/golden/report.html`, `tests/golden/report.md`
  > note: goldens are rendered from `valid/full.yaml` with `SOURCE_DATE_EPOCH=1795176000` and the version
  > replaced by `<PENTREP_VERSION>`; a failure shows a unified diff. Reviewing the first golden found a bug: Pygments
  > strips and adds newlines by default, which moved the blank line between a request body and its response.
  > Lexers now run with `stripnl=False, ensurenl=False`, and `tests/render/test_highlight.py` checks that the
  > highlighted text equals the evidence exactly. Regenerated, reviewed diff: only that blank line.
- [x] M5.10 Security and leak tests on output: XSS in a description, `{{ 7*7 }}` and `{% %}` in a title rendered literally, `javascript:` link neutralised, no network access (add the `pytest-socket` dev dep), `assert_no_leaks` on HTML/MD built from `leaky.yaml`
  files: `tests/security/test_hardening.py`, `tests/security/test_leaks.py`, `pyproject.toml`, `uv.lock`
  > note: these tests found a real gap: a `[x](javascript:…)` link reached the Markdown report as working link
  > syntax. `md_block` now breaks inline links and reference definitions that point to `javascript:`, `vbscript:`,
  > `data:` or `file:` (they are shown as text); HTML already rendered them as text. The no-network test uses the
  > `socket_disabled` fixture from pytest-socket. The leak test covers HTML and MD files plus stdout/stderr, with and
  > without `--debug`, and a sanity test confirms the secrets do appear with `--no-redact`.
- [x] M5.11 Template override test (override only `partials/cover.html.j2`; everything else stays golden-identical) and `docs/templates.md`
  files: `tests/render/test_override.py`, `tests/fixtures/templates/**`, `docs/templates.md`
  > note: the override mechanism came from M5.3/M5.8, so the override test passed on the first run. Its
  > cover fixture is in `tests/fixtures/templates/`. A doc test checks that `docs/templates.md` names every context
  > key, every view field, every filter and every built-in partial, so the doc cannot drift from the code.
- [x] M5.12 verify: `uv run pytest && uv run pentrep build examples/findings.yaml -f html -f md -o tmp/m5` (exit 0; `tmp/m5/pentest-report.{html,md}` and `tmp/m5/assets/` exist; `grep -o "REDACTED" tmp/m5/pentest-report.html | wc -l` ≥ 6); golden tests pass on ubuntu and macOS in CI
  > note: (2026-11-26): passed. Locally: 890 tests, 98.45 % coverage. `build examples/findings.yaml -f html -f md
  > -o tmp/m5` exits 0 and writes both files plus `assets/`; the token count is 7 (the 6 redacted values plus the
  > `[REDACTED:NAME]` example in Appendix B).
  > CI run 45766141610 on `m5-render` is green, 13/13 jobs, so the golden files pass unchanged on ubuntu-22.04,
  > ubuntu-24.04 and macos-latest.

## M6 — PDF export
Runnable at the end: `pentrep build examples/findings.yaml` (default `-f all`) produces HTML, MD and PDF.

- [x] M6.1 Decide the font (Q-06), bundle the OFL font and its licence, and add a wheel-size check script (≤ 2 MB, NFR-12)
  files: `src/pentrep/themes/classic/fonts/**`, `src/pentrep/themes/classic/style.css`, `tests/unit/test_package_size.py`
  > note: Q-06 decided: Source Sans 3 Regular/Italic/Bold plus Source Code Pro Regular (TrueType, OFL 1.1),
  > taken from Adobe's official npm packages `source-sans@3.52.0` and `source-code-pro@2.42.0`. The licence is
  > `fonts/OFL.txt`, one file with both copyright notices (merged from two files on 2026-11-26) and referenced in
  > the README. The `@font-face` rules are in a separate `fonts.css` that only the PDF renderer loads (a font
  > `url()` in the inlined `style.css` would break FR-45). The wheel is 704 KB; the size check is a test that builds
  > the wheel, not a separate script.
- [x] M6.2 TDD: PDF wrapper with lazy WeasyPrint import and a dependency check that raises `RenderError` with OS-specific hints (apt, brew, Docker); test the missing-library case with a simulated import failure. Add the `weasyprint` dep
  files: `src/pentrep/render/pdf.py`, `tests/render/test_pdf.py`, `pyproject.toml`, `uv.lock`
  > note: WeasyPrint 70 (`weasyprint>=70,<71`) is imported with `importlib` only inside `render_pdf`; a missing
  > package or system library becomes a `RenderError` that names the library and gives an apt/brew hint plus the
  > Docker alternative. A `URLFetcher` subclass allows only `data:` URIs and files in the theme directory; anything
  > else stops the render (no network, NFR-09). A pypdf-based test found that `@font-face` was being ignored (the
  > PDF used system fonts) until one `FontConfiguration` is shared by `CSS()` and `write_pdf()`. `pdf` tests skip
  > with a reason when the libraries are missing. `pypdf` was added here (planned for M6.5) to inspect fonts.
- [x] M6.3 Print CSS: `@page` A4/Letter, classification header, `Page X of Y` footer, no header on the cover, page break before each finding, TOC page numbers via `target-counter`, bookmarks for h1/h2
  files: `src/pentrep/themes/classic/style.css`, `src/pentrep/themes/classic/partials/*`
  > note: the page size is set by the PDF renderer (`--paper`); `style.css` adds the running header
  > (classification, plus the FR-36 banner through `string-set` when unredacted), the `Page X of Y` footer, no
  > header/footer on the cover, TOC page numbers with `leader()` + `target-counter()`, and bookmarks for h1–h3 (h3 =
  > findings; h4+ are off). The font test found that page margin boxes fell back to DejaVu Serif, because they do not
  > inherit the body font, so `@page` sets it too. The golden HTML was regenerated; the reviewed diff is CSS only.
- [x] M6.4 TDD: `build -f pdf` / `-f all` with `--paper`; on partial success, HTML and MD are written, then exit 3 with a hint and no traceback
  files: `src/pentrep/cli.py`, `tests/cli/test_build.py`
  > note: the PDF is rendered last, from the same HTML (including any `--template-dir` overrides), so HTML
  > and MD are already on disk if PDF fails; then the error, an `hint:` line and exit 3 follow, with no traceback.
  > `--paper a4|letter` (default a4) is validated by Typer (exit 2 otherwise). A missing system library is
  > simulated in the test.
- [x] M6.5 PDF structural tests (marker `pdf`) with pypdf: page size, finding titles in the text, one finding per page, footers, bookmarks. Add the `pypdf` dev dep
  files: `tests/render/test_pdf.py`, `pyproject.toml`, `uv.lock`
  > note: the structure was built in M6.3, so these tests passed on the first run; a mutation check
  > (removing the page break before `.finding`) makes the new-page test fail. Besides the planned checks there are
  > tests for the classification header, the TOC page numbers and the FR-36 banner on every page header. `pypdf`
  > (`>=6,<7`) was already added in M6.2.
- [x] M6.6 Content-parity test (same ids, titles, scores and severities in HTML, MD and PDF) and the PDF leak test on `leaky.yaml`
  files: `tests/render/test_parity.py`, `tests/security/test_leaks.py`
  > note: parity compares (id, title, severity, score) per finding, parsed from the HTML finding header,
  > the Markdown finding header and the PDF text, for `full.yaml` and `minimal.yaml` built with `-f all`. The PDF leak
  > test checks the extracted text (after confirming that extraction sees `[REDACTED:` tokens), the raw PDF bytes, and
  > stdout/stderr of a `--debug` build.
- [x] M6.7 CI: set `PENTREP_REQUIRE_PDF=1` so a skipped `pdf` test fails in CI; check that PDF tests run on ubuntu and macOS
  files: `tests/conftest.py`, `.github/workflows/ci.yml`
  > note: CI sets `PENTREP_REQUIRE_PDF=1`, so with missing libraries the run stops (`pytest.exit`, exit 1) instead
  > of skipping; the run/skip/fail decision is a small tested function in `tests/conftest.py`. macOS jobs also set
  > `DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib` for cffi. CI run 45767770156: all 12 test jobs report 929 passed and
  > 0 skipped, so the pdf tests run on ubuntu-22.04, ubuntu-24.04 and macos-latest.
- [x] M6.8 verify: `uv run pytest -m pdf && uv run pentrep build examples/findings.yaml -o tmp/m6 && uv run pentrep build examples/findings.yaml -f pdf --paper letter -o tmp/m6-letter` (both exit 0, `tmp/m6/pentest-report.pdf` opens, and CI shows 0 skipped `pdf` tests)
  > note: (2026-11-26): passed. Locally: `pytest -m pdf` gives 20 passed, 0 skipped; both builds exit 0; the A4 PDF
  > has 7 pages of 595×842 pt and the Letter PDF has 8 pages of 612×792 pt, and both open with pypdf. CI run 45767770156
  > is green (13/13 jobs, 0 skipped). A visual check of the rendered pages found long evidence lines running off the
  > page; `tests/render/test_pdf.py::test_long_evidence_lines_wrap_inside_the_page` now guards this.

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
