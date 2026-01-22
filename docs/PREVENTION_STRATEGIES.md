# Joan Agent Workflow - Prevention Strategies

This document outlines strategies to prevent common workflow failures.

## 1. Sub-Task Completion Verification

### Problem
Dev workers complete work but forget to check off `[ ]` sub-tasks in task descriptions, blocking Reviewer from validating completion.

### Root Cause
Agent execution variability - worker may skip the "update description" step even though instructions specify it.

### Prevention Strategy: Coordinator Post-Verification

**Add verification step to coordinator after processing worker results:**

```typescript
// After executing joan_actions from worker result
if (worker_result.success && worker_result.joan_actions.update_description) {
  // Re-fetch task to verify description was actually updated
  const updatedTask = await joan.getTask(task_id);

  // Check if description contains [x] for completed sub-tasks
  const hasCheckedTasks = updatedTask.description.includes('[x]');

  if (!hasCheckedTasks && worker_result.joan_actions.add_tags.includes('Dev-Complete')) {
    // Worker forgot to check off sub-tasks - do it automatically
    const fixedDescription = autoCheckSubTasks(updatedTask.description);
    await joan.updateTask(task_id, { description: fixedDescription });

    // Log the auto-fix
    await joan.addComment(task_id,
      `ALS/1\nactor: coordinator\nintent: recovery\naction: auto-checked-subtasks\n` +
      `summary: Worker completed work but forgot to check off sub-tasks. Auto-fixed.\n`
    );
  }
}
```

**Implementation Location:** `/Users/alexbenson/joan-agents/skills/agents/dispatch.md`
- Add verification after "Step 6: Execute Joan Actions"
- Before moving to next task in queue

**Benefit:** Zero-trust verification - coordinator confirms workers' work

---

## 2. Manual Column Move Protection

### Problem
Manual task moves in Joan UI create tag/column drift, breaking workflow state machine.

### Root Cause
Tags and columns must stay synchronized. Manual moves don't update tags automatically.

### Prevention Strategies

#### Strategy A: Lock Down Manual Moves (Recommended)
**Add Joan UI customization to warn on manual moves:**

```javascript
// Joan UI script (if extensible)
onTaskMove((task, fromColumn, toColumn) => {
  if (!task.tags.some(t => WORKFLOW_TAGS.includes(t.name))) {
    showWarning(
      'This task has no workflow tags. ' +
      'Consider using /agents:clean-project after manual moves.'
    );
  }
});
```

#### Strategy B: Automatic Cleanup on Startup
**Always run cleanup when starting coordinator:**

```bash
# In .joan-agents.json, add:
"settings": {
  "autoCleanOnStartup": true  // Run /agents:clean-project before first poll
}
```

#### Strategy C: Documentation
**Add prominent warning in project CLAUDE.md:**

```markdown
## ⚠️ CRITICAL: Manual Task Moves

If you manually move tasks between columns in Joan UI:
1. Run `/agents:clean-project --apply` immediately after
2. Or add/remove workflow tags manually to match the new column:
   - To Do: (no tags)
   - Analyse + Ready: `Ready` tag
   - Analyse + Plan pending: `Plan-Pending-Approval` tag
   - Development: `Planned` tag
   - Review: `Dev-Complete`, `Test-Complete`, `Design-Complete` tags
   - Deploy: `Review-Approved` + `Ops-Ready` tags

**Best practice:** Let agents move tasks. They update tags atomically.
```

---

## 3. Configuration Validation

### Problem
Config violations (like `devs.count: 2` in strict serial mode) silently break workflow.

### Prevention Strategy: Startup Validation

**Add config schema validation before coordinator starts:**

```typescript
// In coordinator startup (dispatch.md or init command)
function validateConfig(config: JoanAgentsConfig): ValidationResult {
  const errors: string[] = [];

  // Enforce strict serial mode
  if (config.agents.devs.count !== 1) {
    errors.push(
      `devs.count must be 1 for strict serial mode (found: ${config.agents.devs.count}). ` +
      `This prevents merge conflicts. Update .joan-agents.json.`
    );
  }

  // Validate required settings exist
  if (!config.settings.stuckStateMinutes) {
    errors.push('Missing settings.stuckStateMinutes - add default 120');
  }

  if (!config.settings.pipeline) {
    errors.push('Missing settings.pipeline - add default { baQueueDraining: true, maxBaTasksPerCycle: 10 }');
  }

  // Validate workerTimeouts
  const requiredWorkers = ['ba', 'architect', 'dev', 'reviewer', 'ops'];
  const missingTimeouts = requiredWorkers.filter(
    w => !config.settings.workerTimeouts?.[w]
  );

  if (missingTimeouts.length > 0) {
    errors.push(`Missing worker timeouts: ${missingTimeouts.join(', ')}`);
  }

  return { valid: errors.length === 0, errors };
}

// Before starting loop
const validation = validateConfig(config);
if (!validation.valid) {
  console.error('❌ Configuration validation failed:\n' + validation.errors.join('\n'));
  process.exit(1);
}
```

**Alternative:** Update `/agents:init` to enforce these defaults when creating config.

---

## 4. Process Monitoring

### Problem
Coordinator process terminates silently - no visibility into whether loop is running.

### Prevention Strategies

#### Strategy A: Use External Scheduler (Recommended)
```bash
# Use loop mode (automatically uses external scheduler):
/agents:dispatch --loop

# Benefits:
# - Fresh context every cycle (prevents context drift)
# - Heartbeat monitoring (kills stuck processes)
# - Automatic restart on failure
# - Clean logs
```

#### Strategy B: Add Status Check Command
```bash
# Add /agents:running command
/agents:running

# Output:
# ✓ Coordinator running (PID 12345, heartbeat 30s ago)
# OR
# ✗ Coordinator not running (last heartbeat 19m ago)
```

**Implementation:**
```bash
#!/bin/bash
# Check if coordinator is running
HEARTBEAT_FILE="/tmp/joan-agents-${PROJECT_NAME}.heartbeat"

if [ ! -f "$HEARTBEAT_FILE" ]; then
  echo "✗ Coordinator not running (no heartbeat file)"
  exit 1
fi

LAST_HEARTBEAT=$(cat "$HEARTBEAT_FILE")
CURRENT_TIME=$(date +%s)
AGE=$((CURRENT_TIME - LAST_HEARTBEAT))

if [ $AGE -gt 600 ]; then  # 10 minutes
  echo "✗ Coordinator not running (last heartbeat ${AGE}s ago)"
  exit 1
else
  echo "✓ Coordinator running (heartbeat ${AGE}s ago)"
  exit 0
fi
```

#### Strategy C: GitHub Actions for Cloud Monitoring
```yaml
# .github/workflows/joan-coordinator.yml
name: Joan Coordinator Monitor

on:
  schedule:
    - cron: '*/30 * * * *'  # Every 30 minutes
  workflow_dispatch:

jobs:
  check-coordinator:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Check coordinator heartbeat
        run: |
          if ! ./scripts/check-coordinator.sh; then
            echo "::warning::Coordinator appears stuck"
          fi
```

---

## 5. Worker Result Validation

### Problem
Workers return malformed JSON or incomplete results, coordinator can't process them.

### Prevention Strategy: Schema Validation

**Add JSON schema validation before processing worker results:**

```typescript
import Ajv from 'ajv';
import workerResultSchema from './worker-result-schema.json';

const ajv = new Ajv();
const validateWorkerResult = ajv.compile(workerResultSchema);

// After spawning worker and receiving result
if (!validateWorkerResult(workerResult)) {
  console.error('Worker returned invalid result:', validateWorkerResult.errors);

  // Fallback: release claim, add failure comment
  await joan.removeTag(task_id, claim_tag);
  await joan.addComment(task_id,
    `ALS/1\nactor: coordinator\nintent: failure\naction: worker-invalid-result\n` +
    `summary: Worker returned malformed result. Manual intervention required.\n` +
    `details:\n${JSON.stringify(validateWorkerResult.errors, null, 2)}`
  );

  continue; // Skip to next task
}
```

---

## 6. Stuck State Auto-Recovery Enhancement

### Problem
Tasks stuck in mid-workflow states don't automatically recover.

### Current State
Coordinator has stuck state detection (v4.5) but only logs diagnostics.

### Enhancement: Auto-Requeue

```typescript
// In stuck state detection (dispatch.md)
for (const stuckTask of stuckTasks) {
  // Log diagnostic
  await joan.addComment(stuckTask.id, diagnosticComment);

  // Auto-requeue if safe
  if (canAutoRequeue(stuckTask)) {
    // Reset to last known good state
    const resetActions = determineResetActions(stuckTask);

    await joan.removeTag(stuckTask.id, ...resetActions.remove_tags);
    await joan.addTag(stuckTask.id, ...resetActions.add_tags);
    await joan.moveTask(stuckTask.id, resetActions.target_column);

    FORCE_REQUEUE.push(stuckTask.id);
  }
}
```

---

## Summary

### Quick Wins (Implement First)
1. ✅ Add config validation to `/agents:init` and `/agents:dispatch`
2. ✅ Add `/agents:running` status check command
3. ✅ Add warning in project CLAUDE.md about manual moves
4. ✅ Use `/agents:dispatch --loop` for long-running operations (external scheduler)

### Medium Priority
1. Add coordinator sub-task verification (post-condition checks)
2. Add worker result JSON schema validation
3. Enhance stuck state detection with auto-requeue

### Future Enhancements
1. Joan UI extension for manual move warnings
2. Cloud monitoring via GitHub Actions
3. Structured logging with searchable audit trail

---

## Testing the Fixes

After implementing prevention strategies, test with:

```bash
# Test 1: Config validation catches errors
echo '{"devs": {"count": 2}}' > test-config.json
/agents:dispatch  # Should error and refuse to start

# Test 2: Manual move cleanup
# Manually move task in Joan UI
/agents:clean-project --dry-run  # Should detect drift

# Test 3: Status check
/agents:running  # Should show accurate status

# Test 4: Stuck state recovery
# Leave task in Development for 2+ hours
/agents:dispatch  # Should auto-requeue after stuckStateMinutes
```
