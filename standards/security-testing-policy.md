# Security testing policy
Only test targets the product owner is authorized to assess. Each environment records URL, exact allowed hosts, staging/production, enabled state, and approved actions. Configuration is standing scope, not proof of ownership; ask if ownership is unclear.
Default permitted action: read-only. Mutating fixtures requires fixture-write; controlled email/SMS requires messaging; sandbox payment actions require sandbox-payment. These are separate permissions. User authorization persists when saved here.
No destructive tests, load tests, brute force, real charges, mass messaging, or third-party assessment under default scope. Active security probes require a separately documented method, request budget, target, and stop conditions before execution. Merely selecting staging does not authorize every action.
Stay within approved hosts; stop before an out-of-scope redirect. Production fixture mutation requires explicit scoped authorization. Test card use must target a confirmed payment sandbox, even when the app itself is production.
Use synthetic sensitive data. On unexpected real data exposure, stop expanding access, preserve minimal redacted evidence, and report. Stop for instability, unexpected cost, irreversible effects, or scope ambiguity.
Baseline manual assessment: authentication/session behavior; access to another owned test user's objects; role changes; organization boundaries; reset/logout/revocation; sensitive data exposure; input and upload handling where present. Backend and infrastructure controls remain unverified without supporting access.
Reference: https://owasp.org/www-project-application-security-verification-standard/ (ASVS 5.0.0)
Reference: https://wstg.owasp.org/v4.2/ (WSTG v4.2)
These assessments do not constitute security certification or regulatory compliance certification.
