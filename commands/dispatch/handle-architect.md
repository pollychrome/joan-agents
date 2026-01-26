---
description: Handle Architect queue - create plans, finalize approved plans
argument-hint: [--task=UUID] [--mode=plan|finalize|revise|advisory] [--all]
allowed-tools: Bash, Read, Task
---

# Architect Handler

Process Architect queue: create implementation plans, finalize approved plans, provide conflict guidance.

## Arguments

- `--task=UUID` → Process single task (event-driven mode)
- `--mode=plan|finalize|revise|advisory` → Operation mode
- `--all` → Process all Architect tasks in queue (polling mode)

## Configuration

```
config = JSON.parse(read(".joan-agents.json"))
PROJECT_ID = config.projectId
PROJECT_NAME = config.projectName

# Model resolution: settings.models.architect → settings.model → "opus" (built-in default)
MODEL = config.settings.models?.architect OR config.settings.model OR "opus"

MODE = config.settings.mode OR "standard"
TIMEOUT_ARCHITECT = config.settings.workerTimeouts.architect OR 20

IF NOT config.agents.architect.enabled:
  Report: "Architect agent disabled in config"
  EXIT
```

## Single Task Mode (Event-Driven)

```
IF TASK_ID provided:
  Report: "Architect Handler: Processing task {TASK_ID} mode={OPERATION_MODE}"

  # Use shared smart payload extraction (see helpers.md)
  payload_data = extractSmartPayload(TASK_ID, PROJECT_ID)
  task = payload_data.task
  handoff_context = payload_data.handoff_context
  recent_comments = payload_data.recent_comments
  COLUMN_CACHE = payload_data.COLUMN_CACHE

  # Build tag set (see helpers.md)
  TAG_SET = buildTagSet(task.tags)

  # Verify task is in expected state
  IF NOT (task.column_name == "Analyse" OR task.column_id == COLUMN_CACHE["Analyse"] OR
          (task.column_name == "Review" OR task.column_id == COLUMN_CACHE["Review"]) AND TAG_SET.has("Invoke-Architect")):
    Report: "Task not in expected column for Architect, skipping"
    EXIT

  # Auto-detect mode if not provided
  IF NOT OPERATION_MODE:
    IF TAG_SET.has("Invoke-Architect") AND NOT TAG_SET.has("Architect-Assist-Complete"):
      OPERATION_MODE = "advisory-conflict"
    ELIF TAG_SET.has("Plan-Pending-Approval") AND TAG_SET.has("Plan-Approved"):
      OPERATION_MODE = "finalize"
    ELIF TAG_SET.has("Plan-Pending-Approval") AND TAG_SET.has("Plan-Rejected"):
      OPERATION_MODE = "revise"
    ELIF TAG_SET.has("Ready") AND NOT TAG_SET.has("Plan-Pending-Approval"):
      OPERATION_MODE = "plan"
    ELSE:
      Report: "Cannot determine Architect mode from tags: {TAG_SET}"
      EXIT

  # Build work package
  WORK_PACKAGE = {
    task_id: task.id,
    task_title: task.title,
    task_description: task.description,
    task_tags: Array.from(TAG_SET),
    mode: OPERATION_MODE,
    workflow_mode: MODE,
    project_id: PROJECT_ID,
    project_name: PROJECT_NAME,
    handoff_context: handoff_context,
    recent_comments: recent_comments
  }

  GOTO DISPATCH_WORKER
```

## Batch Mode (Polling)

When `--all` is provided (legacy mode, no smart payload):

```
IF ALL_MODE:
  Report: "Architect Handler: Processing all Architect tasks"

  tasks = mcp__joan__list_tasks(project_id: PROJECT_ID)
  columns = mcp__joan__list_columns(PROJECT_ID)

  # Build caches
  COLUMN_CACHE = {}
  FOR col IN columns:
    COLUMN_CACHE[col.name] = col.id

  TAG_INDEX = {}
  FOR task IN tasks:
    tagSet = Set()
    FOR tag IN task.tags:
      tagSet.add(tag.name)
    TAG_INDEX[task.id] = tagSet

  # Build Architect queue
  ARCHITECT_QUEUE = []

  FOR task IN tasks:
    taskId = task.id
    tags = TAG_INDEX[taskId]

    # P0: Advisory mode (invocation)
    IF task.column_id == COLUMN_CACHE["Review"] AND
       tags.has("Invoke-Architect") AND
       NOT tags.has("Architect-Assist-Complete"):
      ARCHITECT_QUEUE.unshift({task, mode: "advisory-conflict"})
      CONTINUE

    # Finalize approved plan
    IF task.column_id == COLUMN_CACHE["Analyse"] AND
       tags.has("Plan-Pending-Approval") AND
       tags.has("Plan-Approved") AND
       NOT tags.has("Plan-Rejected"):
      ARCHITECT_QUEUE.push({task, mode: "finalize"})
      CONTINUE

    # Revise rejected plan
    IF task.column_id == COLUMN_CACHE["Analyse"] AND
       tags.has("Plan-Pending-Approval") AND
       tags.has("Plan-Rejected"):
      ARCHITECT_QUEUE.push({task, mode: "revise"})
      CONTINUE

    # Create new plan
    IF task.column_id == COLUMN_CACHE["Analyse"] AND
       tags.has("Ready") AND
       NOT tags.has("Plan-Pending-Approval"):
      ARCHITECT_QUEUE.push({task, mode: "plan"})

  Report: "Architect queue: {ARCHITECT_QUEUE.length} tasks"

  IF ARCHITECT_QUEUE.length == 0:
    Report: "No Architect tasks to process"
    EXIT

  # Check pipeline gate for plan mode tasks
  IF hasTasksInDevPipeline(tasks, TAG_INDEX, COLUMN_CACHE):
    Report: "Pipeline gate BLOCKED - task in Development/Review, skipping new plans"
    ARCHITECT_QUEUE = ARCHITECT_QUEUE.filter(item => item.mode != "plan")

  IF ARCHITECT_QUEUE.length == 0:
    Report: "All remaining tasks blocked by pipeline gate"
    EXIT

  # Process first task
  item = ARCHITECT_QUEUE[0]
  task = item.task
  mode = item.mode

  full_task = mcp__joan__get_task(task.id)
  comments = mcp__joan__list_task_comments(task.id)

  WORK_PACKAGE = {
    task_id: full_task.id,
    task_title: full_task.title,
    task_description: full_task.description,
    task_tags: extractTagNames(full_task.tags),
    mode: mode,
    workflow_mode: MODE,
    project_id: PROJECT_ID,
    project_name: PROJECT_NAME,
    handoff_context: null,
    recent_comments: comments
  }

  GOTO DISPATCH_WORKER
```

## DISPATCH_WORKER

```
Report: "**Architect worker dispatched for '{WORK_PACKAGE.task_title}' (mode: {WORK_PACKAGE.mode})**"

logWorkerActivity(".", "Architect", "START", "task=#{WORK_PACKAGE.task_id} '{WORK_PACKAGE.task_title}' mode={WORK_PACKAGE.mode}")

max_turns = TIMEOUT_ARCHITECT * 2

Task agent:
  subagent_type: architect-worker
  model: MODEL
  max_turns: max_turns
  prompt: |
    ## Architect Worker - Phase 3 Result Protocol

    Process this task and return a structured result.

    ## Work Package
    ```json
    {JSON.stringify(WORK_PACKAGE, null, 2)}
    ```

    ## Mode: {WORK_PACKAGE.mode}

    ### If mode == "plan":
    - Analyze codebase and create detailed implementation plan
    - Return result_type "plan_created"
    - Include plan content in output.plan_description

    ### If mode == "finalize":
    - Finalize the approved plan
    - Return result_type "plan_finalized"

    ### If mode == "revise":
    - Review rejection feedback in recent_comments
    - Update plan based on feedback
    - Return result_type "plan_revised"

    ### If mode == "advisory-conflict":
    - Analyze merge conflict details in recent_comments
    - Provide resolution strategy
    - Return result_type "advisory_complete"

    ## Return Format (Phase 3)

    Return a JSON object with:
    ```json
    {
      "success": true,
      "result_type": "plan_created" | "plan_finalized" | "plan_revised" | "advisory_complete",
      "structured_comment": { ... },
      "output": {
        "plan_description": "Updated task description with plan (for plan_created/plan_revised)",
        "resolution_strategy": "Strategy for conflict resolution (for advisory_complete)"
      }
    }
    ```

    ## Structured Comment (server generates ALS format)

    For plan_created:
    ```json
    "structured_comment": {
      "actor": "architect", "intent": "plan", "action": "plan-created",
      "summary": "Brief summary of the plan",
      "key_decisions": ["Decision 1", "Decision 2"],
      "files_of_interest": ["file1.ts", "file2.ts"]
    }
    ```

    For plan_finalized (handoff to dev):
    ```json
    "structured_comment": {
      "actor": "architect", "intent": "handoff", "action": "context-handoff",
      "from_stage": "architect", "to_stage": "dev",
      "summary": "Plan finalized, ready for implementation",
      "key_decisions": ["Key architectural decisions"],
      "files_of_interest": ["Files to modify"],
      "warnings": ["Any concerns"]
    }
    ```

    For advisory_complete:
    ```json
    "structured_comment": {
      "actor": "architect", "intent": "advisory", "action": "conflict-resolution",
      "summary": "Resolution strategy summary",
      "metadata": {"resolution_strategy": "Detailed strategy"}
    }
    ```

    IMPORTANT: Do NOT return joan_actions. Joan backend handles state transitions automatically.

WORKER_RESULT = Task.result

# Log worker completion
IF WORKER_RESULT.success:
  logWorkerActivity(".", "Architect", "COMPLETE", "task=#{WORK_PACKAGE.task_id} success result_type={WORKER_RESULT.result_type}")
ELSE:
  logWorkerActivity(".", "Architect", "FAIL", "task=#{WORK_PACKAGE.task_id} error={WORKER_RESULT.error}")

# Process worker result
GOTO PROCESS_RESULT
```

## PROCESS_RESULT (Phase 3)

```
# Use shared result submission (see helpers.md)
submitWorkerResult("architect-worker", WORKER_RESULT, WORK_PACKAGE, PROJECT_ID)

# YOLO mode: Auto-approve plan immediately after creation
IF MODE == "yolo" AND WORKER_RESULT.result_type == "plan_created":
  Report: "  [YOLO] Auto-approved plan - backend will handle Plan-Approved tag"
```

## Pipeline Gate Check

```
def hasTasksInDevPipeline(tasks, TAG_INDEX, COLUMN_CACHE):
  FOR task IN tasks:
    # Check Development column
    IF task.column_id == COLUMN_CACHE["Development"]:
      IF TAG_INDEX[task.id].has("Planned") OR
         TAG_INDEX[task.id].has("Claimed-Dev-1") OR
         TAG_INDEX[task.id].has("Rework-Requested"):
        RETURN true

    # Check Review column
    IF task.column_id == COLUMN_CACHE["Review"]:
      IF NOT TAG_INDEX[task.id].has("Review-Approved") OR
         NOT TAG_INDEX[task.id].has("Ops-Ready"):
        RETURN true

  RETURN false
```

## Helper Functions

See `helpers.md` for shared functions: `extractSmartPayload`, `buildTagSet`, `extractTagNames`, `submitWorkerResult`, `logWorkerActivity`.
