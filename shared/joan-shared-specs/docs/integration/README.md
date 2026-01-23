# Integration

This section covers backend configuration, API mappings, and system setup for agent enablement.

## Documents

| Document | Description |
|----------|-------------|
| [system-tags-and-enablement.md](./system-tags-and-enablement.md) | System tag definitions, agent enablement endpoints, and inbox coupling |
| [mcp-api-map.md](./mcp-api-map.md) | Complete mapping of MCP tools and resources to Joan API endpoints |
| [mcp-column-management.md](./mcp-column-management.md) | MCP column CRUD and reordering behaviors |

## Key Concepts

- **System tags** - Seeded tag definitions that power inbox triggers and agent behavior
- **Agent enablement** - Per-project toggle to activate agentic features
- **MCP bridge** - Translation layer between MCP protocol and Joan REST API

## Agent Enablement Endpoints

```
GET  /api/v1/system-tags                         # List system tag definitions
POST /api/v1/projects/:projectId/enable-agents   # Enable agents for project
POST /api/v1/projects/:projectId/disable-agents  # Disable agents for project
GET  /api/v1/projects/:projectId/agents-status   # Check agent status
```

## MCP Tool Categories

| Category | Tools |
|----------|-------|
| Projects | `list_projects`, `get_project`, `create_project`, `update_project` |
| Tasks | `list_tasks`, `get_task`, `create_task`, `update_task`, `complete_task` |
| Tags | `list_project_tags`, `add_tag_to_task`, `remove_tag_from_task`, `set_task_tags` |
| Comments | `list_task_comments`, `create_task_comment`, `update_task_comment` |
| Milestones | `list_milestones`, `create_milestone`, `link_tasks_to_milestone` |
