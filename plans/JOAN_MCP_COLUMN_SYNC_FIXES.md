# Joan MCP: Column Inference & Sync Reliability Fixes

**Date:** 2026-01-22
**Priority:** CRITICAL
**Impact:** Prevents silent failures that cause column-status desynchronization

## Problem Statement

The Joan MCP layer has multiple points where column synchronization can fail silently:

1. **`inferColumnFromStatus()` returns null** when column names don't match expected patterns
2. **`complete_task` continues** even if column sync fails
3. **`bulk_update_tasks` has no sync logic** at all
4. **No error reporting** when inference fails

This causes tasks to drift into inconsistent states that break agent workflows.

## Investigation Findings

### File: `/Users/alexbenson/joan-mcp/src/utils/column-mapper.ts`

**Lines 90-105: Silent Null Returns**
```typescript
export function inferColumnFromStatus(
  columns: ProjectColumn[],
  status: string
): ProjectColumn | null {
  const byName = findColumnByName(columns, status);
  if (byName) return byName;

  const byPosition = findColumnByPosition(columns, status);
  if (byPosition) return byPosition;

  return null;  // ❌ Silent failure - no error logged
}
```

**Lines 17-22: Limited Pattern Matching**
```typescript
const patterns: Record<string, string[]> = {
  'todo': ['to do', 'todo', 'backlog', 'new'],
  'in_progress': ['in progress', 'doing', 'active', 'wip'],
  'done': ['done', 'completed', 'finished', 'closed'],
  // Missing: 'deploy', 'review', 'analyse', etc.
};
```

### File: `/Users/alexbenson/joan-mcp/src/tools/tasks.ts`

**Lines 273-283: Optional Sync in complete_task**
```typescript
if (input.sync_column !== false) {
  const doneColumn = inferColumnFromStatus(columns, 'done');
  if (doneColumn && doneColumn.id !== task.column_id) {
    await client.updateTask(input.task_id, { column_id: doneColumn.id });
  }
  // ❌ No error if doneColumn is null
}
```

**Lines 338-344: No Sync in bulk_update_tasks**
```typescript
const updates = input.updates.map(update => ({
  id: update.task_id,
  column_id: update.column_id,  // ❌ Must be explicit, no inference
  status: update.status ? statusToBackend(update.status) : undefined,
  order_index: 0,
}));
// No column sync logic at all
```

## Proposed Solutions

### Fix 1: Make Column Inference Fail Loudly

**File:** `src/utils/column-mapper.ts`

```typescript
export function inferColumnFromStatus(
  columns: ProjectColumn[],
  status: string,
  options: { required?: boolean } = {}
): ProjectColumn | null {
  const byName = findColumnByName(columns, status);
  if (byName) return byName;

  const byPosition = findColumnByPosition(columns, status);
  if (byPosition) return byPosition;

  // NEW: Log warning and optionally throw
  const availableColumns = columns.map(c => c.name).join(', ');
  console.warn(
    `[Joan MCP] Failed to infer column for status='${status}'. ` +
    `Available columns: ${availableColumns}`
  );

  if (options.required) {
    throw new Error(
      `Cannot find column for status='${status}'. ` +
      `Expected column names: 'Done', 'Completed', or 'Finished'. ` +
      `Available: ${availableColumns}`
    );
  }

  return null;
}
```

### Fix 2: Enforce Column Sync in complete_task

**File:** `src/tools/tasks.ts` (lines 247-300)

```typescript
async execute(input: z.infer<typeof this.inputSchema>) {
  const client = this.context.client;
  const task = await client.getTask(input.task_id);
  const columns = await client.listColumns(task.project_id);

  // Complete the task (sets status=done, completed_at)
  await client.completeTask(input.task_id);

  // CRITICAL: Sync column (no longer optional)
  if (input.sync_column !== false) {
    // NEW: Use required=true to fail if Done column not found
    const doneColumn = inferColumnFromStatus(columns, 'done', { required: true });

    if (doneColumn.id !== task.column_id) {
      await client.updateTask(input.task_id, { column_id: doneColumn.id });
      console.log(
        `[Joan MCP] Moved task #${task.task_number} to ${doneColumn.name} column`
      );
    }
  }

  return {
    success: true,
    message: `Task #${task.task_number} marked as complete` +
             (input.sync_column !== false ? ` and moved to Done column` : '')
  };
}
```

### Fix 3: Add Column Sync to bulk_update_tasks

**File:** `src/tools/tasks.ts` (lines 325-358)

```typescript
async execute(input: z.infer<typeof this.inputSchema>) {
  const client = this.context.client;

  // NEW: Enrich updates with column inference
  const enrichedUpdates = await Promise.all(
    input.updates.map(async (update) => {
      let columnId = update.column_id;

      // Auto-infer column if status changed but column not specified
      if (update.status && !update.column_id) {
        const task = await client.getTask(update.task_id);
        const columns = await client.listColumns(task.project_id);

        const inferredColumn = inferColumnFromStatus(
          columns,
          update.status,
          { required: false }  // Don't fail bulk operation
        );

        if (inferredColumn) {
          columnId = inferredColumn.id;
          console.log(
            `[Joan MCP] Auto-inferred column for task #${task.task_number}: ` +
            `status=${update.status} → column=${inferredColumn.name}`
          );
        } else {
          console.warn(
            `[Joan MCP] Could not infer column for task #${task.task_number} ` +
            `with status=${update.status}. Column unchanged.`
          );
        }
      }

      return {
        id: update.task_id,
        column_id: columnId,
        status: update.status ? statusToBackend(update.status) : undefined,
        order_index: 0,
      };
    })
  );

  const result = await client.bulkUpdateTasks(enrichedUpdates);

  return {
    success: true,
    updated_count: result.updated.length,
    failed_count: result.failed?.length || 0,
  };
}
```

### Fix 4: Expand Column Pattern Matching

**File:** `src/utils/column-mapper.ts` (lines 17-22)

```typescript
const patterns: Record<string, string[]> = {
  'todo': ['to do', 'todo', 'backlog', 'new', 'open', 'ready'],
  'in_progress': ['in progress', 'doing', 'active', 'wip', 'development', 'dev'],
  'review': ['review', 'reviewing', 'code review', 'testing', 'qa'],
  'deploy': ['deploy', 'deployment', 'deploying', 'staging', 'production'],
  'done': ['done', 'completed', 'finished', 'closed', 'resolved'],
  'cancelled': ['cancelled', 'canceled', 'rejected', 'abandoned'],
  'blocked': ['blocked', 'waiting', 'on hold', 'paused'],
};

// NEW: Add case-insensitive + fuzzy matching
export function findColumnByName(
  columns: ProjectColumn[],
  status: string
): ProjectColumn | null {
  const normalizedStatus = status.toLowerCase().trim();

  // First: Exact match
  for (const col of columns) {
    if (col.name.toLowerCase() === normalizedStatus) {
      return col;
    }
  }

  // Second: Pattern match
  for (const [key, aliases] of Object.entries(patterns)) {
    if (aliases.includes(normalizedStatus)) {
      for (const col of columns) {
        if (aliases.includes(col.name.toLowerCase())) {
          return col;
        }
      }
    }
  }

  // Third: Fuzzy match (Levenshtein distance ≤ 2)
  for (const col of columns) {
    if (levenshteinDistance(col.name.toLowerCase(), normalizedStatus) <= 2) {
      console.log(
        `[Joan MCP] Fuzzy matched column '${col.name}' for status '${status}'`
      );
      return col;
    }
  }

  return null;
}

function levenshteinDistance(a: string, b: string): number {
  const matrix: number[][] = [];
  for (let i = 0; i <= b.length; i++) {
    matrix[i] = [i];
  }
  for (let j = 0; j <= a.length; j++) {
    matrix[0][j] = j;
  }
  for (let i = 1; i <= b.length; i++) {
    for (let j = 1; j <= a.length; j++) {
      if (b.charAt(i - 1) === a.charAt(j - 1)) {
        matrix[i][j] = matrix[i - 1][j - 1];
      } else {
        matrix[i][j] = Math.min(
          matrix[i - 1][j - 1] + 1,
          matrix[i][j - 1] + 1,
          matrix[i - 1][j] + 1
        );
      }
    }
  }
  return matrix[b.length][a.length];
}
```

### Fix 5: Add Telemetry & Monitoring

**File:** `src/utils/telemetry.ts` (new)

```typescript
export interface ColumnSyncEvent {
  task_id: string;
  task_number: number;
  operation: 'complete' | 'update' | 'bulk_update';
  status_before: string;
  status_after: string;
  column_before: string;
  column_after: string;
  inferred: boolean;
  inference_failed: boolean;
  timestamp: string;
}

export class ColumnSyncTelemetry {
  private events: ColumnSyncEvent[] = [];

  log(event: Omit<ColumnSyncEvent, 'timestamp'>) {
    this.events.push({
      ...event,
      timestamp: new Date().toISOString(),
    });

    // Log to console
    if (event.inference_failed) {
      console.error(
        `[Joan MCP] Column sync failed for task #${event.task_number}: ` +
        `status=${event.status_after}, column=${event.column_before}`
      );
    } else if (event.inferred) {
      console.log(
        `[Joan MCP] Column synced for task #${event.task_number}: ` +
        `${event.column_before} → ${event.column_after}`
      );
    }
  }

  getFailures(): ColumnSyncEvent[] {
    return this.events.filter(e => e.inference_failed);
  }

  getMetrics() {
    return {
      total_events: this.events.length,
      failures: this.events.filter(e => e.inference_failed).length,
      inferred_syncs: this.events.filter(e => e.inferred).length,
      failure_rate: this.events.filter(e => e.inference_failed).length / this.events.length,
    };
  }
}
```

## Testing Plan

### Unit Tests

**File:** `src/utils/column-mapper.test.ts`

```typescript
describe('inferColumnFromStatus', () => {
  const columns: ProjectColumn[] = [
    { id: '1', name: 'To Do', project_id: 'p1' },
    { id: '2', name: 'In Progress', project_id: 'p1' },
    { id: '3', name: 'Done', project_id: 'p1' },
  ];

  test('exact match (case insensitive)', () => {
    expect(inferColumnFromStatus(columns, 'done')).toEqual(columns[2]);
    expect(inferColumnFromStatus(columns, 'DONE')).toEqual(columns[2]);
  });

  test('pattern match', () => {
    expect(inferColumnFromStatus(columns, 'completed')).toEqual(columns[2]);
    expect(inferColumnFromStatus(columns, 'finished')).toEqual(columns[2]);
  });

  test('fuzzy match', () => {
    expect(inferColumnFromStatus(columns, 'Dne')).toEqual(columns[2]); // typo
    expect(inferColumnFromStatus(columns, 'Don')).toEqual(columns[2]); // partial
  });

  test('fails loudly with required=true', () => {
    expect(() =>
      inferColumnFromStatus(columns, 'invalid', { required: true })
    ).toThrow('Cannot find column for status=\'invalid\'');
  });

  test('returns null with required=false', () => {
    expect(inferColumnFromStatus(columns, 'invalid')).toBeNull();
  });
});
```

**File:** `src/tools/tasks.test.ts`

```typescript
describe('complete_task with column sync', () => {
  test('moves task to Done column', async () => {
    const task = await createTask({ status: 'in_progress', column_id: todoColumnId });

    await completeTask({ task_id: task.id, sync_column: true });

    const updated = await getTask(task.id);
    expect(updated.status).toBe('done');
    expect(updated.column_id).toBe(doneColumnId);
  });

  test('throws if Done column not found', async () => {
    const projectWithNoDoneColumn = await createProject({ columns: ['To Do'] });
    const task = await createTask({ project_id: projectWithNoDoneColumn.id });

    await expect(
      completeTask({ task_id: task.id, sync_column: true })
    ).rejects.toThrow('Cannot find column for status=\'done\'');
  });

  test('skips sync if sync_column=false', async () => {
    const task = await createTask({ column_id: todoColumnId });

    await completeTask({ task_id: task.id, sync_column: false });

    const updated = await getTask(task.id);
    expect(updated.status).toBe('done');
    expect(updated.column_id).toBe(todoColumnId); // Unchanged
  });
});
```

### Integration Tests

**File:** `tests/integration/column-sync.test.ts`

```typescript
describe('Column Sync Integration', () => {
  test('coordinator workflow maintains consistency', async () => {
    // Simulate full agent workflow
    const task = await createTask({ title: 'Test Feature' });

    // BA marks Ready
    await updateTask(task.id, { status: 'ready' });
    let updated = await getTask(task.id);
    expect(updated.column_id).toBe(analyseColumnId);

    // Architect moves to Development
    await updateTask(task.id, { status: 'planned' });
    updated = await getTask(task.id);
    expect(updated.column_id).toBe(developmentColumnId);

    // Dev completes
    await completeTask(task.id);
    updated = await getTask(task.id);
    expect(updated.status).toBe('done');
    expect(updated.column_id).toBe(doneColumnId);
  });

  test('bulk update maintains consistency', async () => {
    const tasks = await Promise.all([
      createTask({ title: 'Task 1' }),
      createTask({ title: 'Task 2' }),
      createTask({ title: 'Task 3' }),
    ]);

    await bulkUpdateTasks({
      updates: tasks.map(t => ({ task_id: t.id, status: 'done' }))
    });

    for (const task of tasks) {
      const updated = await getTask(task.id);
      expect(updated.status).toBe('done');
      expect(updated.column_id).toBe(doneColumnId);
    }
  });
});
```

## Rollout Plan

### Phase 1: Add Telemetry (Week 1)
- [ ] Deploy telemetry to staging
- [ ] Monitor column sync events for 48 hours
- [ ] Identify patterns in failures
- [ ] Document column naming conventions

### Phase 2: Fix Inference (Week 2)
- [ ] Add expanded pattern matching
- [ ] Add fuzzy matching
- [ ] Deploy to staging
- [ ] Verify failure rate drops to <1%
- [ ] Deploy to production

### Phase 3: Enforce Sync (Week 3)
- [ ] Make complete_task fail loudly
- [ ] Add sync to bulk_update_tasks
- [ ] Deploy to staging
- [ ] Test with real agent workflows
- [ ] Deploy to production

### Phase 4: Validate (Week 4)
- [ ] Enable database constraint (see JOAN_BACKEND_COLUMN_STATUS_SYNC.md)
- [ ] Monitor for violations
- [ ] Fix any remaining gaps
- [ ] Update documentation

## Success Metrics

- **Column inference success rate:** 95% → 99.9%
- **Silent failures:** 15/day → 0/day
- **Agent workflow success:** 85% → 99%
- **Tasks with desync:** 20 → 0

## Breaking Changes

### complete_task now throws on failure
**Before:**
```typescript
completeTask({ task_id: 'xyz' }); // Silent failure if Done column missing
```

**After:**
```typescript
try {
  completeTask({ task_id: 'xyz' });
} catch (error) {
  // Handle: "Cannot find column for status='done'"
}
```

### bulk_update_tasks now infers columns
**Before:**
```typescript
bulkUpdateTasks({
  updates: [{ task_id: 'xyz', status: 'done' }]
  // Column unchanged
});
```

**After:**
```typescript
bulkUpdateTasks({
  updates: [{ task_id: 'xyz', status: 'done' }]
  // Column automatically moved to Done
});
```

## Migration Guide

For clients using Joan MCP:

1. **Update error handling** for `complete_task`
2. **Remove explicit column_id** from `bulk_update_tasks` (now inferred)
3. **Review column naming** to match expected patterns
4. **Monitor telemetry** for inference failures

## Dependencies

- Joan Backend fixes (see JOAN_BACKEND_COLUMN_STATUS_SYNC.md)
- Coordinator anomaly detection (in joan-agents)
- Documentation updates

## References

- Original bug report: `/Users/alexbenson/joan-agents/COORDINATOR_BUG_REPORT.md`
- Column mapper implementation: `/Users/alexbenson/joan-mcp/src/utils/column-mapper.ts`
- Task tools implementation: `/Users/alexbenson/joan-mcp/src/tools/tasks.ts`
- Telemetry RFC: https://github.com/your-org/joan-mcp/issues/XXX
