# Execution
State the goal and the session-brief fields in chat first and wait for the
user's explicit confirmation (see AGENTS.md and templates/session-brief.md).
Only then, from the repository root:
    python3 tooling/lab.py preflight _example --env staging
    python3 tooling/lab.py new-run _example --env staging --agent codex \
      --goal "confirm reachability and the primary create-note journey" \
      --confirmed-by "the name who confirmed the plan in chat"
    python3 tooling/lab.py smoke _example --run RUN_ID --agent codex
The smoke command checks HTTP reachability only. Browser journeys are executed
by an agent using cases/catalog.json; record evidence with the result command.
new-run appends a dated line to coordination/session-log.md automatically; that
file plus the run's manifest.json, results, and report.md are the testing log.
Add deterministic product-specific automation once real selectors, APIs, and
requirements are known.
