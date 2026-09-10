# QA Lab

A local workspace for running product quality assurance and application security
assessment with two AI coding agents that check each other's work.

QA Lab is a filesystem and a small standard library command line tool. It holds
the standards, templates, per product test catalogs, run records, and evidence
for an assessment. It does not launch agents and it does not run in the cloud.
You open one agent session per product, point it at its folder, and the
filesystem is the durable record of what was actually done.

Built and maintained by Joshua Theophilus.

## The model

Most AI assisted testing uses one agent. One agent plans the tests, runs them,
and grades itself. QA Lab runs two.

You use two agents from two different providers, and each one runs on the most
capable model that provider offers. The reference setup is Codex on OpenAI's
strongest model and Claude Code on Anthropic's strongest model. Each agent
creates its own runs with its own test identities, records factual results
through the command line tool, and then reviews the other agent's high risk
findings and a sample of its critical passes. Neither agent can edit the other's
original evidence.

The rule the whole workspace enforces is simple. Evidence determines a result,
not agent agreement. A passing reachability check is not a passing product
assessment. Agreement between the two agents cannot waive a mandatory check or a
missing piece of evidence. The product owner makes the final release decision.

## Shared engineering layer: ECC

QA Lab uses the ECC plugin as the engineering layer both agents work inside.
ECC is an open source agent harness by Affaan Mustafa. It provides planning,
test driven development, fresh context code review, and security scanning as
reusable workflows, so the two agents follow the same process instead of
improvising it each session.

Here is exactly how QA Lab uses it:

- Planning before any change to the lab tooling, through ECC's planning workflow.
- `/code-review` for a fresh context review of every change to `tooling/`.
- `/security-scan`, which runs ECC's AgentShield, against the repository before
  any new product target is enabled.
- ECC's test driven workflow for future changes to `tooling/lab.py`.

ECC is a separate dependency. It is not bundled in this repository and you
install it yourself. Full credit and installation instructions:

- Repository: https://github.com/affaan-m/ECC
- Website: https://ecc.tools
- License: MIT

If you do not want to install ECC, the lab still works. You lose the shared
review and scanning workflows and take on running that discipline yourself.

## Requirements

Python 3.10 or newer. Nothing else. The runner is standard library only and
there is no package to install.

## Quickstart

```sh
python3 tooling/lab.py list
python3 tooling/lab.py validate
python3 -m unittest discover -s tests -v
```

`products/_example/` is a fully populated example product called Admin Notes. It
is a synthetic multi tenant notes application. Read through it to see how a real
product folder is meant to look, then copy it.

## Add your own product

1. Copy `products/_example/` to `products/<your-slug>/` and set the real name
   and slug in `product.json`.
2. Replace the invented requirements, role and permission matrix, threat model,
   personas, and scenarios with your own confirmed information. Leave the URLs
   disabled.
3. Run `python3 tooling/lab.py validate`.

Do not copy run history or credentials between products.

## Run a session

Provide the URL when you start each session, and say whether it is staging or
production. URLs start unset on purpose. Configuration records who authorized the
assessment and how, and it expires after fourteen days.

```sh
python3 tooling/lab.py configure <slug> --env staging \
  --url https://YOUR-AUTHORIZED-HOST \
  --authorized-by "name and role" \
  --auth-method "how ownership was confirmed" \
  --build YOUR-BUILD

python3 tooling/lab.py preflight <slug> --env staging
python3 tooling/lab.py new-run <slug> --env staging --agent codex
python3 tooling/lab.py smoke <slug> --run RUN_ID --agent codex
python3 tooling/lab.py result <slug> --run RUN_ID --agent codex \
  --case PRODUCT-001 --status blocked --note "Requirements pending"
python3 tooling/lab.py report <slug> --run RUN_ID
python3 tooling/lab.py close <slug> --run RUN_ID --agent codex
```

Production defaults to read only. Fixture writes, controlled messaging, and
sandbox payments are separate permissions that must be added to the saved scope.
Plain HTTP targets and private or loopback addresses are rejected unless you pass
`--allow-insecure` or `--allow-private` for a local staging host. Cloud metadata
endpoints are always rejected.

Other commands: `runs <slug>` lists a product's runs, `verify-sources` checks
whether the standards or guides changed since a run was created, `disable` takes
an environment back to read only and unconfigured, and `aliases` proposes
dedicated inbox addresses for confirmed personas without creating any accounts.

## Accounts and private data

See `local/README.md`. Put a dedicated email address and a test phone number in
`local/identity.json` using `templates/identity.example.json`. No password goes
in a session. Authenticate in the browser when you need to. Evidence directories
and the `local/` directory are ignored by Git. The runner refuses to record a
result note that looks like it contains a secret or a value from your identity
file.

## What this is not

- Not a vulnerability scanner. There is no automated crawling or exploitation.
- Not a certification. These assessments do not constitute security or
  regulatory compliance certification.
- Not a release gate on its own. The tool prints an assessment status. A person
  decides whether to release.
- Not tamper proof storage. Result history is append only through the command
  line tool, but the files stay editable by hand. This is workflow preservation,
  not an audit vault.

## More

- `SECURITY.md` for the authorization model and data handling rules.
- `CONTRIBUTING.md` for the `product.json` contract and how to add cases.
- `standards/` for the testing standard, security testing policy, evidence
  standard, severity and release gates, and the agent collaboration rules.

## License

MIT. See `LICENSE`.
