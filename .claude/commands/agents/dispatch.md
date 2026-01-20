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
   TAG_CACHE = {}
```

---

## Main Loop

```
WHILE true:
  Step 1: Cache Tags and Columns
  Step 2: Fetch Tasks
  Step 2b: Recover Stale Claims (self-healing)
  Step 2c: Detect and Clean Anomalies (self-healing)
  Step 3: Build Priority Queues
  Step 4: Dispatch Workers
  Step 5: Handle Idle / Exit

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
      # This is informational - may need Plan-Pending-Approval added or may be stale

Report: "Anomaly detection complete"
```

**Why this matters:**
- Partial worker failures leave inconsistent tag states
- Manual task moves in Joan UI bypass tag cleanup
- Without detection, tasks get stuck in limbo forever
- Auto-cleanup makes the system self-healing

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

```
FOR EACH {worker, task, result} IN RESULTS:

  Report: "Processing result from {worker} worker for '{task.title}'"

  # 1. Parse result (handle both JSON and text responses)
  parsed = parse_json_from_result(result)

  IF parsed is null OR not valid:
    Report: "WARNING: Could not parse result from {worker} worker"
    Report: "Raw result: {result}"
    CONTINUE

  # 2. Check success status
  IF NOT parsed.success:
    Report: "Worker reported FAILURE: {parsed.summary}"
    IF parsed.needs_human:
      Report: "Needs human intervention: {parsed.needs_human}"
      # Add failure tag for visibility
      mcp__joan__add_tag_to_task(PROJECT_ID, task.id, TAG_CACHE["Implementation-Failed"])
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

Report: "All {RESULTS.length} worker results processed"
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

## Step 5: Handle Idle / Exit

```
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

  IF LOOP_MODE:
    Report: "Re-polling in 30 seconds..."
    Wait 30 seconds

IF NOT LOOP_MODE:
  Report: "Single pass complete. Exiting."
  EXIT

# Continue to next iteration
```

---

## Constraints

**CRITICAL - Autonomous Operation:**
- NEVER ask the user questions or prompt for input
- NEVER offer choices like "Would you like me to..." or "Should I..."
- NEVER pause to wait for user confirmation
- Human interaction happens via TAGS in Joan UI, not via conversation
- In loop mode: poll → dispatch → sleep → repeat (no interruptions)
- Only exit when: (a) single-pass mode completes, or (b) max idle polls reached

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
