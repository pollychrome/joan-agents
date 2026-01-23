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

## Single Task Mode (Event-Driven)

```
IF TASK_ID provided:
  Report: "Ops Handler: Processing task {TASK_ID} mode={OPERATION_MODE}"

  task = mcp__joan__get_task(TASK_ID)
  comments = mcp__joan__list_task_comments(TASK_ID)
  columns = mcp__joan__list_columns(PROJECT_ID)

  COLUMN_CACHE = {}
  FOR col IN columns:
    COLUMN_CACHE[col.name] = col.id

  TAG_SET = Set()
  FOR tag IN task.tags:
    TAG_SET.add(tag.name)

  # Verify task is in Review or Deploy column
  IF task.column_id != COLUMN_CACHE["Review"] AND task.column_id != COLUMN_CACHE["Deploy"]:
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

  GOTO BUILD_WORK_PACKAGE with task
```

## BUILD_WORK_PACKAGE

```
full_task = mcp__joan__get_task(task.id)
comments = mcp__joan__list_task_comments(task.id)

# Extract Reviewer→Ops handoff context
reviewer_context = extractStageContext(comments, "reviewer", "ops")

# For merge-with-guidance, also extract Architect guidance
architect_guidance = null
IF OPERATION_MODE == "merge-with-guidance":
  architect_guidance = extractArchitectGuidance(comments)

WORK_PACKAGE = {
  task_id: full_task.id,
  task_title: full_task.title,
  task_description: full_task.description,
  task_tags: extractTagNames(full_task.tags),
  mode: OPERATION_MODE,
  workflow_mode: MODE,
  project_id: PROJECT_ID,
  project_name: PROJECT_NAME,
  previous_stage_context: reviewer_context,
  architect_guidance: architect_guidance
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
    Process this task and return a WorkerResult JSON.

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
       - If resolution fails: Return invoke_agent for Architect
    4. Run verification tests
    5. Push to develop
    6. Delete feature branch (local and remote)
    7. Move task to Deploy column
    8. Remove Review-Approved, Ops-Ready tags
    9. In YOLO mode: Immediately complete task to Done

    ### If mode == "merge-with-guidance":
    1. Read Architect guidance from work_package.architect_guidance
    2. Apply recommended conflict resolution
    3. Run verification tests
    4. If still failing: Return rework-requested to Dev
    5. If passing: Complete merge, delete branch, move to Deploy

    Return WorkerResult JSON with:
    - success: true/false
    - joan_actions: tag/column operations
    - invoke_agent: (optional) if Architect guidance needed

WORKER_RESULT = Task.result

IF WORKER_RESULT.success:
  logWorkerActivity(".", "Ops", "COMPLETE", "task=#{WORK_PACKAGE.task_id} success")
ELSE:
  logWorkerActivity(".", "Ops", "FAIL", "task=#{WORK_PACKAGE.task_id} error={WORKER_RESULT.error}")

GOTO PROCESS_RESULT
```

## PROCESS_RESULT

```
IF NOT WORKER_RESULT.success:
  Report: "Ops worker failed: {WORKER_RESULT.error}"
  mcp__joan__create_task_comment(
    task_id: WORK_PACKAGE.task_id,
    content: "ALS/1\nactor: coordinator\nintent: error\naction: worker-failed\nsummary: Ops worker failed: {WORKER_RESULT.error}"
  )
  RETURN

# Check for agent invocation request
IF WORKER_RESULT.invoke_agent:
  invocation = WORKER_RESULT.invoke_agent
  Report: "Ops requesting Architect invocation for conflict resolution"

  # Add Invoke-Architect tag
  addTag(PROJECT_ID, WORK_PACKAGE.task_id, "Invoke-Architect")

  # Store invocation context as comment
  invoke_comment = formatInvokeComment(invocation)
  mcp__joan__create_task_comment(WORK_PACKAGE.task_id, invoke_comment)
  Report: "  Stored invocation context, Architect will process next cycle"

  # Set INVOCATION_PENDING flag for fast resolution (skip sleep)
  # This is handled by the router, not this handler
  RETURN with INVOCATION_PENDING = true

# Execute joan_actions
FOR action IN WORKER_RESULT.joan_actions:
  executeJoanAction(action, PROJECT_ID, WORK_PACKAGE.task_id)

# YOLO mode: auto-complete to Done
IF MODE == "yolo" AND WORKER_RESULT.outcome == "merged":
  Report: "  [YOLO] Auto-completing task to Done"

  columns = mcp__joan__list_columns(PROJECT_ID)
  done_col = find col IN columns WHERE col.name == "Done"
  IF done_col:
    mcp__joan__update_task(WORK_PACKAGE.task_id, column_id: done_col.id)

  mcp__joan__create_task_comment(
    task_id: WORK_PACKAGE.task_id,
    content: "ALS/1\nactor: coordinator\nintent: auto-complete\naction: yolo-done\nsummary: YOLO mode auto-completed task after merge"
  )

Report: "**Ops worker completed for '{WORK_PACKAGE.task_title}'**"
```

## Helper Functions

```
def extractArchitectGuidance(comments):
  FOR comment IN reversed(comments):
    content = comment.content
    IF "action: architect-guidance" IN content OR "action: conflict-resolution" IN content:
      # Parse the guidance
      RETURN {
        resolution_strategy: extractField(content, "resolution_strategy:"),
        files_to_keep: extractListFromALS(content, "files_to_keep:"),
        changes_to_apply: extractListFromALS(content, "changes_to_apply:"),
        test_commands: extractListFromALS(content, "test_commands:")
      }
  RETURN null

def formatInvokeComment(invocation):
  lines = [
    "ALS/1",
    "actor: ops",
    "intent: request",
    "action: invoke-request",
    "invoked_agent: architect",
    "invocation_mode: {invocation.mode}",
    "summary: {invocation.context.reason}"
  ]

  IF invocation.context.question:
    lines.push("question: {invocation.context.question}")

  IF invocation.context.files_of_interest:
    lines.push("files_of_interest:")
    FOR file IN invocation.context.files_of_interest:
      lines.push("- {file}")

  IF invocation.context.conflict_details:
    cd = invocation.context.conflict_details
    lines.push("conflict_details:")
    lines.push("  conflicting_files: {cd.conflicting_files}")
    lines.push("  develop_summary: {cd.develop_summary}")
    lines.push("  feature_summary: {cd.feature_summary}")

  lines.push("resume_as:")
  lines.push("  agent_type: ops")
  lines.push("  mode: merge-with-guidance")

  RETURN lines.join("\n")

def addTag(projectId, taskId, tagName):
  project_tags = mcp__joan__list_project_tags(projectId)
  tag = find tag IN project_tags WHERE tag.name == tagName
  IF NOT tag:
    tag = mcp__joan__create_project_tag(projectId, tagName)
  mcp__joan__add_tag_to_task(projectId, taskId, tag.id)

def removeTag(projectId, taskId, tagName):
  project_tags = mcp__joan__list_project_tags(projectId)
  tag = find tag IN project_tags WHERE tag.name == tagName
  IF tag:
    TRY:
      mcp__joan__remove_tag_from_task(projectId, taskId, tag.id)
    CATCH:
      PASS

def executeJoanAction(action, projectId, taskId):
  type = action.type

  IF type == "add_tag":
    addTag(projectId, taskId, action.tag_name)
    Report: "  Added tag: {action.tag_name}"

  ELIF type == "remove_tag":
    removeTag(projectId, taskId, action.tag_name)
    Report: "  Removed tag: {action.tag_name}"

  ELIF type == "move_to_column":
    columns = mcp__joan__list_columns(projectId)
    col = find col IN columns WHERE col.name == action.column_name
    IF col:
      mcp__joan__update_task(taskId, column_id: col.id)
      Report: "  Moved to column: {action.column_name}"

  ELIF type == "add_comment":
    mcp__joan__create_task_comment(taskId, action.content)
    Report: "  Added comment"

def extractStageContext(comments, fromStage, toStage):
  FOR comment IN reversed(comments):
    content = comment.content
    IF "intent: handoff" IN content AND "from_stage: {fromStage}" IN content AND "to_stage: {toStage}" IN content:
      RETURN parseHandoffContent(content)
  RETURN null

def extractTagNames(tags):
  names = []
  FOR tag IN tags:
    names.push(tag.name)
  RETURN names

def extractField(content, fieldName):
  FOR line IN content.split("\n"):
    trimmed = line.trim()
    IF trimmed.startsWith(fieldName):
      RETURN trimmed.substring(fieldName.length).trim()
  RETURN null

def extractListFromALS(content, sectionName):
  items = []
  inSection = false
  FOR line IN content.split("\n"):
    trimmed = line.trim()
    IF trimmed == sectionName:
      inSection = true
      CONTINUE
    IF inSection AND trimmed.startsWith("- "):
      items.push(trimmed.substring(2))
    ELIF inSection AND NOT trimmed.startsWith("- ") AND trimmed.length > 0:
      inSection = false
  RETURN items

def logWorkerActivity(projectDir, workerType, status, message):
  logFile = "{projectDir}/.claude/logs/worker-activity.log"
  timestamp = NOW.strftime("%Y-%m-%d %H:%M:%S")
  Bash: mkdir -p "$(dirname {logFile})" && echo "[{timestamp}] [{workerType}] [{status}] {message}" >> {logFile}
```
