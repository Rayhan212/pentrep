# Web Application Penetration Test – Acme Customer Portal

![Example Security Labs logo](assets/logo.png)

Example Security Labs

- **Client:** Acme Corp
- **Report date:** 2026-11-20
- **Version:** 1.0
- **Classification:** CONFIDENTIAL

## Document control

| Field | Value |
| --- | --- |
| Report version | 1.0 |
| Report date | 2026-11-20 |
| Classification | CONFIDENTIAL |
| Client | Acme Corp (Jane Doe, CISO) |
| Testing period | 2026-11-02 to 2026-11-13 |

| Tester | Role | Email |
| --- | --- | --- |
| Alex Tester | Lead Penetration Tester | alex@example-security.test |

## Table of contents

- [Executive summary](#executive-summary)
- [Scope and methodology](#scope-and-methodology)
- [Findings summary](#findings-summary)
- [Detailed findings](#detailed-findings)
  - [PT-001: SQL Injection in Login Endpoint](#pt-001-sql-injection-in-login-endpoint)
  - [PT-002: Reflected Cross-Site Scripting in Search](#pt-002-reflected-cross-site-scripting-in-search)
- [Appendix A: CVSS 3.1 severity scale](#appendix-a-cvss-31-severity-scale)
- [Appendix B: Redaction](#appendix-b-redaction)

## Executive summary

The portal's authentication layer is vulnerable to SQL injection, which
allows an unauthenticated attacker to take over any account. Immediate
remediation of PT-001 is recommended.

| Severity | Findings |
| --- | ---: |
| Critical | 1 |
| High | 0 |
| Medium | 1 |
| Low | 0 |
| Informational/None | 0 |
| Total | 2 |

Overall risk: **Critical**

## Scope and methodology

### In scope

| Asset | Type | Notes |
| --- | --- | --- |
| https://portal.acme.example | url |  |
| 203.0.113.10 | ip | Production API host |

### Out of scope

| Asset | Type | Notes |
| --- | --- | --- |
| https://status.acme.example | url | Hosted by a third party |

### Methodology

Testing followed the **OWASP Web Security Testing Guide v4.2** as a
grey-box assessment with two standard-user accounts supplied by Acme.

## Findings summary

| ID | Title | Severity | Status |
| --- | --- | --- | --- |
| [PT-001](#pt-001-sql-injection-in-login-endpoint) | SQL Injection in Login Endpoint | **Critical (9.8)** | Open |
| [PT-002](#pt-002-reflected-cross-site-scripting-in-search) | Reflected Cross-Site Scripting in Search | **Medium (6.1)** | Open |

## Detailed findings

### PT-001: SQL Injection in Login Endpoint

- **Severity:** **Critical (9.8)**
- **CVSS 3.1:** 9.8 (Impact 5.9, Exploitability 3.9)
- **Vector:** `CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H`
- **Status:** Open
- **CWE:** [CWE-89](https://cwe.mitre.org/data/definitions/89.html)
- **Affected assets:** https://portal.acme.example/api/v1/login

**Description**

The `username` field of the JSON login request is concatenated into a
SQL query without parameterisation.

**Impact**

An unauthenticated attacker can bypass authentication as any user,
including administrators, and read or modify the entire database.

**Steps to reproduce**

1. Send the request shown in Evidence 1 to `/api/v1/login`.
2. Observe that a valid session for the `admin` user is returned.

**Evidence**

**Evidence 1: Boolean-based payload returns an admin session**

```http
POST /api/v1/login HTTP/1.1
Host: portal.acme.example
Content-Type: application/json

{"username":"admin' OR '1'='1' -- ","password":"[REDACTED:SECRET]"}

HTTP/1.1 200 OK
Set-Cookie: session=[REDACTED:COOKIE]; Path=/; HttpOnly; Secure
Content-Type: application/json

{"token":"[REDACTED:JWT]","email":"[REDACTED:EMAIL]","staff_id":"[REDACTED:ACME_EMPLOYEE_ID]"}
```

**Evidence 2: sqlmap enumerating database tables**

![sqlmap enumerating database tables](assets/PT-001-2.png)

**Remediation**

Use parameterised queries (prepared statements) for all database access
and add a WAF rule as defence in depth until the fix is deployed.

**References**

- <https://owasp.org/www-community/attacks/SQL_Injection>
- <https://cheatsheetseries.owasp.org/cheatsheets/SQL_Injection_Prevention_Cheat_Sheet.html>

### PT-002: Reflected Cross-Site Scripting in Search

- **Severity:** **Medium (6.1)**
- **CVSS 3.1:** 6.1 (Impact 2.7, Exploitability 2.8)
- **Vector:** `CVSS:3.1/AV:N/AC:L/PR:N/UI:R/S:C/C:L/I:L/A:N`
- **Status:** Open
- **CWE:** [CWE-79](https://cwe.mitre.org/data/definitions/79.html)
- **Affected assets:** https://portal.acme.example/search?q=

**Description**

The `q` parameter is reflected into the results page without output
encoding, allowing arbitrary JavaScript to run in the victim's browser.

**Impact**

An attacker who tricks a logged-in user into opening a crafted link can
perform actions as that user and read data shown in the page.

**Steps to reproduce**

1. Log in as any user.
2. Open `https://portal.acme.example/search?q=<svg/onload=alert(document.domain)>`.
3. Observe the alert box showing `portal.acme.example`.

**Evidence**

**Evidence 1: Reflected payload in the HTML response (internal debug header included)**

```html
X-Backend-Host: [REDACTED:PRIVATE_IP]
<div class="results">No results for <svg/onload=alert(document.domain)></div>
```

**Remediation**

Apply context-aware output encoding to all reflected input and deploy a
Content-Security-Policy that disallows inline scripts.

**References**

- <https://owasp.org/www-community/attacks/xss/>

## Appendix A: CVSS 3.1 severity scale

| Severity | Base score |
| --- | --- |
| None | 0.0 |
| Low | 0.1 – 3.9 |
| Medium | 4.0 – 6.9 |
| High | 7.0 – 8.9 |
| Critical | 9.0 – 10.0 |

## Appendix B: Redaction

Secrets and personal data in evidence and reproduction steps were replaced with `[REDACTED:NAME]` tokens. Redaction is pattern-based and is a safety net, not a guarantee.

| Pattern | Values redacted |
| --- | ---: |
| SECRET | 1 |
| COOKIE | 1 |
| JWT | 1 |
| EMAIL | 1 |
| ACME_EMPLOYEE_ID | 1 |
| PRIVATE_IP | 1 |

Note: 1 image evidence item was not scanned (image redaction is not supported in v0.1)

---

Generated 2026-11-20T12:00:00Z by pentrep <PENTREP_VERSION>.
