# ALS v0.1 Spec (Agentic Language Syntax)

ALS defines a compact, machine-readable comment block for all human and agent breadcrumbs.
Tags remain the only triggers; ALS is for auditability and human coordination.

---

## Format

An ALS block is the first content in a comment:

```
ALS/1
actor: human|ba|architect|dev|reviewer|ops|coordinator
intent: request|response|decision|status|handoff|failure
action: <action-id>
tags.add: [TagA, TagB]
tags.remove: [TagC]
summary: One-line outcome (<= 120 chars).
details:
- Optional bullets with instructions or evidence.
links:
- pr: https://...
- plan: plan-123.md
```

Rules:
- ALS block must come first in the comment.
- `tags.add`/`tags.remove` must reflect actual tag changes.
- Comments never trigger behavior; tags do.

---

## Action IDs

### BA
- `clarify-request`
- `clarify-verified`
- `clarify-followup`

### Architect
- `plan-ready`
- `plan-approved`

### Dev
- `dev-start`
- `dev-complete`
- `rework-start`
- `rework-complete`
- `conflict-resolved`
- `dev-failure`

### Reviewer
- `review-start`
- `review-approve`
- `review-rework`
- `review-conflict`

### Ops
- `ops-merge`
- `ops-rework`
- `ops-conflict`
- `ops-deploy`

---

## Examples

### Plan Ready (Architect)
```
ALS/1
actor: architect
intent: request
action: plan-ready
tags.add: [Plan-Pending-Approval]
tags.remove: [Ready]
summary: Plan attached; add Plan-Approved to proceed.
links:
- plan: plan-123.md
```

### Plan Approved (Human)
```
ALS/1
actor: human
intent: decision
action: plan-approved
tags.add: [Plan-Approved]
summary: Approved plan for implementation.
```

### Review Rework (Reviewer)
```
ALS/1
actor: reviewer
intent: decision
action: review-rework
tags.add: [Rework-Requested, Planned]
tags.remove: [Review-In-Progress, Review-Approved]
summary: Fix null check and add unit test.
details:
- src/foo.ts:42 add guard on user.profile
- tests: add unit coverage for empty profile
```

### Rework Complete (Dev)
```
ALS/1
actor: dev
intent: response
action: rework-complete
tags.add: [Rework-Complete]
tags.remove: [Rework-Requested]
summary: Addressed null guard + added unit test.
links:
- pr: https://github.com/org/repo/pull/123
```

---

## Human Inbox Integration

Human Inbox actions should add tags and post an ALS block in one click.
ALS blocks are the canonical breadcrumb format for manual intervention.
