---
description: Handle Ops queue - merge to develop, track deployments
argument-hint: [--task=UUID] [--mode=merge|merge-with-guidance] [--all]
allowed-tools: Bash, Read, Task
---

# Ops Handler

Process Ops queue: merge approved PRs to develop, handle conflict resolution with Architect guidance.

## Arguments

- `--task=UUID` → Process single task (event-driven mode)
- `--mode=merge|merge-with-guidance` → Operation mode
- `--all` → Process all Ops tasks in queue (polling mode)

## Configuration

```
config = JSON.parse(read(".joan-agents.json"))
PROJECT_ID = config.projectId
PROJECT_NAME = config.projectName
MODEL = config.settings.model OR "opus"
MODE = config.settings.mode OR "standard"
TIMEOUT_OPS = config.settings.workerTimeouts.ops OR 15

IF NOT config.agents.ops.enabled:
  Report: "Ops agent disabled in config"
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
  Report: "Ops Handler: Processing task {TASK_ID} mode={OPERATION_MODE}"

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

## Batch Mode (Polling)

When `--all` is provided (legacy mode, no smart payload):

```
IF ALL_MODE:
  Report: "Ops Handler: Processing Ops queue"

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

  # Build Ops queue
  OPS_QUEUE = []

  FOR task IN tasks:
    taskId = task.id
    tags = TAG_INDEX[taskId]

    # P0: Merge with Architect guidance (invocation complete)
    IF task.column_id == COLUMN_CACHE["Review"] AND tags.has("Architect-Assist-Complete"):
      OPS_QUEUE.unshift({task, mode: "merge-with-guidance"})
      CONTINUE

    # Normal merge (approved + ops-ready)
    IF (task.column_id == COLUMN_CACHE["Review"] OR task.column_id == COLUMN_CACHE["Deploy"]) AND
       tags.has("Review-Approved") AND tags.has("Ops-Ready"):
      OPS_QUEUE.push({task, mode: "merge"})

  Report: "Ops queue: {OPS_QUEUE.length} tasks"

  IF OPS_QUEUE.length == 0:
    Report: "No Ops tasks to process"
    EXIT

  # Process first task
  item = OPS_QUEUE[0]
  task = item.task
  OPERATION_MODE = item.mode

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
      "comment": "ALS/1 format comment (see below)",
      "output": {
        "merged_commit": "abc123",
        "branch_deleted": true,
        "conflict_files": []  // For merge_conflict
      }
    }
    ```

    ## ALS Comment Format

    For merge_complete:
    ```
    ALS/1
    actor: ops
    intent: complete
    action: merged-to-develop
    summary: [Merge summary]
    merged_commit: [commit hash]
    branch_deleted: [feature/branch-name]
    ```

    For invoke_architect (need Architect guidance):
    ```
    ALS/1
    actor: ops
    intent: request
    action: invoke-request
    invoked_agent: architect
    invocation_mode: advisory-conflict
    summary: [Why guidance is needed]
    question: [Specific question for Architect]
    files_of_interest:
    - [conflicting file 1]
    - [conflicting file 2]
    conflict_details:
      conflicting_files: [list]
      develop_summary: [what develop changed]
      feature_summary: [what feature changed]
    ```

    For merge_conflict (send back to dev):
    ```
    ALS/1
    actor: ops
    intent: rework
    action: merge-conflict-unresolved
    from_stage: ops
    to_stage: dev
    summary: [Conflict cannot be auto-resolved]
    conflict_files:
    - [file1]
    - [file2]
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
IF NOT WORKER_RESULT.success:
  Report: "Ops worker failed: {WORKER_RESULT.error}"
  # Submit failure result
  Bash: python3 ~/joan-agents/scripts/submit-result.py ops-worker merge_conflict false \
    --project-id "{PROJECT_ID}" \
    --task-id "{WORK_PACKAGE.task_id}" \
    --error "{WORKER_RESULT.error}"
  RETURN

# Phase 3: Submit result to Joan API (state transitions handled server-side)
result_type = WORKER_RESULT.result_type
comment = WORKER_RESULT.comment OR ""
output_json = JSON.stringify(WORKER_RESULT.output OR {})

Report: "Submitting result: {result_type}"

Bash: python3 ~/joan-agents/scripts/submit-result.py ops-worker "{result_type}" true \
  --project-id "{PROJECT_ID}" \
  --task-id "{WORK_PACKAGE.task_id}" \
  --output '{output_json}' \
  --comment '{comment}'

# YOLO mode: auto-complete to Done is handled by backend
IF MODE == "yolo" AND result_type == "merge_complete":
  Report: "  [YOLO] Auto-completing task to Done - backend will handle"

Report: "**Ops worker completed for '{WORK_PACKAGE.task_title}' - {result_type}**"
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
