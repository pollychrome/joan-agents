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
MODEL = config.settings.model OR "opus"
MODE = config.settings.mode OR "standard"
TIMEOUT_DEV = config.settings.workerTimeouts.dev OR 60

IF NOT config.agents.devs.enabled:
  Report: "Dev agent disabled in config"
  EXIT
```

## Single Task Mode (Event-Driven)

```
IF TASK_ID provided:
  Report: "Dev Handler: Processing task {TASK_ID} mode={OPERATION_MODE}"

  task = mcp__joan__get_task(TASK_ID)
  comments = mcp__joan__list_task_comments(TASK_ID)
  columns = mcp__joan__list_columns(PROJECT_ID)

  COLUMN_CACHE = {}
  FOR col IN columns:
    COLUMN_CACHE[col.name] = col.id

  TAG_SET = Set()
  FOR tag IN task.tags:
    TAG_SET.add(tag.name)

  # Verify task is in Development column
  IF task.column_id != COLUMN_CACHE["Development"]:
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

  # CLAIM TASK FIRST (atomic operation)
  GOTO CLAIM_TASK
```

## Batch Mode (Polling)

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

  GOTO CLAIM_TASK with task
```

## CLAIM_TASK

```
Report: "Claiming task '{task.title}' for Dev-1"

# Atomically add Claimed-Dev-1 tag
project_tags = mcp__joan__list_project_tags(PROJECT_ID)
claim_tag = find tag IN project_tags WHERE tag.name == "Claimed-Dev-1"
IF NOT claim_tag:
  claim_tag = mcp__joan__create_project_tag(PROJECT_ID, "Claimed-Dev-1")

mcp__joan__add_tag_to_task(PROJECT_ID, task.id, claim_tag.id)

# Verify claim succeeded (race condition check)
verification = mcp__joan__get_task(task.id)
claimed = false
FOR tag IN verification.tags:
  IF tag.name == "Claimed-Dev-1":
    claimed = true
    BREAK

IF NOT claimed:
  Report: "Claim verification failed - race condition, skipping"
  EXIT

Report: "Claim successful, proceeding with {OPERATION_MODE}"

# Fetch full details for work package
full_task = mcp__joan__get_task(task.id)
comments = mcp__joan__list_task_comments(task.id)

# Extract Architect→Dev handoff context
architect_context = extractStageContext(comments, "architect", "dev")

# For rework mode, extract Reviewer→Dev feedback
reviewer_feedback = null
IF OPERATION_MODE == "rework":
  reviewer_feedback = extractReviewerFeedback(comments)

WORK_PACKAGE = {
  task_id: full_task.id,
  task_title: full_task.title,
  task_description: full_task.description,
  task_tags: extractTagNames(full_task.tags),
  mode: OPERATION_MODE,
  workflow_mode: MODE,
  project_id: PROJECT_ID,
  project_name: PROJECT_NAME,
  previous_stage_context: architect_context,
  reviewer_feedback: reviewer_feedback
}

GOTO DISPATCH_WORKER
```

## DISPATCH_WORKER

```
Report: "**Dev worker claimed task '{WORK_PACKAGE.task_title}' (mode: {OPERATION_MODE})**"

logWorkerActivity(".", "Dev", "START", "task=#{WORK_PACKAGE.task_id} '{WORK_PACKAGE.task_title}' mode={OPERATION_MODE}")

max_turns = TIMEOUT_DEV * 2  # 60 min = 120 turns

Task agent:
  subagent_type: dev-worker
  model: MODEL
  max_turns: max_turns
  prompt: |
    Process this task and return a WorkerResult JSON.

    ## Work Package
    ```json
    {JSON.stringify(WORK_PACKAGE, null, 2)}
    ```

    ## Mode: {WORK_PACKAGE.mode}

    ### If mode == "implement":
    - Create feature branch from develop
    - Implement all sub-tasks (DES-*, DEV-*, TEST-*)
    - Create pull request
    - On success: Remove Claimed-Dev-1, remove Planned, add Dev-Complete/Design-Complete/Test-Complete
    - Move to Review column

    ### If mode == "rework":
    - Read reviewer feedback from work package
    - Address specific issues mentioned
    - Push fixes to existing branch
    - On success: Remove Claimed-Dev-1, remove Rework-Requested, add Rework-Complete
    - Move to Review column

    ### If mode == "conflict":
    - Merge develop into feature branch
    - Resolve conflicts
    - Run tests
    - On success: Remove Claimed-Dev-1, remove Merge-Conflict, add Rework-Complete
    - Move to Review column

    IMPORTANT: Always return joan_actions to remove Claimed-Dev-1 tag on completion or failure.

WORKER_RESULT = Task.result

IF WORKER_RESULT.success:
  logWorkerActivity(".", "Dev", "COMPLETE", "task=#{WORK_PACKAGE.task_id} success")
ELSE:
  logWorkerActivity(".", "Dev", "FAIL", "task=#{WORK_PACKAGE.task_id} error={WORKER_RESULT.error}")

GOTO PROCESS_RESULT
```

## PROCESS_RESULT

```
# ALWAYS release claim first, even on failure
ensureClaimReleased(PROJECT_ID, WORK_PACKAGE.task_id)

IF NOT WORKER_RESULT.success:
  Report: "Dev worker failed: {WORKER_RESULT.error}"

  # Add Implementation-Failed tag
  project_tags = mcp__joan__list_project_tags(PROJECT_ID)
  fail_tag = find tag IN project_tags WHERE tag.name == "Implementation-Failed"
  IF NOT fail_tag:
    fail_tag = mcp__joan__create_project_tag(PROJECT_ID, "Implementation-Failed")
  mcp__joan__add_tag_to_task(PROJECT_ID, WORK_PACKAGE.task_id, fail_tag.id)

  # Add failure comment
  mcp__joan__create_task_comment(
    task_id: WORK_PACKAGE.task_id,
    content: "ALS/1\nactor: coordinator\nintent: error\naction: implementation-failed\nsummary: Dev worker failed: {WORKER_RESULT.error}\ndetails:\n- Manual intervention required\n- Remove Implementation-Failed tag after resolving issue"
  )
  RETURN

# Execute joan_actions
FOR action IN WORKER_RESULT.joan_actions:
  executeJoanAction(action, PROJECT_ID, WORK_PACKAGE.task_id)

# Write handoff context (Dev→Reviewer)
IF WORKER_RESULT.handoff_context:
  handoff_comment = formatHandoffComment({
    from_stage: "dev",
    to_stage: "reviewer",
    summary: WORKER_RESULT.handoff_context.summary OR "Implementation complete",
    key_decisions: WORKER_RESULT.handoff_context.key_decisions OR [],
    files_of_interest: WORKER_RESULT.handoff_context.files_of_interest OR [],
    warnings: WORKER_RESULT.handoff_context.warnings OR []
  })
  mcp__joan__create_task_comment(WORK_PACKAGE.task_id, handoff_comment)
  Report: "  Wrote Dev→Reviewer handoff"

Report: "**Dev worker completed for '{WORK_PACKAGE.task_title}'**"
```

## Helper Functions

```
def ensureClaimReleased(projectId, taskId):
  # Always remove Claimed-Dev-1 tag
  project_tags = mcp__joan__list_project_tags(projectId)
  claim_tag = find tag IN project_tags WHERE tag.name == "Claimed-Dev-1"
  IF claim_tag:
    TRY:
      mcp__joan__remove_tag_from_task(projectId, taskId, claim_tag.id)
      Report: "  Released claim (Claimed-Dev-1 removed)"
    CATCH:
      Report: "  Warning: Failed to release claim"

def extractReviewerFeedback(comments):
  # Find most recent rework request comment
  FOR comment IN reversed(comments):
    content = comment.content
    IF "action: rework-requested" IN content OR "intent: rework" IN content:
      # Parse blockers, warnings, suggestions
      RETURN {
        blockers: extractListFromALS(content, "blockers:"),
        warnings: extractListFromALS(content, "warnings:"),
        suggestions: extractListFromALS(content, "suggestions:")
      }
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
      inSection = false  # New section started
  RETURN items

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

  IF context.key_decisions AND context.key_decisions.length > 0:
    lines.push("key_decisions:")
    FOR decision IN context.key_decisions:
      lines.push("- {decision}")

  IF context.files_of_interest AND context.files_of_interest.length > 0:
    lines.push("files_of_interest:")
    FOR file IN context.files_of_interest:
      lines.push("- {file}")

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
