# Testing standard — 1.0
Every assessment covers product requirements, QA engineering, and applicable security controls. This standard applies to all products; product guides refine it.
## Mandatory workflow
Read requirements → check scope and readiness → create and claim run → verify fixtures → smoke → execute risk-prioritized cases → independent review → report → retest fixes → cleanup and handoff.
Pin the build identifier if available. If unavailable, record unknown and limit release conclusions. Record deployment changes; split results by build. Two runs do not guarantee safety.
## Traceability
Each case has an ID, source requirement (or explicitly marked assumption), actor, preconditions, steps, expected behavior, risk, and evidence requirements. Track requirement → case → result → finding → retest. Do not invent expected behavior from implementation alone.
## Coverage
Assess core journeys; negative and boundary inputs; persisted state and downstream effects; roles and object ownership; organization isolation; session lifecycle; accessibility and responsive behavior; error/empty/loading states; integrations; privacy; applicable performance and recovery behavior. Source, dependency, infrastructure, and log checks require the corresponding access.
## Results
Allowed: passed, failed, blocked, not-run, not-applicable. A pass requires evidence. Not applicable requires rationale. Blocked and not-run never count as passed. Keep numerator and denominator visible; avoid a single reassuring score.
## Regression
Confirmed defects receive stable finding IDs and regression cases where useful. Retest the original reproduction and adjacent behavior on a recorded build. Do not erase the original failure.
## Standards mapping
Security requirements target applicable OWASP ASVS 5.0.0 controls, with WSTG v4.2 testing methods. Record exact control IDs only after consulting the source; do not claim full coverage from a short checklist. Accessibility target: WCAG 2.2 AA where applicable; automated checks alone are insufficient.
