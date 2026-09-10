# Execution
From the repository root:
    python3 tooling/lab.py preflight _example --env staging
    python3 tooling/lab.py new-run _example --env staging --agent codex
    python3 tooling/lab.py smoke _example --run RUN_ID --agent codex
The smoke command checks HTTP reachability only. Browser journeys are executed
by an agent using cases/catalog.json; record evidence with the result command.
Add deterministic product-specific automation once real selectors, APIs, and
requirements are known.
