# Admin Notes role and permission matrix (invented, for the example)

| Role | Resource / action | Own | Other user (same org) | Other org | Expected |
|------|-------------------|-----|------------------------|-----------|----------|
| owner (any signed-in user) | read/update/delete own note | allow | deny unless shared | deny | server-side enforced |
| owner | read note shared with them | n/a | allow while share active | deny | share revocation takes effect immediately |
| org-member | list organization members | allow (self view) | allow (names only) | deny | no email or role escalation data leaked |
| org-admin | invite member, set role member/admin | allow | allow within own org | deny | cannot grant a role above their own |
| org-admin | remove member | allow within own org | allow | deny | removed member loses access on next request |
| any | access note by direct id without permission | n/a | n/a | deny | 403 or 404, no note body in the response |

Real products: replace every row with confirmed behavior from your own sources.
