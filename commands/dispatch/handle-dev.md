---
description: Handle Dev queue - claim tasks, implement features, handle rework
argument-hint: [--task=UUID] [--mode=implement|rework|conflict] [--all]
allowed-tools: Bash, Read, Task
---

# Dev Handler

Process Dev queue: claim tasks, implement on feature branches, handle rework and conflicts.

## Arguments

- `--task=UUID` → Process single task (event-driven mode)
- `--mode=implement|rework|conflict` → Operation mode
- `--all` → Process available Dev task (polling mode, strict serial = 1 task)

## Configuration

```
config = JSON.parse(read(".joan-agents.json"))
PROJECT_ID = config.projectId
PROJECT_NAME = config.projectName

# Model resolution: settings.models.dev → settings.model → "opus" (built-in default)
MODEL = config.settings.models?.dev OR config.settings.model OR "opus"

MODE = config.settings.mode OR "standard"
TIMEOUT_DEV = config.settings.workerTimeouts.dev OR 60

# YOLO recovery tracking (prevents infinite loops)
RECOVERY_ATTEMPTED = false

IF NOT config.agents.devs.enabled:
  Report: "Dev agent disabled in config"
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
  Report: "Dev Handler: Processing task {TASK_ID} mode={OPERATION_MODE}"

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

  # Verify task is in Development column
  IF task.column_name != "Development" AND task.column_id != COLUMN_CACHE["Development"]:
    Report: "Task not in Development column, skipping"
    EXIT

  # Check if already claimed by another dev
  IF TAG_SET.has("Claimed-Dev-1"):
    Report: "Task already claimed, skipping"
    EXIT

  # Auto-detect mode
  IF NOT OPERATION_MODE:
    IF TAG_SET.has("Merge-Conflict"):
      OPERATION_MODE = "conflict"
    ELIF TAG_SET.has("Rework-Requested"):
      OPERATION_MODE = "rework"
    ELIF TAG_SET.has("Planned"):
      OPERATION_MODE = "implement"
    ELSE:
      Report: "Cannot determine Dev mode from tags: {TAG_SET}"
      EXIT

  # Build work package (claim happens via result submission)
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
  Report: "Dev Handler: Looking for available task (strict serial mode)"

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

  # Build Dev queue (priority: conflict > rework > implement)
  DEV_QUEUE = []

  FOR task IN tasks:
    taskId = task.id
    tags = TAG_INDEX[taskId]

    IF task.column_id != COLUMN_CACHE["Development"]:
      CONTINUE

    # Skip if already claimed
    IF tags.has("Claimed-Dev-1"):
      CONTINUE

    # Skip failed tasks
    IF tags.has("Implementation-Failed") OR tags.has("Branch-Setup-Failed"):
      CONTINUE

    # Conflict priority
    IF tags.has("Merge-Conflict") AND tags.has("Planned"):
      DEV_QUEUE.unshift({task, mode: "conflict"})
      CONTINUE

    # Rework priority
    IF tags.has("Rework-Requested") AND NOT tags.has("Merge-Conflict"):
      DEV_QUEUE.push({task, mode: "rework"})
      CONTINUE

    # Normal implementation
    IF tags.has("Planned") AND NOT tags.has("Rework-Requested"):
      DEV_QUEUE.push({task, mode: "implement"})

  Report: "Dev queue: {DEV_QUEUE.length} available tasks"

  IF DEV_QUEUE.length == 0:
    Report: "No Dev tasks available"
    EXIT

  # Take first task (strict serial = 1)
  item = DEV_QUEUE[0]
  task = item.task
  OPERATION_MODE = item.mode

  # Fetch full details for work package
  full_task = mcp__joan__get_task(task.id)
  comments = mcp__joan__list_task_comments(task.id)

  WORK_PACKAGE = {
    task_id: full_task.id,
    task_title: full_task.title,
    task_description: full_task.description,
    task_tags: extractTagNames(full_task.tags),
    mode: OPERATION_MODE,
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
Report: "**Dev worker dispatched for '{WORK_PACKAGE.task_title}' (mode: {OPERATION_MODE})**"

logWorkerActivity(".", "Dev", "START", "task=#{WORK_PACKAGE.task_id} '{WORK_PACKAGE.task_title}' mode={OPERATION_MODE}")

max_turns = TIMEOUT_DEV * 2  # 60 min = 120 turns

Task agent:
  subagent_type: dev-worker
  model: MODEL
  max_turns: max_turns
  prompt: |
    ## Dev Worker - Phase 3 Result Protocol

    Process this task and return a structured result.

    ## Work Package
    ```json
    {JSON.stringify(WORK_PACKAGE, null, 2)}
    ```

    ## Mode: {WORK_PACKAGE.mode}

    ### If mode == "implement":
    - Create feature branch from develop
    - Implement all sub-tasks (DES-*, DEV-*, TEST-*)
    - Create pull request
    - Return result_type "implementation_complete"
    - Include PR info in output

    ### If mode == "rework":
    - Read reviewer feedback from work package
    - Address specific issues mentioned
    - Push fixes to existing branch
    - Return result_type "rework_complete"

    ### If mode == "conflict":
    - Merge develop into feature branch
    - Resolve conflicts
    - Run tests
    - Return result_type "rework_complete"

    ### On Failure:
    - Return result_type "implementation_failed" with error details
    - Or "branch_setup_failed" if git branch setup fails

    ## Return Format (Phase 3)

    Return a JSON object with:
    ```json
    {
      "success": true,
      "result_type": "implementation_complete" | "rework_complete" | "implementation_failed" | "branch_setup_failed",
      "comment": "ALS/1 format handoff comment (see below)",
      "output": {
        "pr_number": 42,
        "pr_url": "https://github.com/...",
        "branch_name": "feature/task-name",
        "files_changed": ["file1.ts", "file2.ts"]
      }
    }
    ```

    ## ALS Comment Format

    For implementation_complete/rework_complete (handoff to reviewer):
    ```
    ALS/1
    actor: dev
    intent: handoff
    action: context-handoff
    from_stage: dev
    to_stage: reviewer
    summary: [Implementation summary]
    key_decisions:
    - [Implementation decision 1]
    - [Implementation decision 2]
    files_of_interest:
    - [Modified file 1]
    - [Modified file 2]
    warnings:
    - [Any concerns or incomplete items]
    ```

    For implementation_failed:
    ```
    ALS/1
    actor: dev
    intent: error
    action: implementation-failed
    summary: [What failed and why]
    blockers:
    - [Blocker 1]
    - [Blocker 2]
    ```

    IMPORTANT: Do NOT return joan_actions. Joan backend handles state transitions automatically.

WORKER_RESULT = Task.result

# Log worker completion
IF WORKER_RESULT.success:
  logWorkerActivity(".", "Dev", "COMPLETE", "task=#{WORK_PACKAGE.task_id} success result_type={WORKER_RESULT.result_type}")
ELSE:
  logWorkerActivity(".", "Dev", "FAIL", "task=#{WORK_PACKAGE.task_id} error={WORKER_RESULT.error}")

# Process worker result
GOTO PROCESS_RESULT
```

## PROCESS_RESULT (Phase 3)

```
IF NOT WORKER_RESULT.success:
  Report: "Dev worker failed: {WORKER_RESULT.error}"

  # YOLO mode: Attempt intelligent recovery instead of failing immediately
  IF MODE == "yolo" AND NOT RECOVERY_ATTEMPTED:
    Report: "  [YOLO] Attempting intelligent recovery..."
    GOTO YOLO_RECOVERY

  # Standard mode or recovery already attempted: Submit failure
  Bash: python3 ~/joan-agents/scripts/submit-result.py dev-worker implementation_failed false \
    --project-id "{PROJECT_ID}" \
    --task-id "{WORK_PACKAGE.task_id}" \
    --error "{WORKER_RESULT.error}"
  RETURN

# Phase 3: Submit result to Joan API (state transitions handled server-side)
result_type = WORKER_RESULT.result_type
comment = WORKER_RESULT.comment OR ""
output_json = JSON.stringify(WORKER_RESULT.output OR {})

Report: "Submitting result: {result_type}"

Bash: python3 ~/joan-agents/scripts/submit-result.py dev-worker "{result_type}" true \
  --project-id "{PROJECT_ID}" \
  --task-id "{WORK_PACKAGE.task_id}" \
  --output '{output_json}' \
  --comment '{comment}'

Report: "**Dev worker completed for '{WORK_PACKAGE.task_title}' - {result_type}**"
```

## YOLO_RECOVERY

YOLO mode intelligent failure recovery. Instead of giving up, attempt to:
1. Fix the specific error
2. If that fails, reduce scope and implement core functionality only

```
RECOVERY_ATTEMPTED = true

# Build recovery work package with error context
RECOVERY_PACKAGE = {
  ...WORK_PACKAGE,
  mode: "yolo-recovery",
  previous_error: WORKER_RESULT.error,
  failed_subtask: WORKER_RESULT.errors[0] OR "unknown",
  recovery_instructions: [
    "Previous attempt failed with: {WORKER_RESULT.error}",
    "STRATEGY 1: Analyze the error and fix the specific issue",
    "STRATEGY 2: If unfixable, reduce scope - implement ONLY the core functionality",
    "STRATEGY 3: Skip problematic sub-tasks, document what was skipped",
    "GOAL: Get something working that compiles and passes basic tests"
  ]
}

Report: "  [YOLO] Re-dispatching with recovery instructions"
logWorkerActivity(".", "Dev", "YOLO-RECOVERY", "task=#{WORK_PACKAGE.task_id} attempting recovery")

max_turns = TIMEOUT_DEV * 2

Task agent:
  subagent_type: dev-worker
  model: MODEL
  max_turns: max_turns
  prompt: |
    ## YOLO RECOVERY MODE ##

    Previous implementation attempt FAILED. Your job is to recover intelligently.

    ## Original Work Package
    ```json
    {JSON.stringify(WORK_PACKAGE, null, 2)}
    ```

    ## Error From Previous Attempt
    {RECOVERY_PACKAGE.previous_error}

    ## Recovery Strategy (in order of preference)

    1. **FIX THE ERROR**: Analyze what went wrong and fix it directly
       - Read the error message carefully
       - Check the failing test/code
       - Make targeted fixes

    2. **REDUCE SCOPE**: If the error is in a specific sub-task, skip it
       - Comment out or stub the problematic functionality
       - Implement the rest of the feature
       - Document what was skipped in the PR

    3. **MINIMAL IMPLEMENTATION**: If multiple things are broken
       - Implement just enough to compile and pass basic tests
       - Create placeholder/stub implementations for complex parts
       - Add TODO comments for incomplete work

    ## Success Criteria
    - Code compiles without errors
    - At least one test passes (can be a simple smoke test)
    - PR can be created with description of what was implemented vs. skipped

    ## Output (Phase 3 Format)
    Return a JSON object with:
    - success: true/false
    - result_type: "implementation_complete" or "implementation_failed"
    - comment: ALS handoff comment (include warnings about skipped/stubbed items)
    - output: { pr_number, pr_url, files_changed, recovery_notes }

WORKER_RESULT = Task.result

IF WORKER_RESULT.success:
  logWorkerActivity(".", "Dev", "YOLO-RECOVERED", "task=#{WORK_PACKAGE.task_id} recovery succeeded")
  Report: "  [YOLO] Recovery successful!"

  # Add recovery note to comment if not present
  IF WORKER_RESULT.comment AND NOT "YOLO recovery" IN WORKER_RESULT.comment:
    WORKER_RESULT.comment = WORKER_RESULT.comment + "\nwarnings:\n- YOLO recovery: Some functionality may be incomplete - review carefully"

ELSE:
  logWorkerActivity(".", "Dev", "YOLO-RECOVERY-FAILED", "task=#{WORK_PACKAGE.task_id} recovery also failed")
  Report: "  [YOLO] Recovery also failed"

GOTO PROCESS_RESULT
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
