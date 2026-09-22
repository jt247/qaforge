# Contributing

QAForge is a small standard library tool plus a set of standards and templates.
Keep changes small, tested, and honest about their limits.

## Ground rules

- The runner stays standard library only. No third party packages.
- No product names, client names, real hosts, credentials, or personal test
  identities in the repository. The example product is synthetic on purpose.
- Every result a real run records needs local evidence. Do not weaken that.
- A smoke or reachability check never establishes release readiness. Language in
  the tool and docs must not imply otherwise.

## Working on `tooling/lab.py`

1. Plan the change first.
2. Write or update a test in `tests/test_lab.py` before the code.
3. Run `python3 -m unittest discover -s tests -v`.
4. Run `python3 tooling/lab.py validate`.
5. Run a fresh context code review and a secret scan before opening a pull
   request. The reference workflows are ECC's `/code-review` and
   `/security-scan`.

## The `product.json` contract

There is no separate JSON Schema. `validate_config` in `tooling/lab.py` is the
single source of truth and its rules are documented in the module docstring at
the top of that file. A product has `schema_version` 1, a `name`, a `slug` that
matches `[a-z0-9-]+`, and `environments.staging` and `environments.production`.
An environment that is enabled also carries `authorized_by`, `auth_method`,
`granted_at`, and `expires_at`, all set by the `configure` command.

## Adding cases to a catalog

Each case needs an `id`, a `title`, a `mandatory` flag, an `actor`, a `source`
(a requirement id or an explicit assumption), `steps`, an `expected` outcome, a
`risk` level, and an `execution` type (`http-smoke` or `agent`). Every catalog
must contain a case with id `WEB-001`; the smoke command records against it.

## Pull requests

Describe what changed and why, list the tests you added, and note anything you
did not cover. CI runs the unit tests, `lab.py validate`, and a secret scan on
every pull request.
