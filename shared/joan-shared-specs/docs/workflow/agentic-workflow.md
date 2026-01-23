# Agentic Workflow (Tag Driven)

## Principles
- Tags are the only triggers. Comments are breadcrumbs only (ALS).
- The coordinator is the only looping agent; all workers are single-pass.
- Columns provide context, tags drive dispatch.

## Core columns
- To Do
- Analyse
- Development
- Review
- Deploy
- Done

## Core tags
- Ready
- Needs-Clarification
- Clarification-Answered
- Plan-Pending-Approval
- Plan-Approved
- Plan-Rejected
- Planned
- Claimed-Dev-N
- Dev-Complete
- Design-Complete
- Test-Complete
- Review-In-Progress
- Review-Approved
- Rework-Requested
- Rework-Complete
- Merge-Conflict
- Implementation-Failed
- Branch-Setup-Failed
- Ops-Ready (explicit human merge gate)

## Dispatcher priority (coordinator)
1. Development + Merge-Conflict + unclaimed
2. Development + Rework-Requested + unclaimed (no Merge-Conflict)
3. Development + Planned + unclaimed (no Rework-Requested, no failure tags)
4. Analyse + Plan-Pending-Approval + Plan-Approved (finalize plan)
5. Analyse + Plan-Pending-Approval + Plan-Rejected (revise plan)
6. Analyse + Ready (create plan)
7. Analyse + Needs-Clarification + Clarification-Answered (re-check)
8. To Do + no Ready (evaluate)
9. Review + Dev-Complete + Design-Complete + Test-Complete + no Review-In-Progress + no Review-Approved + no Rework-Requested
10. Review + Rework-Complete + no Review-In-Progress + no Review-Approved + no Rework-Requested
11. Review + Review-Approved + Ops-Ready (Ops merge)
12. Review + Rework-Requested + no Review-Approved (Ops sends back)

## Role transitions (summary)

### BA
- To Do -> Analyse: add Ready OR add Needs-Clarification.
- Clarification request: add Needs-Clarification, ALS `clarify-request`.
- Human answer: add Clarification-Answered (keep Needs-Clarification).
- Clarification verified: remove Needs-Clarification + Clarification-Answered, add Ready, ALS `clarify-verified`.
- Clarification follow-up: remove Clarification-Answered, keep Needs-Clarification, ALS `clarify-followup`.

### Architect
- Plan ready: remove Ready, add Plan-Pending-Approval, ALS `plan-ready`.
- Plan approved (human): add Plan-Approved (keep Plan-Pending-Approval).
- Plan rejected (human): add Plan-Rejected, remove Plan-Approved if present (keep Plan-Pending-Approval).
- Plan approved (finalize): remove Plan-Pending-Approval + Plan-Approved, add Planned, ALS `plan-approved`.
- Plan rejected (revise): remove Plan-Rejected, update plan, keep Plan-Pending-Approval, ALS `plan-ready`.
- Clarification needed: add Needs-Clarification.

### Dev
- Claim: add Claimed-Dev-N and verify.
- Complete: remove Planned + claim + (Rework-Requested/Merge-Conflict if present); add Dev-Complete, Design-Complete, Test-Complete (+ Rework-Complete if rework); ALS `dev-complete` or `rework-complete`.
- Failures: add Implementation-Failed or Branch-Setup-Failed (human must clear).

### Reviewer
- Start: add Review-In-Progress.
- Approve: add Review-Approved, remove Review-In-Progress (and Rework-Complete), ALS `review-approve`.
- Rework: remove completion tags + Review-In-Progress/Review-Approved/Rework-Complete; add Rework-Requested + Planned; ALS `review-rework`.

### Ops
- Merge: Review + Review-Approved + Ops-Ready -> merge PR, move to Deploy, ALS `ops-merge`.
- Conflict: add Merge-Conflict + Rework-Requested + Planned, ALS `ops-conflict`.
- Rework: remove completion tags + claims; add Rework-Requested + Planned; ALS `ops-rework`.

Note: Human approve merge adds Ops-Ready and keeps Review-Approved; inbox hides items with both tags.

## Context Handoffs (v4.2)

Workers pass structured context between workflow stages using ALS `handoff` blocks.
This enables each worker to receive relevant context from the previous stage.

### Handoff Flow
```
BA evaluates → BA→Architect handoff
      ↓
Architect plans → reads BA context, produces Architect→Dev handoff
      ↓
Dev implements → reads Architect context, produces Dev→Reviewer handoff
      ↓
Reviewer reviews → reads Dev context
      ├── APPROVE: Reviewer→Ops handoff
      └── REJECT: Reviewer→Dev (rework) handoff
```

### Context Content by Stage

| Transition | Contains |
|------------|----------|
| BA → Architect | Requirements clarifications, user decisions |
| Architect → Dev | Architecture decisions, files to modify, dependencies |
| Dev → Reviewer | Implementation notes, files changed, warnings |
| Reviewer → Ops | Review summary, approval notes |
| Reviewer → Dev (rework) | Blockers with file:line, warnings, suggestions |

See [worker-result-schema.md](./worker-result-schema.md) for the full `StageContext` interface.

## PR/branch metadata
- Dev attaches PR and branch links as task resources and includes them in ALS comments.

## Sources
- joan-agents/.claude/agents/*.md
- docs/orchestration-spec.md
