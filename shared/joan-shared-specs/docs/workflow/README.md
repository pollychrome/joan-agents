# Workflow & Orchestration

This section defines how agents coordinate and communicate within the Joan multi-agent system.

## Documents

| Document | Description |
|----------|-------------|
| [agentic-workflow.md](./agentic-workflow.md) | Core tag-driven workflow, column definitions, dispatcher priority, and role transitions |
| [als-spec.md](./als-spec.md) | ALS (Agentic Language Syntax) comment format for auditability and coordination |
| [worker-result-schema.md](./worker-result-schema.md) | Worker output format, `joan_actions`, and stage context handoffs |

## Key Concepts

- **Tags are triggers** - Comments are breadcrumbs only; tags drive all dispatch and state transitions
- **Single-pass workers** - Only the coordinator loops; all other agents complete in one pass
- **Column context** - Columns provide workflow stage context, but tags determine next actions

## Quick Reference

### Core Columns
`To Do` → `Analyse` → `Development` → `Review` → `Deploy` → `Done`

### Core Tags
- Intake: `Ready`, `Needs-Clarification`, `Clarification-Answered`
- Planning: `Plan-Pending-Approval`, `Plan-Approved`, `Plan-Rejected`, `Planned`
- Dev: `Claimed-Dev-N`, `Dev-Complete`, `Design-Complete`, `Test-Complete`
- Review: `Review-In-Progress`, `Review-Approved`, `Rework-Requested`, `Rework-Complete`
- Ops: `Ops-Ready`
- Errors: `Merge-Conflict`, `Implementation-Failed`, `Branch-Setup-Failed`
