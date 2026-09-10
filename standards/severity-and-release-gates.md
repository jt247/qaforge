# Severity and release gates
Critical: severe compromise such as broad unauthorized sensitive-data access or systemic account takeover.
High: significant access-control failure, important data loss, or essential journey failure without a viable workaround.
Medium: material defect with limited impact or a workable alternative.
Low: minor usability, presentation, or limited-impact defect.
Severity and business scheduling priority are distinct; record impact and rationale, not just a label.
Release requires all mandatory cases passed or applicability exclusions explicitly reviewed; no unresolved Critical/High findings; no blocked mandatory checks; current build identification; completed independent review of critical journeys and high-risk findings; and owner acceptance of any permitted remaining risk.
The CLI emits an assessment status, never automatic release approval. A green read-only smoke result establishes page reachability only. Agent agreement cannot waive evidence or mandatory checks. The product owner makes the final release decision.
