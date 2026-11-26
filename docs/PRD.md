# pentrep — Product Requirements Document (v0.1)

| Field | Value |
|---|---|
| Document status | Draft |
| Target release | v0.1.0 |
| Last updated | 2026-11-26 |
| Keywords | MUST / MUST NOT / SHOULD / MAY are used as defined in RFC 2119 |

---

## 1. Overview & problem statement

**pentrep** is a Python command-line tool that turns a single, human-written `findings.yaml` file (the results of a penetration test) into a professional pentest report in **HTML, PDF and Markdown**.

### Problem

Solo and freelance penetration testers usually write reports by hand in Word or Google Docs. In practice this means:

1. **Formatting takes time away from the findings.** Cover pages, tables of contents, severity tables and consistent styling are rebuilt for every engagement.
2. **CVSS scores drift from their vectors.** Scores are copied from an online calculator, so the vector string, the numeric score and the severity label in the report can disagree.
3. **Sensitive data leaks into evidence.** Raw HTTP requests and tool output contain session cookies, JWTs, passwords, internal IPs and customer email addresses. Redaction is manual and easy to forget.
4. **Reports can't be version-controlled.** Binary `.docx` files diff badly, so there's no clean history of what changed between report versions or retests.

### Solution

The tester writes findings once, in a validated plain-text YAML file. pentrep then:

- validates the file and reports every error with its file, line and column,
- computes the CVSS 3.1 base score and severity from the vector string,
- redacts common secrets and PII from evidence by default,
- renders a consistent, branded report in three formats from one source.

---

## 2. Goals / non-goals (v0.1)

### Goals

| ID | Goal | Measured by |
|---|---|---|
| G-01 | A new user goes from install to a rendered sample report with 3 commands (`pipx install pentrep`, `pentrep init`, `pentrep build`) | M7 acceptance test in a clean container |
| G-02 | The CVSS score, severity and vector in a report can never disagree | Score and severity are always derived from the vector; the schema has no field to set them manually (FR-20 to FR-24) |
| G-03 | Secrets and PII in text evidence are redacted unless the user explicitly opts out | Redaction is on by default; the seeded-secret test corpus has 0 leaks in any output format (FR-30 to FR-37) |
| G-04 | One `findings.yaml` produces HTML, PDF and Markdown with the same content | Golden-file and content-parity tests (Section 8) |
| G-05 | The project is credible as a portfolio piece: tested, typed, linted and documented | ≥ 85 % line coverage, `mypy --strict` clean, `ruff` clean, CI green |

### Non-goals (out of scope for v0.1)

- CVSS 4.0, and CVSS 3.1 temporal/environmental scoring
- Importers for scanner output (Burp XML, Nuclei JSON, ZAP, Nessus)
- More than one built-in theme, or a `--theme` selector
- DOCX output
- Multi-file / `include` YAML, or merging findings from several testers (team mode)
- `serve --watch` or live preview
- Redacting text inside images (OCR, blurring screenshots)
- Multi-language reports (i18n) and digitally signed PDFs
- Integrations with trackers (Jira, DefectDojo) and any web UI
- Official Windows support (Windows users are directed to the Docker image)

---

## 3. Target users & user stories

### Primary persona: solo / freelance penetration tester

- Runs web application, API and external network assessments alone or as the lead tester.
- Comfortable with a terminal, YAML and git. Writes findings in Markdown.
- Delivers PDF reports to clients. Keeps working notes in git.
- Pain points: hours spent on formatting, CVSS mistakes, fear of leaking client secrets in screenshots and request dumps.

### Secondary persona: reviewer / recruiter

- Wants to judge the tool in under 5 minutes, without reading the code first.
- Uses the sample report in the README or GitHub Pages, or runs the Docker image once.

### User stories

| ID | User story | Related FRs |
|---|---|---|
| US-01 | As a pentester, I want to generate a starter `findings.yaml` with realistic examples, so that I don't have to learn the schema from scratch. | FR-01 |
| US-02 | As a pentester, I want to validate my findings file and see every error with its line number, so that I can fix mistakes before the client sees them. | FR-02, FR-10 to FR-16 |
| US-03 | As a pentester, I want to write only the CVSS vector and get the score and severity calculated, so that my report never contains a wrong score. | FR-20 to FR-24 |
| US-04 | As a pentester, I want cookies, tokens, passwords, internal IPs and emails in my evidence redacted automatically, so that I don't leak client secrets in a report. | FR-30 to FR-37 |
| US-05 | As a pentester, I want to add my own redaction patterns and an allowlist, so that client-specific identifiers are hidden and my test accounts stay readable. | FR-33, FR-34 |
| US-06 | As a pentester, I want one command to produce PDF, HTML and Markdown, so that I can send a PDF to the client and keep Markdown in git. | FR-03, FR-40 to FR-49 |
| US-07 | As a freelancer, I want my company name, logo and accent colour on the report, so that it looks like my own deliverable. | FR-14, FR-41 |
| US-08 | As a pentester, I want to override the report templates, so that I can match a client's required report structure. | FR-48 |
| US-09 | As a user of editors like VS Code, I want a JSON Schema for `findings.yaml`, so that I get autocomplete and inline validation while typing. | FR-04 |
| US-10 | As a reviewer, I want to run pentrep through Docker without installing system libraries, so that I can try PDF output in one command. | FR-60 to FR-62 |

---

## 4. Functional requirements

### 4.1 CLI commands & flags

The executable is `pentrep`. It is also runnable as `python -m pentrep`.

**Global behaviour**

| ID | Requirement |
|---|---|
| FR-00a | `pentrep --version` MUST print `pentrep <semver>` and exit with code 0. |
| FR-00b | `pentrep --help` and `pentrep <command> --help` MUST list every flag with a one-line description. |
| FR-00c | Exit codes MUST be: `0` success, `1` validation failed, `2` usage error (unknown flag or missing argument), `3` rendering/IO failure (for example PDF dependencies missing or output directory not writable). |
| FR-00d | Python tracebacks MUST NOT be shown unless `--debug` is passed. Unexpected exceptions MUST print `internal error: <message> (re-run with --debug for details)` and exit with code 3. |
| FR-00e | Errors and warnings MUST go to stderr. Machine-readable output (`schema`) MUST go to stdout. Colour MUST be disabled when stdout is not a TTY or `NO_COLOR` is set. |

**FR-01 — `pentrep init [DIR] [--force]`**

- Creates in `DIR` (default `.`): `findings.yaml` (the example in Section 4.2.3), `assets/logo.png` and `evidence/pt-001-sqlmap.png` (placeholder images).
- If any target file already exists, it MUST exit with code 1 and list the conflicting files, unless `--force` is given.
- The generated `findings.yaml` MUST pass `pentrep validate` with 0 errors and 0 warnings.

**FR-02 — `pentrep validate FILE [--strict] [--format text|json]`**

- Parses and validates `FILE` against the schema (Section 4.2), including CVSS vectors and referenced files.
- Reports **all** errors found in one run, up to 100, sorted by line number. It does not stop at the first error.
- Exits with code 0 if there are no errors (warnings allowed), or 1 otherwise. `--strict` treats warnings as errors.
- `--format json` prints a JSON array of diagnostics (`code`, `severity`, `path`, `line`, `column`, `message`, `hint`) to stdout, for CI and editor integration.
- On success in text mode it prints: `✓ findings.yaml is valid: 2 findings (1 critical, 1 medium), 0 warnings`.
- On success in text mode it then prints a redaction preview computed with the file's redaction settings, for example
  `Redaction preview: 6 values in 2 findings would be redacted: SECRET×1, COOKIE×1, JWT×1, EMAIL×1, ACME_EMPLOYEE_ID×1, PRIVATE_IP×1`,
  followed by the FR-35 image note when image evidence exists. It shows only pattern names and counts, never the values. With
  `redaction.enabled: false` it prints `Redaction preview: redaction is disabled (redaction.enabled: false)`.

**FR-03 — `pentrep build FILE [options]`**

| Flag | Default | Description |
|---|---|---|
| `-f, --format` | `all` | `html`, `pdf`, `md` or `all`. Repeatable (`-f html -f md`). |
| `-o, --output-dir DIR` | `./report` | Created if missing. Existing files with the same name are overwritten. |
| `-n, --name NAME` | `pentest-report` | Output basename: `<NAME>.html`, `<NAME>.pdf`, `<NAME>.md`. Must match `^[A-Za-z0-9._-]{1,100}$`. |
| `--template-dir DIR` | none | Overrides built-in templates (FR-48). |
| `--paper a4\|letter` | `a4` | PDF page size. |
| `--no-redact` | off | Disables redaction and marks the report as an unredacted draft (FR-36). |
| `--strict` | off | Fails the build on validation warnings. |
| `-q, --quiet` | off | Prints only errors. |

- `build` MUST run the same validation as `validate` first. If validation fails, no output files are written and the exit code is 1.
- On success it prints each written path with its size and the redaction summary (FR-35).
- If `pdf` is requested and WeasyPrint's system libraries are missing, the other requested formats MUST still be written. pentrep then prints an error naming the missing library, with the install hint for the current OS and the Docker alternative, and exits with code 3.

**FR-04 — `pentrep schema [-o FILE]`**

- Prints the JSON Schema (draft 2020-12) generated from the Pydantic models to stdout, or writes it to `FILE`.
- The schema MUST validate the `init` example and MUST reject each fixture in `tests/fixtures/invalid/` that is a pure schema error.

### 4.2 `findings.yaml` schema

#### 4.2.1 General rules

| ID | Requirement |
|---|---|
| FR-10 | The file MUST be UTF-8 YAML 1.2 and at most 10 MB. It is parsed with a safe loader: no tags that build arbitrary objects, and no anchor/alias expansion beyond 1,000 nodes (protects against "billion laughs" attacks). |
| FR-11 | Unknown keys MUST be an error (`extra="forbid"`). The message suggests the closest known key when the similarity ratio is ≥ 0.6, for example `unknown field 'remediaton'; did you mean 'remediation'?`. |
| FR-12 | Every diagnostic MUST carry the file path, line, column, a dotted path (`findings[1].cvss_vector`), a stable error code (Section 4.2.4) and a message. |
| FR-13 | Fields marked *Markdown* accept CommonMark plus GFM tables and fenced code. Raw HTML inside Markdown MUST be escaped, not rendered. YAML string values MUST NEVER be evaluated as Jinja templates (prevents template injection). |
| FR-14 | Relative file paths (`logo`, evidence `path`) resolve against the directory containing `findings.yaml`. A path that resolves outside that directory (via `..` or a symlink) MUST be rejected (E302). |
| FR-15 | Dates use ISO 8601 (`YYYY-MM-DD`). `end_date` MUST be ≥ `start_date`. |
| FR-16 | `schema_version` MUST be `1`. Any other value MUST fail with E106, naming the versions this pentrep release supports. |

#### 4.2.2 Field reference

**Top level**

| Key | Type | Required | Constraints |
|---|---|---|---|
| `schema_version` | int | yes | `1` |
| `engagement` | object | yes | see below |
| `branding` | object | no | see below |
| `redaction` | object | no | see Section 4.4 |
| `findings` | list[Finding] | yes | 1 to 500 items |

**`engagement`**

| Key | Type | Required | Constraints / default |
|---|---|---|---|
| `title` | str | yes | 5–150 chars |
| `client.name` | str | yes | 1–100 chars |
| `client.contact` | str | no | ≤ 150 chars |
| `testers` | list | yes | 1–10 items. Each has `name` (required), `email` (optional, valid email) and `role` (optional) |
| `start_date` | date | yes | |
| `end_date` | date | yes | ≥ `start_date` |
| `report_date` | date | no | Defaults to today, or to the date of `SOURCE_DATE_EPOCH` when that is set |
| `report_version` | str | no | Default `"1.0"`. Pattern `^\d+\.\d+$` |
| `classification` | str | no | Default `"CONFIDENTIAL"`. ≤ 40 chars. Printed on every PDF page |
| `scope.in_scope` | list[Asset] | yes | ≥ 1 item |
| `scope.out_of_scope` | list[Asset] | no | |
| `methodology` | Markdown | yes | ≥ 20 chars |
| `executive_summary` | Markdown | no | If omitted, the summary section shows only the generated statistics (FR-43) |

`Asset` = `{ asset: str (required), type: url | ip | cidr | hostname | api | mobile_app | other (required), notes: str (optional) }`

**`branding`**

| Key | Type | Required | Constraints / default |
|---|---|---|---|
| `company_name` | str | no | ≤ 80 chars. Shown on the cover and in the footer |
| `logo` | path | no | PNG, JPEG or SVG, ≤ 2 MB |
| `accent_color` | str | no | `#RRGGBB`, default `#1F4E79` |

**`findings[]` (Finding)**

| Key | Type | Required | Constraints / default |
|---|---|---|---|
| `id` | str | yes | `^[A-Z]{2,5}-\d{3,4}$`, unique in the file (E104) |
| `title` | str | yes | 5–120 chars |
| `cvss_vector` | str | conditional | CVSS 3.1 base vector (Section 4.3). Required unless `severity: informational` |
| `severity` | enum | conditional | Only allowed value: `informational`. Allowed only when `cvss_vector` is absent. Both present or both absent → E206 |
| `status` | enum | no | `open` (default), `remediated`, `risk_accepted` |
| `cwe` | list[int] | no | Each 1–9999. Rendered as links to `https://cwe.mitre.org/data/definitions/<n>.html` |
| `affected_assets` | list[str] | yes | ≥ 1 item |
| `description` | Markdown | yes | ≥ 20 chars |
| `impact` | Markdown | yes | ≥ 20 chars |
| `steps_to_reproduce` | list[Markdown] | yes | ≥ 1 item. Rendered as an ordered list |
| `evidence` | list[Evidence] | no | 0–30 items. An empty list raises W102 |
| `remediation` | Markdown | yes | ≥ 20 chars |
| `references` | list[URL] | no | `http`/`https` only |

`Evidence`:

| Key | Type | Required | Constraints |
|---|---|---|---|
| `type` | enum | yes | `text`, `http` or `image` |
| `caption` | str | yes | 3–200 chars. Used as the image alt text |
| `content` | str | for `text` / `http` | ≤ 200 KB. Rendered verbatim in a monospaced block. `http` gets request/response syntax highlighting |
| `language` | str | no (`text` only) | Code-highlighting hint, for example `bash` or `json` |
| `path` | path | for `image` | PNG, JPEG, GIF or WebP, ≤ 5 MB, must exist (E301, E303) |

Giving `content` for an `image` evidence item, or `path` for a `text`/`http` item, is an error (E103).

#### 4.2.3 Complete example (2 findings)

```yaml
schema_version: 1

engagement:
  title: "Web Application Penetration Test – Acme Customer Portal"
  client:
    name: "Acme Corp"
    contact: "Jane Doe, CISO"
  testers:
    - name: "Alex Tester"
      email: "alex@example-security.test"
      role: "Lead Penetration Tester"
  start_date: 2026-11-02
  end_date: 2026-11-13
  report_date: 2026-11-20
  report_version: "1.0"
  classification: "CONFIDENTIAL"
  scope:
    in_scope:
      - asset: "https://portal.acme.example"
        type: url
      - asset: "203.0.113.10"
        type: ip
        notes: "Production API host"
    out_of_scope:
      - asset: "https://status.acme.example"
        type: url
        notes: "Hosted by a third party"
  methodology: |
    Testing followed the **OWASP Web Security Testing Guide v4.2** as a
    grey-box assessment with two standard-user accounts supplied by Acme.
  executive_summary: |
    The portal's authentication layer is vulnerable to SQL injection, which
    allows an unauthenticated attacker to take over any account. Immediate
    remediation of PT-001 is recommended.

branding:
  company_name: "Example Security Labs"
  logo: assets/logo.png
  accent_color: "#1F4E79"

redaction:
  enabled: true
  custom_patterns:
    - name: ACME_EMPLOYEE_ID
      regex: 'ACME-\d{6}'
  allowlist:
    - "attacker@example-security.test"

findings:
  - id: PT-001
    title: "SQL Injection in Login Endpoint"
    cvss_vector: "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H"
    status: open
    cwe: [89]
    affected_assets:
      - "https://portal.acme.example/api/v1/login"
    description: |
      The `username` field of the JSON login request is concatenated into a
      SQL query without parameterisation.
    impact: |
      An unauthenticated attacker can bypass authentication as any user,
      including administrators, and read or modify the entire database.
    steps_to_reproduce:
      - "Send the request shown in Evidence 1 to `/api/v1/login`."
      - "Observe that a valid session for the `admin` user is returned."
    evidence:
      - type: http
        caption: "Boolean-based payload returns an admin session"
        content: |
          POST /api/v1/login HTTP/1.1
          Host: portal.acme.example
          Content-Type: application/json

          {"username":"admin' OR '1'='1' -- ","password":"x"}

          HTTP/1.1 200 OK
          Set-Cookie: session=9f8e7d6c5b4a3921; Path=/; HttpOnly; Secure
          Content-Type: application/json

          {"token":"eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJhZG1pbiJ9.c2lnbmF0dXJl","email":"admin@acme.example","staff_id":"ACME-104233"}
      - type: image
        caption: "sqlmap enumerating database tables"
        path: evidence/pt-001-sqlmap.png
    remediation: |
      Use parameterised queries (prepared statements) for all database access
      and add a WAF rule as defence in depth until the fix is deployed.
    references:
      - "https://owasp.org/www-community/attacks/SQL_Injection"
      - "https://cheatsheetseries.owasp.org/cheatsheets/SQL_Injection_Prevention_Cheat_Sheet.html"

  - id: PT-002
    title: "Reflected Cross-Site Scripting in Search"
    cvss_vector: "CVSS:3.1/AV:N/AC:L/PR:N/UI:R/S:C/C:L/I:L/A:N"
    status: open
    cwe: [79]
    affected_assets:
      - "https://portal.acme.example/search?q="
    description: |
      The `q` parameter is reflected into the results page without output
      encoding, allowing arbitrary JavaScript to run in the victim's browser.
    impact: |
      An attacker who tricks a logged-in user into opening a crafted link can
      perform actions as that user and read data shown in the page.
    steps_to_reproduce:
      - "Log in as any user."
      - "Open `https://portal.acme.example/search?q=<svg/onload=alert(document.domain)>`."
      - "Observe the alert box showing `portal.acme.example`."
    evidence:
      - type: text
        caption: "Reflected payload in the HTML response (internal debug header included)"
        language: html
        content: |
          X-Backend-Host: 10.20.0.15
          <div class="results">No results for <svg/onload=alert(document.domain)></div>
    remediation: |
      Apply context-aware output encoding to all reflected input and deploy a
      Content-Security-Policy that disallows inline scripts.
    references:
      - "https://owasp.org/www-community/attacks/xss/"
```

Expected derived values: PT-001 scores **9.8 Critical**, PT-002 scores **6.1 Medium**. After redaction, the PT-001 HTTP evidence MUST render exactly as:

```text
{"username":"admin' OR '1'='1' -- ","password":"[REDACTED:SECRET]"}
...
Set-Cookie: session=[REDACTED:COOKIE]; Path=/; HttpOnly; Secure
...
{"token":"[REDACTED:JWT]","email":"[REDACTED:EMAIL]","staff_id":"[REDACTED:ACME_EMPLOYEE_ID]"}
```

The PT-002 evidence line renders as `X-Backend-Host: [REDACTED:PRIVATE_IP]`.

#### 4.2.4 Diagnostic codes

| Code | Level | Meaning |
|---|---|---|
| E100 | error | YAML syntax error |
| E101 | error | Unknown field (with "did you mean" hint) |
| E102 | error | Missing required field |
| E103 | error | Wrong type, length or pattern; or a field not allowed for this evidence type |
| E104 | error | Duplicate finding `id` |
| E105 | error | `end_date` is before `start_date` |
| E106 | error | Unsupported `schema_version` |
| E201 | error | CVSS vector missing the `CVSS:3.1/` prefix, or an unsupported version |
| E202 | error | Unknown CVSS metric |
| E203 | error | Invalid value for a CVSS metric |
| E204 | error | Missing CVSS base metric(s) |
| E205 | error | Duplicate CVSS metric |
| E206 | error | Both `cvss_vector` and `severity` given, or neither |
| E301 | error | Referenced file not found |
| E302 | error | Path resolves outside the project directory |
| E303 | error | Unsupported file type, or file too large |
| E304 | error | Invalid custom redaction regex, or invalid pattern name |
| W101 | warning | Placeholder text found (`TODO`, `TBD`, `lorem ipsum`, `FIXME`, case-insensitive) |
| W102 | warning | Finding has no evidence |
| W201 | warning | Temporal/environmental CVSS metrics present; they are ignored in v0.1 |

Text-mode format, one diagnostic per entry:

```text
findings.yaml:57:18: error[E203] findings[0].cvss_vector: invalid value 'X' for metric 'AV'
  hint: AV must be one of N (Network), A (Adjacent), L (Local), P (Physical)
```

### 4.3 CVSS 3.1 scoring

| ID | Requirement |
|---|---|
| FR-20 | pentrep MUST implement the CVSS v3.1 base score equations from the FIRST specification (Section 7.1) in its own module (`cvss.py`), with no third-party CVSS library at runtime. |
| FR-21 | **Parsing:** after trimming whitespace, the vector MUST start with `CVSS:3.1/` (E201; `CVSS:3.0/` gets a hint to change the prefix). It then contains `/`-separated `METRIC:VALUE` pairs in any order. Metric names and values are case-sensitive. All 8 base metrics (AV, AC, PR, UI, S, C, I, A) MUST each appear exactly once (E204, E205). Unknown metrics → E202. Invalid values → E203. Temporal metrics (E, RL, RC) and environmental metrics (CR, IR, AR, MAV, MAC, MPR, MUI, MS, MC, MI, MA) are recognised, ignored and raise W201. |
| FR-22 | **Weights:** AV N=0.85, A=0.62, L=0.55, P=0.20 · AC L=0.77, H=0.44 · PR N=0.85, L=0.62 (0.68 if S:C), H=0.27 (0.50 if S:C) · UI N=0.85, R=0.62 · C/I/A H=0.56, L=0.22, N=0. |
| FR-23 | **Equations:** ISS = 1 − (1−C)(1−I)(1−A). Impact = 6.42 × ISS if S:U, else 7.52 × (ISS − 0.029) − 3.25 × (ISS − 0.02)^15. Exploitability = 8.22 × AV × AC × PR × UI. Base score = 0 if Impact ≤ 0; otherwise Roundup(min(Impact + Exploitability, 10)) if S:U, or Roundup(min(1.08 × (Impact + Exploitability), 10)) if S:C. **Roundup** MUST use the integer algorithm from spec Appendix A: `i = round(x × 100000)`; return `i / 100000` if `i % 10000 == 0`, else `(floor(i / 10000) + 1) / 10`. |
| FR-24 | **Severity:** 0.0 → None; 0.1–3.9 → Low; 4.0–6.9 → Medium; 7.0–8.9 → High; 9.0–10.0 → Critical. Findings with `severity: informational` have no score and display "Informational". In reports, a score of 0.0 is labelled "None" and sorted with Informational. |
| FR-25 | The report MUST show, for each scored finding, the canonical base vector (metrics in specification order, ignored metrics stripped), the base score with one decimal, and the severity label. The template context MUST also expose the Impact and Exploitability sub-scores, rounded to one decimal. |

**Reference vectors (all MUST match exactly in unit tests)**

| Vector (prefix `CVSS:3.1/` omitted) | Score | Severity |
|---|---|---|
| `AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H` | 9.8 | Critical |
| `AV:N/AC:L/PR:N/UI:N/S:C/C:H/I:H/A:H` | 10.0 | Critical |
| `AV:N/AC:L/PR:L/UI:N/S:C/C:H/I:H/A:H` | 9.9 | Critical |
| `AV:N/AC:L/PR:L/UI:N/S:U/C:H/I:H/A:H` | 8.8 | High |
| `AV:L/AC:L/PR:L/UI:N/S:U/C:H/I:H/A:H` | 7.8 | High |
| `AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:N/A:N` | 7.5 | High |
| `AV:N/AC:L/PR:L/UI:N/S:U/C:H/I:N/A:N` | 6.5 | Medium |
| `AV:N/AC:L/PR:N/UI:R/S:C/C:L/I:L/A:N` | 6.1 | Medium |
| `AV:N/AC:H/PR:N/UI:N/S:U/C:H/I:N/A:N` | 5.9 | Medium |
| `AV:P/AC:L/PR:N/UI:N/S:U/C:L/I:N/A:N` | 2.4 | Low |
| `AV:N/AC:L/PR:N/UI:N/S:U/C:N/I:N/A:N` | 0.0 | None |

Roundup unit cases: `Roundup(4.02) = 4.1`, `Roundup(4.00) = 4.0`, `Roundup(4.000000000000001) = 4.0`.

During M3 the table is extended to ≥ 30 vectors, each cross-checked against the official FIRST CVSS 3.1 calculator and stored in `tests/fixtures/cvss_vectors.json`.

### 4.4 PII redaction

| ID | Requirement |
|---|---|
| FR-30 | Redaction is **on by default**. It applies to evidence `content` (types `text` and `http`) and to `steps_to_reproduce`. Setting `redaction.apply_to_all_text: true` extends it to `description`, `impact` and `remediation`. Engagement metadata, titles, `affected_assets` and `references` are never redacted. |
| FR-31 | Each match is replaced with `[REDACTED:<NAME>]`. When a pattern defines a `value` group, only that group is replaced and the surrounding key (for example `password=` or `Set-Cookie: session=`) is kept. |
| FR-32 | Built-in patterns, applied in this priority order (on overlapping matches the higher-priority pattern wins; among equal priorities the earliest and then longest match wins; every character is redacted at most once): |

| # | Name | Detects | Notes |
|---|---|---|---|
| 1 | `PRIVATE_KEY` | `-----BEGIN … PRIVATE KEY-----` … `-----END … PRIVATE KEY-----` blocks | Whole block replaced |
| 2 | `JWT` | `eyJ[A-Za-z0-9_-]+\.eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]*` | |
| 3 | `BEARER` | Value after `Authorization: Bearer` / `Authorization: Basic` (case-insensitive) | Header name kept |
| 4 | `COOKIE` | Values of `name=value` pairs in `Cookie:` and `Set-Cookie:` header lines | Cookie names and attributes (`Path`, `Domain`, `Expires`, `Max-Age`, `SameSite`, `HttpOnly`, `Secure`) kept |
| 5 | `AWS_KEY` | `\b(AKIA\|ASIA)[0-9A-Z]{16}\b` | |
| 6 | `SECRET` | Value after keys `password`, `passwd`, `pwd`, `secret`, `api_key`/`apikey`/`api-key`, `access_token`, `refresh_token`, `client_secret` (case-insensitive), separated by `=` or `:`, optionally quoted (query strings, form bodies, JSON, headers) | Key kept |
| 7 | `CARD` | 13–19 digits, optionally grouped by spaces or hyphens, **and** passing the Luhn check | Non-Luhn digit runs are not redacted |
| 8 | `EMAIL` | `[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}` | |
| 9 | `PRIVATE_IP` | IPv4 addresses in 10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16 and 169.254.0.0/16, confirmed with the `ipaddress` module | Public, loopback and documentation ranges are not redacted |

| ID | Requirement |
|---|---|
| FR-33 | `redaction.custom_patterns`: up to 50 items of `{ name, regex }`. `name` matches `^[A-Z][A-Z0-9_]{1,31}$` and must not clash with a built-in name. `regex` uses Python `re` syntax, is compiled at validation time (E304 on failure) and may define a `(?P<value>…)` group. Custom patterns run after all built-in ones. |
| FR-34 | `redaction.allowlist`: up to 200 exact strings. A match whose redacted text equals an allowlist entry is left unchanged and not counted. |
| FR-35 | After a build, the CLI MUST print a summary that contains counts and never the original values, for example `Redacted 6 values in 2 findings: SECRET×1, COOKIE×1, JWT×1, EMAIL×1, ACME_EMPLOYEE_ID×1, PRIVATE_IP×1`. When image evidence exists it MUST also print `Note: 1 image evidence item was not scanned (image redaction is not supported in v0.1)`. |
| FR-36 | `--no-redact` or `redaction.enabled: false` disables redaction. The report MUST then show the banner `UNREDACTED DRAFT – DO NOT DISTRIBUTE` on the cover and in every PDF page header and HTML/MD section header. The CLI prints a warning on stderr. |
| FR-37 | Redaction MUST be deterministic (same input → byte-identical output) and applied identically to all three output formats. Original values MUST NOT appear in any output file, in stdout/stderr, or in `--debug` logs. |

### 4.5 Output formats & theme

| ID | Requirement |
|---|---|
| FR-40 | **Report structure** (all formats, in this order): Cover → Document control (version, date, classification, testers) → Table of contents → Executive summary → Scope & methodology → Findings summary table → Detailed findings → Appendix A: CVSS 3.1 severity scale → Appendix B: redaction note (pattern counts, or the unredacted-draft statement). |
| FR-41 | **Cover** shows the engagement title, client name, report date, report version, classification and, if configured, the logo and `company_name`. `accent_color` is applied to headings, table headers and the cover band. |
| FR-42 | **Finding order:** CVSS score descending, then `id` ascending. Findings scored 0.0 or marked Informational come last. Each detailed finding shows: id and title, severity badge, score, vector, status, CWE links, affected assets, description, impact, steps to reproduce (numbered), evidence (numbered "Evidence N" with caption), remediation and references. |
| FR-43 | **Generated statistics** in the executive summary: a table of finding counts per severity (Critical, High, Medium, Low, Informational/None, Total) and an "Overall risk" rating equal to the highest severity among findings with status `open`, or "None" when nothing is open. |
| FR-44 | **Severity colours** are fixed (Critical `#7B1FA2`, High `#C62828`, Medium `#E65100`, Low `#2E7D32`, Informational `#455A64`). Badge text MUST have a contrast ratio ≥ 4.5:1 against its badge colour (WCAG AA). This is checked by a unit test. |
| FR-45 | **HTML:** a single self-contained file. CSS is inlined; logo and evidence images are embedded as `data:` URIs. It MUST NOT contain `<script>` elements, and no `src`/`href`/`url()` may point to an external resource. External URLs are allowed only in `<a href>` (references, CWE links). It sets `<html lang="en">`, uses semantic headings (h1 → h2 → h3 with no skipped levels), uses evidence captions as `alt` text and includes a print stylesheet. |
| FR-46 | **PDF:** rendered by WeasyPrint from the same HTML with print CSS. Page size A4 (or Letter via `--paper`). Every page except the cover shows a header with the classification and a footer `Page X of Y`. The table of contents lists page numbers, and PDF bookmarks exist for every h1/h2. Every detailed finding starts on a new page. Embedded fonts are limited to fonts bundled in the package (OFL-licensed) so output is identical across machines. |
| FR-47 | **Markdown:** GitHub-Flavored Markdown with one `#` title and `##`/`###` sections. The summary and statistics are GFM tables. Severity is shown as text (`**Critical (9.8)**`). Images are copied to `<output-dir>/assets/<finding-id>-<n>.<ext>` and referenced by relative path. Evidence uses fenced code blocks; a fence longer than any backtick run in the content is chosen automatically. |
| FR-48 | **Theme & template override:** v0.1 ships one theme, `classic` (`report.html.j2`, `report.md.j2`, `partials/*.j2`, `style.css`). `--template-dir DIR` is searched before the built-in theme (Jinja2 `ChoiceLoader`), so a user can override a single partial. Jinja2 autoescaping MUST be on for HTML templates. The template context (`engagement`, `branding`, `findings`, `stats`, `redaction`, `generated_at`, `pentrep_version`) is documented in `docs/templates.md`. |
| FR-49 | **Reproducibility:** with the same input, the same pentrep version and a fixed `report_date` (or `SOURCE_DATE_EPOCH`), HTML and Markdown output MUST be byte-identical across runs and across supported OSes. |

### 4.6 Distribution

| ID | Requirement |
|---|---|
| FR-60 | Published to PyPI as `pentrep` (sdist + pure-Python wheel) by a GitHub Actions workflow using PyPI Trusted Publishing on tags matching `v*.*.*`. No API token is stored in the repository. |
| FR-61 | A Docker image is published to `ghcr.io/<github-user>/pentrep:<version>` and `:latest`, based on `python:3.12-slim` with the Pango/HarfBuzz libraries WeasyPrint needs. It runs as a non-root user and its working directory is `/work`. Usage: `docker run --rm -v "$PWD:/work" ghcr.io/<github-user>/pentrep build findings.yaml`. Uncompressed size ≤ 400 MB. |
| FR-62 | The README contains a 3-command quickstart, a screenshot of the cover and one finding page, links to the sample HTML/PDF report generated from `examples/` (published via GitHub Pages by CI), and OS-specific WeasyPrint install notes. |

---

## 5. Non-functional requirements

| ID | Category | Requirement | Verification |
|---|---|---|---|
| NFR-01 | Performance | `pentrep validate` on a file with 50 findings completes in ≤ 1.0 s | Benchmark test on GitHub Actions `ubuntu-latest`, median of 5 runs |
| NFR-02 | Performance | `pentrep build -f html -f md` with 50 findings and 20 images (≤ 500 KB each) completes in ≤ 3 s | Same benchmark harness |
| NFR-03 | Performance | `pentrep build -f pdf` with the same input completes in ≤ 15 s | Same benchmark harness |
| NFR-04 | Performance | `pentrep --help` completes in ≤ 400 ms (WeasyPrint and Jinja2 are imported lazily) | Benchmark test; CI also fails if `weasyprint` is imported during `--help` |
| NFR-05 | Error messages | 100 % of diagnostics include file, line, column, dotted path, code and message. Every E2xx (CVSS) error includes a `hint:` listing the valid values | One invalid fixture per error code, with expected stderr compared as a golden file |
| NFR-06 | Error messages | No Python traceback appears for any fixture in `tests/fixtures/invalid/` or for missing PDF libraries unless `--debug` is passed | CLI tests assert `Traceback` is not in stderr |
| NFR-07 | Compatibility | Python 3.11, 3.12, 3.13 and 3.14 are supported (`requires-python = ">=3.11"`). Python 3.10 is excluded because it reached end-of-life in October 2026 | CI matrix |
| NFR-08 | Compatibility | Linux (Ubuntu 22.04 and 24.04, x86_64) and macOS 14+ (arm64) are supported for all three formats | CI runs the full test suite on `ubuntu-22.04`, `ubuntu-24.04` and `macos-latest` (Pango from Homebrew) |
| NFR-09 | Security | No network access at runtime. pentrep makes zero outbound connections | Test runs `build` with sockets blocked (`pytest-socket`) |
| NFR-10 | Security | YAML safe loading, path confinement (FR-14), escaped Markdown HTML and no evaluation of YAML as templates (FR-13) | Dedicated tests: a `!!python/object` tag, a `../` path, a `<script>` in a description and a `{{ 7*7 }}` in a title must all be rejected or rendered inert |
| NFR-11 | Code quality | `ruff check` and `ruff format --check` pass. `mypy --strict` passes on `src/` | CI job |
| NFR-12 | Packaging | `pipx install pentrep` in a fresh environment installs all runtime dependencies. The wheel is ≤ 2 MB including the bundled fonts | Release workflow check |
| NFR-13 | Documentation | Every CLI flag appears in `--help` and in the README. Every error code appears in `docs/errors.md` | A test parses `docs/errors.md` and compares it with the `ErrorCode` enum |
| NFR-14 | Licensing | MIT licence. Bundled fonts are under SIL OFL, with their licence files included | Release checklist |

---

## 6. Tech stack & rationale

| Concern | Choice | Rationale |
|---|---|---|
| Language | Python ≥ 3.11 | Common in security tooling. 3.11+ gives faster startup and better error messages |
| CLI | **Typer** (on Click) + Rich | Commands defined from type hints, automatic help, coloured output. Rich is already a Typer dependency |
| Schema & validation | **Pydantic v2** | Declarative models with `extra="forbid"`, precise error locations, and built-in JSON Schema export for `pentrep schema` |
| YAML parsing | **ruamel.yaml** (safe, YAML 1.2) | Keeps line and column for every node, which is needed to map Pydantic errors back to `file:line:col` (FR-12). PyYAML does not expose these easily after loading |
| Markdown → HTML | **markdown-it-py** (`html=False`) + GFM table plugin | CommonMark-compliant, with raw HTML disabled by configuration (FR-13) |
| Templating | **Jinja2** (autoescape on for HTML) | De facto standard. `ChoiceLoader` makes template overrides simple (FR-48) |
| PDF | **WeasyPrint** | Renders HTML/CSS to PDF without a browser, with support for paged media (`@page`, counters, bookmarks). Much lighter than headless Chromium |
| Syntax highlighting | **Pygments** | Highlights HTTP and code evidence as static, inline CSS. No JavaScript needed (FR-45) |
| CVSS | Own implementation | Shows understanding of the specification, has no dependency risk, and is easy to test against FIRST vectors |
| Build backend & dev env | **hatchling**, **uv** | Standard `pyproject.toml`, fast and reproducible dev environment with a lockfile |
| Testing | **pytest**, pytest-cov, **hypothesis**, pypdf, pytest-socket | Unit, property-based and golden-file tests. pypdf extracts PDF text for assertions |
| Quality | **ruff**, **mypy --strict**, **pre-commit** | One fast linter/formatter plus strict typing, enforced locally and in CI |
| CI/CD | GitHub Actions, PyPI Trusted Publishing, GHCR | Free for public repos, with no long-lived secrets |

Dependency versions are pinned to a major version in `pyproject.toml` (for example `weasyprint>=X,<X+1`) and locked in `uv.lock`, so PDF layout doesn't change unexpectedly.

---

## 7. Project structure

```text
pentrep/
├── .github/
│   └── workflows/
│       ├── ci.yml              # lint, type-check, tests (matrix), coverage gate
│       ├── release.yml         # build + publish to PyPI on tag v*.*.*
│       ├── docker.yml          # build + push image to GHCR
│       └── pages.yml           # build sample report from examples/ → GitHub Pages
├── docs/
│   ├── PRD.md
│   ├── errors.md               # every diagnostic code with example and fix
│   ├── schema.md               # human-readable findings.yaml reference
│   └── templates.md            # template context for --template-dir
├── examples/
│   ├── findings.yaml           # same content as the `init` scaffold
│   ├── assets/logo.png
│   └── evidence/pt-001-sqlmap.png
├── src/
│   └── pentrep/
│       ├── __init__.py         # __version__
│       ├── __main__.py         # python -m pentrep
│       ├── cli.py              # Typer app: init, validate, build, schema
│       ├── models.py           # Pydantic models (Engagement, Finding, Evidence…)
│       ├── loader.py           # ruamel.yaml load + line/col mapping
│       ├── diagnostics.py      # ErrorCode enum, Diagnostic, formatting (text/json)
│       ├── cvss.py             # CVSS 3.1 parser, scoring, severity
│       ├── redact.py           # built-in + custom patterns, allowlist, summary
│       ├── stats.py            # severity counts, overall risk, sorting
│       ├── render/
│       │   ├── __init__.py
│       │   ├── context.py      # builds the template context
│       │   ├── markdown.py     # markdown-it-py setup (html disabled)
│       │   ├── html.py         # HTML renderer (inline CSS, data URIs)
│       │   ├── md.py           # Markdown report renderer + asset copy
│       │   └── pdf.py          # WeasyPrint wrapper (lazy import, dependency check)
│       ├── scaffold/           # files copied by `pentrep init`
│       │   ├── findings.yaml
│       │   ├── assets/logo.png
│       │   └── evidence/pt-001-sqlmap.png
│       └── themes/
│           └── classic/
│               ├── report.html.j2
│               ├── report.md.j2
│               ├── partials/   # cover, toc, summary, finding, appendix
│               ├── style.css
│               └── fonts/      # OFL fonts + licence files
├── tests/
│   ├── conftest.py
│   ├── unit/
│   │   ├── test_cvss.py
│   │   ├── test_redact.py
│   │   ├── test_models.py
│   │   ├── test_loader.py
│   │   └── test_stats.py
│   ├── cli/
│   │   └── test_cli.py         # Typer CliRunner: exit codes, stdout/stderr
│   ├── render/
│   │   ├── test_html.py
│   │   ├── test_md.py
│   │   ├── test_pdf.py
│   │   └── test_golden.py
│   ├── security/
│   │   └── test_hardening.py   # YAML tags, path traversal, XSS, SSTI, no network
│   ├── perf/
│   │   └── test_benchmarks.py  # NFR-01..04 (marked, run in CI)
│   ├── fixtures/
│   │   ├── valid/
│   │   ├── invalid/            # one file per error code + expected stderr
│   │   ├── cvss_vectors.json
│   │   └── redaction/          # positive/negative corpora per pattern
│   └── golden/
│       ├── report.html
│       └── report.md
├── Dockerfile
├── .dockerignore
├── .pre-commit-config.yaml
├── pyproject.toml
├── uv.lock
├── CHANGELOG.md                # Keep a Changelog format
├── LICENSE                     # MIT
└── README.md
```

---

## 8. Testing strategy

### 8.1 Tools & gates

- **pytest** is the test runner. **pytest-cov** runs with branch coverage enabled.
- **Coverage gates (CI fails below these):**
  - ≥ 85 % line coverage for the whole `src/pentrep` package,
  - ≥ 95 % line **and** branch coverage for `cvss.py` and `redact.py`.
- Tests marked `pdf` need WeasyPrint system libraries. They run in CI on all OSes and are skipped locally with a visible reason when the libraries are missing.
- Tests marked `perf` run in a dedicated CI job, so timing noise doesn't make the main matrix flaky.

### 8.2 Test layers

| Layer | What is tested | Examples / criteria |
|---|---|---|
| Unit: CVSS | Parser, weights, Roundup, severity bands | All vectors in `cvss_vectors.json` (≥ 30, checked against the FIRST calculator), the Roundup edge cases from Section 4.3, and one test per E201–E205/W201 |
| Property-based (hypothesis) | CVSS invariants | For every valid random vector: 0.0 ≤ score ≤ 10.0; the score has exactly one decimal; severity matches its band; raising any C/I/A metric from N → L → H never lowers the score; canonicalising a shuffled vector is idempotent |
| Unit: redaction | Every built-in pattern | For each pattern, a positive corpus (≥ 5 samples that MUST be redacted) and a negative corpus (≥ 5 lookalikes that MUST NOT be, for example public IPs, non-Luhn card numbers, `password` in prose without `=`/`:`). Plus tests for priority/overlap, allowlist, custom `value` groups, E304 and determinism |
| Unit: models & loader | Schema rules and line mapping | One fixture per E1xx/E3xx code, asserting code, dotted path, **line and column** |
| CLI | Commands, flags, exit codes | `CliRunner` covers every flag in Section 4.1, every exit code (0/1/2/3), `--format json` output against a JSON Schema, `--quiet`, `NO_COLOR`, and `init` conflict handling |
| Golden files | HTML and Markdown output | `tests/golden/report.html` and `report.md` are rendered from `tests/fixtures/valid/full.yaml` with `SOURCE_DATE_EPOCH` fixed and the version string normalised. The test compares byte-for-byte and shows a unified diff on failure. Golden files are regenerated only with `pytest --update-golden`, and the diff is reviewed in the PR |
| PDF (structural) | PDF output, where golden bytes are impractical because of metadata and font hinting | With pypdf: correct page size; every finding title appears in the extracted text; each finding starts on a new page; `Page X of Y` footers present; a bookmark exists for every h2; no seeded secret appears in the extracted text |
| Content parity | Same content in all formats | For the full fixture, the set of finding ids, titles, scores and severities extracted from HTML, MD and PDF is identical |
| Security | Hardening (NFR-09, NFR-10) | Unsafe YAML tags, `../` and symlink escape, `<script>` and `javascript:` links in Markdown, `{{ … }}` and `{% … %}` in fields (rendered literally), no network access, no `<script>` in HTML output, no external `src` |
| Leak test | End-to-end redaction | A fixture seeds 20 unique secrets across all pattern types. After `build -f all`, none of them appears in any output file, in stdout/stderr or in the `--debug` log |
| Packaging smoke | Install & run | In CI: build the wheel, install it into a fresh venv, run `init` + `build -f all` in a temp directory, and assert three files exist with size > 0. The same flow runs inside the Docker image |

---

## 9. Milestones

Each milestone is complete only when **all** of its acceptance criteria pass in CI.

### M1 — Project skeleton & CI

- [ ] `pyproject.toml` (hatchling, `requires-python >=3.11`), `src/` layout, MIT `LICENSE`, `uv.lock`.
- [ ] `pentrep --version` prints `pentrep 0.1.0.dev0` and exits 0. `python -m pentrep --version` gives the same result.
- [ ] `ci.yml` runs ruff, `mypy --strict` and pytest on Python 3.11–3.14 × {ubuntu-22.04, ubuntu-24.04, macos-latest}. All jobs are green.
- [ ] pre-commit config runs ruff and mypy. `pre-commit run --all-files` passes.

### M2 — Schema, loader & `init` / `validate` / `schema`

- [ ] Pydantic models implement every field and constraint in Section 4.2.2.
- [ ] `pentrep init tmp/` creates the 3 files. A second run exits 1 and lists the conflicts. With `--force` it exits 0.
- [ ] `pentrep validate` on the `init` output exits 0 with `0 warnings`.
- [ ] For every fixture in `tests/fixtures/invalid/`, `validate` exits 1 and stderr matches the expected golden output (code, path, line, column).
- [ ] A file with 3 independent errors reports all 3 in one run.
- [ ] `--format json` output validates against the diagnostics JSON Schema.
- [ ] `pentrep schema` output validates the `init` example (checked with the `jsonschema` package in the tests).

### M3 — CVSS 3.1

- [ ] All ≥ 30 vectors in `cvss_vectors.json` match the expected score and severity exactly.
- [ ] Roundup edge cases pass.
- [ ] The hypothesis properties in Section 8.2 pass with 1,000 examples each.
- [ ] Each of E201–E206 and W201 has a fixture that produces it, with the correct hint.
- [ ] `cvss.py` has ≥ 95 % line and branch coverage.

### M4 — PII redaction

- [ ] All 9 built-in patterns pass their positive and negative corpora.
- [ ] The Section 4.2.3 example redacts to exactly the expected text shown there.
- [ ] Custom patterns with and without a `value` group work. An invalid regex produces E304 at validation time.
- [ ] Allowlisted values remain and are not counted in the summary.
- [ ] The summary line in FR-35 is printed with the correct counts, and the image note appears when image evidence exists.
- [ ] Running the redaction twice on the same input gives byte-identical results.
- [ ] `redact.py` has ≥ 95 % line and branch coverage.

### M5 — HTML & Markdown rendering (`classic` theme)

- [ ] `pentrep build examples/findings.yaml -f html -f md` exits 0 and writes `report/pentest-report.html`, `report/pentest-report.md` and `report/assets/`.
- [ ] The HTML and MD golden tests pass.
- [ ] HTML checks pass: no `<script>`, no external `src`/`url()`, images are `data:` URIs, `lang="en"`, no skipped heading levels.
- [ ] Findings are ordered as in FR-42. Statistics and overall risk match FR-43 for 4 fixture combinations (all open, all remediated, mixed, informational only).
- [ ] The severity badge contrast test (FR-44) passes.
- [ ] `--template-dir` overriding only `partials/cover.html.j2` changes the cover and leaves the rest identical to the golden file.
- [ ] `--no-redact` output contains the FR-36 banner, and the CLI prints a warning.
- [ ] Output is byte-identical across ubuntu and macOS CI runners (the same golden files pass on both).

### M6 — PDF

- [ ] `pentrep build examples/findings.yaml -f pdf` writes a valid PDF that opens with pypdf.
- [ ] All PDF structural tests in Section 8.2 pass on ubuntu and macOS.
- [ ] `--paper letter` produces 612 × 792 pt pages. The default produces A4 (595 × 842 pt, ±1 pt).
- [ ] When WeasyPrint's libraries are unavailable (simulated in a test), `build -f all` still writes HTML and MD, prints the install hint and exits 3, with no traceback.
- [ ] The content-parity test across HTML, MD and PDF passes.

### M7 — Distribution & documentation (v0.1.0 release)

- [ ] A tag `v0.1.0-rc1` publishes to TestPyPI. In a clean `python:3.12` container, `pipx install --index-url https://test.pypi.org/simple/ --pip-args="--extra-index-url https://pypi.org/simple" pentrep` → `pentrep init` → `pentrep build findings.yaml -f html -f md` exits 0.
- [ ] The Docker image builds, is ≤ 400 MB, runs as non-root, and `docker run --rm -v "$PWD:/work" <image> build findings.yaml` produces all three formats.
- [ ] The NFR-01 to NFR-04 benchmarks pass in the `perf` CI job.
- [ ] The README contains the quickstart, screenshots and links to the GitHub Pages sample report. `docs/errors.md` covers every error code (NFR-13 test passes).
- [ ] The tag `v0.1.0` publishes to PyPI and GHCR. `CHANGELOG.md` has a 0.1.0 entry.

---

## 10. Risks & open questions

### Risks

| # | Risk | Likelihood / impact | Mitigation |
|---|---|---|---|
| R-01 | WeasyPrint needs Pango/HarfBuzz system libraries; installs fail on macOS without Homebrew and on Windows | High / Medium | Lazy import with a clear error and OS-specific hint (FR-03). HTML/MD still work without them. Docker image is the zero-setup path. README install matrix |
| R-02 | Regex redaction misses secrets (false negatives) or hides useful data (false positives) | Medium / High | Redaction is documented as a **safety net, not a guarantee**. Positive/negative corpora per pattern. Allowlist and custom patterns. Summary counts so the tester reviews them. A permanent README notice that images are not scanned |
| R-03 | A user-supplied custom regex causes catastrophic backtracking and a hang (Python `re` has no timeout) | Low / Medium | Limits on pattern count and evidence size (200 KB). The pitfall is documented. Running each pattern with a time budget (for example via the `regex` package's `timeout`) is left as open question Q-04 |
| R-04 | Floating-point errors cause off-by-0.1 CVSS scores | Medium / High | The spec's integer Roundup algorithm (FR-23), ≥ 30 reference vectors and property tests |
| R-05 | WeasyPrint upgrades change PDF layout | Medium / Low | Pinned major version plus lockfile. No byte-level PDF golden tests; structural assertions only |
| R-06 | HTML golden files differ across OSes (line endings, font fallback, Pygments version) | Medium / Medium | Normalised `\n` newlines, Pygments version locked, bundled fonts, and golden tests run on both ubuntu and macOS from M5 |
| R-07 | The `pentrep` name is already taken on PyPI or GHCR before release | Low / Medium | Check availability at M1, and reserve it by publishing `0.0.1` early if needed. Fallback name: `pentrep-cli` |
| R-08 | Scope creep (CVSS 4.0, importers, multi-theme) delays v0.1 | Medium / Medium | Non-goals list in Section 2. Ideas go into a `ROADMAP.md`/GitHub issues, not into v0.1 |

### Open questions

| # | Question | Default if not decided by M2 |
|---|---|---|
| Q-01 | Should findings with status `remediated` or `risk_accepted` be counted in the severity table, or shown in a separate "resolved" column? | Counted in the table; the status column shows the state. Overall risk counts only `open` findings (FR-43) |
| Q-02 | Should `PRIVATE_IP` also cover IPv6 ULA (`fc00::/7`) and link-local (`fe80::/10`) addresses? | Not in v0.1; add to the roadmap |
| Q-03 | Should redaction optionally use consistent pseudonyms (`[REDACTED:EMAIL#1]`, `#2`) so readers can tell distinct values apart? | Not in v0.1 (plain tokens) |
| Q-04 | Should custom regexes run with a timeout, using the third-party `regex` module instead of `re`? | Use `re` in v0.1. Revisit if R-03 shows up in practice |
| Q-05 | Is a `retest` workflow needed (for example `retest_date` and before/after status per finding)? | Out of scope. The `status` field covers the basic case |
| Q-06 | Which OFL font family should the `classic` theme bundle (Inter, Source Sans 3, IBM Plex)? | **Decided (M6.1):** Source Sans 3 (Regular, Italic, Bold) plus Source Code Pro Regular for evidence, from Adobe's npm releases. The wheel is about 0.7 MB. The fonts are used for PDF only; the HTML report stays self-contained and uses the same names in its font stack |
| Q-07 | Should HTML/MD work on Windows without Docker (CI-tested), even though PDF is unsupported there? | No official support in v0.1. Accept community reports |
