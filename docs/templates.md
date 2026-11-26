# Templates and `--template-dir`

pentrep renders reports with [Jinja2](https://jinja.palletsprojects.com/) templates. v0.1 ships one theme,
`classic`. You can override any of its files without copying the whole theme:

```bash
pentrep build findings.yaml --template-dir my-templates/
```

pentrep looks for each template in `--template-dir` first and falls back to the built-in theme (a Jinja
`ChoiceLoader`). To replace only the cover, create `my-templates/partials/cover.html.j2`; every other part
of the report keeps using the built-in files. `style.css` can be overridden the same way.

Rules that also apply to your templates:

- HTML templates (`*.html.j2`) are autoescaped. Values from findings.yaml are data and are never evaluated as
  templates, so `{{ 7*7 }}` in a title is printed literally.
- Undefined variables are errors (`StrictUndefined`). A template error stops the build with exit code 3,
  before any file is written.
- Keep the HTML self-contained: no `<script>`, and no `src`/`url()` pointing outside the file (FR-45). Use
  `image_src` for images.
- Markdown templates (`*.md.j2`) are not autoescaped: pass every value through one of the Markdown filters
  below.

## Theme files

| File | Content |
|---|---|
| `report.html.j2` | HTML page: head, inline CSS, all sections in FR-40 order, footer |
| `report.md.j2` | The whole Markdown report |
| `style.css` | Screen and print styles. `--accent` is set from `branding.accent_color` |
| `partials/macros.html.j2` | `draft_banner(redaction)` and `badge(severity)` macros |
| `partials/cover.html.j2` | Cover: logo, company, title, client, date, version, classification |
| `partials/document_control.html.j2` | Version, dates, classification, testers |
| `partials/toc.html.j2` | Table of contents with links to sections and findings |
| `partials/executive_summary.html.j2` | Executive summary text, severity counts, overall risk |
| `partials/scope.html.j2` | In-scope and out-of-scope assets, methodology |
| `partials/summary_table.html.j2` | One row per finding |
| `partials/finding.html.j2` | One detailed finding (rendered once per item of `findings`) |
| `partials/appendix.html.j2` | Appendix A (severity scale) and Appendix B (redaction) |

## Context

| Variable | Type | Description |
|---|---|---|
| `engagement` | `Engagement` model | Everything under `engagement:` in findings.yaml, with defaults applied (`report_date`, `report_version`, `classification`) |
| `branding` | `BrandingView` | See below |
| `findings` | list of `FindingView` | Sorted by score (descending), then id; 0.0 and informational findings last (FR-42) |
| `stats` | `Stats` | `counts`: dict of `Critical`, `High`, `Medium`, `Low`, `Informational/None`, `Total`; `overall_risk`: a `Severity` (FR-43) |
| `redaction` | `RedactionView` | See below |
| `generated_at` | str | `SOURCE_DATE_EPOCH` as `YYYY-MM-DDTHH:MM:SSZ` when set, else the report date (FR-49) |
| `pentrep_version` | str | The pentrep version |
| `css` | str | `style.css` (HTML only), already marked safe |
| `image_src` | function | `image_src(path, mime, asset_name)`: a `data:` URI in HTML, a relative `assets/...` path in Markdown |

A `Severity` has `label` (`None`, `Informational`, `Low`, `Medium`, `High`, `Critical`) and `rank`.

### `FindingView`

| Field | Description |
|---|---|
| `id`, `title` | From findings.yaml |
| `anchor` | HTML id, for example `finding-pt-001` |
| `severity` | `Severity` (Informational for `severity: informational`) |
| `badge` | CSS class suffix: `critical`, `high`, `medium`, `low`, `none` or `informational` |
| `score` | Base score (float), or `None` for informational findings |
| `score_text` | `9.8`, or `N/A` |
| `vector` | Canonical vector (temporal/environmental metrics removed), or `None` |
| `impact_score`, `exploitability_score` | Sub-scores rounded to one decimal, or `None` |
| `status`, `status_label` | `open` / `Open`, `remediated` / `Remediated`, `risk_accepted` / `Risk accepted` |
| `cwe` | List of `(number, url)` pairs |
| `affected_assets`, `references` | Lists of strings |
| `description`, `impact`, `remediation` | Markdown (redacted when `apply_to_all_text` is set) |
| `steps_to_reproduce` | List of Markdown strings (redacted) |
| `evidence` | List of `EvidenceView` |

### `EvidenceView`

| Field | Description |
|---|---|
| `number` | 1-based position within the finding ("Evidence N") |
| `type` | `text`, `http` or `image` |
| `caption` | Caption; use it as `alt` text for images |
| `content` | Redacted text, or `None` for images |
| `language` | Highlighting language (`http` for HTTP evidence), or `None` |
| `image_path` | Resolved image file, or `None` |
| `asset_name` | File name used in Markdown output, for example `PT-001-2.png` |
| `mime` | Image MIME type, for example `image/png` |

### `BrandingView`

| Field | Description |
|---|---|
| `company_name` | Or `None` |
| `accent_color` | `#RRGGBB` |
| `logo_path`, `logo_asset_name`, `logo_mime` | The logo file, its Markdown asset name and MIME type, or `None` |

### `RedactionView`

| Field | Description |
|---|---|
| `enabled` | Redaction was applied |
| `unredacted` | `True` with `--no-redact` or `redaction.enabled: false`: show `banner` everywhere (FR-36) |
| `banner` | `UNREDACTED DRAFT – DO NOT DISTRIBUTE` |
| `counts` | `(pattern name, count)` pairs in order of first appearance |
| `values` | Total number of redacted values |
| `images_not_scanned` | Number of image evidence items (not scanned) |
| `lines` | The FR-35 summary lines printed by the CLI |

## Filters

HTML templates:

| Filter | Use |
|---|---|
| `markdown` | User Markdown → HTML. Raw HTML is escaped, only http/https/mailto links are kept, images are not rendered, headings become bold paragraphs |
| `markdown_inline` | One line of Markdown without a `<p>` wrapper (list items) |
| `highlight` | `content \| highlight(language)`: evidence text → Pygments HTML with inline styles; the text stays verbatim |

Markdown templates:

| Filter | Use |
|---|---|
| `md_inline` | Plain text shown literally (Markdown punctuation is backslash-escaped) |
| `md_cell` | Plain text in a table cell |
| `md_block` | User Markdown: raw HTML and dangerous links are neutralised, headings become bold lines |
| `md_step` | One user Markdown line for a numbered list |
| `md_url` | A URL inside `<…>`, with `<`, `>`, spaces and backticks percent-encoded |
| `slug` | GitHub's anchor for a heading, for table-of-contents links |
| `fence` | A backtick fence longer than any backtick run in the content |
