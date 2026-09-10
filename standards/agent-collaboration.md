# Agent collaboration
One run belongs to one agent. Claim/release through the CLI uses an atomic lock directory. Other agents create their own runs and fixtures. Do not share a browser profile or modify the same account concurrently.
The run manifest records owner and fixture namespace. The plan lists responsibility and overlap. Save independent observations before reviewing the other agent's conclusions to reduce anchoring.
Peer review records original run/case, reviewer run/case, reproduction evidence, agreement/disagreement, and disposition. Preserve unresolved disputes. Merge findings by root cause while retaining both evidence trails.
When interrupted, leave a handoff and release the claim. An abandoned claim is not automatically removed; confirm the previous process has stopped before using release with that agent identity.
File coordination supports Codex and Claude Code sessions but does not launch either runtime. Product conversations are entry points; these files hold durable state.
