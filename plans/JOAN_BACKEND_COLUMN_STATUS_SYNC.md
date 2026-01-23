# Joan Backend: Column-Status Synchronization Fixes

**Date:** 2026-01-22
**Priority:** CRITICAL
**Impact:** Prevents agent workflow failures due to data inconsistency

## Problem Statement

Tasks in Joan can have `status="done"` while `column_id` points to non-terminal columns (e.g., "To Do", "In Progress"). This breaks:
1. Agent workflows that filter by column + status
2. Coordinator queue building logic
3. User expectations (UI shows completed tasks in active columns)

### Root Cause

No database constraint or API validation enforces consistency between:
- `column_id` (kanban position)
- `status` (task state)
- `completed_at` (completion timestamp)

These fields drift independently through:
- Manual UI drag-drop operations
- API bulk updates without sync
- Failed column inference in MCP layer

## Proposed Solution

### Phase 1: Data Cleanup (Immediate)

**Goal:** Fix existing broken tasks

**Script:** `scripts/fix-column-status-desync.sql`

```sql
-- Find all tasks with status="done" outside Done column
WITH done_column AS (
  SELECT id FROM columns
  WHERE name IN ('Done', 'Completed', 'Finished')
  LIMIT 1
),
broken_tasks AS (
  SELECT t.id, t.task_number, t.title, t.status, t.column_id, c.name as current_column
  FROM tasks t
  JOIN columns c ON t.column_id = c.id
  WHERE t.status = 'done'
    AND t.column_id != (SELECT id FROM done_column)
)
-- Move broken tasks to Done column
UPDATE tasks
SET column_id = (SELECT id FROM done_column)
WHERE id IN (SELECT id FROM broken_tasks);

-- Log results
SELECT
  COUNT(*) as fixed_count,
  STRING_AGG(CONCAT('#', task_number, ' ', title), ', ') as fixed_tasks
FROM broken_tasks;
```

**Verification:**
```sql
-- Should return 0 rows after fix
SELECT t.id, t.task_number, c.name as column_name, t.status
FROM tasks t
JOIN columns c ON t.column_id = c.id
WHERE t.status = 'done' AND c.name NOT IN ('Done', 'Completed', 'Finished');
```

### Phase 2: Database Constraint (Short-term)

**Goal:** Prevent future desynchronization at database level

**Migration:** `migrations/YYYYMMDD_add_status_column_constraint.sql`

```sql
-- Step 1: Create helper function
CREATE OR REPLACE FUNCTION is_status_column_consistent(
  p_status TEXT,
  p_column_id UUID
) RETURNS BOOLEAN AS $$
DECLARE
  v_column_name TEXT;
BEGIN
  -- Get column name
  SELECT name INTO v_column_name
  FROM columns
  WHERE id = p_column_id;

  -- Check consistency rules
  IF p_status = 'done' THEN
    -- Completed tasks must be in Done column
    RETURN v_column_name IN ('Done', 'Completed', 'Finished');
  ELSIF p_status = 'cancelled' THEN
    -- Cancelled tasks must be in Done or Cancelled column
    RETURN v_column_name IN ('Done', 'Completed', 'Finished', 'Cancelled');
  ELSE
    -- Active tasks cannot be in Done column
    RETURN v_column_name NOT IN ('Done', 'Completed', 'Finished');
  END IF;
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- Step 2: Add check constraint
ALTER TABLE tasks
ADD CONSTRAINT check_status_column_consistency
CHECK (is_status_column_consistent(status, column_id));

-- Step 3: Create index for performance
CREATE INDEX idx_tasks_status_column ON tasks(status, column_id);
```

**Rollback Plan:**
```sql
ALTER TABLE tasks DROP CONSTRAINT IF EXISTS check_status_column_consistency;
DROP FUNCTION IF EXISTS is_status_column_consistent(TEXT, UUID);
DROP INDEX IF EXISTS idx_tasks_status_column;
```

### Phase 3: API Validation (Short-term)

**Goal:** Reject invalid updates at API boundary

**File:** `src/api/tasks/update.ts` (or equivalent)

```typescript
// Add validation middleware
async function validateStatusColumnConsistency(
  taskId: string,
  updates: Partial<TaskUpdateInput>
): Promise<void> {
  const task = await db.tasks.findUnique({ where: { id: taskId } });
  const newStatus = updates.status ?? task.status;
  const newColumnId = updates.column_id ?? task.column_id;

  const column = await db.columns.findUnique({ where: { id: newColumnId } });

  // Rule 1: Completed tasks must be in Done column
  if (newStatus === 'done' && !['Done', 'Completed', 'Finished'].includes(column.name)) {
    throw new ValidationError(
      `Cannot set status='done' for task in column '${column.name}'. ` +
      `Task must be in Done column.`
    );
  }

  // Rule 2: Active tasks cannot be in Done column
  if (newStatus !== 'done' && ['Done', 'Completed', 'Finished'].includes(column.name)) {
    throw new ValidationError(
      `Cannot set status='${newStatus}' for task in Done column. ` +
      `Move task to active column first.`
    );
  }
}

// Apply to all update endpoints
export async function updateTask(taskId: string, updates: TaskUpdateInput) {
  await validateStatusColumnConsistency(taskId, updates);
  return db.tasks.update({ where: { id: taskId }, data: updates });
}
```

### Phase 4: Automatic Sync (Medium-term)

**Goal:** Auto-sync status when column changes (and vice versa)

**File:** `src/api/tasks/sync.ts`

```typescript
export async function syncTaskFields(
  taskId: string,
  updates: Partial<TaskUpdateInput>
): Promise<TaskUpdateInput> {
  const task = await db.tasks.findUnique({ where: { id: taskId } });
  const enrichedUpdates = { ...updates };

  // Sync 1: Column changed to Done → set status=done
  if (updates.column_id) {
    const newColumn = await db.columns.findUnique({ where: { id: updates.column_id } });
    if (['Done', 'Completed', 'Finished'].includes(newColumn.name)) {
      enrichedUpdates.status = 'done';
      enrichedUpdates.completed_at = new Date();
    }
  }

  // Sync 2: Status changed to done → move to Done column
  if (updates.status === 'done' && !updates.column_id) {
    const project = await db.projects.findUnique({ where: { id: task.project_id } });
    const doneColumn = await db.columns.findFirst({
      where: {
        project_id: project.id,
        name: { in: ['Done', 'Completed', 'Finished'] }
      }
    });
    if (doneColumn) {
      enrichedUpdates.column_id = doneColumn.id;
    }
  }

  // Sync 3: Status changed from done → clear completed_at
  if (updates.status && updates.status !== 'done' && task.status === 'done') {
    enrichedUpdates.completed_at = null;
  }

  return enrichedUpdates;
}
```

## Testing Plan

### Unit Tests
```typescript
describe('Task Status-Column Sync', () => {
  test('moving to Done column sets status=done', async () => {
    const task = await createTask({ status: 'in_progress' });
    await updateTask(task.id, { column_id: doneColumnId });
    const updated = await getTask(task.id);
    expect(updated.status).toBe('done');
    expect(updated.completed_at).toBeTruthy();
  });

  test('setting status=done moves to Done column', async () => {
    const task = await createTask({ column_id: todoColumnId });
    await updateTask(task.id, { status: 'done' });
    const updated = await getTask(task.id);
    const column = await getColumn(updated.column_id);
    expect(column.name).toBe('Done');
  });

  test('rejects status=done in To Do column', async () => {
    const task = await createTask({ column_id: todoColumnId });
    await expect(
      updateTask(task.id, { status: 'done' })
    ).rejects.toThrow('Cannot set status=\'done\' for task in column \'To Do\'');
  });
});
```

### Integration Tests
```typescript
describe('Coordinator Workflow', () => {
  test('completed tasks are in Done column', async () => {
    // Simulate full workflow
    const task = await createTask({ title: 'Test Task' });
    await moveTask(task.id, developmentColumnId);
    await completeTask(task.id);

    // Verify final state
    const final = await getTask(task.id);
    const column = await getColumn(final.column_id);
    expect(column.name).toBe('Done');
    expect(final.status).toBe('done');
    expect(final.completed_at).toBeTruthy();
  });
});
```

## Rollout Plan

### Week 1: Data Cleanup
- [ ] Run SQL script on staging database
- [ ] Verify no broken tasks remain
- [ ] Run on production during maintenance window
- [ ] Monitor for new desync cases

### Week 2: Database Constraint
- [ ] Deploy migration to staging
- [ ] Run integration tests
- [ ] Deploy to production
- [ ] Monitor for constraint violations (indicates MCP bugs)

### Week 3: API Validation
- [ ] Deploy validation middleware to staging
- [ ] Test with real agent workflows
- [ ] Deploy to production
- [ ] Update API documentation

### Week 4: Auto-Sync
- [ ] Deploy sync logic to staging
- [ ] A/B test with subset of users
- [ ] Deploy to production
- [ ] Deprecate sync_column flag in MCP

## Success Metrics

- **Zero tasks** with status="done" outside Done column
- **Zero database constraint violations** in 30 days
- **Agent workflow success rate** increases from 85% to 99%
- **Coordinator idle polls** decrease (tasks no longer stuck)

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| Database constraint breaks existing workflows | Deploy with constraint DEFERRED, monitor violations |
| Auto-sync conflicts with manual UI operations | Make sync opt-out with clear UI warning |
| Performance impact of validation | Add indexes, cache column lookups |
| Breaking change for API clients | Version API, provide migration guide |

## Dependencies

- Joan MCP fixes (see JOAN_MCP_COLUMN_SYNC.md)
- Coordinator anomaly detection (see joan-agents)
- Database migration tooling
- API versioning strategy

## References

- Original investigation: `/Users/alexbenson/joan-agents/COORDINATOR_BUG_REPORT.md`
- MCP column inference: `/Users/alexbenson/joan-mcp/src/utils/column-mapper.ts`
- Task schema: `/Users/alexbenson/joan-mcp/src/client/types.ts`
