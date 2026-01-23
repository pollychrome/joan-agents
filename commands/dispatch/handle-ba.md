---
description: Handle BA queue - evaluate requirements, mark tasks Ready
argument-hint: [--task=UUID] [--all] [--max=N]
allowed-tools: Bash, Read, Task
---

# BA Handler

Process BA queue: evaluate requirements, ask clarifying questions, mark tasks Ready.

## Arguments

- `--task=UUID` → Process single task (event-driven mode)
- `--all` → Process all BA tasks in queue (polling mode)
- `--max=N` → Maximum tasks to process (default: 10)

## Configuration

```
# Load config
config = JSON.parse(read(".joan-agents.json"))
PROJECT_ID = config.projectId
PROJECT_NAME = config.projectName
MODEL = config.settings.model OR "opus"
MODE = config.settings.mode OR "standard"
TIMEOUT_BA = config.settings.workerTimeouts.ba OR 10

IF NOT config.agents.businessAnalyst.enabled:
  Report: "BA agent disabled in config"
  EXIT
```

## Single Task Mode (Event-Driven)

When `--task=UUID` is provided:

```
IF TASK_ID provided:
  Report: "BA Handler: Processing single task {TASK_ID}"

  # Fetch only the specific task
  task = mcp__joan__get_task(TASK_ID)
  comments = mcp__joan__list_task_comments(TASK_ID)

  # Verify task is in expected state (To Do column, no Ready tag)
  columns = mcp__joan__list_columns(PROJECT_ID)
  TODO_COLUMN_ID = find column where name == "To Do"

  IF task.column_id != TODO_COLUMN_ID:
    Report: "Task not in To Do column, skipping"
    EXIT

  # Check for Ready tag
  hasReadyTag = false
  FOR tag IN task.tags:
    IF tag.name == "Ready":
      hasReadyTag = true
      BREAK

  IF hasReadyTag:
    Report: "Task already has Ready tag, skipping"
    EXIT

  # Determine mode
  hasNeedsClarification = false
  hasClarificationAnswered = false
  FOR tag IN task.tags:
    IF tag.name == "Needs-Clarification":
      hasNeedsClarification = true
    IF tag.name == "Clarification-Answered":
      hasClarificationAnswered = true

  IF hasNeedsClarification AND hasClarificationAnswered:
    mode = "reevaluate"
  ELSE:
    mode = "evaluate"

  # Build work package
  WORK_PACKAGE = {
    task_id: task.id,
    task_title: task.title,
    task_description: task.description,
    task_tags: extractTagNames(task.tags),
    mode: mode,
    workflow_mode: MODE,
    project_id: PROJECT_ID,
    project_name: PROJECT_NAME
  }

  # Dispatch BA worker
  GOTO DISPATCH_WORKER
```

## Batch Mode (Polling)

When `--all` is provided:

```
IF ALL_MODE:
  MAX_TASKS = MAX_OVERRIDE OR 10
  Report: "BA Handler: Processing up to {MAX_TASKS} tasks"

  # Fetch all tasks
  tasks = mcp__joan__list_tasks(project_id: PROJECT_ID)
  columns = mcp__joan__list_columns(PROJECT_ID)

  # Build column and tag indexes
  COLUMN_CACHE = {}
  FOR col IN columns:
    COLUMN_CACHE[col.name] = col.id

  TAG_INDEX = {}
  FOR task IN tasks:
    tagSet = Set()
    FOR tag IN task.tags:
      tagSet.add(tag.name)
    TAG_INDEX[task.id] = tagSet

  # Build BA queue
  BA_QUEUE = []

  FOR task IN tasks:
    taskId = task.id

    # Reevaluate: Needs-Clarification + Clarification-Answered
    IF task.column_id == COLUMN_CACHE["Analyse"] AND
       TAG_INDEX[taskId].has("Needs-Clarification") AND
       TAG_INDEX[taskId].has("Clarification-Answered"):
      BA_QUEUE.push({task, mode: "reevaluate"})
      CONTINUE

    # Evaluate: In To Do, no Ready tag
    IF task.column_id == COLUMN_CACHE["To Do"] AND
       NOT TAG_INDEX[taskId].has("Ready"):
      BA_QUEUE.push({task, mode: "evaluate"})

  Report: "BA queue: {BA_QUEUE.length} tasks"

  IF BA_QUEUE.length == 0:
    Report: "No BA tasks to process"
    EXIT

  # Process tasks up to max
  processed = 0
  FOR item IN BA_QUEUE:
    IF processed >= MAX_TASKS:
      BREAK

    task = item.task
    mode = item.mode

    # Fetch full task details
    full_task = mcp__joan__get_task(task.id)
    comments = mcp__joan__list_task_comments(task.id)

    WORK_PACKAGE = {
      task_id: full_task.id,
      task_title: full_task.title,
      task_description: full_task.description,
      task_tags: extractTagNames(full_task.tags),
      mode: mode,
      workflow_mode: MODE,
      project_id: PROJECT_ID,
      project_name: PROJECT_NAME
    }

    # Dispatch BA worker for this task
    GOTO DISPATCH_WORKER

    processed += 1

  Report: "Processed {processed} BA tasks"
  EXIT
```

## DISPATCH_WORKER

```
Report: "**BA worker dispatched for '{WORK_PACKAGE.task_title}'**"

# Log worker start
logWorkerActivity(".", "BA", "START", "task=#{task.id} '{WORK_PACKAGE.task_title}'")

# Calculate timeout in max_turns (roughly 1 turn = 30 seconds)
max_turns = TIMEOUT_BA * 2  # 10 min = 20 turns

Task agent:
  subagent_type: ba-worker
  model: MODEL
  max_turns: max_turns
  prompt: |
    Process this task and return a WorkerResult JSON.

    ## Work Package
    ```json
    {JSON.stringify(WORK_PACKAGE, null, 2)}
    ```

    ## Instructions
    You are the BA (Business Analyst) worker. Evaluate requirements and either:
    1. Mark task Ready (requirements complete)
    2. Add Needs-Clarification tag with questions
    3. Update task description with clarified requirements

    Return a WorkerResult JSON with:
    - success: boolean
    - joan_actions: array of MCP operations to execute
    - handoff_context: context for next stage (Architect)

WORKER_RESULT = Task.result

# Log worker completion
IF WORKER_RESULT.success:
  logWorkerActivity(".", "BA", "COMPLETE", "task=#{task.id} success")
ELSE:
  logWorkerActivity(".", "BA", "FAIL", "task=#{task.id} error={WORKER_RESULT.error}")

# Process worker result
GOTO PROCESS_RESULT
```

## PROCESS_RESULT

```
IF NOT WORKER_RESULT.success:
  Report: "BA worker failed: {WORKER_RESULT.error}"
  # Add failure comment
  mcp__joan__create_task_comment(
    task_id: WORK_PACKAGE.task_id,
    content: "ALS/1\nactor: coordinator\nintent: error\naction: worker-failed\nsummary: BA worker failed: {WORKER_RESULT.error}"
  )
  RETURN

# Execute joan_actions
FOR action IN WORKER_RESULT.joan_actions:
  action_type = action.type

  IF action_type == "add_tag":
    # Find or create tag
    project_tags = mcp__joan__list_project_tags(PROJECT_ID)
    tag = find tag IN project_tags WHERE tag.name == action.tag_name
    IF NOT tag:
      tag = mcp__joan__create_project_tag(PROJECT_ID, action.tag_name)
    mcp__joan__add_tag_to_task(PROJECT_ID, WORK_PACKAGE.task_id, tag.id)
    Report: "  Added tag: {action.tag_name}"

  ELIF action_type == "remove_tag":
    project_tags = mcp__joan__list_project_tags(PROJECT_ID)
    tag = find tag IN project_tags WHERE tag.name == action.tag_name
    IF tag:
      mcp__joan__remove_tag_from_task(PROJECT_ID, WORK_PACKAGE.task_id, tag.id)
      Report: "  Removed tag: {action.tag_name}"

  ELIF action_type == "move_to_column":
    columns = mcp__joan__list_columns(PROJECT_ID)
    col = find col IN columns WHERE col.name == action.column_name
    IF col:
      mcp__joan__update_task(WORK_PACKAGE.task_id, column_id: col.id)
      Report: "  Moved to column: {action.column_name}"

  ELIF action_type == "update_description":
    mcp__joan__update_task(WORK_PACKAGE.task_id, description: action.description)
    Report: "  Updated description"

  ELIF action_type == "add_comment":
    mcp__joan__create_task_comment(WORK_PACKAGE.task_id, action.content)
    Report: "  Added comment"

# Write handoff context if provided
IF WORKER_RESULT.handoff_context:
  handoff_comment = formatHandoffComment(WORKER_RESULT.handoff_context)
  mcp__joan__create_task_comment(WORK_PACKAGE.task_id, handoff_comment)
  Report: "  Wrote BA→Architect handoff"

Report: "**BA worker completed for '{WORK_PACKAGE.task_title}'**"
```

## Helper Functions

```
def extractTagNames(tags):
  names = []
  FOR tag IN tags:
    names.push(tag.name)
  RETURN names

def formatHandoffComment(context):
  lines = [
    "ALS/1",
    "actor: ba",
    "intent: handoff",
    "action: context-handoff",
    "from_stage: ba",
    "to_stage: architect",
    "summary: {context.summary OR 'Requirements evaluated'}"
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
