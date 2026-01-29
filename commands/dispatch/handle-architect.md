---
description: Handle Architect queue - create plans, finalize approved plans
argument-hint: --task=UUID [--mode=plan|finalize|revise|advisory]
allowed-tools: Bash, Read, Task, mcp__joan__*, mcp__plugin_agents_joan__*
---

# Architect Handler

Process Architect queue: create implementation plans, finalize approved plans, provide conflict guidance.

## CRITICAL: Smart Payload Check (Do This First!)

**BEFORE calling ANY MCP tools**, check for a pre-fetched smart payload file:

1. First, try to read the file `.claude/smart-payload-{TASK_ID}.json` where TASK_ID comes from the `--task=` argument
2. If the file exists and contains valid JSON with a `"task"` field: Use that data. DO NOT call MCP.
3. If the file doesn't exist or is invalid: Fall back to MCP calls.

This is critical because the coordinator pre-fetches task data to avoid redundant API calls.

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

  # Read smart payload from environment variable (set by ws-client.py)
  SMART_PAYLOAD_RAW = Bash: echo "$JOAN_SMART_PAYLOAD"
  HAS_SMART_PAYLOAD = SMART_PAYLOAD_RAW AND SMART_PAYLOAD_RAW.trim().length > 10

  IF HAS_SMART_PAYLOAD:
    Report: "Using smart payload ({SMART_PAYLOAD_RAW.length} chars)"
    payload_data = JSON.parse(SMART_PAYLOAD_RAW)
    task = payload_data.task
    handoff_context = payload_data.handoff_context OR null
    recent_comments = payload_data.recent_comments OR []
    subtasks = payload_data.subtasks OR []
    # Build COLUMN_CACHE from payload columns if provided
    COLUMN_CACHE = {}
    IF payload_data.columns:
      FOR col IN payload_data.columns:
        COLUMN_CACHE[col.name] = col.id
  ELSE:
    Report: "No smart payload found, falling back to MCP fetch"
    task = mcp__joan__get_task(TASK_ID)
    comments = mcp__joan__list_task_comments(TASK_ID)
    columns = mcp__joan__list_columns(PROJECT_ID)
    handoff_context = null
    recent_comments = comments
    subtasks = []
    COLUMN_CACHE = {}
    FOR col IN columns:
      COLUMN_CACHE[col.name] = col.id

  # Build tag set from task.tags (handles both string arrays and {name,id} objects)
  TAG_SET = Set()
  FOR tag IN task.tags:
    IF typeof tag == "string":
      TAG_SET.add(tag)
    ELSE:
      TAG_SET.add(tag.name)

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
