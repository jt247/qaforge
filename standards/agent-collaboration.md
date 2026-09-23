# Agent collaboration
One run belongs to one agent. Claim/release through the CLI uses an atomic lock directory. Other agents create their own runs and fixtures. Do not share a browser profile or modify the same account concurrently.
The run manifest records owner and fixture namespace. The plan lists responsibility and overlap. Save independent observations before reviewing the other agent's conclusions to reduce anchoring.
Peer review records original run/case, reviewer run/case, reproduction evidence, agreement/disagreement, and disposition. Preserve unresolved disputes. Merge findings by root cause while retaining both evidence trails.

## Independent review protocol
1. Read the original run's `report.md`, `plan.md`, `brief.md`, and the product `findings/INDEX.md`. Save your own expectations before reading the original agent's notes in detail.
2. Create your own run on the same build with `new-run --agent <you> --review-of <original-run-id> --goal "independent review of <original-run-id>" --confirmed-by <name>`. Use your own test identities and a fresh browser profile.
3. Reproduce every High and Critical finding from the original run. Record each as a case result in your run with your own evidence.
4. Sample the original run's critical passes (at least the mandatory cases marked `risk: high`) and repeat them. Record each result with evidence.
5. Fill `peer-review.md` in your run: for every item, original run/case, your run/case, your evidence, agree/disagree, and disposition. Leave disagreements open; do not average them away.
6. Update `findings/INDEX.md` (confirm, reject, or dispute each finding) and `coordination/state.md`, then `close` your run.
When interrupted, leave a handoff and release the claim. An abandoned claim is not automatically removed; confirm the previous process has stopped before using release with that agent identity.
File coordination supports Codex and Claude Code sessions but does not launch either runtime. Product conversations are entry points; these files hold durable state.
