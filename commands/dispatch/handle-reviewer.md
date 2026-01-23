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
MODEL = config.settings.model OR "opus"
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

  task = mcp__joan__get_task(TASK_ID)
  comments = mcp__joan__list_task_comments(TASK_ID)
  columns = mcp__joan__list_columns(PROJECT_ID)

  COLUMN_CACHE = {}
  FOR col IN columns:
    COLUMN_CACHE[col.name] = col.id

  TAG_SET = Set()
  FOR tag IN task.tags:
    TAG_SET.add(tag.name)

  # Verify task is in Review column
  IF task.column_id != COLUMN_CACHE["Review"]:
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

  GOTO BUILD_WORK_PACKAGE with task
```

## BUILD_WORK_PACKAGE

```
full_task = mcp__joan__get_task(task.id)
comments = mcp__joan__list_task_comments(task.id)

# Extract Dev→Reviewer handoff context
dev_context = extractStageContext(comments, "dev", "reviewer")

WORK_PACKAGE = {
  task_id: full_task.id,
  task_title: full_task.title,
  task_description: full_task.description,
  task_tags: extractTagNames(full_task.tags),
  mode: "review",
  workflow_mode: MODE,
  project_id: PROJECT_ID,
  project_name: PROJECT_NAME,
  previous_stage_context: dev_context
}

GOTO DISPATCH_WORKER
```

## DISPATCH_WORKER

```
Report: "**Reviewer worker dispatched for '{WORK_PACKAGE.task_title}'**"

# Add Review-In-Progress tag
project_tags = mcp__joan__list_project_tags(PROJECT_ID)
review_tag = find tag IN project_tags WHERE tag.name == "Review-In-Progress"
IF NOT review_tag:
  review_tag = mcp__joan__create_project_tag(PROJECT_ID, "Review-In-Progress")
mcp__joan__add_tag_to_task(PROJECT_ID, WORK_PACKAGE.task_id, review_tag.id)

logWorkerActivity(".", "Reviewer", "START", "task=#{WORK_PACKAGE.task_id} '{WORK_PACKAGE.task_title}'")

max_turns = TIMEOUT_REVIEWER * 2

Task agent:
  subagent_type: reviewer-worker
  model: MODEL
  max_turns: max_turns
  prompt: |
    Process this task and return a WorkerResult JSON.

    ## Work Package
    ```json
    {JSON.stringify(WORK_PACKAGE, null, 2)}
    ```

    ## Review Process
    1. Merge develop into feature branch (detect conflicts)
    2. If conflicts: Return rework-requested with Merge-Conflict tag
    3. Run comprehensive code review:
       - Functional completeness (all sub-tasks checked)
       - Code quality (conventions, logic, error handling)
       - Security (no secrets, input validation)
       - Tests (exist and pass)
    4. If issues found: Return rework-requested with detailed feedback
    5. If approved: Return approved with Review-Approved tag

    Return WorkerResult JSON with:
    - success: true/false
    - outcome: "approved" | "rework-requested"
    - joan_actions: tag operations
    - handoff_context: context for next stage (Ops if approved, Dev if rework)

WORKER_RESULT = Task.result

IF WORKER_RESULT.success:
  logWorkerActivity(".", "Reviewer", "COMPLETE", "task=#{WORK_PACKAGE.task_id} outcome={WORKER_RESULT.outcome}")
ELSE:
  logWorkerActivity(".", "Reviewer", "FAIL", "task=#{WORK_PACKAGE.task_id} error={WORKER_RESULT.error}")

GOTO PROCESS_RESULT
```

## PROCESS_RESULT

```
# Always remove Review-In-Progress
removeTag(PROJECT_ID, WORK_PACKAGE.task_id, "Review-In-Progress")

IF NOT WORKER_RESULT.success:
  Report: "Reviewer worker failed: {WORKER_RESULT.error}"
  mcp__joan__create_task_comment(
    task_id: WORK_PACKAGE.task_id,
    content: "ALS/1\nactor: coordinator\nintent: error\naction: worker-failed\nsummary: Reviewer worker failed: {WORKER_RESULT.error}"
  )
  RETURN

# Execute joan_actions
FOR action IN WORKER_RESULT.joan_actions:
  executeJoanAction(action, PROJECT_ID, WORK_PACKAGE.task_id)

# Handle outcome-specific actions
outcome = WORKER_RESULT.outcome

IF outcome == "approved":
  # Write Reviewer→Ops handoff
  IF WORKER_RESULT.handoff_context:
    handoff_comment = formatHandoffComment({
      from_stage: "reviewer",
      to_stage: "ops",
      summary: WORKER_RESULT.handoff_context.summary OR "Review approved",
      key_decisions: WORKER_RESULT.handoff_context.key_decisions OR [],
      warnings: WORKER_RESULT.handoff_context.warnings OR []
    })
    mcp__joan__create_task_comment(WORK_PACKAGE.task_id, handoff_comment)
    Report: "  Wrote Reviewer→Ops handoff"

  # YOLO mode: auto-add Ops-Ready tag
  IF MODE == "yolo":
    addTag(PROJECT_ID, WORK_PACKAGE.task_id, "Ops-Ready")
    Report: "  [YOLO] Auto-added Ops-Ready tag"
    mcp__joan__create_task_comment(
      task_id: WORK_PACKAGE.task_id,
      content: "ALS/1\nactor: coordinator\nintent: auto-approve\naction: yolo-ops-ready\nsummary: YOLO mode auto-approved for merge"
    )

ELIF outcome == "rework-requested":
  # Write Reviewer→Dev rework handoff
  IF WORKER_RESULT.handoff_context:
    rework_comment = formatReworkComment(WORKER_RESULT.handoff_context)
    mcp__joan__create_task_comment(WORK_PACKAGE.task_id, rework_comment)
    Report: "  Wrote Reviewer→Dev rework feedback"

  # Move task back to Development
  columns = mcp__joan__list_columns(PROJECT_ID)
  dev_col = find col IN columns WHERE col.name == "Development"
  IF dev_col:
    mcp__joan__update_task(WORK_PACKAGE.task_id, column_id: dev_col.id)
    Report: "  Moved to Development column"

Report: "**Reviewer worker completed for '{WORK_PACKAGE.task_title}' - {outcome}**"
```

## Helper Functions

```
def formatReworkComment(context):
  lines = [
    "ALS/1",
    "actor: reviewer",
    "intent: rework",
    "action: rework-requested",
    "from_stage: reviewer",
    "to_stage: dev",
    "summary: {context.summary OR 'Changes requested'}"
  ]

  IF context.blockers AND context.blockers.length > 0:
    lines.push("blockers:")
    FOR blocker IN context.blockers:
      lines.push("- {blocker}")

  IF context.warnings AND context.warnings.length > 0:
    lines.push("warnings:")
    FOR warning IN context.warnings:
      lines.push("- {warning}")

  IF context.suggestions AND context.suggestions.length > 0:
    lines.push("suggestions:")
    FOR suggestion IN context.suggestions:
      lines.push("- {suggestion}")

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
      PASS  # Tag might already be removed

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

  IF context.key_decisions AND context.key_decisions.length > 0:
    lines.push("key_decisions:")
    FOR decision IN context.key_decisions:
      lines.push("- {decision}")

  IF context.warnings AND context.warnings.length > 0:
    lines.push("warnings:")
    FOR warning IN context.warnings:
      lines.push("- {warning}")

  RETURN lines.join("\n")

def logWorkerActivity(projectDir, workerType, status, message):
  logFile = "{projectDir}/.claude/logs/worker-activity.log"
  timestamp = NOW.strftime("%Y-%m-%d %H:%M:%S")
  Bash: mkdir -p "$(dirname {logFile})" && echo "[{timestamp}] [{workerType}] [{status}] {message}" >> {logFile}
```
