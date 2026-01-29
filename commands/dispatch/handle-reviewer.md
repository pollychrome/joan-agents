---
description: Handle Reviewer queue - code review, approve or request rework
argument-hint: --task=UUID
allowed-tools: Bash, Read, Task, mcp__joan__*, mcp__plugin_agents_joan__*
---

# Reviewer Handler

Process Reviewer queue: deep code review, merge develop into feature, approve or request rework.

## CRITICAL: Smart Payload Check (Do This First!)

**BEFORE calling ANY MCP tools**, check for a pre-fetched smart payload file:

1. First, try to read the file `.claude/smart-payload-{TASK_ID}.json` where TASK_ID comes from the `--task=` argument
2. If the file exists and contains valid JSON with a `"task"` field: Use that data. DO NOT call MCP.
3. If the file doesn't exist or is invalid: Fall back to MCP calls.

This is critical because the coordinator pre-fetches task data to avoid redundant API calls.

## Arguments

- `--task=UUID` → Process single task (event-driven mode)
- `--all` → Process all Reviewer tasks in queue (polling mode)

## Configuration

```
config = JSON.parse(read(".joan-agents.json"))
PROJECT_ID = config.projectId
PROJECT_NAME = config.projectName

# Model resolution: settings.models.reviewer → settings.model → "opus" (built-in default)
MODEL = config.settings.models?.reviewer OR config.settings.model OR "opus"

MODE = config.settings.mode OR "standard"
TIMEOUT_REVIEWER = config.settings.workerTimeouts.reviewer OR 20

IF NOT config.agents.reviewer.enabled:
  Report: "Reviewer agent disabled in config"
  EXIT
```

## Single Task Mode (Event-Driven)

```
IF TASK_ID provided:
  Report: "Reviewer Handler: Processing task {TASK_ID}"

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

  # Verify task is in Review column
  IF task.column_name != "Review" AND task.column_id != COLUMN_CACHE["Review"]:
    Report: "Task not in Review column, skipping"
    EXIT

  # Verify task has completion tags
  IF NOT (TAG_SET.has("Dev-Complete") AND TAG_SET.has("Design-Complete") AND TAG_SET.has("Test-Complete")) AND
     NOT TAG_SET.has("Rework-Complete"):
    Report: "Task missing completion tags, skipping"
    EXIT

  # Skip if already in review or approved
  IF TAG_SET.has("Review-In-Progress") OR TAG_SET.has("Review-Approved") OR TAG_SET.has("Rework-Requested"):
    Report: "Task already being reviewed or processed, skipping"
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
  mode: "review",
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
Report: "**Reviewer worker dispatched for '{WORK_PACKAGE.task_title}'**"

logWorkerActivity(".", "Reviewer", "START", "task=#{WORK_PACKAGE.task_id} '{WORK_PACKAGE.task_title}'")

max_turns = TIMEOUT_REVIEWER * 2

Task agent:
  subagent_type: reviewer-worker
  model: MODEL
  max_turns: max_turns
  prompt: |
    ## Reviewer Worker - Phase 3 Result Protocol

    Process this task and return a structured result.

    ## Work Package
    ```json
    {JSON.stringify(WORK_PACKAGE, null, 2)}
    ```

    ## Review Process
    1. Merge develop into feature branch (detect conflicts)
    2. If conflicts: Return result_type "review_rejected" with Merge-Conflict details
    3. Run comprehensive code review:
       - Functional completeness (all sub-tasks checked)
       - Code quality (conventions, logic, error handling)
       - Security (no secrets, input validation)
       - Tests (exist and pass)
    4. If issues found: Return result_type "review_rejected" with detailed feedback
    5. If approved: Return result_type "review_approved"

    ## YOLO Mode Behavior
    If workflow_mode == "yolo":
    - Only reject for CRITICAL issues (security vulnerabilities, crashes, data loss)
    - Demote BLOCKER issues to warnings
    - Approve with warnings for non-critical issues

    ## Return Format (Phase 3)

    Return a JSON object with:
    ```json
    {
      "success": true,
      "result_type": "review_approved" | "review_rejected",
      "structured_comment": { ... },
      "output": {
        "issues_found": 0,
        "blockers": [],
        "warnings": ["Minor style issue in file.ts:42"]
      }
    }
    ```

    ## Structured Comment (server generates ALS format)

    For review_approved (handoff to ops):
    ```json
    "structured_comment": {
      "actor": "reviewer", "intent": "handoff", "action": "context-handoff",
      "from_stage": "reviewer", "to_stage": "ops",
      "summary": "Review summary - approved",
      "key_decisions": ["Review observations"],
      "warnings": ["Any non-blocking concerns"]
    }
    ```

    For review_rejected (handoff back to dev):
    ```json
    "structured_comment": {
      "actor": "reviewer", "intent": "rework", "action": "rework-requested",
      "from_stage": "reviewer", "to_stage": "dev",
      "summary": "What needs to be fixed",
      "blockers": ["file:line - Issue description"],
      "warnings": ["Non-blocking suggestions"],
      "suggestions": ["Optional improvements"]
    }
    ```

    IMPORTANT: Do NOT return joan_actions. Joan backend handles state transitions automatically.

WORKER_RESULT = Task.result

# Log worker completion
IF WORKER_RESULT.success:
  logWorkerActivity(".", "Reviewer", "COMPLETE", "task=#{WORK_PACKAGE.task_id} success result_type={WORKER_RESULT.result_type}")
ELSE:
  logWorkerActivity(".", "Reviewer", "FAIL", "task=#{WORK_PACKAGE.task_id} error={WORKER_RESULT.error}")

# Process worker result
GOTO PROCESS_RESULT
```

## PROCESS_RESULT (Phase 3)

```
# Use shared result submission (see helpers.md)
submitWorkerResult("reviewer-worker", WORKER_RESULT, WORK_PACKAGE, PROJECT_ID)

# YOLO mode: auto-add Ops-Ready tag is handled by backend
IF MODE == "yolo" AND WORKER_RESULT.result_type == "review_approved":
  Report: "  [YOLO] Auto-approved for merge - backend will handle Ops-Ready tag"
```

## Helper Functions

See `helpers.md` for shared functions: `extractSmartPayload`, `buildTagSet`, `extractTagNames`, `submitWorkerResult`, `logWorkerActivity`.
