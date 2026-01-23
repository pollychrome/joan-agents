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
MODEL = config.settings.model OR "opus"
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

  task = mcp__joan__get_task(TASK_ID)
  comments = mcp__joan__list_task_comments(TASK_ID)
  columns = mcp__joan__list_columns(PROJECT_ID)

  # Build column cache
  COLUMN_CACHE = {}
  FOR col IN columns:
    COLUMN_CACHE[col.name] = col.id

  # Build tag set
  TAG_SET = Set()
  FOR tag IN task.tags:
    TAG_SET.add(tag.name)

  # Verify task is in expected state
  IF NOT (task.column_id == COLUMN_CACHE["Analyse"] OR
          (task.column_id == COLUMN_CACHE["Review"] AND TAG_SET.has("Invoke-Architect"))):
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

  # Extract BA→Architect handoff context
  ba_context = extractStageContext(comments, "ba", "architect")

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
    previous_stage_context: ba_context
  }

  GOTO DISPATCH_WORKER
```

## Batch Mode (Polling)

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
  # (Serial pipeline: only one task at a time in Dev→Review→Deploy)
  IF hasTasksInDevPipeline(tasks, TAG_INDEX, COLUMN_CACHE):
    Report: "Pipeline gate BLOCKED - task in Development/Review, skipping new plans"
    # Filter out "plan" mode tasks, keep finalize/revise/advisory
    ARCHITECT_QUEUE = ARCHITECT_QUEUE.filter(item => item.mode != "plan")

  IF ARCHITECT_QUEUE.length == 0:
    Report: "All remaining tasks blocked by pipeline gate"
    EXIT

  # Process first task (one at a time for Architect)
  item = ARCHITECT_QUEUE[0]
  task = item.task
  mode = item.mode

  full_task = mcp__joan__get_task(task.id)
  comments = mcp__joan__list_task_comments(task.id)

  ba_context = extractStageContext(comments, "ba", "architect")

  WORK_PACKAGE = {
    task_id: full_task.id,
    task_title: full_task.title,
    task_description: full_task.description,
    task_tags: extractTagNames(full_task.tags),
    mode: mode,
    workflow_mode: MODE,
    project_id: PROJECT_ID,
    project_name: PROJECT_NAME,
    previous_stage_context: ba_context
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
    Process this task and return a WorkerResult JSON.

    ## Work Package
    ```json
    {JSON.stringify(WORK_PACKAGE, null, 2)}
    ```

    ## Mode: {WORK_PACKAGE.mode}

    ### If mode == "plan":
    - Analyze codebase and create detailed implementation plan
    - Add plan to task description
    - Add Plan-Pending-Approval tag
    - Remove Ready tag

    ### If mode == "finalize":
    - Remove Plan-Pending-Approval and Plan-Approved tags
    - Add Planned tag
    - Move task to Development column

    ### If mode == "revise":
    - Review rejection feedback in comments
    - Update plan based on feedback
    - Remove Plan-Rejected tag
    - Keep Plan-Pending-Approval (awaits re-approval)

    ### If mode == "advisory-conflict":
    - Analyze merge conflict details in task comments
    - Provide resolution strategy
    - Add Architect-Assist-Complete tag
    - Remove Invoke-Architect tag

    Return WorkerResult JSON with joan_actions array.

WORKER_RESULT = Task.result

IF WORKER_RESULT.success:
  logWorkerActivity(".", "Architect", "COMPLETE", "task=#{WORK_PACKAGE.task_id} success")
ELSE:
  logWorkerActivity(".", "Architect", "FAIL", "task=#{WORK_PACKAGE.task_id} error={WORKER_RESULT.error}")

GOTO PROCESS_RESULT
```

## PROCESS_RESULT

```
IF NOT WORKER_RESULT.success:
  Report: "Architect worker failed: {WORKER_RESULT.error}"
  mcp__joan__create_task_comment(
    task_id: WORK_PACKAGE.task_id,
    content: "ALS/1\nactor: coordinator\nintent: error\naction: worker-failed\nsummary: Architect worker failed: {WORKER_RESULT.error}"
  )
  RETURN

# Execute joan_actions
FOR action IN WORKER_RESULT.joan_actions:
  executeJoanAction(action, PROJECT_ID, WORK_PACKAGE.task_id)

# Write handoff context (Architect→Dev)
IF WORKER_RESULT.handoff_context AND WORK_PACKAGE.mode IN ["plan", "finalize"]:
  handoff_comment = formatHandoffComment({
    from_stage: "architect",
    to_stage: "dev",
    summary: WORKER_RESULT.handoff_context.summary,
    key_decisions: WORKER_RESULT.handoff_context.key_decisions OR [],
    files_of_interest: WORKER_RESULT.handoff_context.files_of_interest OR [],
    warnings: WORKER_RESULT.handoff_context.warnings OR [],
    dependencies: WORKER_RESULT.handoff_context.dependencies OR []
  })
  mcp__joan__create_task_comment(WORK_PACKAGE.task_id, handoff_comment)
  Report: "  Wrote Architect→Dev handoff"

Report: "**Architect worker completed for '{WORK_PACKAGE.task_title}'**"
```

## Pipeline Gate Check

```
def hasTasksInDevPipeline(tasks, TAG_INDEX, COLUMN_CACHE):
  FOR task IN tasks:
    # Check Development column (not Done or merged)
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

```
def executeJoanAction(action, projectId, taskId):
  type = action.type

  IF type == "add_tag":
    project_tags = mcp__joan__list_project_tags(projectId)
    tag = find tag IN project_tags WHERE tag.name == action.tag_name
    IF NOT tag:
      tag = mcp__joan__create_project_tag(projectId, action.tag_name)
    mcp__joan__add_tag_to_task(projectId, taskId, tag.id)
    Report: "  Added tag: {action.tag_name}"

  ELIF type == "remove_tag":
    project_tags = mcp__joan__list_project_tags(projectId)
    tag = find tag IN project_tags WHERE tag.name == action.tag_name
    IF tag:
      mcp__joan__remove_tag_from_task(projectId, taskId, tag.id)
      Report: "  Removed tag: {action.tag_name}"

  ELIF type == "move_to_column":
    columns = mcp__joan__list_columns(projectId)
    col = find col IN columns WHERE col.name == action.column_name
    IF col:
      mcp__joan__update_task(taskId, column_id: col.id)
      Report: "  Moved to column: {action.column_name}"

  ELIF type == "update_description":
    mcp__joan__update_task(taskId, description: action.description)
    Report: "  Updated description"

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

def formatHandoffComment(context):
  lines = [
    "ALS/1",
    "actor: {context.from_stage}",
    "intent: handoff",
    "action: context-handoff",
    "from_stage: {context.from_stage}",
    "to_stage: {context.to_stage}",
    "summary: {context.summary}"
  ]

  IF context.key_decisions.length > 0:
    lines.push("key_decisions:")
    FOR decision IN context.key_decisions:
      lines.push("- {decision}")

  IF context.files_of_interest.length > 0:
    lines.push("files_of_interest:")
    FOR file IN context.files_of_interest:
      lines.push("- {file}")

  IF context.warnings.length > 0:
    lines.push("warnings:")
    FOR warning IN context.warnings:
      lines.push("- {warning}")

  IF context.dependencies.length > 0:
    lines.push("dependencies:")
    FOR dep IN context.dependencies:
      lines.push("- {dep}")

  RETURN lines.join("\n")

def logWorkerActivity(projectDir, workerType, status, message):
  logFile = "{projectDir}/.claude/logs/worker-activity.log"
  timestamp = NOW.strftime("%Y-%m-%d %H:%M:%S")
  Bash: mkdir -p "$(dirname {logFile})" && echo "[{timestamp}] [{workerType}] [{status}] {message}" >> {logFile}
```
