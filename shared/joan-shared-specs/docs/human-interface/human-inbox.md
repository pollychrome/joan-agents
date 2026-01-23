# Human Inbox (Unified Queue)

## Goals
- One place for humans to answer questions and approve work.
- One-click actions that apply tags and add a breadcrumb comment.
- Clear reasons for why a task needs human input.

## Non-Goals
- Replace existing Kanban columns.
- Remove task comments or manual overrides.

## Entry Conditions
A task appears in the Human Inbox if it has any of:
- Needs-Clarification
- Plan-Pending-Approval
- Merge-Conflict
- Implementation-Failed
- Branch-Setup-Failed
- Review-Approved (explicit human merge gating)
- Stale (>= 4 hours since task last update time, configurable)

## Exclusion Conditions
A task is excluded from the Human Inbox if it has:
- `Review-Approved` AND `Ops-Ready` (approved for merge, waiting for Ops to complete)

## Reason mapping (tag -> reason)
- Needs-Clarification -> needs-clarification
- Plan-Pending-Approval -> plan-pending-approval
- Merge-Conflict -> merge-conflict
- Implementation-Failed -> implementation-failed
- Branch-Setup-Failed -> branch-setup-failed
- Review-Approved -> review-approved

## Actions and Tag Mutations
Each action applies tags and writes an ALS breadcrumb.
- Answer Clarification: add Clarification-Answered (keep Needs-Clarification)
- Approve Plan: add Plan-Approved (keep Plan-Pending-Approval)
- Reject Plan: add Plan-Rejected, remove Plan-Approved if present (keep Plan-Pending-Approval)
- Resolve Conflict: add Rework-Requested + Planned, remove Merge-Conflict
- Recover (Implementation-Failed): remove Implementation-Failed, ensure Planned exists
- Recover (Branch-Setup-Failed): remove Branch-Setup-Failed, ensure Planned exists
- Approve Merge: add Ops-Ready (keep Review-Approved)
- Request Rework (Review Approved): add Rework-Requested + Planned, remove Review-Approved (and Ops-Ready if present)

Note:
- Pending tags (`Needs-Clarification`, `Plan-Pending-Approval`) are cleared by BA/Architect, not by inbox actions.

## Comment Requirements
- Actions must write an ALS block first in the comment.
- tags.add/tags.remove must reflect the actual tag changes.
- Tags drive behavior, comments are breadcrumbs only.

## UX Touch Points
- Board view: Human Inbox column or dedicated inbox view.
- Task detail: banner showing required action and next tag.
- AI chat: action buttons that apply tags and add comments.
- Notifications: in-app and optional email/Slack for new inbox items.
- Bulk actions: approve multiple plans, mark clarifications answered.
- Activity feed: audit trail of human actions and tag changes.

## Context for Humans
Each inbox item should show:
- Reason badge (tag that caused the item)
- Last agent comment (summary only)
- Branch and PR link (if available)
- Age since last update
- Task priority

## Safety and Ownership
- Optional "assign to me" to avoid collisions.
- Confirm for destructive actions (reject plan, rework request).
- Undo within short window if supported.

## Acceptance Criteria
- Any human action completes in two clicks or less.
- Tag changes and breadcrumbs are always written together.
- Tasks leave the inbox when the owning agent clears the pending tag (e.g., Needs-Clarification or Plan-Pending-Approval).

## Sources
- Joan/workers/src/services/inboxService.ts
- Joan/frontend/src/services/inboxApi.ts
