# Admin Notes threat model (invented, for the example)

Assets: note content, user credentials and sessions, organization membership
and roles, invitation tokens.

Actors: anonymous visitor, authenticated user, organization admin, a malicious
authenticated user with a second owned account, a malicious admin of a
different organization.

Trust boundaries: browser to API, API to database, invitation email delivery.

Abuse cases to test:
- Read another user's note by guessing or enumerating note ids (IDOR).
- Keep access to a note after the share is revoked.
- Read or write across organization boundaries.
- Escalate own role by replaying or tampering with the invite acceptance call.
- Reuse a session cookie after logout or after an admin removes the account.
- Submit oversized or script-bearing note content and have it stored or
  reflected without encoding.
- Retrieve other users' emails or roles from a members list response.

Controls assumed present (verify, do not assume): server-side authorization on
every note and membership operation, session invalidation on logout and
removal, output encoding on note rendering, input length limits.

Source and deployment controls (rate limiting, transport config, logging)
remain unverified without the corresponding access.
