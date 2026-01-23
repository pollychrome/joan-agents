# Joan Shared Specs

Canonical specifications and cross-repo references for agentic orchestration across the Joan ecosystem.

## Overview

This repository defines the shared contracts between:

| Repository | Role |
|------------|------|
| **Joan** | Backend API + Frontend application |
| **joan-agents** | Agent prompts + orchestration logic |
| **joan-mcp** | MCP server for Claude Code integration |

Consumed as a git submodule at `shared/joan-shared-specs` in each repo.

---

## What lives here

- Agentic workflow logic and tag-driven orchestration
- ALS comment syntax and action IDs
- Human Inbox triggers, actions, and audit trail
- System tags and agent enablement in Joan
- Frontend inbox touchpoints and expected behavior
- MCP tool/resource mappings to Joan API endpoints
- MCP feature specs (column management, etc.)

## Quick links

- [Docs index](./docs/README.md)

### Workflow
- [Agentic workflow](./docs/workflow/agentic-workflow.md)
- [ALS spec](./docs/workflow/als-spec.md)
- [Worker result schema](./docs/workflow/worker-result-schema.md)

### Human interface
- [Human inbox](./docs/human-interface/human-inbox.md)
- [Frontend inbox features](./docs/human-interface/frontend-inbox-features.md)

### Integration
- [System tags and enablement](./docs/integration/system-tags-and-enablement.md)
- [MCP API map](./docs/integration/mcp-api-map.md)
- [MCP column management](./docs/integration/mcp-column-management.md)

### Reference
- [Alignment gaps](./docs/reference/alignment-gaps.md)

---

## Documentation

### [Workflow & Orchestration](./docs/workflow/)
How agents coordinate and communicate within the multi-agent system.

| Document | Description |
|----------|-------------|
| [Agentic Workflow](./docs/workflow/agentic-workflow.md) | Tag-driven workflow, columns, dispatcher priority, role transitions |
| [ALS Spec](./docs/workflow/als-spec.md) | Agentic Language Syntax for audit-friendly comments |
| [Worker Result Schema](./docs/workflow/worker-result-schema.md) | Worker output format and context handoffs |

### [Human Interface](./docs/human-interface/)
How humans interact with the agentic system.

| Document | Description |
|----------|-------------|
| [Human Inbox](./docs/human-interface/human-inbox.md) | Unified queue: entry conditions, actions, tag mutations |
| [Frontend Features](./docs/human-interface/frontend-inbox-features.md) | Components, API usage, behavior highlights |

### [Integration](./docs/integration/)
Backend configuration and API mappings.

| Document | Description |
|----------|-------------|
| [System Tags](./docs/integration/system-tags-and-enablement.md) | Tag definitions, agent enablement endpoints |
| [MCP API Map](./docs/integration/mcp-api-map.md) | MCP tools/resources → Joan API endpoints |
| [MCP Column Management](./docs/integration/mcp-column-management.md) | Column CRUD spec |

### [Reference](./docs/reference/)
Status tracking and alignment.

| Document | Description |
|----------|-------------|
| [Alignment Gaps](./docs/reference/alignment-gaps.md) | Known inconsistencies and pending decisions |

---

## Quick Reference

### Core Workflow
```
To Do → Analyse → Development → Review → Deploy → Done
```

### Key Tags
| Category | Tags |
|----------|------|
| Intake | `Ready`, `Needs-Clarification`, `Clarification-Answered` |
| Planning | `Plan-Pending-Approval`, `Plan-Approved`, `Plan-Rejected`, `Planned` |
| Dev | `Claimed-Dev-N`, `Dev-Complete`, `Design-Complete`, `Test-Complete` |
| Review | `Review-In-Progress`, `Review-Approved`, `Rework-Requested`, `Rework-Complete` |
| Ops | `Ops-Ready` |
| Errors | `Merge-Conflict`, `Implementation-Failed`, `Branch-Setup-Failed` |

### Inbox Triggers
Tags that surface tasks in the human inbox:
- `Needs-Clarification` - Agent needs input
- `Plan-Pending-Approval` - Plan ready for review
- `Merge-Conflict` - Git conflict detected
- `Implementation-Failed` / `Branch-Setup-Failed` - Agent failure
- `Review-Approved` - Ready for merge approval

Note: Items with `Review-Approved` + `Ops-Ready` are excluded from the inbox.

---

## Update Flow

1. **Update specs here first** - All changes start in this repo
2. **Bump submodule** - Update the commit reference in `Joan`, `joan-agents`, and `joan-mcp`
3. **Implement changes** - Update code paths to match new specs

### Submodule Commands
```bash
# Update submodule to latest
git submodule update --remote shared/joan-shared-specs

# Check current commit
git -C shared/joan-shared-specs log -1 --oneline
```

---

## Contributing

When adding new specs:
1. Place in the appropriate category folder under `docs/`
2. Update the category's `README.md`
3. Update this root README's documentation table
4. Document any gaps or decisions needed in `docs/reference/alignment-gaps.md`
