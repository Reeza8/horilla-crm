# Security Policy

Horilla takes security seriously. This document explains how to report vulnerabilities, which versions we support, what is in or out of scope, and how we handle disclosure and CVE assignment.

This policy applies to Horilla CRM ([`horilla/horilla-crm`](https://github.com/horilla/horilla-crm)).

## Supported versions

Horilla CRM ships on a frequent release cadence. Security support is defined by **release position**, not by hard-coded version numbers in this file:

| Release line | Security support |
|--------------|------------------|
| Latest stable release on `master` / GitHub Releases | **Yes** — actively maintained |
| Immediately previous stable release | **Yes** — still accepted for critical/high issues |
| Older releases | **No** — upgrade to a supported release |

Check [GitHub Releases](https://github.com/horilla/horilla-crm/releases) for the current latest and previous tags. Reports that only affect unsupported releases will normally be closed with guidance to upgrade.

## Reporting a vulnerability

**Do not** open a public GitHub issue or discussion for a security vulnerability.  
**Do not** disclose exploit details publicly until we have published a fix or explicitly agreed otherwise.

### How to report

Use **GitHub Private Vulnerability Reporting** only:

1. Open a [private vulnerability report](https://github.com/horilla/horilla-crm/security/advisories/new) on this repository.
2. Include enough detail for us to reproduce the issue (see below).

We do **not** accept or triage security vulnerability reports by email. General support inboxes are for product help, not vulnerability disclosure.

We aim to **acknowledge** valid reports within **72 hours**. Resolution time depends on severity and complexity; we will keep you informed via the private advisory thread.

### What to include

- Affected Horilla CRM **version** or commit / Docker tag
- Environment notes (self-hosted Compose, reverse proxy, auth mode) — use variable *names* and redacted examples only
- Step-by-step reproduction (minimal PoC preferred)
- Impact (who can exploit it, and what they gain)
- Whether a fix or workaround is already known

**Never** paste live secrets, tokens, database dumps, or customer PII / CRM record data.

Reporter-supplied CVSS scores are helpful input; maintainers decide the final severity.

Please avoid dumping large batches of unverified findings without waiting for triage feedback on earlier reports.

## Scope

### In scope

- Vulnerabilities in **Horilla CRM application code** shipped in this repository
- Unsafe **default configuration** that we ship (for example a publicly known default `SECRET_KEY` in production paths)
- Issues that are **authentically exploitable** with realistic privileges on a **supported** version

### Out of scope

We will normally **not** treat the following as Horilla CRM product CVEs. We may still harden or document them when useful.

| Class | Notes |
|-------|--------|
| CSV / Excel formula injection | Spreadsheet clients interpret cell content; not a Horilla application bug |
| Privilege escalation by users who already administer users/roles | Trusted-admin capability by design |
| Issues only on EOL Python or EOL Horilla CRM versions | Upgrade to a supported line |
| Pure deployment misconfiguration | Operator responsibility (`DEBUG=True`, open admin, weak secrets you set yourself). **Exception:** shipping an insecure default that works out of the box |
| Media / static XSS when files are served outside documented secure paths | Follow Docker / deployment docs; do not serve private uploads with a raw unauthenticated `/media/` alias |
| Dependency CVEs with **no reachable path** in Horilla CRM | Tracked via Dependabot when applicable |
| Third-party plugins or custom code not shipped by Horilla | Report to that project’s maintainers |
| Compromise of marketing sites, email, or social accounts | Operational incident response — not a product advisory |
| Demands for cash payment (“beg bounties”) | Credit only (see Rewards) |

### Grey areas

- Dynamic code execution or unsafe template rendering reachable by non-admin users: treated as **high priority**
- Object-level authorization gaps on CRM records (leads, accounts, opportunities, etc.): **in scope** when authentically exploitable
- Default secrets in images or quickstart docs: **in-scope product defects**

## Severity (guidance)

Final severity is decided by maintainers:

| Level | Examples |
|-------|----------|
| Critical | Unauthenticated RCE, unauthenticated auth bypass, mass data exposure without auth |
| High | Authenticated RCE, large-scale IDOR on CRM/customer data, authenticated auth bypass |
| Medium | XSS requiring user interaction, limited IDOR, open redirect |
| Low | Low-impact issues, verbose errors without clear exploit path |

## Disclosure and CVE process

1. Private intake via GitHub Private Vulnerability Reporting (private advisory draft)
2. Triage: in scope? valid? duplicate? supported version?
3. Fix on a supported branch; coordinate disclosure with the reporter when practical
4. Publish a GitHub Security Advisory and **request a CVE ID via GitHub** when the issue meets our publish criteria
5. Credit the reporter in the advisory (unless anonymity is requested)

We use **GitHub as the CVE Numbering Authority** for Horilla CRM advisories. We do not require reporters to self-request CVEs from MITRE; unsupported self-requests may be disputed.

**We publish a CVE when all of the following are true:**

- Affects a **supported** release
- Is **authentically exploitable** with realistic privileges
- Is in **Horilla CRM code** or an unsafe default we ship
- Is **not** a duplicate of an already-published advisory for the same root cause

Issues fixed only on unsupported lines are generally **closed without a new CVE**, with a short disposition note.

## Rewards

There is **no cash bug bounty** at this time. We offer public credit in advisories and release notes. A paid program may be considered later when triage capacity is stable.

## Security tooling

We aim to keep the following enabled on this repository:

- Private vulnerability reporting
- Dependabot alerts and security updates
- Secret scanning (and push protection where available)

## Contact

- Security reports: [GitHub Private Vulnerability Reporting](https://github.com/horilla/horilla-crm/security/advisories/new) only — see [Reporting a vulnerability](#reporting-a-vulnerability)
- Non-security questions about this policy: open a GitHub Discussion, or contact the maintainers through the project’s normal channels

## Disclaimer

The Horilla project and its maintainers assume no liability for security vulnerabilities reported or discovered. We greatly appreciate responsible disclosure that helps keep users safe.
