---
description: Handle Dev queue - claim tasks, implement features, handle rework
argument-hint: --task=UUID [--mode=implement|rework|conflict]
allowed-tools: Bash, Read, Task, mcp__joan__*, mcp__plugin_agents_joan__*
---

# Dev Handler

Process Dev queue: claim tasks, implement on feature branches, handle rework and conflicts.

## CRITICAL: Smart Payload Check (Do This First!)

**BEFORE calling ANY MCP tools**, check for a pre-fetched smart payload file:

1. First, try to read the file `.claude/smart-payload-{TASK_ID}.json` where TASK_ID comes from the `--task=` argument
2. If the file exists and contains valid JSON with a `"task"` field: Use that data. DO NOT call MCP.
3. If the file doesn't exist or is invalid: Fall back to MCP calls.

This is critical because the coordinator pre-fetches task data to avoid redundant API calls.

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

## Single Task Mode (Event-Driven)

```
IF TASK_ID provided:
  Report: "Dev Handler: Processing task {TASK_ID} mode={OPERATION_MODE}"

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
    rework_feedback = payload_data.rework_feedback OR null
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
    rework_feedback = null
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

  # Claim task before starting work (prevents double-dispatch by scheduler)
  Report: "  Claiming task: adding Claimed-Dev-1"
  project_tags = mcp__joan__list_project_tags(project_id: PROJECT_ID)
  claim_tag = project_tags.find(t => t.name == "Claimed-Dev-1")
  IF NOT claim_tag:
    claim_tag = mcp__joan__create_project_tag(project_id: PROJECT_ID, name: "Claimed-Dev-1", color: "#0EA5E9")
  mcp__joan__add_tag_to_task(project_id: PROJECT_ID, task_id: task.id, tag_id: claim_tag.id)

  # Verify claim succeeded
  updated_tags = mcp__joan__get_task_tags(project_id: PROJECT_ID, task_id: task.id)
  IF NOT "Claimed-Dev-1" IN extractTagNames(updated_tags):
    Report: "  Failed to claim task, aborting"
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
      "structured_comment": { ... },
      "output": {
        "pr_number": 42,
        "pr_url": "https://github.com/...",
        "branch_name": "feature/task-name",
        "files_changed": ["file1.ts", "file2.ts"]
      }
    }
    ```

    ## Structured Comment (server generates ALS format)

    For implementation_complete/rework_complete:
    ```json
    "structured_comment": {
      "actor": "dev", "intent": "handoff", "action": "context-handoff",
      "from_stage": "dev", "to_stage": "reviewer",
      "summary": "Implementation summary",
      "key_decisions": ["Decision 1", "Decision 2"],
      "files_of_interest": ["file1.ts", "file2.ts"],
      "warnings": ["Any concerns"]
    }
    ```

    For implementation_failed:
    ```json
    "structured_comment": {
      "actor": "dev", "intent": "error", "action": "implementation-failed",
      "summary": "What failed and why",
      "blockers": ["Blocker 1", "Blocker 2"]
    }
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
  # YOLO mode: Attempt intelligent recovery instead of failing immediately
  IF MODE == "yolo" AND NOT RECOVERY_ATTEMPTED:
    Report: "  [YOLO] Attempting intelligent recovery..."
    GOTO YOLO_RECOVERY

# Use shared result submission (see helpers.md)
submitWorkerResult("dev-worker", WORKER_RESULT, WORK_PACKAGE, PROJECT_ID)
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
    - structured_comment: { actor: "dev", intent: "handoff", action: "context-handoff", from_stage: "dev", to_stage: "reviewer", summary: "...", warnings: ["YOLO recovery: ..."] }
    - output: { pr_number, pr_url, files_changed, recovery_notes }

WORKER_RESULT = Task.result

IF WORKER_RESULT.success:
  logWorkerActivity(".", "Dev", "YOLO-RECOVERED", "task=#{WORK_PACKAGE.task_id} recovery succeeded")
  Report: "  [YOLO] Recovery successful!"

  # Add recovery warning to structured comment if not already present
  IF WORKER_RESULT.structured_comment:
    IF NOT WORKER_RESULT.structured_comment.warnings:
      WORKER_RESULT.structured_comment.warnings = []
    IF NOT "YOLO recovery" IN WORKER_RESULT.structured_comment.warnings.join(""):
      WORKER_RESULT.structured_comment.warnings.push("YOLO recovery: Some functionality may be incomplete - review carefully")
  ELIF WORKER_RESULT.comment AND NOT "YOLO recovery" IN WORKER_RESULT.comment:
    WORKER_RESULT.comment = WORKER_RESULT.comment + "\nwarnings:\n- YOLO recovery: Some functionality may be incomplete - review carefully"

ELSE:
  logWorkerActivity(".", "Dev", "YOLO-RECOVERY-FAILED", "task=#{WORK_PACKAGE.task_id} recovery also failed")
  Report: "  [YOLO] Recovery also failed"

GOTO PROCESS_RESULT
```

## Helper Functions

See `helpers.md` for shared functions: `extractSmartPayload`, `buildTagSet`, `extractTagNames`, `submitWorkerResult`, `logWorkerActivity`.
