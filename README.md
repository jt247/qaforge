# QAForge

A workspace for running product quality assurance and broad, browser based
application testing with two AI coding agents that check each other's work.

QAForge is a filesystem and a small standard library command line tool. It
holds the standards, templates, per product test catalogs, run records, and
evidence for an assessment. It does not launch agents and it does not run in
the cloud. You open one agent session per product, point it at its folder, and
the filesystem is the durable record of what was actually done.

Built and maintained by Joshua Theophilus.

## Two ways in

QAForge never calls an AI API itself. It runs inside the Claude Code and Codex
sessions you already pay for, and the same one-shot bootstrap sets everything up
whichever door you use. You need one or both of:

- **Claude Code** (desktop app or CLI) on a plan that includes it.
- **ChatGPT Plus or higher** with **Codex** (the ChatGPT desktop app or the
  Codex CLI). Check OpenAI's current plan eligibility before relying on this.

### Door 1: no coding required

1. Open Claude Code (desktop app is easiest) or Codex from the ChatGPT desktop
   app.
2. Tell it to clone `https://github.com/jt247/qaforge` into a folder and open
   that folder as the project.
3. Say, in plain language, what you want to test: the app's name, its URL,
   staging or production, and that you want QAForge set up and run against it.
4. The assistant reads `AGENTS.md`, runs the bootstrap itself, creates the
   product folder, states the goal and the testing plan, and waits for you to
   confirm in chat before it runs anything. You never type a command unless
   you want to.

### Door 2: terminal

```sh
git clone https://github.com/jt247/qaforge
cd qaforge
python3 tooling/lab.py init
python3 tooling/lab.py session <product-slug> --agent claude
python3 tooling/lab.py session <product-slug> --agent codex
```

`init` checks Python and Git, reports whether ECC and a browser MCP are
present, creates `local/identity.json` from the template, validates every
product folder, and runs the unit tests. It prints READY or tells you exactly
what is missing.

`session` starts your own already signed in `claude` or `codex` CLI in this
repository with the session brief preloaded, so the agent opens by stating the
goal and plan and waiting for your confirmation. Add `--print-only` to get the
prompt as text and paste it into a desktop app instead.

Authentication is whatever each CLI already uses: your subscription login by
default, or `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` if you prefer keys. See
`.env.example`. QAForge reads neither.

### ECC and the browser tool

Browser based checks need a browser MCP. The ECC plugin ships one
(`chrome-devtools`) as its default connector, so installing ECC covers both the
engineering workflows and the browser tool in one step:

```sh
npx ecc-universal setup
```

When the installer asks for a hook profile, pick `none` or `minimal` to start;
the `standard` profile adds confirmation prompts on every file edit that you may
not want while testing. If you skip ECC, configure the Playwright MCP instead;
`init` will tell you whether either is detected.

There is no server to host and no dependency to install beyond Python 3.10 or
newer.

## What this covers

QAForge runs broad web application and browser based QA:

- Core user flows and journeys, end to end.
- UI checks: layout, responsiveness, keyboard access, visible focus, and
  labels.
- Form and input checks: validation, boundary and empty values, duplicate
  submissions, and type checks on fields.
- Saved state: does data persist correctly after a reload, an edit, or a
  rejected action.
- Error, loading, and empty states.
- Basic access and permission boundaries: can one user see another user's
  data, does logout actually end a session.
- Reachability and basic sensitive data exposure in what the browser and the
  application's own responses reveal.

## What this does not cover

QAForge does not claim penetration testing or detailed, technical
cybersecurity testing. It does not scan for vulnerabilities, attempt
exploitation, fuzz inputs at the network or protocol level, or test
infrastructure, source code, or dependencies. The access and session checks
above are ordinary QA and product security hygiene, not a security
assessment. If you need a penetration test or a compliance audit, hire someone
qualified to do that; this tool does not substitute for it and does not issue
any certification.

## The model

Most AI assisted testing uses one agent. One agent plans the tests, runs them,
and grades itself. QAForge runs two.

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

QAForge uses the ECC plugin as the engineering layer both agents work inside.
ECC is an open source agent harness by Affaan Mustafa. It provides planning,
test driven development, fresh context code review, and security scanning as
reusable workflows, so the two agents follow the same process instead of
improvising it each session.

Here is exactly how QAForge uses it:

- Planning before any change to the tooling, through ECC's planning workflow.
- `/code-review` for a fresh context review of every change to `tooling/`.
- `/security-scan`, which runs ECC's AgentShield, against the repository before
  any new product target is enabled.
- ECC's test driven workflow for future changes to `tooling/lab.py`.

ECC is a separate dependency. It is not bundled in this repository and you
install it yourself. Full credit and installation instructions:

- Repository: https://github.com/affaan-m/ECC
- Website: https://ecc.tools
- License: MIT

If you do not want to install ECC, QAForge still works. You lose the shared
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

Every session starts with the agent stating the goal and the session brief in
chat and waiting for your explicit confirmation before it runs anything. See
`AGENTS.md` and `templates/session-brief.md`. Provide the URL when you confirm
each session, and say whether it is staging or production. URLs start unset on
purpose. Configuration records who authorized the assessment and how, and it
expires after fourteen days.

```sh
python3 tooling/lab.py configure <slug> --env staging \
  --url https://YOUR-AUTHORIZED-HOST \
  --authorized-by "name and role" \
  --auth-method "how ownership was confirmed" \
  --build YOUR-BUILD

python3 tooling/lab.py preflight <slug> --env staging
python3 tooling/lab.py new-run <slug> --env staging --agent codex \
  --goal "<what is being tested and why, from the confirmed brief>" \
  --confirmed-by "<who confirmed the plan in chat>"
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

`new-run` refuses without `--goal` and `--confirmed-by`, and it appends a dated
line to the product's `coordination/session-log.md` automatically. That file,
together with the run's `manifest.json`, dated results, and `report.md`, is the
testing log: what was tested, why, who confirmed it, and when.

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

- Not penetration testing or detailed cybersecurity testing. See "What this
  does not cover" above.
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
