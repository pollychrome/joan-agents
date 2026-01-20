---
description: Run coordinator (single pass or loop) - recommended mode
argument-hint: [--loop] [--max-idle=N]
allowed-tools: mcp__joan__*, Read, Task
---

# Coordinator (Dispatcher)

The coordinator is the **recommended way** to run the Joan agent system. It:
- Polls Joan once per interval (not N times for N agents)
- Dispatches single-pass workers for available tasks
- Claims dev tasks atomically before dispatching
- Uses tags for all state transitions (no comment parsing)

**IMPORTANT**: This command runs coordinator logic DIRECTLY (not as a subagent) to ensure MCP tool access. Workers are spawned as subagents with task data passed via prompt.

## Arguments

- `--loop` → Run continuously until idle threshold reached
- No flag → Single pass (dispatch once, then exit)
- `--max-idle=N` → Override idle threshold (only applies in loop mode)

## Configuration

Load from `.joan-agents.json`:
```
PROJECT_ID = config.projectId
PROJECT_NAME = config.projectName
POLL_INTERVAL = config.settings.pollingIntervalMinutes (default: 10)
MAX_IDLE = --max-idle override or config.settings.maxIdlePolls (default: 6)
MODEL = config.settings.model (default: "opus")
DEV_COUNT = config.agents.devs.count (default: 2)
STALE_CLAIM_MINUTES = config.settings.staleClaimMinutes (default: 60)
MAX_POLL_CYCLES = config.settings.maxPollCyclesBeforeRestart (default: 10)
STUCK_STATE_MINUTES = config.settings.stuckStateMinutes (default: 120)

# Enabled flags (all default to true)
BA_ENABLED = config.agents.businessAnalyst.enabled
ARCHITECT_ENABLED = config.agents.architect.enabled
REVIEWER_ENABLED = config.agents.reviewer.enabled
OPS_ENABLED = config.agents.ops.enabled
DEVS_ENABLED = config.agents.devs.enabled
```

If config missing, report error and exit.

Parse arguments:
```
LOOP_MODE = true if --loop flag present, else false
```

## Initialization

```
1. Report: "Coordinator started for {PROJECT_NAME}"
   Report: "Mode: {LOOP_MODE ? 'Loop' : 'Single pass'}"
   Report: "Dev workers available: {DEV_COUNT}"
   Report: "Enabled agents: {list enabled agents}"

2. Initialize state:
   IDLE_COUNT = 0
   POLL_CYCLE_COUNT = 0
   TAG_CACHE = {}
   FORCE_REQUEUE = []  # Tasks flagged for priority re-processing
```

---

## Main Loop

```
WHILE true:
  Step 1: Cache Tags and Columns
  Step 2: Fetch Tasks
  Step 2a: Write Heartbeat (external scheduler support)
  Step 2b: Recover Stale Claims (self-healing)
  Step 2c: Detect and Clean Anomalies (self-healing)
  Step 2d: Detect Stuck Workflow States (self-healing)
  Step 2e: State Machine Validation (self-healing)
  Step 3: Build Priority Queues
  Step 4: Dispatch Workers
  Step 5: Handle Idle / Exit / Restart

  IF not LOOP_MODE:
    EXIT after one pass
```

---

## Step 1: Cache Tags and Columns (once per loop iteration)

```
1. Fetch all project tags:
   tags = mcp__joan__list_project_tags(PROJECT_ID)

2. Build tag name → ID map:
   TAG_CACHE = {
     "Ready": "uuid-1",
     "Planned": "uuid-2",
     "Needs-Clarification": "uuid-3",
     ... (all workflow tags)
   }

3. Fetch all project columns:
   columns = mcp__joan__list_columns(PROJECT_ID)

4. Build column name → ID map:
   COLUMN_CACHE = {
     "To Do": "uuid-a",
     "Analyse": "uuid-b",
     "Development": "uuid-c",
     "Review": "uuid-d",
     "Deploy": "uuid-e",
     "Done": "uuid-f"
   }

5. Helper functions:

   hasTag(task, tagName):
   - Check if task.tags array contains any tag with id === TAG_CACHE[tagName]

   isClaimedByAnyDev(task):
   - For each tagName in TAG_CACHE keys:
       IF tagName starts with "Claimed-Dev-" AND hasTag(task, tagName): RETURN true
   - RETURN false

   inColumn(task, columnName):
   - RETURN task.column_id === COLUMN_CACHE[columnName]

IMPORTANT: Always use inColumn(task, "Column Name") to check columns.
Do NOT compare task.status string - it may be out of sync with column_id.
```

---

## Step 2: Fetch Tasks

```
1. Fetch all tasks for project:
   tasks = mcp__joan__list_tasks(project_id=PROJECT_ID)

2. For each task, note:
   - task.id
   - task.title
   - task.column_id (use this for column checks via inColumn())
   - task.tags[]

NOTE: Do NOT use task.status for column checks - it may be stale.
Always use task.column_id with the inColumn() helper.
```

---

## Step 2a: Write Heartbeat (External Scheduler Support)

Write current timestamp to heartbeat file for external scheduler monitoring.
This allows `/agents:scheduler` to detect stuck coordinators and restart them.

```
# Get project name for heartbeat file naming (sanitize for filesystem)
PROJECT_SLUG = PROJECT_NAME.toLowerCase().replace(/[^a-z0-9]+/g, '-')

Run bash command:
  echo $(date +%s) > /tmp/joan-agents-{PROJECT_SLUG}.heartbeat

# Silent operation - only report if debugging
```

**Why heartbeat?**
- External scheduler (`/agents:scheduler`) spawns fresh Claude processes to avoid context overflow
- Scheduler monitors heartbeat file to detect stuck coordinators
- If heartbeat becomes stale (older than stuck_timeout), scheduler kills and restarts
- Even single-pass coordinators write heartbeat - the freshness indicates activity
- This enables self-healing when coordinators freeze due to context bloat

---

## Step 2b: Recover Stale Claims (Self-Healing)

When the coordinator is killed or workers crash, `Claimed-Dev-N` tags may remain orphaned.
This step detects and releases stale claims so tasks can be picked up again.

```
STALE_THRESHOLD_MINUTES = STALE_CLAIM_MINUTES  # From config, default 60

For each task in tasks:
  IF isClaimedByAnyDev(task):

    # Check task's updated_at timestamp
    claim_age_minutes = (NOW - task.updated_at) in minutes

    # A task claimed but not updated for STALE_THRESHOLD is likely orphaned
    IF claim_age_minutes > STALE_THRESHOLD_MINUTES:

      # Find which dev has the claim
      FOR N in 1..DEV_COUNT:
        IF hasTag(task, "Claimed-Dev-{N}"):

          Report: "Releasing stale claim on '{task.title}' (Claimed-Dev-{N}, idle {claim_age_minutes} min)"

          # Remove the stale claim tag
          mcp__joan__remove_tag_from_task(PROJECT_ID, task.id, TAG_CACHE["Claimed-Dev-{N}"])

          # Add comment for audit trail
          mcp__joan__create_task_comment(task.id,
            "ALS/1
            actor: coordinator
            intent: recovery
            action: release-stale-claim
            tags.add: []
            tags.remove: [Claimed-Dev-{N}]
            summary: Released stale claim after {claim_age_minutes} min idle.
            details:
            - threshold: {STALE_THRESHOLD_MINUTES} min
            - reason: Worker likely crashed or was terminated")

          BREAK  # Only one claim per task

Report: "Stale claim recovery complete"
```

**Why this matters:**
- Without recovery, orphaned claims block tasks indefinitely
- Workers may crash, be killed, or hit timeouts
- This makes the system self-healing without manual intervention

---

## Step 2c: Detect and Clean Anomalies (Self-Healing)

Tasks can end up in inconsistent states due to partial failures, manual moves, or worker crashes.
This step detects and auto-cleans anomalies to prevent stuck states.

```
WORKFLOW_TAGS = ["Review-Approved", "Ops-Ready", "Plan-Approved", "Planned",
                 "Plan-Pending-Approval", "Ready", "Rework-Requested"]
TERMINAL_COLUMNS = ["Deploy", "Done"]

For each task in tasks:

  # Anomaly 1: Completed tasks with stale workflow tags
  IF inColumn(task, "Deploy") OR inColumn(task, "Done"):
    stale_tags = []
    FOR tagName IN WORKFLOW_TAGS:
      IF hasTag(task, tagName):
        stale_tags.push(tagName)

    IF stale_tags.length > 0:
      Report: "ANOMALY: '{task.title}' in {column} has stale tags: {stale_tags}"

      # Auto-clean stale tags
      FOR tagName IN stale_tags:
        mcp__joan__remove_tag_from_task(PROJECT_ID, task.id, TAG_CACHE[tagName])

      # Audit trail
      mcp__joan__create_task_comment(task.id,
        "ALS/1
        actor: coordinator
        intent: recovery
        action: anomaly-cleanup
        tags.add: []
        tags.remove: {stale_tags}
        summary: Cleaned stale workflow tags from completed task.
        details:
        - column: {task column name}
        - reason: Tasks in terminal columns should not have active workflow tags")

  # Anomaly 2: Conflicting approval/rejection tags
  IF hasTag(task, "Review-Approved") AND hasTag(task, "Rework-Requested"):
    Report: "ANOMALY: '{task.title}' has both Review-Approved AND Rework-Requested"

    # Remove the older state (approval came after rework request would be invalid)
    mcp__joan__remove_tag_from_task(PROJECT_ID, task.id, TAG_CACHE["Review-Approved"])

    mcp__joan__create_task_comment(task.id,
      "ALS/1
      actor: coordinator
      intent: recovery
      action: anomaly-cleanup
      tags.add: []
      tags.remove: [Review-Approved]
      summary: Removed conflicting Review-Approved tag (Rework-Requested takes precedence).
      details:
      - reason: Cannot be both approved and requesting rework simultaneously")

  # Anomaly 3: Plan-Approved without Plan-Pending-Approval
  IF hasTag(task, "Plan-Approved") AND NOT hasTag(task, "Plan-Pending-Approval"):
    IF NOT inColumn(task, "Development") AND NOT inColumn(task, "Deploy") AND NOT inColumn(task, "Done"):
      Report: "ANOMALY: '{task.title}' has Plan-Approved but no Plan-Pending-Approval"

      # Auto-fix: Add the missing Plan-Pending-Approval tag so architect can finalize
      mcp__joan__add_tag_to_task(PROJECT_ID, task.id, TAG_CACHE["Plan-Pending-Approval"])

      mcp__joan__create_task_comment(task.id,
        "ALS/1
        actor: coordinator
        intent: recovery
        action: anomaly-cleanup
        tags.add: [Plan-Pending-Approval]
        tags.remove: []
        summary: Added missing Plan-Pending-Approval tag to enable plan finalization.
        details:
        - reason: Plan-Approved was present but Plan-Pending-Approval was missing (likely worker crash)
        - effect: Task will now be queued for architect finalization")

Report: "Anomaly detection complete"
```

**Why this matters:**
- Partial worker failures leave inconsistent tag states
- Manual task moves in Joan UI bypass tag cleanup
- Without detection, tasks get stuck in limbo forever
- Auto-cleanup makes the system self-healing

---

## Step 2d: Detect Stuck Workflow States (Self-Healing)

Tasks can get stuck in mid-workflow states due to context bloat, lost worker results, or coordinator crashes.
This step detects tasks that have been in the same workflow state for too long and flags them for re-processing.

```
STUCK_THRESHOLD_MINUTES = STUCK_STATE_MINUTES  # From config, default 120

# Define expected state transitions and their max durations (minutes)
# Format: [column, required_tags, forbidden_tags, max_minutes, description]
WORKFLOW_STATE_TIMEOUTS = [
  # Architect should finalize approved plans quickly
  ["Analyse", ["Plan-Pending-Approval", "Plan-Approved"], ["Plan-Rejected"], 30, "Plan finalization"],

  # Architect should create plans within 1 hour of Ready
  ["Analyse", ["Ready"], ["Plan-Pending-Approval"], 60, "Plan creation"],

  # Clarification answers should be processed quickly
  ["Analyse", ["Needs-Clarification", "Clarification-Answered"], [], 30, "Clarification processing"],

  # Planned tasks should be claimed within 2 hours
  ["Development", ["Planned"], ["Claimed-Dev-"], 120, "Dev claim"],

  # Rework should be picked up within 2 hours
  ["Development", ["Rework-Requested", "Planned"], ["Claimed-Dev-"], 120, "Rework claim"],

  # Review should start within 2 hours of completion
  ["Review", ["Dev-Complete", "Design-Complete", "Test-Complete"], ["Review-In-Progress", "Review-Approved", "Rework-Requested"], 120, "Review start"],
]

CLEAR FORCE_REQUEUE  # Reset at start of detection

For each task in tasks:
  state_age_minutes = (NOW - task.updated_at) in minutes

  FOR EACH [expected_column, required_tags, forbidden_tags, max_minutes, description] IN WORKFLOW_STATE_TIMEOUTS:

    # Check if task is in this workflow state
    IF NOT inColumn(task, expected_column):
      CONTINUE

    # Check required tags are present
    all_required = true
    FOR tag IN required_tags:
      # Handle wildcard prefix matching (e.g., "Claimed-Dev-")
      IF tag ends with "-":
        # Check if ANY tag with this prefix exists
        prefix_found = false
        FOR actual_tag IN task.tags:
          IF actual_tag.name starts with tag:
            prefix_found = true
            BREAK
        # For forbidden tags with prefix, we want NONE to match
        IF tag IN forbidden_tags AND prefix_found:
          all_required = false
          BREAK
      ELSE:
        IF NOT hasTag(task, tag):
          all_required = false
          BREAK

    IF NOT all_required:
      CONTINUE

    # Check no forbidden tags are present
    has_forbidden = false
    FOR tag IN forbidden_tags:
      IF tag ends with "-":
        # Prefix matching for forbidden tags
        FOR actual_tag IN task.tags:
          IF actual_tag.name starts with tag:
            has_forbidden = true
            BREAK
      ELSE:
        IF hasTag(task, tag):
          has_forbidden = true
          BREAK
    IF has_forbidden:
      CONTINUE

    # Task matches this workflow state - check age
    IF state_age_minutes > max_minutes:
      Report: "STUCK STATE: '{task.title}' in {description} state for {state_age_minutes} min (max: {max_minutes})"

      # Add diagnostic comment
      mcp__joan__create_task_comment(task.id,
        "ALS/1
        actor: coordinator
        intent: diagnostic
        action: stuck-state-detected
        tags.add: []
        tags.remove: []
        summary: Task stuck in workflow state for {state_age_minutes} minutes.
        details:
        - state: {description}
        - expected_tags: {required_tags}
        - column: {expected_column}
        - threshold: {max_minutes} minutes
        - action: Force re-queuing for next dispatch cycle")

      # Mark for priority re-processing
      FORCE_REQUEUE.push({task: task, state: description, required_tags: required_tags})

      BREAK  # Only report each task once

IF FORCE_REQUEUE.length > 0:
  Report: "Detected {FORCE_REQUEUE.length} stuck tasks for re-processing"
ELSE:
  Report: "No stuck states detected"
```

**Why this matters:**
- Context bloat can cause coordinators to skip queue-building logic
- Lost worker results leave tasks in mid-transition states
- Without detection, tasks can remain stuck for hours/days
- Force re-queuing gives stuck tasks priority processing

---

## Step 2e: State Machine Validation (Self-Healing)

Validates that task tag combinations match valid workflow states.
Invalid combinations are auto-remediated to restore consistent state.

```
# Define invalid tag combinations that should never coexist
INVALID_TAG_COMBINATIONS = [
  # Ready should be removed when plan is created
  {
    tags: ["Ready", "Plan-Pending-Approval"],
    remediation: "remove",
    remove_tag: "Ready",
    reason: "Ready tag should be removed when plan is created"
  },

  # Ready should definitely not exist alongside Plan-Approved
  {
    tags: ["Ready", "Plan-Approved"],
    remediation: "remove",
    remove_tag: "Ready",
    reason: "Ready tag is stale - plan has been approved"
  },

  # Cannot be both approved and requesting rework
  {
    tags: ["Review-Approved", "Rework-Requested"],
    remediation: "remove",
    remove_tag: "Review-Approved",
    reason: "Rework-Requested takes precedence over Review-Approved"
  },

  # Plan-Rejected should not coexist with Plan-Approved
  {
    tags: ["Plan-Approved", "Plan-Rejected"],
    remediation: "remove",
    remove_tag: "Plan-Rejected",
    reason: "Plan-Approved takes precedence (latest action)"
  },

  # Claimed tasks should not have Implementation-Failed
  {
    tags_pattern: ["Claimed-Dev-*", "Implementation-Failed"],
    remediation: "remove_pattern",
    remove_pattern: "Claimed-Dev-*",
    reason: "Failed implementations should release claims"
  },

  # Completed tasks should not still be claimed
  {
    tags_pattern: ["Claimed-Dev-*", "Dev-Complete"],
    remediation: "remove_pattern",
    remove_pattern: "Claimed-Dev-*",
    reason: "Completed tasks should release claims"
  },
]

REMEDIATED_COUNT = 0

For each task in tasks:

  FOR EACH invalid IN INVALID_TAG_COMBINATIONS:

    # Check if this invalid combination exists
    IF invalid.tags:
      # Exact tag matching
      all_present = true
      FOR tag IN invalid.tags:
        IF NOT hasTag(task, tag):
          all_present = false
          BREAK
      IF NOT all_present:
        CONTINUE

    ELIF invalid.tags_pattern:
      # Pattern matching (e.g., "Claimed-Dev-*")
      all_present = true
      FOR pattern IN invalid.tags_pattern:
        IF pattern ends with "*":
          prefix = pattern without "*"
          found = false
          FOR actual_tag IN task.tags:
            IF actual_tag.name starts with prefix:
              found = true
              BREAK
          IF NOT found:
            all_present = false
            BREAK
        ELSE:
          IF NOT hasTag(task, pattern):
            all_present = false
            BREAK
      IF NOT all_present:
        CONTINUE

    # Invalid combination found - apply remediation
    Report: "INVALID STATE: '{task.title}' has invalid tag combination"
    Report: "  Tags: {task.tags as names}"
    Report: "  Reason: {invalid.reason}"

    IF invalid.remediation == "remove":
      IF TAG_CACHE[invalid.remove_tag]:
        mcp__joan__remove_tag_from_task(PROJECT_ID, task.id, TAG_CACHE[invalid.remove_tag])
        Report: "  Remediation: Removed '{invalid.remove_tag}'"

    ELIF invalid.remediation == "remove_pattern":
      prefix = invalid.remove_pattern without "*"
      FOR actual_tag IN task.tags:
        IF actual_tag.name starts with prefix:
          mcp__joan__remove_tag_from_task(PROJECT_ID, task.id, actual_tag.id)
          Report: "  Remediation: Removed '{actual_tag.name}'"

    # Audit trail
    mcp__joan__create_task_comment(task.id,
      "ALS/1
      actor: coordinator
      intent: recovery
      action: invalid-state-remediation
      tags.add: []
      tags.remove: [{removed tag(s)}]
      summary: Auto-fixed invalid tag combination.
      details:
      - reason: {invalid.reason}
      - remediation: {invalid.remediation}")

    REMEDIATED_COUNT++

IF REMEDIATED_COUNT > 0:
  Report: "State machine validation: remediated {REMEDIATED_COUNT} invalid states"
ELSE:
  Report: "State machine validation: all tasks in valid states"
```

**Why this matters:**
- Invalid tag combinations can cause tasks to match multiple queues or none
- Partial worker failures leave inconsistent states
- Auto-remediation restores tasks to processable states
- This catches the exact issue that caused tasks #81/#82 to be stuck

---

## Step 3: Build Priority Queues

Build queues in priority order. Each task goes into AT MOST one queue.

```
BA_QUEUE = []
ARCHITECT_QUEUE = []
DEV_QUEUE = []
REVIEWER_QUEUE = []
OPS_QUEUE = []

For each task in tasks:

  # Priority 1: Dev tasks needing conflict resolution
  IF inColumn(task, "Development")
     AND hasTag(task, "Merge-Conflict")
     AND NOT isClaimedByAnyDev(task):
    DEV_QUEUE.push({task, mode: "conflict"})
    CONTINUE

  # Priority 2: Dev tasks needing rework
  IF inColumn(task, "Development")
     AND hasTag(task, "Rework-Requested")
     AND NOT isClaimedByAnyDev(task)
     AND NOT hasTag(task, "Merge-Conflict"):
    DEV_QUEUE.push({task, mode: "rework"})
    CONTINUE

  # Priority 3: Dev tasks ready for implementation
  IF inColumn(task, "Development")
     AND hasTag(task, "Planned")
     AND NOT isClaimedByAnyDev(task)
     AND NOT hasTag(task, "Rework-Requested")
     AND NOT hasTag(task, "Implementation-Failed")
     AND NOT hasTag(task, "Worktree-Failed"):
    DEV_QUEUE.push({task, mode: "implement"})
    CONTINUE

  # Priority 4: Architect tasks with Plan-Approved (finalize)
  IF inColumn(task, "Analyse")
     AND hasTag(task, "Plan-Pending-Approval")
     AND hasTag(task, "Plan-Approved")
     AND NOT hasTag(task, "Plan-Rejected"):
    ARCHITECT_QUEUE.push({task, mode: "finalize"})
    CONTINUE

  # Priority 4.5: Architect tasks with Plan-Rejected (revise)
  IF inColumn(task, "Analyse")
     AND hasTag(task, "Plan-Pending-Approval")
     AND hasTag(task, "Plan-Rejected"):
    ARCHITECT_QUEUE.push({task, mode: "revise"})
    CONTINUE

  # Priority 5: Architect tasks with Ready (create plan)
  IF inColumn(task, "Analyse")
     AND hasTag(task, "Ready")
     AND NOT hasTag(task, "Plan-Pending-Approval"):
    ARCHITECT_QUEUE.push({task, mode: "plan"})
    CONTINUE

  # Priority 6: BA tasks with Clarification-Answered (reevaluate)
  IF inColumn(task, "Analyse")
     AND hasTag(task, "Needs-Clarification")
     AND hasTag(task, "Clarification-Answered"):
    BA_QUEUE.push({task, mode: "reevaluate"})
    CONTINUE

  # Priority 7: BA tasks in To Do (evaluate)
  IF inColumn(task, "To Do")
     AND NOT hasTag(task, "Ready"):
    BA_QUEUE.push({task, mode: "evaluate"})
    CONTINUE

  # Priority 8: Reviewer tasks ready for review
  IF inColumn(task, "Review")
     AND hasTag(task, "Dev-Complete")
     AND hasTag(task, "Design-Complete")
     AND hasTag(task, "Test-Complete")
     AND NOT hasTag(task, "Review-In-Progress")
     AND NOT hasTag(task, "Review-Approved")
     AND NOT hasTag(task, "Rework-Requested"):
    REVIEWER_QUEUE.push({task})
    CONTINUE

  # Priority 8b: Rework-Complete triggers re-review
  IF inColumn(task, "Review")
     AND hasTag(task, "Rework-Complete")
     AND NOT hasTag(task, "Review-In-Progress")
     AND NOT hasTag(task, "Review-Approved")
     AND NOT hasTag(task, "Rework-Requested"):
    REVIEWER_QUEUE.push({task})
    CONTINUE

  # Priority 9: Ops tasks with Review-Approved AND Ops-Ready
  # NOTE: Check both Review AND Deploy to handle column drift (task moved before Ops processed)
  IF (inColumn(task, "Review") OR inColumn(task, "Deploy"))
     AND hasTag(task, "Review-Approved")
     AND hasTag(task, "Ops-Ready"):
    OPS_QUEUE.push({task, mode: "merge"})
    CONTINUE

  # Priority 10: Ops tasks with Rework-Requested in Review
  IF inColumn(task, "Review")
     AND hasTag(task, "Rework-Requested")
     AND NOT hasTag(task, "Review-Approved"):
    OPS_QUEUE.push({task, mode: "rework"})
    CONTINUE

  # DIAGNOSTIC: Identify tasks with workflow tags that didn't match any queue
  # This catches edge cases and helps diagnose stuck tasks
  workflow_tags_present = []
  FOR tagName IN WORKFLOW_TAGS:
    IF hasTag(task, tagName):
      workflow_tags_present.push(tagName)

  IF workflow_tags_present.length > 0:
    Report: "UNQUEUED: '{task.title}' has tags {workflow_tags_present} in column '{task.column}' but didn't match any queue condition"

Report queue sizes:
"Queues: BA={BA_QUEUE.length}, Architect={ARCHITECT_QUEUE.length}, Dev={DEV_QUEUE.length}, Reviewer={REVIEWER_QUEUE.length}, Ops={OPS_QUEUE.length}"
```

---

## Step 4: Dispatch Workers (MCP Proxy Pattern)

**ARCHITECTURE:** Workers do NOT have MCP access. The coordinator:
1. Builds a complete "work package" with all task data
2. Dispatches worker with work package via prompt
3. Receives structured JSON result from worker
4. Executes MCP actions on behalf of worker
5. Verifies post-conditions

This pattern ensures workers are isolated, parallelizable, and fault-tolerant.

```
DISPATCHED = 0
RESULTS = []  # Collect worker results for batch processing

# Helper: Build Work Package
def build_work_package(task, mode, extra={}):
  # Fetch full task details and comments
  full_task = mcp__joan__get_task(task.id)
  comments = mcp__joan__list_task_comments(task.id)

  return {
    "task_id": task.id,
    "task_title": task.title,
    "task_description": full_task.description,
    "task_tags": [t.name for t in full_task.tags],
    "task_column": get_column_name(full_task.column_id),
    "task_comments": comments,
    "mode": mode,
    "project_id": PROJECT_ID,
    "project_name": PROJECT_NAME,
    **extra
  }

# 4a: Dispatch BA worker (one task)
IF BA_ENABLED AND BA_QUEUE.length > 0:
  item = BA_QUEUE.shift()
  work_package = build_work_package(item.task, item.mode)

  Report: "Dispatching BA worker for '{item.task.title}' (mode: {item.mode})"

  result = Task tool call:
    subagent_type: "business-analyst"
    model: MODEL
    prompt: |
      You are a Business Analyst worker. Process this task and return a structured JSON result.

      ## Work Package
      ```json
      {work_package as JSON}
      ```

      ## Instructions
      Follow /agents:ba-worker logic for mode "{item.mode}".

      ## Required Output
      Return ONLY a JSON object with this structure (no markdown, no explanation):
      ```json
      {
        "success": true/false,
        "summary": "What you did",
        "joan_actions": {
          "add_tags": ["tag names to add"],
          "remove_tags": ["tag names to remove"],
          "add_comment": "ALS/1 format comment",
          "move_to_column": "column name or null"
        },
        "worker_type": "ba",
        "task_id": "{task.id}",
        "needs_human": "reason if blocked, or null"
      }
      ```

  RESULTS.push({worker: "ba", task: item.task, result: result})
  DISPATCHED++

# 4b: Dispatch Architect worker (one task)
IF ARCHITECT_ENABLED AND ARCHITECT_QUEUE.length > 0:
  item = ARCHITECT_QUEUE.shift()
  work_package = build_work_package(item.task, item.mode)

  Report: "Dispatching Architect worker for '{item.task.title}' (mode: {item.mode})"

  result = Task tool call:
    subagent_type: "architect"
    model: MODEL
    prompt: |
      You are an Architect worker. Process this task and return a structured JSON result.

      ## Work Package
      ```json
      {work_package as JSON}
      ```

      ## Instructions
      Follow /agents:architect-worker logic for mode "{item.mode}".

      ## Required Output
      Return ONLY a JSON object with this structure:
      ```json
      {
        "success": true/false,
        "summary": "What you did",
        "joan_actions": {
          "add_tags": ["tag names"],
          "remove_tags": ["tag names"],
          "add_comment": "ALS/1 format comment",
          "move_to_column": "column name or null",
          "update_description": "new description with plan, or null"
        },
        "worker_type": "architect",
        "task_id": "{task.id}",
        "needs_human": "reason if blocked, or null"
      }
      ```

  RESULTS.push({worker: "architect", task: item.task, result: result})
  DISPATCHED++

# 4c: Dispatch Dev workers (one per available dev)
IF DEVS_ENABLED:
  available_devs = find_available_devs()

  FOR EACH dev_id IN available_devs:
  IF DEV_QUEUE.length > 0:
    item = DEV_QUEUE.shift()
    task = item.task

    # ATOMIC CLAIM before dispatch (coordinator does this, not worker)
    mcp__joan__add_tag_to_task(PROJECT_ID, task.id, TAG_CACHE["Claimed-Dev-{dev_id}"])
    Wait 1 second
    updated_task = mcp__joan__get_task(task.id)

    IF claim verified (Claimed-Dev-{dev_id} tag present):
      work_package = build_work_package(task, item.mode, {"dev_id": dev_id})

      Report: "Dispatching Dev worker {dev_id} for '{task.title}' (mode: {item.mode})"

      result = Task tool call:
        subagent_type: "implementation-worker"
        model: MODEL
        prompt: |
          You are Dev Worker {dev_id}. Implement this task and return a structured JSON result.

          ## Work Package
          ```json
          {work_package as JSON}
          ```

          ## Instructions
          Follow /agents:dev-worker logic for mode "{item.mode}".
          IMPORTANT: Create a git worktree at ../worktrees/{task.id} for isolated development.

          ## Required Output
          Return ONLY a JSON object:
          ```json
          {
            "success": true/false,
            "summary": "What you implemented",
            "joan_actions": {
              "add_tags": ["Dev-Complete", "Design-Complete", "Test-Complete"],
              "remove_tags": ["Claimed-Dev-{dev_id}", "Planned"],
              "add_comment": "ALS/1 format",
              "move_to_column": "Review"
            },
            "git_actions": {
              "branch_created": "feature/...",
              "files_changed": ["file1.ts", "file2.ts"],
              "commit_made": true,
              "pr_created": {"number": N, "url": "..."}
            },
            "worker_type": "dev",
            "task_id": "{task.id}",
            "needs_human": null
          }
          ```

      RESULTS.push({worker: "dev", dev_id: dev_id, task: task, result: result})
      DISPATCHED++

    ELSE:
      # Claim failed - another coordinator got it
      mcp__joan__remove_tag_from_task(PROJECT_ID, task.id, TAG_CACHE["Claimed-Dev-{dev_id}"])
      Continue

# 4d: Dispatch Reviewer worker (one task)
IF REVIEWER_ENABLED AND REVIEWER_QUEUE.length > 0:
  item = REVIEWER_QUEUE.shift()
  work_package = build_work_package(item.task, "review")

  Report: "Dispatching Reviewer worker for '{item.task.title}'"

  result = Task tool call:
    subagent_type: "code-reviewer"
    model: MODEL
    prompt: |
      You are a Code Reviewer worker. Review this task and return a structured JSON result.

      ## Work Package
      ```json
      {work_package as JSON}
      ```

      ## Instructions
      Follow /agents:reviewer-worker logic.

      ## Required Output
      Return ONLY a JSON object:
      ```json
      {
        "success": true/false,
        "summary": "Review findings",
        "joan_actions": {
          "add_tags": ["Review-Approved"] or ["Rework-Requested", "Planned"],
          "remove_tags": ["Review-In-Progress"] or completion tags if rejecting,
          "add_comment": "ALS/1 format with review details",
          "move_to_column": null or "Development" if rework needed
        },
        "worker_type": "reviewer",
        "task_id": "{task.id}",
        "needs_human": null
      }
      ```

  RESULTS.push({worker: "reviewer", task: item.task, result: result})
  DISPATCHED++

# 4e: Dispatch Ops worker (one task)
IF OPS_ENABLED AND OPS_QUEUE.length > 0:
  item = OPS_QUEUE.shift()
  work_package = build_work_package(item.task, item.mode)

  Report: "Dispatching Ops worker for '{item.task.title}' (mode: {item.mode})"

  result = Task tool call:
    subagent_type: "ops"
    model: MODEL
    prompt: |
      You are an Ops worker. Handle integration operations and return a structured JSON result.

      ## Work Package
      ```json
      {work_package as JSON}
      ```

      ## Instructions
      Follow /agents:ops-worker logic for mode "{item.mode}".

      ## Required Output
      Return ONLY a JSON object:
      ```json
      {
        "success": true/false,
        "summary": "What you did",
        "joan_actions": {
          "add_tags": [],
          "remove_tags": ["Review-Approved", "Ops-Ready"],
          "add_comment": "ALS/1 format",
          "move_to_column": "Deploy" or "Development" if conflict
        },
        "git_actions": {
          "merged_to": "develop",
          "commit_sha": "..."
        },
        "worker_type": "ops",
        "task_id": "{task.id}",
        "needs_human": null or "reason"
      }
      ```

  RESULTS.push({worker: "ops", task: item.task, result: result})
  DISPATCHED++

Report: "Dispatched {DISPATCHED} workers"
```

---

## Step 4f: Execute Worker Results (MCP Proxy)

After all workers complete, execute their requested MCP actions.
**Enhanced error handling ensures failures are recorded and claims are released.**

```
PARSE_FAILURES = 0

FOR EACH {worker, task, result, dev_id} IN RESULTS:

  Report: "Processing result from {worker} worker for '{task.title}'"

  # 1. Parse result (handle both JSON and text responses)
  parsed = parse_json_from_result(result)

  IF parsed is null:
    PARSE_FAILURES++
    Report: "ERROR: Unparseable result from {worker} worker for '{task.title}'"

    # Log failure details for debugging
    raw_preview = first 500 chars of result
    Report: "  Raw result preview: {raw_preview}"

    # Record the failure in task comments for audit trail
    mcp__joan__create_task_comment(task.id,
      "ALS/1
      actor: coordinator
      intent: error
      action: result-parse-failure
      tags.add: []
      tags.remove: []
      summary: Worker returned unparseable result.
      details:
      - worker_type: {worker}
      - raw_result_preview: {raw_preview}
      - action: Task will be re-processable on next poll cycle")

    # For dev workers, release the claim so task can be re-processed
    IF worker == "dev" AND dev_id:
      claim_tag = "Claimed-Dev-{dev_id}"
      IF TAG_CACHE[claim_tag]:
        mcp__joan__remove_tag_from_task(PROJECT_ID, task.id, TAG_CACHE[claim_tag])
        Report: "  Released claim {claim_tag} (task will be retried)"

    CONTINUE

  # 1b. Validate required fields
  required_fields = ["success", "summary", "joan_actions", "worker_type", "task_id"]
  missing_fields = []
  FOR field IN required_fields:
    IF field NOT IN parsed:
      missing_fields.push(field)

  IF missing_fields.length > 0:
    PARSE_FAILURES++
    Report: "ERROR: Missing required fields in {worker} result: {missing_fields}"

    mcp__joan__create_task_comment(task.id,
      "ALS/1
      actor: coordinator
      intent: error
      action: result-validation-failure
      tags.add: []
      tags.remove: []
      summary: Worker result missing required fields.
      details:
      - worker_type: {worker}
      - missing_fields: {missing_fields}
      - action: Task will be re-processable on next poll cycle")

    # Release dev claims
    IF worker == "dev" AND dev_id:
      claim_tag = "Claimed-Dev-{dev_id}"
      IF TAG_CACHE[claim_tag]:
        mcp__joan__remove_tag_from_task(PROJECT_ID, task.id, TAG_CACHE[claim_tag])
        Report: "  Released claim {claim_tag} (task will be retried)"

    CONTINUE

  # 2. Check success status
  IF NOT parsed.success:
    Report: "Worker reported FAILURE: {parsed.summary}"
    IF parsed.needs_human:
      Report: "Needs human intervention: {parsed.needs_human}"
      # Add failure tag for visibility
      mcp__joan__add_tag_to_task(PROJECT_ID, task.id, TAG_CACHE["Implementation-Failed"])

    # Release dev claims on failure
    IF worker == "dev" AND dev_id:
      claim_tag = "Claimed-Dev-{dev_id}"
      IF TAG_CACHE[claim_tag]:
        mcp__joan__remove_tag_from_task(PROJECT_ID, task.id, TAG_CACHE[claim_tag])
        Report: "  Released claim {claim_tag}"

    CONTINUE

  # 3. Execute joan_actions
  actions = parsed.joan_actions

  # 3a. Add tags
  IF actions.add_tags AND actions.add_tags.length > 0:
    FOR tag_name IN actions.add_tags:
      IF TAG_CACHE[tag_name]:
        mcp__joan__add_tag_to_task(PROJECT_ID, task.id, TAG_CACHE[tag_name])
        Report: "  Added tag: {tag_name}"
      ELSE:
        Report: "  WARNING: Unknown tag '{tag_name}', skipping"

  # 3b. Remove tags
  IF actions.remove_tags AND actions.remove_tags.length > 0:
    FOR tag_name IN actions.remove_tags:
      IF TAG_CACHE[tag_name]:
        mcp__joan__remove_tag_from_task(PROJECT_ID, task.id, TAG_CACHE[tag_name])
        Report: "  Removed tag: {tag_name}"

  # 3c. Add comment
  IF actions.add_comment AND actions.add_comment.length > 0:
    mcp__joan__create_task_comment(task.id, actions.add_comment)
    Report: "  Added comment"

  # 3d. Update description (for architect plans)
  IF actions.update_description:
    mcp__joan__update_task(task.id, description=actions.update_description)
    Report: "  Updated task description"

  # 3e. Move to column
  IF actions.move_to_column AND COLUMN_CACHE[actions.move_to_column]:
    mcp__joan__update_task(task.id, column_id=COLUMN_CACHE[actions.move_to_column])
    Report: "  Moved to column: {actions.move_to_column}"

  # 4. Verify post-conditions
  updated_task = mcp__joan__get_task(task.id)

  # Verify tags were applied
  FOR tag_name IN (actions.add_tags or []):
    IF TAG_CACHE[tag_name] AND NOT hasTag(updated_task, tag_name):
      Report: "  WARNING: Tag '{tag_name}' not applied, retrying..."
      mcp__joan__add_tag_to_task(PROJECT_ID, task.id, TAG_CACHE[tag_name])

  # Verify tags were removed
  FOR tag_name IN (actions.remove_tags or []):
    IF TAG_CACHE[tag_name] AND hasTag(updated_task, tag_name):
      Report: "  WARNING: Tag '{tag_name}' not removed, retrying..."
      mcp__joan__remove_tag_from_task(PROJECT_ID, task.id, TAG_CACHE[tag_name])

  Report: "Completed processing for '{task.title}': {parsed.summary}"

# Summary
IF PARSE_FAILURES > 0:
  Report: "WARNING: {PARSE_FAILURES} worker results failed to parse (tasks will be retried)"

Report: "All {RESULTS.length} worker results processed ({RESULTS.length - PARSE_FAILURES} successful, {PARSE_FAILURES} failed)"
```

### Helper: parse_json_from_result(result)

```
# Workers return text that should contain JSON
# Extract JSON from the result, handling various formats

1. Try direct JSON.parse(result)
2. If fails, look for ```json ... ``` block and extract
3. If fails, look for { ... } pattern and extract
4. If all fail, return null
```

### Helper: find_available_devs()

```
claimed_devs = []
For each task in all tasks:
  For N in 1..DEV_COUNT:
    IF hasTag("Claimed-Dev-{N}"):
      claimed_devs.push(N)

available = []
For N in 1..DEV_COUNT:
  IF N not in claimed_devs:
    available.push(N)

RETURN available
```

---

## Step 5: Handle Idle / Exit / Restart

```
# Track poll cycles for context management
POLL_CYCLE_COUNT++

# Calculate pending work (tasks waiting for human tags)
PENDING_HUMAN = count tasks with:
  - Plan-Pending-Approval (no Plan-Approved) → waiting for human approval
  - Review-Approved (no Ops-Ready) → waiting for human merge approval
  - Implementation-Failed or Worktree-Failed → waiting for human fix

IF DISPATCHED == 0:
  IDLE_COUNT++

  Report: "Poll complete: dispatched 0 workers"
  IF PENDING_HUMAN > 0:
    Report: "  {PENDING_HUMAN} tasks awaiting human action in Joan UI"
  Report: "  Idle count: {IDLE_COUNT}/{MAX_IDLE}"
  Report: "  Poll cycle: {POLL_CYCLE_COUNT}/{MAX_POLL_CYCLES}"

  IF NOT LOOP_MODE:
    Report: "Single pass complete. Exiting."
    EXIT

  IF IDLE_COUNT >= MAX_IDLE:
    Report: "Max idle polls reached. Shutting down coordinator."
    EXIT

  Report: "Sleeping {POLL_INTERVAL} minutes..."
  Wait POLL_INTERVAL minutes

ELSE:
  IDLE_COUNT = 0  # Reset on activity
  Report: "Poll complete: dispatched {DISPATCHED} workers"
  Report: "  Poll cycle: {POLL_CYCLE_COUNT}/{MAX_POLL_CYCLES}"

  IF LOOP_MODE:
    Report: "Re-polling in 30 seconds..."
    Wait 30 seconds

IF NOT LOOP_MODE:
  Report: "Single pass complete. Exiting."
  EXIT

# Context Window Management: Restart to clear context after N cycles
# This prevents context bloat from causing queue-building logic to fail
IF LOOP_MODE AND POLL_CYCLE_COUNT >= MAX_POLL_CYCLES:
  Report: ""
  Report: "╔══════════════════════════════════════════════════════════════════╗"
  Report: "║  CONTEXT REFRESH: Reached {MAX_POLL_CYCLES} poll cycles.                          ║"
  Report: "║  Restarting coordinator to clear context and prevent drift...   ║"
  Report: "╚══════════════════════════════════════════════════════════════════╝"
  Report: ""
  Report: "To run continuously, use a wrapper script:"
  Report: "  while true; do"
  Report: "    claude /agents:dispatch --loop"
  Report: "    [ $? -ne 100 ] && break"
  Report: "    echo 'Restarting coordinator with fresh context...'"
  Report: "  done"
  Report: ""

  # Exit with special code 100 = restart requested
  # A wrapper script can detect this and restart the coordinator
  EXIT with code 100

# Continue to next iteration
```

**Why context refresh matters:**
- Long-running coordinators accumulate context that can cause instruction drift
- After many poll cycles, the model may skip queue-building logic or misparse results
- Restarting with fresh context ensures reliable workflow execution
- Exit code 100 signals "restart requested" vs normal exit (0) or error (1)

---

## Constraints

**CRITICAL - Autonomous Operation:**
- NEVER ask the user questions or prompt for input
- NEVER offer choices like "Would you like me to..." or "Should I..."
- NEVER pause to wait for user confirmation
- Human interaction happens via TAGS in Joan UI, not via conversation
- In loop mode: poll → dispatch → sleep → repeat (no interruptions)
- Only exit when: (a) single-pass mode completes, (b) max idle polls reached, or (c) max poll cycles reached (context refresh)

**Operational Rules:**
- NEVER parse comments for triggers (tags only)
- ALWAYS claim dev tasks before dispatching
- Dispatch at most ONE worker per type per cycle (except devs)
- Workers are single-pass - they exit after completing their task
- Report all queue sizes and dispatch actions for observability

**CRITICAL - Worker Dispatch Format:**
- ALWAYS use the EXACT command format: `/agents:dev-worker --task=... --dev=... --mode=...`
- NEVER create custom prompts with instructions like "checkout the branch" or task lists
- The worker commands (dev-worker.md) contain ALL the logic including worktree creation
- Custom prompts bypass worktree creation and cause branch conflicts between parallel workers
- The "Task Details" section is ONLY contextual reference - do NOT expand it into instructions

---

## Examples

```bash
# Single pass - dispatch workers once, then exit
/agents:dispatch

# Continuous loop - dispatch until idle
/agents:dispatch --loop

# Extended idle threshold (2 hours at 10-min intervals)
/agents:dispatch --loop --max-idle=12
```

Begin coordination now.
