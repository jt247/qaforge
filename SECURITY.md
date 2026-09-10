# Security and authorization model

QA Lab is used to assess web applications. This file describes how the workspace
keeps that activity authorized and safe. It is not a vulnerability disclosure
policy for this repository; for that, open a private advisory on GitHub.

## Authorization

Only assess a target the product owner is authorized to assess. Configuration is
standing scope, not proof of ownership. If ownership is unclear, ask before
configuring.

Each environment records its URL, the exact allowed hosts, whether it is staging
or production, its enabled state, the approved actions, who authorized the
assessment, and how that authorization was confirmed. The `configure` command
requires `--authorized-by` and `--auth-method` and it sets an expiry fourteen
days out. After that, `preflight`, `new-run`, and `smoke` refuse to run until
the scope is reconfigured. The `disable` command returns an environment to read
only and unconfigured.

## Permitted actions

The default and only automatic permission is read only. Three further
permissions are separate and must each be added to the saved scope:

- `fixture-write` for creating or changing test fixtures.
- `messaging` for controlled test email or SMS.
- `sandbox-payment` for sandbox payment actions, which must target a confirmed
  payment sandbox even when the application itself is production.

Selecting staging does not authorize every action. Production fixture mutation
requires explicit scoped authorization.

## Target safety

The runner rejects a target that is not HTTPS, resolves to a private, loopback,
link local, carrier grade NAT, or reserved address, or is an internal hostname.
`--allow-insecure` and `--allow-private` override the first two for a local
staging host that you control. Cloud metadata endpoints are rejected regardless
of any flag. The smoke check follows redirects only within the approved hosts
and blocks an HTTPS to HTTP downgrade.

## Out of scope under default authorization

No destructive tests, load tests, brute force, real charges, mass messaging, or
assessment of third party systems. Active security probes require a separately
documented method, request budget, target list, and stop conditions agreed
before execution.

Stop and report on instability, unexpected cost, irreversible effects, scope
ambiguity, or unexpected exposure of real personal data. Preserve minimal
redacted evidence and do not expand access.

## Data handling

Use synthetic data only. Raw evidence and the `local/` directory are ignored by
Git. Never store passwords, one time codes, full card numbers, session cookies,
tokens, real personal information, or phone numbers in tracked files. The runner
refuses to record a result note that matches a secret pattern or contains a
value from `local/identity.json`. Retain raw evidence locally for thirty days by
default; deletion is manual and documented.

## Standards

Security work targets applicable OWASP ASVS 5.0.0 controls with OWASP WSTG v4.2
testing methods. Accessibility targets WCAG 2.2 AA where applicable. Record exact
control identifiers only after consulting the source.

- https://owasp.org/www-project-application-security-verification-standard/
- https://wstg.owasp.org/v4.2/

## Not a certification

These assessments do not constitute security certification or regulatory
compliance certification.
