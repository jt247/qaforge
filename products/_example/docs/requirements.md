# Admin Notes requirements (invented, for the example only)

| ID | Requirement | Linked cases |
|----|-------------|--------------|
| REQ-1 | A visitor can create an account with email and password and lands on an empty notes list. | AUTH-001, EX-001 |
| REQ-2 | A signed-in user can create, edit, and delete their own notes; changes persist across reload. | DATA-001, EX-002 |
| REQ-3 | A user can only read or modify notes they own or notes shared with them inside their organization. | ACCESS-001, EX-003 |
| REQ-4 | An organization admin can invite a member and set their role to member or admin. | EX-004 |
| REQ-5 | Logout ends the session; a previously valid session cookie can no longer read notes. | AUTH-001 |
| REQ-6 | Note titles are 1 to 120 characters; empty or oversized input is rejected without a partial save. | DATA-001 |

Real products: assign REQ- IDs from your own confirmed sources and link each to
a case in cases/catalog.json. Do not treat template cases as confirmed scope.
