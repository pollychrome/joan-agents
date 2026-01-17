# Human Inbox Spec: Unified Human Input Queue

This spec defines a single Human Inbox queue for all human-required actions.
Tags drive agent behavior; comments provide breadcrumbs for humans.

---

## Goals

- One place for humans to answer questions and approve work.
- One-click actions that apply tags and add a breadcrumb comment.
- Clear reasons for why a task needs human input.

## Non-Goals

- Replace existing Kanban columns.
- Remove task comments or manual overrides.

---

## Entry Conditions

A task appears in Human Inbox if it has any of:

- `Needs-Clarification`
- `Plan-Pending-Approval`
- `Merge-Conflict`
- `Implementation-Failed`
- `Worktree-Failed`
- Stale state older than threshold (configurable)

Optional:

- `Review-Approved` (if you want explicit human merge gating)

---

## Human Actions (One Click)

Each action applies tags and posts a comment template.

| Action | Tags Applied | Outcome |
| --- | --- | --- |
| Clarification Answered | `Clarification-Answered` | BA re-checks |
| Approve Plan | `Plan-Approved` | Architect finalizes plan |
| Reject Plan | `Plan-Rejected` | Architect returns to clarification |
| Request Rework | `Rework-Requested`, `Planned` | Dev picks up rework |
| Resolve Conflict Manually | `Rework-Requested`, `Planned` | Dev resolves conflicts |

---

## UX Touch Points

- Board view: Human Inbox column or dedicated inbox view.
- Task detail: banner showing required action and next tag.
- AI chat: action buttons that apply tags and add comments.
- Notifications: in-app and optional email/Slack for new inbox items.
- Bulk actions: approve multiple plans, mark clarifications answered.
- Activity feed: audit trail of human actions and tag changes.

---

## Breadcrumb Comment Templates (ALS)

Short and consistent ALS blocks, added automatically by the UI.
See `docs/09-als-spec.md` for format details.

---

## Context for Humans

Each inbox item should show:

- Reason badge (tag that caused the item)
- Last agent comment (summary only)
- Branch and PR link (if available)
- Age since last update
- Task priority

---

## Safety and Ownership

- Optional "assign to me" to avoid collisions.
- Confirm for destructive actions (reject plan, rework request).
- Undo within short window if supported.

---

## Acceptance Criteria

- Any human action completes in two clicks or less.
- Tag changes and breadcrumbs are always written together.
- Tasks leave the inbox immediately after required tag change.
