# Human Interface

This section covers how humans interact with the agentic system through the inbox and frontend components.

## Documents

| Document | Description |
|----------|-------------|
| [human-inbox.md](./human-inbox.md) | Unified inbox queue: entry conditions, actions, tag mutations, and UX expectations |
| [frontend-inbox-features.md](./frontend-inbox-features.md) | Frontend components, API usage, and behavior highlights |

## Key Concepts

- **Unified queue** - All human-required actions surface in a single inbox
- **Tag-driven entry** - Tasks appear based on specific trigger tags
- **One-click actions** - UX goal is minimal friction (1-2 clicks max)

## Inbox Trigger Tags

| Tag | Reason | Typical Action |
|-----|--------|----------------|
| `Needs-Clarification` | Agent needs input | Answer question |
| `Plan-Pending-Approval` | Plan ready for review | Approve or reject |
| `Merge-Conflict` | Git conflict detected | Provide resolution guidance |
| `Implementation-Failed` | Agent failed | Request rework |
| `Branch-Setup-Failed` | Branch setup failed | Request rework |
| `Review-Approved` | Ready for merge approval | Approve merge (adds `Ops-Ready`) |

Notes:
- Items with `Review-Approved` + `Ops-Ready` are excluded from the inbox.

## Frontend Components

- `InboxPage` - Main list with filters and bulk actions
- `InboxActionDialog` - Action execution with templates
- `InboxActionBanner` - Task drawer integration
- Sidebar badge - Real-time count indicator
