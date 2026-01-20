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
  Step 1: Cache Tags
  Step 2: Fetch Tasks
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
  IF inColumn(task, "Review")
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

## Step 4: Dispatch Workers

**IMPORTANT:** Workers run in FOREGROUND (not background) to ensure MCP access if needed.
Dispatch at most ONE worker per type per cycle (except devs which can be up to DEV_COUNT).

**CRITICAL - USE EXACT COMMAND FORMAT:**
- You MUST invoke worker commands EXACTLY as shown (e.g., `/agents:dev-worker --task=... --dev=... --mode=...`)
- DO NOT create custom prompts or inline instructions
- DO NOT write "checkout the branch" or any other custom task steps
- The worker command files (dev-worker.md, etc.) contain all the logic including WORKTREE CREATION
- If you write custom prompts, workers will NOT create worktrees and will cause branch conflicts
- The "Task Details" section is ONLY for reference - the worker command handles everything

```
DISPATCHED = 0

# 4a: Dispatch BA worker (one task)
IF BA_ENABLED AND BA_QUEUE.length > 0:
  item = BA_QUEUE.shift()
  task = item.task

  Dispatch BA worker:
    Task tool call:
      subagent_type: "business-analyst"
      model: MODEL
      prompt: |
        /agents:ba-worker --task={task.id} --mode={item.mode}

        Task Details (for reference):
        - ID: {task.id}
        - Title: {task.title}
        - Description: {task.description}
        - Current Tags: {task.tags}
  DISPATCHED++

# 4b: Dispatch Architect worker (one task)
IF ARCHITECT_ENABLED AND ARCHITECT_QUEUE.length > 0:
  item = ARCHITECT_QUEUE.shift()
  task = item.task

  Dispatch Architect worker:
    Task tool call:
      subagent_type: "architect"
      model: MODEL
      prompt: |
        /agents:architect-worker --task={task.id} --mode={item.mode}

        Task Details (for reference):
        - ID: {task.id}
        - Title: {task.title}
        - Description: {task.description}
        - Current Tags: {task.tags}
  DISPATCHED++

# 4c: Dispatch Dev workers (one per available dev)
IF DEVS_ENABLED:
  available_devs = find_available_devs()  # Devs not currently claimed

  FOR EACH dev_id IN available_devs:
  IF DEV_QUEUE.length > 0:
    item = DEV_QUEUE.shift()
    task = item.task

    # ATOMIC CLAIM before dispatch
    1. mcp__joan__add_tag_to_task(PROJECT_ID, task.id, TAG_CACHE["Claimed-Dev-{dev_id}"])
    2. Wait 1 second
    3. Re-fetch task: mcp__joan__get_task(task.id)
    4. Verify claim succeeded (your tag present, no other Claimed-Dev-* tags)

    IF claim succeeded:
      Dispatch Dev worker:
        Task tool call:
          subagent_type: "implementation-worker"
          model: MODEL
          prompt: |
            /agents:dev-worker --task={task.id} --dev={dev_id} --mode={item.mode}

            Task Details (for reference only - worker command handles everything):
            - ID: {task.id}
            - Title: {task.title}

            IMPORTANT: The dev-worker command creates a WORKTREE for isolated development.
            Do NOT add custom instructions. The command file has all the logic.
      DISPATCHED++

    ELSE:
      # Another coordinator/dev claimed it - skip
      Remove your claim tag if present
      Continue to next task

# 4d: Dispatch Reviewer worker (one task)
IF REVIEWER_ENABLED AND REVIEWER_QUEUE.length > 0:
  item = REVIEWER_QUEUE.shift()
  task = item.task

  Dispatch Reviewer worker:
    Task tool call:
      subagent_type: "code-reviewer"
      model: MODEL
      prompt: |
        /agents:reviewer-worker --task={task.id}

        Task Details (for reference):
        - ID: {task.id}
        - Title: {task.title}
        - Description: {task.description}
        - Current Tags: {task.tags}
  DISPATCHED++

# 4e: Dispatch Ops worker (one task)
IF OPS_ENABLED AND OPS_QUEUE.length > 0:
  item = OPS_QUEUE.shift()
  task = item.task

  Dispatch Ops worker:
    Task tool call:
      subagent_type: "ops"
      model: MODEL
      prompt: |
        /agents:ops-worker --task={task.id} --mode={item.mode}

        Task Details (for reference):
        - ID: {task.id}
        - Title: {task.title}
        - Description: {task.description}
        - Current Tags: {task.tags}
  DISPATCHED++

Report: "Dispatched {DISPATCHED} workers"
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
