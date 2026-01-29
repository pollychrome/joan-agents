---
description: Handle Ops queue - merge to develop, track deployments
argument-hint: --task=UUID [--mode=merge|merge-with-guidance]
allowed-tools: Bash, Read, Task, mcp__joan__*, mcp__plugin_agents_joan__*
---

# Ops Handler

Process Ops queue: merge approved PRs to develop, handle conflict resolution with Architect guidance.

## CRITICAL: Smart Payload Check (Do This First!)

**BEFORE calling ANY MCP tools**, check for a pre-fetched smart payload file:

1. First, try to read the file `.claude/smart-payload-{TASK_ID}.json` where TASK_ID comes from the `--task=` argument
2. If the file exists and contains valid JSON with a `"task"` field: Use that data. DO NOT call MCP.
3. If the file doesn't exist or is invalid: Fall back to MCP calls.

This is critical because the coordinator pre-fetches task data to avoid redundant API calls.

## Arguments

- `--task=UUID` → Process single task (event-driven mode)
- `--mode=merge|merge-with-guidance` → Operation mode
- `--all` → Process all Ops tasks in queue (polling mode)

## Configuration

```
config = JSON.parse(read(".joan-agents.json"))
PROJECT_ID = config.projectId
PROJECT_NAME = config.projectName

# Model resolution: settings.models.ops → settings.model → "haiku" (built-in default)
MODEL = config.settings.models?.ops OR config.settings.model OR "haiku"

MODE = config.settings.mode OR "standard"
TIMEOUT_OPS = config.settings.workerTimeouts.ops OR 15

IF NOT config.agents.ops.enabled:
  Report: "Ops agent disabled in config"
  EXIT
```

## Single Task Mode (Event-Driven)

```
IF TASK_ID provided:
  Report: "Ops Handler: Processing task {TASK_ID} mode={OPERATION_MODE}"

  # Read smart payload from environment variable (set by ws-client.py)
  SMART_PAYLOAD_RAW = Bash: echo "$JOAN_SMART_PAYLOAD"
  HAS_SMART_PAYLOAD = SMART_PAYLOAD_RAW AND SMART_PAYLOAD_RAW.trim().length > 10

  IF HAS_SMART_PAYLOAD:
    Report: "Using smart payload ({SMART_PAYLOAD_RAW.length} chars)"
    payload_data = JSON.parse(SMART_PAYLOAD_RAW)
    task = payload_data.task
    handoff_context = payload_data.handoff_context OR null
    recent_comments = payload_data.recent_comments OR []
    # Build COLUMN_CACHE from payload columns if provided
    COLUMN_CACHE = {}
    IF payload_data.columns:
      FOR col IN payload_data.columns:
        COLUMN_CACHE[col.name] = col.id
  ELSE:
    Report: "No smart payload found, falling back to MCP fetch"
    task = mcp__joan__get_task(TASK_ID)
    columns = mcp__joan__list_columns(PROJECT_ID)
    handoff_context = null
    recent_comments = []
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

  # Verify task is in Review or Deploy column
  IF task.column_name != "Review" AND task.column_name != "Deploy" AND
     task.column_id != COLUMN_CACHE["Review"] AND task.column_id != COLUMN_CACHE["Deploy"]:
    Report: "Task not in Review/Deploy column, skipping"
    EXIT

  # Auto-detect mode
  IF NOT OPERATION_MODE:
    IF TAG_SET.has("Architect-Assist-Complete"):
      OPERATION_MODE = "merge-with-guidance"
    ELIF TAG_SET.has("Review-Approved") AND TAG_SET.has("Ops-Ready"):
      OPERATION_MODE = "merge"
    ELSE:
      Report: "Cannot determine Ops mode from tags: {TAG_SET}"
      EXIT

  GOTO BUILD_WORK_PACKAGE
```

## BUILD_WORK_PACKAGE

```
WORK_PACKAGE = {
  task_id: task.id,
  task_title: task.title,
  task_description: task.description,
  task_tags: Array.from(TAG_SET OR extractTagNames(task.tags)),
  mode: OPERATION_MODE,
  workflow_mode: MODE,
  project_id: PROJECT_ID,
  project_name: PROJECT_NAME,
  handoff_context: handoff_context,
  recent_comments: recent_comments OR comments
}

GOTO DISPATCH_WORKER
```

## DISPATCH_WORKER

```
Report: "**Ops worker dispatched for '{WORK_PACKAGE.task_title}' (mode: {OPERATION_MODE})**"

logWorkerActivity(".", "Ops", "START", "task=#{WORK_PACKAGE.task_id} '{WORK_PACKAGE.task_title}' mode={OPERATION_MODE}")

max_turns = TIMEOUT_OPS * 2

Task agent:
  subagent_type: ops-worker
  model: MODEL
  max_turns: max_turns
  prompt: |
    ## Ops Worker - Phase 3 Result Protocol

    Process this task and return a structured result.

    ## Work Package
    ```json
    {JSON.stringify(WORK_PACKAGE, null, 2)}
    ```

    ## Mode: {WORK_PACKAGE.mode}

    ### If mode == "merge":
    1. Checkout develop, pull latest
    2. Merge feature branch into develop
    3. If conflicts: Try AI-assisted resolution
       - If resolution succeeds: Continue
       - If resolution fails: Return result_type "invoke_architect"
    4. Run verification tests
    5. Push to develop
    6. Delete feature branch (local and remote)
    7. Return result_type "merge_complete"

    ### If mode == "merge-with-guidance":
    1. Read Architect guidance from handoff_context/recent_comments
    2. Apply recommended conflict resolution
    3. Run verification tests
    4. If still failing: Return result_type "merge_conflict"
    5. If passing: Return result_type "merge_complete"

    ## Return Format (Phase 3)

    Return a JSON object with:
    ```json
    {
      "success": true,
      "result_type": "merge_complete" | "merge_conflict" | "invoke_architect",
      "structured_comment": { ... },
      "output": {
        "merged_commit": "abc123",
        "branch_deleted": true,
        "conflict_files": []  // For merge_conflict
      }
    }
    ```

    ## Structured Comment (server generates ALS format)

    For merge_complete:
    ```json
    "structured_comment": {
      "actor": "ops", "intent": "complete", "action": "merged-to-develop",
      "summary": "Merge summary",
      "metadata": {"merged_commit": "abc123", "branch_deleted": "feature/branch-name"}
    }
    ```

    For invoke_architect (need Architect guidance):
    ```json
    "structured_comment": {
      "actor": "ops", "intent": "request", "action": "invoke-request",
      "summary": "Why guidance is needed",
      "files_of_interest": ["conflicting-file-1", "conflicting-file-2"],
      "metadata": {
        "invoked_agent": "architect",
        "invocation_mode": "advisory-conflict",
        "question": "Specific question for Architect",
        "conflict_details": {
          "conflicting_files": [],
          "develop_summary": "what develop changed",
          "feature_summary": "what feature changed"
        }
      }
    }
    ```

    For merge_conflict (send back to dev):
    ```json
    "structured_comment": {
      "actor": "ops", "intent": "rework", "action": "merge-conflict-unresolved",
      "from_stage": "ops", "to_stage": "dev",
      "summary": "Conflict cannot be auto-resolved",
      "blockers": ["file1 - conflict description", "file2 - conflict description"]
    }
    ```

    IMPORTANT: Do NOT return joan_actions. Joan backend handles state transitions automatically.

WORKER_RESULT = Task.result

# Log worker completion
IF WORKER_RESULT.success:
  logWorkerActivity(".", "Ops", "COMPLETE", "task=#{WORK_PACKAGE.task_id} success result_type={WORKER_RESULT.result_type}")
ELSE:
  logWorkerActivity(".", "Ops", "FAIL", "task=#{WORK_PACKAGE.task_id} error={WORKER_RESULT.error}")

# Process worker result
GOTO PROCESS_RESULT
```

## PROCESS_RESULT (Phase 3)

```
# Use shared result submission (see helpers.md)
submitWorkerResult("ops-worker", WORKER_RESULT, WORK_PACKAGE, PROJECT_ID)

# YOLO mode: auto-complete to Done is handled by backend
IF MODE == "yolo" AND WORKER_RESULT.result_type == "merge_complete":
  Report: "  [YOLO] Auto-completing task to Done - backend will handle"
```

## Helper Functions

See `helpers.md` for shared functions: `extractSmartPayload`, `buildTagSet`, `extractTagNames`, `submitWorkerResult`, `logWorkerActivity`.
