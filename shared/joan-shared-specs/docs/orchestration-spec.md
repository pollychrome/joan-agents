# Orchestration Spec: Tag-Triggered Dispatch

This spec defines a tag-driven workflow with a single dispatcher coordinating single-pass agents.
Breadcrumb comments remain for humans, but tags are the only triggers for agent behavior.

---

## Goals

- Cut polling and comment scanning cost by using tag triggers.
- Centralize scheduling in one dispatcher.
- Preserve human-readable breadcrumbs in comments.
- Keep N-dev parallelism with isolated worktrees.

## Non-Goals

- Redesign Kanban columns or task model.
- Remove comments or reduce human visibility.
- Replace Git worktree flow.

---

## Architecture

### Dispatcher (New)

One loop polls once per interval, builds a priority queue, and dispatches workers in single-pass mode.

### Workers

- Business Analyst, Architect, Reviewer, Ops: single-pass only.
- Devs: assigned-task mode only, launched by dispatcher.

---

## Tag Triggers

### Required Tags (New)

- `Clarification-Answered`
- `Plan-Approved`
- `Plan-Rejected`
- `Review-Approved`
- `Rework-Complete`
- `Ops-Ready`

### Existing Tags (Kept)

`Ready`, `Needs-Clarification`, `Plan-Pending-Approval`, `Planned`, `Dev-Complete`,
`Design-Complete`, `Test-Complete`, `Review-In-Progress`, `Rework-Requested`,
`Merge-Conflict`, `Implementation-Failed`, `Branch-Setup-Failed`, `Claimed-Dev-N`

### Optional Tags

- (none)

---

## Trigger Rules (No Comment Parsing)

### BA

- Act on: `To Do` tasks without `Ready`.
- Re-check: `Analyse + Needs-Clarification + Clarification-Answered`.
- `Clarification-Answered` is additive; BA removes `Needs-Clarification` after verification.

### Architect

- Plan: `Analyse + Ready`.
- Finalize: `Analyse + Plan-Pending-Approval + Plan-Approved`.
- Revise: `Analyse + Plan-Pending-Approval + Plan-Rejected`.
- `Plan-Approved` / `Plan-Rejected` are additive; Architect removes `Plan-Pending-Approval` when finalizing.
- Reject Plan removes `Plan-Approved` if present to avoid conflicting tags.

### Dev

- New work: `Development + Planned + no Claimed-Dev-*`.
- Rework: `Development + Rework-Requested + no Claimed-Dev-*`.

### Reviewer

- Reviewable: `Review + Dev-Complete + Design-Complete + Test-Complete`
  and no `Review-In-Progress` and no `Rework-Requested`.
- Approval writes `Review-Approved`.

### Ops

- Merge only: `Review + Review-Approved + Ops-Ready`.
- `Ops-Ready` is set by a human "Approve Merge" action.
- Human approve merge keeps `Review-Approved`; inbox excludes `Review-Approved + Ops-Ready`.
- Rework path: `Review + Rework-Requested`.
- Track Deploy column.

---

## Context Handoffs (v4.2)

Workers pass structured context between workflow stages using ALS `handoff` intent blocks.
See `docs/workflow/worker-result-schema.md` for the full `StageContext` interface.

- Handoffs are persisted in Joan comments (durable across coordinator restarts)
- Context is per-transition (not cumulative) - each handoff contains only what the next stage needs
- Backward compatible - `previous_stage_context` is optional/null for legacy tasks

### Handoff Routing by Mode

| Mode | Source → Target |
|------|-----------------|
| `plan` | BA → Architect |
| `implement` | Architect → Dev |
| `rework` | Reviewer → Dev |
| `conflict` | Reviewer → Dev |
| `review` | Dev → Reviewer |
| `merge` | Reviewer → Ops |

## Breadcrumb Comments (ALS Only)

All state transitions must write an ALS block. Comments are never triggers.
See `docs/workflow/als-spec.md`.

### Standard ALS Actions

Use these ALS `action` values for breadcrumbs:
- `clarify-request`, `clarify-verified`, `clarify-followup`
- `plan-ready`, `plan-approved`, `plan-rejected`
- `dev-start`, `dev-complete`, `rework-complete`, `conflict-resolved`, `dev-failure`
- `review-start`, `review-approve`, `review-rework`, `review-conflict`
- `ops-merge`, `ops-rework`, `ops-conflict`, `ops-deploy`
- `context-handoff` (v4.2 - stage context handoffs)
- Human inbox: `clarify-answered`, `plan-approved`, `plan-rejected`, `conflict-resolved`, `merge-approved`, `rework-requested`

---

## Dispatcher Flow

1. Poll once per interval.
2. Build priority queue:
   - Rework / merge conflicts
   - New planned work
   - Reviews
   - Deploy tracking
3. Dispatch single-pass workers with `--task-id`.
4. Track in-flight tasks to avoid duplicate dispatches.
5. Cache tag IDs once per run.

---

## Task Metadata

- Store PR link and branch as task resources.
- Breadcrumb comment may include the same link for humans.

---

## Error Handling

- `Implementation-Failed` or `Branch-Setup-Failed`: stop dispatching; route to Human Inbox.
- `Merge-Conflict`: Ops sends back to Development with `Rework-Requested + Planned`.

---

## Acceptance Criteria

- Only the dispatcher polls in a loop.
- No agent uses comments for triggers.
- Every transition posts a breadcrumb comment.
- End-to-end flow works using tags only.

---

## Migration

1. Create new tags.
2. Update docs and templates to use tags, not `@` triggers.
3. Keep comment breadcrumbs for humans.
