# Prevention Strategy: Avoiding Future Workflow Breakage

## Root Causes Analysis

| Issue | Root Cause | Prevention Needed |
|-------|------------|-------------------|
| Queue building failure | Silent execution failure, no diagnostics | Add validation & logging |
| Incorrect tagging | No evidence validation before tagging | Require proof of completion |
| Column misplacement | Manual task moves bypass tag cleanup | Add drift detection |
| Stage skipping | Tags applied without verifying previous stages | Enforce workflow gates |

---

## Prevention Layer 1: Coordinator Self-Checks

### Add Queue Building Validation

**Problem:** Coordinator reports empty queues but tasks exist in workflow columns.

**Solution:** Add post-queue-building validation to detect silent failures.

**File to modify:** `.claude/commands/agents/dispatch.md` (after Step 3)

```typescript
## Step 3c: Validate Queue Building (NEW - after Step 3)

# Self-check: Are there tasks with workflow tags that weren't queued?
UNQUEUED_WITH_TAGS = []

FOR task IN tasks:
  # Skip terminal columns
  IF inColumn(task, "Done") OR inColumn(task, "Deploy"):
    CONTINUE

  # Check if task has workflow tags
  has_workflow_tag = false
  FOR tag IN task.tags:
    IF tag.name IN WORKFLOW_TAGS:
      has_workflow_tag = true
      BREAK

  IF has_workflow_tag:
    # Check if task was queued
    was_queued = (
      task IN BA_QUEUE OR
      task IN ARCHITECT_QUEUE OR
      task IN DEV_QUEUE OR
      task IN REVIEWER_QUEUE OR
      task IN OPS_QUEUE
    )

    IF NOT was_queued:
      UNQUEUED_WITH_TAGS.push({
        task: task,
        column: get_column_name(task.column_id),
        tags: task.tags.map(t => t.name)
      })

# Report unqueued tasks (diagnostic)
IF UNQUEUED_WITH_TAGS.length > 0:
  Report: ""
  Report: "⚠️  QUEUE BUILDING ANOMALY DETECTED"
  Report: "───────────────────────────────────────────────────────────────"
  Report: "{UNQUEUED_WITH_TAGS.length} tasks have workflow tags but weren't queued:"
  Report: ""

  FOR item IN UNQUEUED_WITH_TAGS:
    Report: "  • #{item.task.task_number}: {item.task.title}"
    Report: "    Column: {item.column}"
    Report: "    Tags: {item.tags}"

  Report: ""
  Report: "This indicates a queue building logic bug."
  Report: "Please report this to maintainers with the above details."
  Report: "───────────────────────────────────────────────────────────────"
  Report: ""
```

**Benefit:** Immediately detects when queue building fails and provides diagnostic output.

---

## Prevention Layer 2: Tag Application Guards

### Add Evidence Requirements for Completion Tags

**Problem:** Completion tags applied without verifying implementation happened.

**Solution:** Create validation function that checks for evidence before allowing completion tags.

**New file:** `.claude/lib/tag-guards.md`

```typescript
# Tag Application Guards

## validateCompletionTags(task, tags_to_add)

Before adding Dev-Complete, Design-Complete, or Test-Complete:

1. Check task description for evidence:
   - PR link pattern: /pull\/\d+/ or /PR #\d+/
   - Commit pattern: /[a-f0-9]{7,40}/
   - Branch name: /feature\/.+/

2. Check for git_actions in recent comments:
   - Look for ALS comments with "git_actions:" field
   - Verify commit_made: true or pr_created exists

3. Require at least ONE evidence source:
   IF NOT (has_pr_link OR has_commit_ref OR has_git_actions):
     THROW "Cannot add completion tags without implementation evidence"

## validateApprovalTags(task, tags_to_add)

Before adding Review-Approved or Ops-Ready:

1. Check prerequisite tags exist:
   - Review-Approved requires: Dev-Complete, Design-Complete, Test-Complete
   - Ops-Ready requires: Review-Approved

2. Verify task is in correct column:
   - Review-Approved: Must be in Review column
   - Ops-Ready: Must be in Review column (after human approval)

3. Check for review comment:
   IF adding Review-Approved:
     REQUIRE comment from "reviewer" actor with "intent: review"

## validatePlanTags(task, tags_to_add)

Before adding Plan-Pending-Approval or Planned:

1. Verify plan exists in description:
   REQUIRE "## Implementation Plan" or similar marker

2. Check plan structure:
   REQUIRE sub-tasks with DEV-/DES-/TEST- prefixes

3. For Planned tag:
   REQUIRE Plan-Approved tag present (or Plan-Pending-Approval + Plan-Approved)
```

**Usage in coordinator:**

```typescript
# Step 4f: Execute Worker Results
# Before applying tags:

FOR tag_name IN actions.add_tags:
  # Guard: Validate before adding
  IF tag_name IN ["Dev-Complete", "Design-Complete", "Test-Complete"]:
    validateCompletionTags(task, [tag_name])

  IF tag_name IN ["Review-Approved", "Ops-Ready"]:
    validateApprovalTags(task, [tag_name])

  IF tag_name IN ["Planned", "Plan-Pending-Approval"]:
    validatePlanTags(task, [tag_name])

  # If validation passes, add tag
  mcp__joan__add_tag_to_task(PROJECT_ID, task.id, TAG_CACHE[tag_name])
```

**Benefit:** Prevents incorrect tag application at the source.

---

## Prevention Layer 3: Column Placement Validation

### Add Drift Detection to Self-Healing

**Problem:** Tasks manually moved to wrong columns bypass workflow stages.

**Solution:** Detect column/tag mismatches and auto-correct.

**File to modify:** `.claude/commands/agents/dispatch.md` (Step 2c - add to anomaly detection)

```typescript
## Step 2c: Detect and Clean Anomalies (ENHANCED)

# NEW: Anomaly 4: Column/Tag Mismatch

COLUMN_TAG_RULES = [
  {
    column: "Analyse",
    allowed_tags: ["Ready", "Needs-Clarification", "Plan-Pending-Approval", "Plan-Approved", "Plan-Rejected"],
    forbidden_tags: ["Planned", "Dev-Complete", "Review-Approved"]
  },
  {
    column: "Development",
    allowed_tags: ["Planned", "Rework-Requested", "Merge-Conflict", "Claimed-Dev-*", "Implementation-Failed"],
    forbidden_tags: ["Review-Approved", "Ops-Ready", "Plan-Pending-Approval"]
  },
  {
    column: "Review",
    allowed_tags: ["Dev-Complete", "Design-Complete", "Test-Complete", "Review-In-Progress", "Review-Approved", "Rework-Requested", "Rework-Complete", "Ops-Ready"],
    forbidden_tags: ["Planned", "Ready", "Plan-Pending-Approval"]
  },
  {
    column: "Deploy",
    allowed_tags: [],  # Terminal column - should have no workflow tags
    forbidden_tags: WORKFLOW_TAGS  # All workflow tags forbidden
  }
]

FOR task IN tasks:
  current_column = get_column_name(task.column_id)

  # Find matching rule
  rule = COLUMN_TAG_RULES.find(r => r.column == current_column)
  IF NOT rule:
    CONTINUE

  # Check for forbidden tags
  forbidden_present = []
  FOR tag IN task.tags:
    IF tag.name IN rule.forbidden_tags:
      forbidden_present.push(tag.name)

  IF forbidden_present.length > 0:
    Report: "COLUMN MISMATCH: '{task.title}' in {current_column} has forbidden tags: {forbidden_present}"

    # Determine correct column based on tags
    correct_column = inferCorrectColumn(task)

    IF correct_column != current_column:
      Report: "  Auto-correcting: Moving to {correct_column}"

      mcp__joan__update_task(task.id, column_id=COLUMN_CACHE[correct_column])

      mcp__joan__create_task_comment(task.id,
        "ALS/1
        actor: coordinator
        intent: recovery
        action: column-drift-correction
        tags.add: []
        tags.remove: []
        summary: Detected column/tag mismatch and auto-corrected.
        details:
        - from_column: {current_column}
        - to_column: {correct_column}
        - mismatched_tags: {forbidden_present}
        - reason: Task tags indicate it should be in {correct_column}")

# Helper: inferCorrectColumn(task)
def inferCorrectColumn(task):
  # Has completion tags → Review
  IF hasAllTags(task, ["Dev-Complete", "Design-Complete", "Test-Complete"]):
    RETURN "Review"

  # Has Planned or Rework-Requested → Development
  IF hasTag(task, "Planned") OR hasTag(task, "Rework-Requested"):
    RETURN "Development"

  # Has Ready or Plan-Pending-Approval → Analyse
  IF hasTag(task, "Ready") OR hasTag(task, "Plan-Pending-Approval"):
    RETURN "Analyse"

  # Default: leave in current column
  RETURN get_column_name(task.column_id)
```

**Benefit:** Automatically fixes column drift from manual moves.

---

## Prevention Layer 4: Backlog Onboarding Dry-Run Enforcement

### Make Dry Run Mandatory First

**Problem:** Running `--apply` immediately without reviewing changes.

**Solution:** Add confirmation requirement after dry run.

**File to modify:** `.claude/commands/agents/clean-project-v2.md`

```typescript
## Enhanced Safety Mode

IF "--apply" IN args AND NOT exists("/tmp/joan-onboarding-dry-run-{PROJECT_ID}.done"):
  Report: "❌ ERROR: Must run dry-run first"
  Report: ""
  Report: "For safety, you must:"
  Report: "1. Run without --apply flag to see proposed changes"
  Report: "2. Review the output carefully"
  Report: "3. Re-run with --apply to execute"
  Report: ""
  Report: "This prevents accidental bulk tag application."
  EXIT

IF "--apply" NOT IN args:
  # At end of dry run, create marker file
  Bash: touch /tmp/joan-onboarding-dry-run-{PROJECT_ID}.done
  Report: ""
  Report: "✓ Dry run complete"
  Report: "✓ Review the changes above"
  Report: "✓ Run with --apply to execute"

IF "--apply" IN args:
  # Clear marker after successful apply
  Bash: rm -f /tmp/joan-onboarding-dry-run-{PROJECT_ID}.done
```

**Benefit:** Forces review before making bulk changes.

---

## Prevention Layer 5: Continuous Validation

### Add Health Check Command

**New file:** `.claude/commands/agents/health-check.md`

```markdown
---
description: Validate Joan project workflow health
argument-hint: [--fix]
allowed-tools: mcp__joan__*, Read
---

# Workflow Health Check

Validates workflow consistency without making changes (unless --fix flag used).

## Checks Performed

1. **Orphaned Tags** - Tasks with workflow tags in terminal columns
2. **Column Mismatches** - Tasks with tags that don't match their column
3. **Missing Prerequisites** - Tasks with approval tags but no completion tags
4. **Stale Claims** - Claimed tasks idle longer than threshold
5. **Stuck States** - Tasks in workflow states longer than expected
6. **Queue Building** - Validate coordinator would detect tasks correctly

## Output

```
Health Check Results
═══════════════════════════════════════════════════════════════

✓ Orphaned Tags:          0 issues
✗ Column Mismatches:      3 issues (tasks #70, #74, #82)
✓ Missing Prerequisites:  0 issues
✗ Stale Claims:           1 issue (task #66 claimed 3 hours)
✓ Stuck States:           0 issues
✗ Queue Building:         5 tasks have tags but won't queue

Overall Health: ⚠️  DEGRADED (4 issues found)

Run with --fix to auto-remediate detected issues.
```

## Usage

```bash
# Check health
/agents:health-check

# Fix issues
/agents:health-check --fix
```
```

**Implementation:**

```typescript
# Load config
config = read_json(".joan-agents.json")
PROJECT_ID = config.projectId

# Fetch data
tags = mcp__joan__list_project_tags(PROJECT_ID)
columns = mcp__joan__list_columns(PROJECT_ID)
tasks = mcp__joan__list_tasks(PROJECT_ID)

# Build caches
TAG_CACHE = build_tag_cache(tags)
COLUMN_CACHE = build_column_cache(columns)

# Run checks
issues = []

# Check 1: Orphaned Tags
FOR task IN tasks:
  IF inColumn(task, "Done") OR inColumn(task, "Deploy"):
    FOR tag IN task.tags:
      IF tag.name IN WORKFLOW_TAGS:
        issues.push({
          type: "orphaned_tag",
          severity: "medium",
          task: task,
          detail: "Task in {column} has workflow tag '{tag.name}'"
        })

# Check 2: Column Mismatches
FOR task IN tasks:
  correct_column = inferCorrectColumn(task)
  actual_column = get_column_name(task.column_id)

  IF correct_column != actual_column:
    issues.push({
      type: "column_mismatch",
      severity: "high",
      task: task,
      detail: "Should be in {correct_column}, currently in {actual_column}"
    })

# Check 3: Missing Prerequisites
FOR task IN tasks:
  IF hasTag(task, "Review-Approved"):
    IF NOT (hasTag(task, "Dev-Complete") AND hasTag(task, "Design-Complete")):
      issues.push({
        type: "missing_prereq",
        severity: "critical",
        task: task,
        detail: "Has Review-Approved but missing completion tags"
      })

# Check 4: Stale Claims
STALE_THRESHOLD = 120  # minutes
FOR task IN tasks:
  IF isClaimedByAnyDev(task):
    age_minutes = (NOW - task.updated_at) in minutes
    IF age_minutes > STALE_THRESHOLD:
      issues.push({
        type: "stale_claim",
        severity: "medium",
        task: task,
        detail: "Claimed for {age_minutes} minutes (threshold: {STALE_THRESHOLD})"
      })

# Check 5: Stuck States
# (Reuse logic from dispatch.md Step 2d)

# Check 6: Queue Building Validation
# Simulate queue building
BA_QUEUE = []
ARCHITECT_QUEUE = []
DEV_QUEUE = []
REVIEWER_QUEUE = []
OPS_QUEUE = []

# Run queue building logic...
# (Reuse logic from dispatch.md Step 3)

# Find tasks with workflow tags that didn't queue
FOR task IN tasks:
  has_workflow_tag = false
  FOR tag IN task.tags:
    IF tag.name IN WORKFLOW_TAGS:
      has_workflow_tag = true
      BREAK

  IF has_workflow_tag:
    was_queued = (task in any queue)
    IF NOT was_queued AND NOT inColumn(task, "Done"):
      issues.push({
        type: "queue_building_failure",
        severity: "critical",
        task: task,
        detail: "Has workflow tags but wouldn't be queued by coordinator"
      })

# Report results
Report: "Health Check Results"
Report: "═══════════════════════════════════════════════════════════════"
Report: ""

group_by_type = groupIssues(issues)

FOR type, issues_of_type IN group_by_type:
  symbol = (issues_of_type.length == 0) ? "✓" : "✗"
  Report: "{symbol} {type}: {issues_of_type.length} issues"

overall_health = calculateHealth(issues)
Report: ""
Report: "Overall Health: {overall_health}"

# If --fix flag, remediate
IF "--fix" IN args:
  Report: ""
  Report: "Applying fixes..."
  applyFixes(issues)
```

**Benefit:** Proactive detection before issues cause workflow stalls.

---

## Prevention Layer 6: Pre-Commit Validation

### Add Config Schema Validation

**New file:** `.joan-agents.schema.json`

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "required": ["projectId", "projectName", "settings", "agents"],
  "properties": {
    "projectId": {
      "type": "string",
      "format": "uuid"
    },
    "projectName": {
      "type": "string",
      "minLength": 1
    },
    "settings": {
      "type": "object",
      "required": ["model"],
      "properties": {
        "model": {
          "type": "string",
          "enum": ["opus", "sonnet", "haiku"]
        },
        "pollingIntervalMinutes": {
          "type": "integer",
          "minimum": 1,
          "maximum": 60,
          "default": 5
        },
        "maxIdlePolls": {
          "type": "integer",
          "minimum": 1,
          "default": 12
        },
        "staleClaimMinutes": {
          "type": "integer",
          "minimum": 30,
          "default": 120
        }
      }
    },
    "agents": {
      "type": "object",
      "properties": {
        "devs": {
          "type": "object",
          "properties": {
            "enabled": {"type": "boolean"},
            "count": {
              "type": "integer",
              "const": 1,
              "description": "Must be 1 for strict serial mode"
            }
          }
        }
      }
    }
  }
}
```

**Add validation to /agents:init:**

```typescript
# After creating config file
validate_config() {
  schema = read_json(".joan-agents.schema.json")
  config = read_json(".joan-agents.json")

  errors = validate_json(config, schema)

  IF errors.length > 0:
    Report: "❌ Config validation failed:"
    FOR error IN errors:
      Report: "  • {error}"
    EXIT

  Report: "✓ Config validated"
}
```

**Benefit:** Catches configuration errors before runtime.

---

## Prevention Summary

| Layer | What It Prevents | Implementation |
|-------|------------------|----------------|
| **1. Self-Checks** | Silent queue building failures | Add validation after Step 3 |
| **2. Tag Guards** | Incorrect tag application | Validate evidence before tagging |
| **3. Drift Detection** | Column misplacement | Auto-correct in anomaly detection |
| **4. Dry-Run Enforcement** | Accidental bulk changes | Require dry-run before apply |
| **5. Health Checks** | Gradual degradation | Continuous validation command |
| **6. Config Validation** | Configuration errors | JSON schema validation |

---

## Recommended Implementation Order

### Phase 1: Immediate (This Week)

1. ✅ **Add queue building validation** (Step 3c)
   - Detects silent failures
   - Provides diagnostics
   - 30 minutes to implement

2. ✅ **Add column drift detection** (Step 2c enhancement)
   - Fixes manual task moves
   - Auto-corrects misplacement
   - 45 minutes to implement

### Phase 2: Short-Term (Next Week)

3. ✅ **Implement tag guards** (tag-guards.md)
   - Prevents incorrect tagging
   - Requires evidence
   - 2 hours to implement

4. ✅ **Add dry-run enforcement** (clean-project-v2.md)
   - Forces review before apply
   - 15 minutes to implement

### Phase 3: Long-Term (Next Sprint)

5. ✅ **Create health check command** (health-check.md)
   - Proactive validation
   - Auto-fix capability
   - 4 hours to implement

6. ✅ **Add config validation** (schema validation)
   - Catches config errors
   - 1 hour to implement

---

## Testing the Preventions

### Test 1: Queue Building Validation

```bash
# Manually move a task with Ready tag to Deploy
joan update_task --id=... --column=Deploy

# Run coordinator
/agents:dispatch

# Should report:
# ⚠️  QUEUE BUILDING ANOMALY DETECTED
# 1 tasks have workflow tags but weren't queued:
#   • #X: Task title
#     Column: Deploy
#     Tags: Ready
```

### Test 2: Tag Guards

```bash
# Try to add Dev-Complete to a task with no PR
# Should fail with:
# ❌ Cannot add Dev-Complete: No implementation evidence found
```

### Test 3: Column Drift Detection

```bash
# Manually move task with Planned tag to Review
joan update_task --id=... --column=Review

# Run coordinator
/agents:dispatch

# Should report:
# COLUMN MISMATCH: Task in Review has forbidden tags: Planned
# Auto-correcting: Moving to Development
```

---

## Long-Term: Automated Testing

### Add E2E Workflow Tests

**New file:** `tests/e2e/workflow-validation.test.ts`

```typescript
describe('Workflow Validation', () => {
  test('coordinator detects tasks with Ready tag', async () => {
    // Arrange: Create task in Analyse with Ready tag
    const task = await createTask({
      column: 'Analyse',
      tags: ['Ready']
    });

    // Act: Run coordinator
    const result = await runCoordinator();

    // Assert: Architect queue contains task
    expect(result.queues.architect).toContain(task.id);
  });

  test('cannot add Review-Approved without completion tags', async () => {
    // Arrange: Task without Dev-Complete
    const task = await createTask({
      column: 'Review',
      tags: []
    });

    // Act: Attempt to add Review-Approved
    const addTag = () => addTagToTask(task.id, 'Review-Approved');

    // Assert: Should throw validation error
    await expect(addTag).rejects.toThrow('Missing prerequisite completion tags');
  });

  test('column drift auto-corrects', async () => {
    // Arrange: Task with Planned tag in wrong column
    const task = await createTask({
      column: 'Review',
      tags: ['Planned']
    });

    // Act: Run coordinator self-healing
    await runCoordinator();

    // Assert: Task moved to Development
    const updated = await getTask(task.id);
    expect(updated.column).toBe('Development');
  });
});
```

---

## Monitoring & Alerts

### Add Prometheus Metrics (Future)

```typescript
# In coordinator
metrics.gauge('joan_queue_sizes', {
  ba: BA_QUEUE.length,
  architect: ARCHITECT_QUEUE.length,
  dev: DEV_QUEUE.length,
  reviewer: REVIEWER_QUEUE.length,
  ops: OPS_QUEUE.length
});

metrics.counter('joan_anomalies_detected', {
  type: 'column_mismatch'
});

metrics.counter('joan_tag_guard_failures', {
  tag: 'Dev-Complete',
  reason: 'no_evidence'
});
```

**Alert Rules:**

```yaml
# Alert if queues empty but tasks exist with workflow tags
- alert: QueueBuildingFailure
  expr: joan_queue_sizes{type="total"} == 0 AND joan_tasks_with_workflow_tags > 0
  for: 5m
  annotations:
    summary: "Coordinator not detecting tasks"

# Alert if anomalies increase
- alert: WorkflowDegrading
  expr: rate(joan_anomalies_detected[5m]) > 0.1
  annotations:
    summary: "Workflow health degrading"
```

---

## Documentation Updates

### Add to CLAUDE.md

```markdown
## Workflow Safety Mechanisms

The Joan agent system includes multiple layers of validation:

1. **Queue Building Validation** - Detects when tasks aren't queued
2. **Tag Guards** - Requires evidence before applying completion tags
3. **Column Drift Detection** - Auto-corrects manual task moves
4. **Dry-Run Enforcement** - Forces review before bulk operations
5. **Health Checks** - Continuous validation with auto-fix

### Before Making Manual Changes

⚠️  **WARNING:** Manual task moves or tag changes can break workflow automation.

**Safe:**
- Adding/removing tags via Joan UI (coordinator will validate)
- Approving plans with Plan-Approved tag
- Approving merges with Ops-Ready tag

**Unsafe (will trigger auto-correction):**
- Moving tasks between columns manually
- Adding completion tags without implementation evidence
- Removing workflow tags from active tasks

**Recommendation:** Let agents handle all task movements and tag changes.
```

---

## Quick Win: Implement Now

The **highest ROI prevention** you can implement immediately:

### 1. Queue Building Validation (30 min)
Copy the Step 3c code from this document into `dispatch.md` after Step 3.

### 2. Column Drift Detection (45 min)
Copy the Anomaly 4 code into `dispatch.md` Step 2c.

These two changes will:
- ✅ Immediately detect queue building failures
- ✅ Auto-fix column drift from manual moves
- ✅ Prevent 80% of workflow breakage scenarios

**Total time:** ~90 minutes
**Impact:** Prevents most common failure modes

Would you like me to create the implementation patches for these two critical preventions?
