# Joan MCP: Column Management Feature Spec

**Status:** Proposed
**Author:** Agent System
**Date:** 2026-01-17
**Priority:** High (blocks `/agents:init` auto-setup)

## Summary

Add CRUD operations for Kanban columns to the Joan MCP server. Currently, only `list_columns` exists. This spec proposes `create_column`, `update_column`, `delete_column`, and `reorder_columns` to enable programmatic project setup for the multi-agent workflow.

## Motivation

The Joan multi-agent system requires a specific column structure:

```
To Do → Analyse → Development → Review → Deploy → Done
```

Currently, users must manually create these columns in the Joan UI before agents can operate. Adding column management to MCP enables:

1. **Automated project setup** via `/agents:init`
2. **Validation** that required columns exist
3. **Self-healing** if columns are accidentally deleted
4. **Template-based project creation** for teams

## Existing Tool

```typescript
// Currently available
mcp__joan__list_columns(project_id: string): Column[]

interface Column {
  id: string;           // UUID
  name: string;         // Display name
  position: number;     // Order (0-indexed)
  default_status: string; // Status assigned to tasks in this column
  task_count?: number;  // Number of tasks in column
}
```

## Proposed Tools

### 1. create_column

Create a new Kanban column in a project.

```typescript
mcp__joan__create_column(params: {
  project_id: string;      // Required: Project UUID
  name: string;            // Required: Column display name (1-50 chars)
  position?: number;       // Optional: Insert position (default: append to end)
  default_status?: string; // Optional: Status for tasks placed in this column
  color?: string;          // Optional: Hex color code (e.g., "#3B82F6")
}): Column

// Example
mcp__joan__create_column({
  project_id: "abc-123",
  name: "Analyse",
  position: 1,
  default_status: "analyse",
  color: "#8B5CF6"
})
```

**Behavior:**
- If `position` is specified, existing columns at that position and after shift right
- If `position` is omitted, column is appended at the end
- Column names must be unique within a project (case-insensitive)
- Returns the created column with its assigned UUID

**Errors:**
- `400` - Invalid parameters (empty name, invalid color format)
- `404` - Project not found
- `409` - Column with that name already exists

### 2. update_column

Update an existing column's properties.

```typescript
mcp__joan__update_column(params: {
  project_id: string;      // Required: Project UUID
  column_id: string;       // Required: Column UUID
  name?: string;           // Optional: New display name
  default_status?: string; // Optional: New default status
  color?: string;          // Optional: New color
}): Column

// Example
mcp__joan__update_column({
  project_id: "abc-123",
  column_id: "col-456",
  name: "Analysis",
  color: "#6366F1"
})
```

**Behavior:**
- Only provided fields are updated
- Name uniqueness is enforced on update
- Does not change position (use `reorder_columns` for that)

**Errors:**
- `400` - Invalid parameters
- `404` - Project or column not found
- `409` - New name conflicts with existing column

### 3. delete_column

Delete a column from a project.

```typescript
mcp__joan__delete_column(params: {
  project_id: string;      // Required: Project UUID
  column_id: string;       // Required: Column UUID
  move_tasks_to?: string;  // Optional: Column UUID to move tasks to
}): { deleted: true; tasks_moved?: number }

// Example
mcp__joan__delete_column({
  project_id: "abc-123",
  column_id: "col-456",
  move_tasks_to: "col-789"
})
```

**Behavior:**
- If `move_tasks_to` is specified, all tasks in the deleted column move there
- If `move_tasks_to` is omitted and column has tasks, operation fails
- Remaining columns automatically reposition to close the gap

**Errors:**
- `400` - Column has tasks and no `move_tasks_to` specified
- `403` - Cannot delete reserved workflow column (see Reserved Workflow Columns)
- `404` - Project, column, or target column not found
- `409` - Cannot delete the last column in a project

### 4. reorder_columns

Reorder columns within a project.

```typescript
mcp__joan__reorder_columns(params: {
  project_id: string;      // Required: Project UUID
  column_order: string[];  // Required: Array of column UUIDs in desired order
}): Column[]

// Example - move "Review" before "Development"
mcp__joan__reorder_columns({
  project_id: "abc-123",
  column_order: ["col-1", "col-2", "col-4", "col-3", "col-5", "col-6"]
})
```

**Behavior:**
- All existing column UUIDs must be included in `column_order`
- Returns all columns with updated positions

**Errors:**
- `400` - Missing columns or unknown UUIDs in `column_order`
- `404` - Project not found

## JSON Schema Definitions

### Column Schema

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "properties": {
    "id": {
      "type": "string",
      "format": "uuid",
      "description": "Column UUID"
    },
    "name": {
      "type": "string",
      "minLength": 1,
      "maxLength": 50,
      "description": "Column display name"
    },
    "position": {
      "type": "integer",
      "minimum": 0,
      "description": "Column order (0-indexed)"
    },
    "default_status": {
      "type": "string",
      "description": "Status assigned to tasks placed in this column"
    },
    "color": {
      "type": "string",
      "pattern": "^#[0-9A-Fa-f]{6}$",
      "description": "Hex color code"
    },
    "task_count": {
      "type": "integer",
      "minimum": 0,
      "description": "Number of tasks currently in column"
    },
    "created_at": {
      "type": "string",
      "format": "date-time"
    },
    "updated_at": {
      "type": "string",
      "format": "date-time"
    }
  },
  "required": ["id", "name", "position"]
}
```

### create_column Parameters Schema

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "properties": {
    "project_id": {
      "type": "string",
      "format": "uuid",
      "description": "Project ID to create column in"
    },
    "name": {
      "type": "string",
      "minLength": 1,
      "maxLength": 50,
      "description": "Column display name"
    },
    "position": {
      "type": "integer",
      "minimum": 0,
      "description": "Insert position (0-indexed). Omit to append."
    },
    "default_status": {
      "type": "string",
      "description": "Status for tasks placed in this column"
    },
    "color": {
      "type": "string",
      "pattern": "^#[0-9A-Fa-f]{6}$",
      "description": "Hex color code"
    }
  },
  "required": ["project_id", "name"]
}
```

## Usage Example: Agent Init Setup

```typescript
async function setupProjectColumns(projectId: string) {
  const requiredColumns = [
    { name: "To Do", status: "todo", color: "#6B7280" },
    { name: "Analyse", status: "analyse", color: "#8B5CF6" },
    { name: "Development", status: "in_progress", color: "#3B82F6" },
    { name: "Review", status: "review", color: "#F59E0B" },
    { name: "Deploy", status: "deploy", color: "#10B981" },
    { name: "Done", status: "done", color: "#22C55E" }
  ];

  // Get existing columns
  const existing = await mcp__joan__list_columns({ project_id: projectId });
  const existingNames = new Set(existing.map(c => c.name.toLowerCase()));

  // Create missing columns in order
  for (let i = 0; i < requiredColumns.length; i++) {
    const col = requiredColumns[i];
    if (!existingNames.has(col.name.toLowerCase())) {
      await mcp__joan__create_column({
        project_id: projectId,
        name: col.name,
        position: i,
        default_status: col.status,
        color: col.color
      });
    }
  }

  // Reorder to match workflow
  const finalColumns = await mcp__joan__list_columns({ project_id: projectId });
  const columnMap = new Map(finalColumns.map(c => [c.name.toLowerCase(), c.id]));

  const correctOrder = requiredColumns
    .map(r => columnMap.get(r.name.toLowerCase()))
    .filter(Boolean);

  await mcp__joan__reorder_columns({
    project_id: projectId,
    column_order: correctOrder
  });
}
```

## Reserved Workflow Columns

The following column names are **reserved** for the agent workflow and cannot be deleted (though they can be renamed or reordered):

| Reserved Name | Purpose |
|---------------|---------|
| `To Do` | Entry point for new tasks |
| `Analyse` | Requirements analysis and planning |
| `Development` | Active implementation |
| `Review` | Code review stage |
| `Deploy` | Approved for deployment |
| `Done` | Completed tasks |

**Behavior:**
- Attempting to delete a reserved column returns `403 Forbidden`
- Reserved columns can be renamed (e.g., "To Do" → "Backlog")
- If renamed, the column retains its reserved status via internal flag
- Reserved status is based on column ID, not name

**Errors for delete_column:**
- `403` - Cannot delete reserved workflow column

## Security Considerations

1. **Authorization**: Only project owners/admins can modify columns
2. **Audit trail**: Column changes should be logged
3. **Rate limiting**: Prevent bulk column manipulation abuse
4. **Validation**: Sanitize column names to prevent XSS in UI

## Migration Path

For existing projects:
- No database schema changes required (columns already exist)
- New MCP tools expose existing functionality
- No breaking changes to `list_columns`

## Implementation Priority

1. `create_column` - Essential for auto-setup
2. `reorder_columns` - Required to enforce correct order
3. `update_column` - Nice to have for maintenance
4. `delete_column` - Lower priority, manual cleanup is acceptable

## Acceptance Criteria

- [ ] `create_column` creates column with specified properties
- [ ] `create_column` with `position` shifts existing columns
- [ ] `update_column` updates only specified fields
- [ ] `delete_column` moves tasks when `move_tasks_to` provided
- [ ] `delete_column` fails if column has tasks and no target
- [ ] `delete_column` returns 403 for reserved workflow columns
- [ ] Reserved columns can be renamed but not deleted
- [ ] `reorder_columns` updates all column positions atomically
- [ ] All tools return proper error codes and messages
- [ ] `/agents:init` can set up a project with correct columns
