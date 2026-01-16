# Joan MCP Server: Status Filter Consistency Fix

## Problem Statement

The `list_tasks` MCP tool has inconsistent status filtering behavior that prevents agents from finding tasks by their actual status values.

### Current Behavior

| Task's Actual Status | `list_tasks` Filter Required | Display in List |
|---------------------|------------------------------|-----------------|
| `"todo"` | `"pending"` | `[pending]` |
| `"in_progress"` | `"in_progress"` | `[in_progress]` |

### Expected Behavior

| Task's Actual Status | `list_tasks` Filter | Display in List |
|---------------------|---------------------|-----------------|
| `"todo"` | `"todo"` | `[todo]` |
| `"in_progress"` | `"in_progress"` | `[in_progress]` |
| `"done"` | `"done"` | `[done]` |

## Evidence

```bash
# Task detail shows actual status
mcp__joan__get_task(task_id: "82b25376-...")
# Returns: "status": "todo"

# Filter by actual status returns nothing
mcp__joan__list_tasks(project_id: "...", status: "todo")
# Returns: "No tasks found"

# Filter by mapped value works
mcp__joan__list_tasks(project_id: "...", status: "pending")
# Returns: 20 tasks (all showing [pending])
```

## Scope

### In Scope
- Fix `list_tasks` status filter to match actual task status values
- Ensure display format matches actual status
- Maintain backward compatibility if possible

### Out of Scope
- Changes to task status values themselves
- Column/status relationship changes
- Other MCP tools

## Technical Requirements

### 1. Status Filter Matching

The `status` parameter in `list_tasks` must filter against the actual `status` field stored on tasks.

```typescript
// Current (broken)
if (params.status === "pending") {
  // matches tasks where task.status === "todo" (wrong mapping)
}

// Fixed
if (params.status) {
  // filter where task.status === params.status (direct match)
}
```

### 2. Display Consistency

The status displayed in list output should match the actual status value:

```
# Current output
- #18 Phase 4b: NVD API Client (ID: ...) [pending] (high)

# Expected output
- #18 Phase 4b: NVD API Client (ID: ...) [todo] (high)
```

### 3. Valid Status Values

Based on Joan's task model, supported status values are:
- `todo` - Task not started
- `in_progress` - Task actively being worked
- `done` - Task completed
- `cancelled` - Task cancelled (if supported)

Projects may define custom statuses. The filter should work with any status value.

## Implementation Notes

### Location
The fix is likely in one of these areas:
1. MCP tool handler for `list_tasks`
2. Status mapping/transformation layer
3. Database query builder

### Backward Compatibility

Consider whether existing integrations rely on filtering by `"pending"`. Options:

**Option A: Breaking change (recommended)**
- Remove the mapping entirely
- Update documentation
- Agents update their filter values

**Option B: Accept both values**
- `"pending"` maps to `"todo"` for backward compatibility
- `"todo"` also works (new behavior)
- Log deprecation warning for `"pending"`

## Acceptance Criteria

1. [ ] `list_tasks(status: "todo")` returns tasks where `task.status === "todo"`
2. [ ] `list_tasks(status: "in_progress")` returns tasks where `task.status === "in_progress"`
3. [ ] `list_tasks(status: "done")` returns tasks where `task.status === "done"`
4. [ ] List output displays actual status value (e.g., `[todo]` not `[pending]`)
5. [ ] Custom project statuses filter correctly
6. [ ] No filter returns all tasks (unchanged)

## Testing

### Manual Test Cases

```bash
# 1. Create task with status "todo" (default)
mcp__joan__create_task(title: "Test task", project_id: "...")

# 2. Verify filter works
mcp__joan__list_tasks(project_id: "...", status: "todo")
# Should return the test task

# 3. Update to in_progress
mcp__joan__update_task(task_id: "...", status: "in_progress")

# 4. Verify filter updates
mcp__joan__list_tasks(project_id: "...", status: "in_progress")
# Should return the test task

mcp__joan__list_tasks(project_id: "...", status: "todo")
# Should NOT return the test task
```

## Impact

### Affected Consumers
- BA agent (`/agents:ba`) - currently broken due to this bug
- Any other agent or integration filtering by status

### Required Updates After Fix
- BA agent: Change filter from `"pending"` workaround back to `"todo"` (if workaround was applied)
- Documentation: Update MCP tool docs with correct status values

## Priority

**High** - This bug prevents the BA agent from discovering tasks in the To Do column, blocking the entire agent pipeline.
