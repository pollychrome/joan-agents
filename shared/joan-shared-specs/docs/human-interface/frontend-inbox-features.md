# Frontend Inbox Touchpoints (Joan)

## Primary screens and components
- InboxPage: list/group items, filters (reason, stale), bulk actions.
- InboxActionDialog: apply action + optional comment template.
- InboxActionBanner: shows on task drawer and deep link to inbox.
- InboxTaskCard, InboxActivityFeed: display items and audit history.
- Sidebar: inbox badge count; NotificationDrawer uses inbox notifications.
- KanbanBoard: filter "needs-human-input" based on system tag list (with fallback).

## API usage (frontend)
- GET /api/v1/inbox
- GET /api/v1/inbox/count
- GET /api/v1/inbox/projects/:projectId
- GET /api/v1/inbox/projects/:projectId/count
- GET /api/v1/inbox/task/:taskId
- POST /api/v1/inbox/:taskId/action
- POST /api/v1/inbox/bulk-action
- GET /api/v1/inbox/actions/:reason
- GET /api/v1/inbox/templates
- GET /api/v1/inbox/activities
- GET /api/v1/inbox/projects/:projectId/activities
- GET /api/v1/system-tags
- POST /api/v1/projects/:projectId/enable-agents
- POST /api/v1/projects/:projectId/disable-agents
- GET /api/v1/projects/:projectId/agents-status

## Behavior highlights
- Inbox count is polled for sidebar badge and notifications.
- Task drawer surfaces inbox banner when task has trigger tags.
- Kanban "needs human input" filter uses `/system-tags` and falls back to a static list if the API fails.

## Sources
- Joan/frontend/src/pages/InboxPage.tsx
- Joan/frontend/src/components/inbox/*
- Joan/frontend/src/stores/inboxStore.ts
- Joan/frontend/src/services/inboxApi.ts
- Joan/frontend/src/components/tasks/KanbanBoard.tsx
