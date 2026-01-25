---
description: Handle Reviewer queue - code review, approve or request rework
argument-hint: [--task=UUID] [--all]
allowed-tools: Bash, Read, Task
---

# Reviewer Handler

Process Reviewer queue: deep code review, merge develop into feature, approve or request rework.

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

## Phase 3: Smart Payload Check

```
# Phase 3: Check for pre-fetched smart payload (zero MCP calls)
SMART_PAYLOAD = env.JOAN_SMART_PAYLOAD
HAS_SMART_PAYLOAD = SMART_PAYLOAD AND SMART_PAYLOAD.length > 0

IF HAS_SMART_PAYLOAD:
  smart_data = JSON.parse(SMART_PAYLOAD)
  Report: "Phase 3: Using smart payload (zero MCP fetching)"
```

## Single Task Mode (Event-Driven)

```
IF TASK_ID provided:
  Report: "Reviewer Handler: Processing task {TASK_ID}"

  # Phase 3: Use smart payload if available
  IF HAS_SMART_PAYLOAD:
    task = {
      id: smart_data.task.id,
      title: smart_data.task.title,
      description: smart_data.task.description,
      column_id: smart_data.task.column_id,
      column_name: smart_data.task.column_name,
      tags: smart_data.tags
    }
    handoff_context = smart_data.handoff_context
    recent_comments = smart_data.recent_comments
    COLUMN_CACHE = smart_data.columns OR {}
  ELSE:
    # Fallback: Fetch via MCP
    task = mcp__joan__get_task(TASK_ID)
    comments = mcp__joan__list_task_comments(TASK_ID)
    columns = mcp__joan__list_columns(PROJECT_ID)

    COLUMN_CACHE = {}
    FOR col IN columns:
      COLUMN_CACHE[col.name] = col.id

    handoff_context = null
    recent_comments = comments

  # Build tag set
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

## Batch Mode (Polling)

When `--all` is provided (legacy mode, no smart payload):

```
IF ALL_MODE:
  Report: "Reviewer Handler: Processing Reviewer queue"

  tasks = mcp__joan__list_tasks(project_id: PROJECT_ID)
  columns = mcp__joan__list_columns(PROJECT_ID)

  COLUMN_CACHE = {}
  FOR col IN columns:
    COLUMN_CACHE[col.name] = col.id

  TAG_INDEX = {}
  FOR task IN tasks:
    tagSet = Set()
    FOR tag IN task.tags:
      tagSet.add(tag.name)
    TAG_INDEX[task.id] = tagSet

  # Build Reviewer queue
  REVIEWER_QUEUE = []

  FOR task IN tasks:
    taskId = task.id
    tags = TAG_INDEX[taskId]

    IF task.column_id != COLUMN_CACHE["Review"]:
      CONTINUE

    # Skip if already reviewing/reviewed
    IF tags.has("Review-In-Progress") OR tags.has("Review-Approved") OR tags.has("Rework-Requested"):
      CONTINUE

    # Fresh implementation complete
    IF tags.has("Dev-Complete") AND tags.has("Design-Complete") AND tags.has("Test-Complete"):
      REVIEWER_QUEUE.push({task, mode: "review"})
      CONTINUE

    # Rework complete
    IF tags.has("Rework-Complete"):
      REVIEWER_QUEUE.push({task, mode: "review"})

  Report: "Reviewer queue: {REVIEWER_QUEUE.length} tasks"

  IF REVIEWER_QUEUE.length == 0:
    Report: "No Reviewer tasks to process"
    EXIT

  # Process first task
  item = REVIEWER_QUEUE[0]
  task = item.task

  full_task = mcp__joan__get_task(task.id)
  comments = mcp__joan__list_task_comments(task.id)

  GOTO BUILD_WORK_PACKAGE with full_task, comments
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
      "comment": "ALS/1 format handoff comment (see below)",
      "output": {
        "issues_found": 0,
        "blockers": [],
        "warnings": ["Minor style issue in file.ts:42"]
      }
    }
    ```

    ## ALS Comment Format

    For review_approved (handoff to ops):
    ```
    ALS/1
    actor: reviewer
    intent: handoff
    action: context-handoff
    from_stage: reviewer
    to_stage: ops
    summary: [Review summary - approved]
    key_decisions:
    - [Review observations]
    warnings:
    - [Any non-blocking concerns]
    ```

    For review_rejected (handoff back to dev):
    ```
    ALS/1
    actor: reviewer
    intent: rework
    action: rework-requested
    from_stage: reviewer
    to_stage: dev
    summary: [What needs to be fixed]
    blockers:
    - [file:line - Issue description]
    warnings:
    - [Non-blocking suggestions]
    suggestions:
    - [Optional improvements]
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
IF NOT WORKER_RESULT.success:
  Report: "Reviewer worker failed: {WORKER_RESULT.error}"
  # Submit failure result
  Bash: python3 ~/joan-agents/scripts/submit-result.py reviewer-worker review_rejected false \
    --project-id "{PROJECT_ID}" \
    --task-id "{WORK_PACKAGE.task_id}" \
    --error "{WORKER_RESULT.error}"
  RETURN

# Phase 3: Submit result to Joan API (state transitions handled server-side)
result_type = WORKER_RESULT.result_type
comment = WORKER_RESULT.comment OR ""
output_json = JSON.stringify(WORKER_RESULT.output OR {})

Report: "Submitting result: {result_type}"

Bash: python3 ~/joan-agents/scripts/submit-result.py reviewer-worker "{result_type}" true \
  --project-id "{PROJECT_ID}" \
  --task-id "{WORK_PACKAGE.task_id}" \
  --output '{output_json}' \
  --comment '{comment}'

# YOLO mode: auto-add Ops-Ready tag is handled by backend
IF MODE == "yolo" AND result_type == "review_approved":
  Report: "  [YOLO] Auto-approved for merge - backend will handle Ops-Ready tag"

Report: "**Reviewer worker completed for '{WORK_PACKAGE.task_title}' - {result_type}**"
```

## Helper Functions

```
def extractTagNames(tags):
  names = []
  FOR tag IN tags:
    names.push(tag.name)
  RETURN names

def logWorkerActivity(projectDir, workerType, status, message):
  logFile = "{projectDir}/.claude/logs/worker-activity.log"
  timestamp = NOW.strftime("%Y-%m-%d %H:%M:%S")
  Bash: mkdir -p "$(dirname {logFile})" && echo "[{timestamp}] [{workerType}] [{status}] {message}" >> {logFile}
```
