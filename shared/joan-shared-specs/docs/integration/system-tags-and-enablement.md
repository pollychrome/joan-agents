# System Tags and Agent Enablement (Joan)

## System tag definitions (seeded)
These live in `system_tags` and are linked to `project_tags.system_tag_id`.

| ID | Name | Color | Inbox Trigger | Action Type |
| --- | --- | --- | --- | --- |
| st-needs-clarification | Needs-Clarification | #EF4444 | true | clarification |
| st-plan-pending-approval | Plan-Pending-Approval | #F59E0B | true | approval |
| st-merge-conflict | Merge-Conflict | #EF4444 | true | error |
| st-implementation-failed | Implementation-Failed | #EF4444 | true | error |
| st-branch-setup-failed | Branch-Setup-Failed | #EF4444 | true | error |
| st-review-approved | Review-Approved | #22C55E | true | review |
| st-clarification-answered | Clarification-Answered | #22C55E | false | - |
| st-plan-approved | Plan-Approved | #22C55E | false | - |
| st-plan-rejected | Plan-Rejected | #EF4444 | false | - |
| st-rework-requested | Rework-Requested | #EF4444 | false | - |
| st-ready | Ready | #22C55E | false | - |
| st-planned | Planned | #22C55E | false | - |
| st-dev-complete | Dev-Complete | #22C55E | false | - |
| st-design-complete | Design-Complete | #22C55E | false | - |
| st-test-complete | Test-Complete | #22C55E | false | - |
| st-review-in-progress | Review-In-Progress | #F59E0B | false | - |
| st-rework-complete | Rework-Complete | #84CC16 | false | - |
| st-ops-ready | Ops-Ready | #14B8A6 | false | - |

Notes:
- Action Type is only set for inbox trigger tags.
- Ops merges only when both `Review-Approved` and `Ops-Ready` are present.
- Frontend inbox filters should fall back to a static trigger list if `/system-tags` fails.

## Agent enablement endpoints
- GET /api/v1/system-tags
  - Lists system tag definitions.
- POST /api/v1/projects/:projectId/enable-agents
  - Creates system-managed project tags and links them to system_tags.
  - Sets projects.agents_enabled = true.
- POST /api/v1/projects/:projectId/disable-agents
  - Optionally removes system-managed tags or unlinks system_tag_id.
  - Sets projects.agents_enabled = false.
- GET /api/v1/projects/:projectId/agents-status
  - Returns agents_enabled and count of system-managed tags.

## Inbox coupling
Inbox queries rely on `system_tags.is_inbox_trigger` and a tag-name fallback list.
Manual tags without a system_tag_id are included only if their names match the canonical inbox trigger list.

## Workflow tags not in system_tags
The agent workflow also uses tags not seeded as system tags:
- Claimed-Dev-N (created per dev count during initialization)

Notes:
- `enable-agents` creates project tags for every row in `system_tags`, but does not create `Claimed-Dev-N`.
- Initialize agent tags (e.g., `/agents:init`) to create `Claimed-Dev-N` based on configured dev count.

## Sources
- Joan/migrations/037_system_tags.sql
- Joan/workers/src/routes/system-tags.ts
- Joan/workers/src/services/inboxService.ts
