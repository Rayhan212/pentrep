# CLAUDE.md — working rules for pentrep

## Project
pentrep is a Python CLI that turns a `findings.yaml` file (pentest results) into a professional report in HTML, PDF and Markdown.
It validates the file with line-numbered errors, computes CVSS 3.1 scores from vectors, and redacts secrets/PII in evidence by default.
Target user: solo/freelance pentesters. It is also a portfolio project, so quality and tests matter more than feature count.

- Requirements (source of truth): [docs/PRD.md](docs/PRD.md)
- Task checklist & progress: [docs/PLAN.md](docs/PLAN.md)

## Stack
- Python **>= 3.11** (CI: 3.11–3.14, Ubuntu + macOS). Build backend: hatchling. Env/lock: **uv**.
- Runtime: Typer, Pydantic v2, ruamel.yaml, Jinja2, markdown-it-py, Pygments, WeasyPrint (PDF only, import lazily).
- Dev: pytest, pytest-cov, hypothesis, pypdf, pytest-socket, ruff, mypy (strict), pre-commit.

## Setup, run, test
```bash
uv sync --all-extras          # create .venv + install deps from uv.lock
uv run pre-commit install
uv run pentrep --help
uv run pentrep init tmp/ && uv run pentrep build tmp/findings.yaml -o tmp/report
uv run pytest                 # full suite (pdf tests auto-skip without Pango)
uv run pytest -m "not perf"   # skip benchmarks
uv run pytest --update-golden # regenerate golden files, then review the diff
uv run ruff check . && uv run ruff format --check . && uv run mypy src
```

## Conventions
- Layout: code in `src/pentrep/` (one module per concern: `cli`, `models`, `loader`, `diagnostics`,
  `cvss`, `redact`, `stats`, `render/`), templates in `src/pentrep/themes/classic/`,
  tests in `tests/{unit,cli,render,security,perf}/` and fixtures in `tests/fixtures/`. Follow PRD §7.
- Naming: `snake_case` modules/functions, `PascalCase` classes, `UPPER_SNAKE` constants;
  tests are `test_<module>.py` / `test_<behaviour>()`; invalid fixtures are named after their code (`e203_bad_metric_value.yaml`).
- Type hints on every function signature and public attribute; `mypy --strict` must pass. Avoid `Any`;
  if it's unavoidable, add a comment explaining why.
- Docstrings: one-line summary for every public function/class; add Args/Returns only when not obvious.
- Errors: raise or collect `Diagnostic` with an `ErrorCode` from `diagnostics.py`. Never show bare
  exceptions to the user. New codes must be added to PRD §4.2.4 and `docs/errors.md`.
- Security defaults: safe YAML loading, Jinja autoescape for HTML, markdown-it with `html=False`,
  never render YAML values as templates, confine file paths to the project directory, no network calls.
- Output must be deterministic (FR-49): no timestamps or random values outside `report_date` / `SOURCE_DATE_EPOCH`.

## Workflow (every task)
1. Pick the next unchecked task in `docs/PLAN.md` and re-read the PRD sections it references.
2. **Write failing tests first** (TDD): unit test, fixture, or golden file.
3. Implement the minimum code that makes them pass, then refactor.
4. Run `uv run pytest` and `uv run ruff check . && uv run ruff format --check . && uv run mypy src`. All must be green.
5. Tick the task in `docs/PLAN.md` (add a short note if the scope changed).
6. Commit with Conventional Commits: `feat(cvss): compute base score from vector`, `fix(redact): …`,
   `test: …`, `docs: …`, `refactor: …`, `chore: …`, `ci: …`. One logical change per commit, in the imperative mood.

## Don'ts
- Do **not** add, remove or upgrade a dependency (runtime or dev) without asking first.
- Do **not** change the `findings.yaml` schema (fields, types, constraints, defaults) without first
  updating PRD §4.2 and bumping/justifying `schema_version` — and then the JSON Schema, scaffold and fixtures.
- Do **not** commit `output/`, `report/`, `tmp/`, `.env*`, `.venv/`, coverage or build artifacts
  (they must be in `.gitignore`).
- Do **not** weaken tests, coverage gates or lint rules to get green. Do not regenerate golden files without reviewing the diff.
- Do **not** commit real client data or real secrets. Fixtures use `example`/`.test` domains and RFC 5737 IPs.
- Do **not** expand scope beyond PRD §2 non-goals; log ideas as roadmap items instead.

## Definition of Done (per task)
- [ ] Acceptance criteria of the task / PRD milestone are met, and each one is covered by a test.
- [ ] Tests written before implementation; `pytest` green locally.
- [ ] Coverage gate holds (≥ 85 % overall, ≥ 95 % line+branch for `cvss.py` and `redact.py`).
- [ ] `ruff check`, `ruff format --check`, `mypy --strict` clean.
- [ ] Every user-facing error has a code, file:line:col, and a hint where applicable; no traceback without `--debug`.
- [ ] Docs updated where behaviour changed (README, `docs/errors.md`, `docs/templates.md`, PRD if spec changed).
- [ ] `docs/PLAN.md` checkbox ticked.
- [ ] Committed with a Conventional Commit message; no ignored or secret files staged.
