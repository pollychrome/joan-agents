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

# Model resolution: settings.models.ba → settings.model → "haiku" (built-in default)
MODEL = config.settings.models?.ba OR config.settings.model OR "haiku"

MODE = config.settings.mode OR "standard"
TIMEOUT_BA = config.settings.workerTimeouts.ba OR 10

IF NOT config.agents.businessAnalyst.enabled:
  Report: "BA agent disabled in config"
  EXIT
```

## Model Escalation (BA-specific)

BA uses haiku by default but auto-escalates to sonnet for complex tasks:

```
# BA escalation: haiku → sonnet for complex tasks
IF MODEL == "haiku":
  ESCALATE = false
  ESCALATE_REASON = ""

  # Trigger 1: Long description (>2000 chars)
  IF task_description.length > 2000:
    ESCALATE = true
    ESCALATE_REASON = "description >2000 chars"

  # Trigger 2: Integration keywords
  keywords = ["integration", "api", "third-party", "external", "oauth", "webhook", "database migration"]
  IF any keyword in task_description.toLowerCase():
    ESCALATE = true
    ESCALATE_REASON = "integration keyword detected"

  # Trigger 3: Many acceptance criteria (>5 bullets)
  bullet_count = count occurrences of "- [ ]" or "- " in task_description
  IF bullet_count > 5:
    ESCALATE = true
    ESCALATE_REASON = "{bullet_count} acceptance criteria"

  IF ESCALATE:
    MODEL = "sonnet"
    Report: "BA escalating to sonnet: {ESCALATE_REASON}"
```

## Single Task Mode (Event-Driven)

When `--task=UUID` is provided:

```
IF TASK_ID provided:
  Report: "BA Handler: Processing single task {TASK_ID}"

  # Use shared smart payload extraction (see helpers.md)
  payload_data = extractSmartPayload(TASK_ID, PROJECT_ID)
  task = payload_data.task
  handoff_context = payload_data.handoff_context
  recent_comments = payload_data.recent_comments

  # Determine mode from tags
  hasNeedsClarification = task.tags.includes("Needs-Clarification")
  hasClarificationAnswered = task.tags.includes("Clarification-Answered")

  IF hasNeedsClarification AND hasClarificationAnswered:
    BA_MODE = "reevaluate"
  ELSE:
    BA_MODE = "evaluate"

  # Build work package
  WORK_PACKAGE = {
    task_id: task.id,
    task_title: task.title,
    task_description: task.description,
    task_tags: task.tags,
    mode: BA_MODE,
    workflow_mode: MODE,
    project_id: PROJECT_ID,
    project_name: PROJECT_NAME,
    handoff_context: handoff_context,
    recent_comments: recent_comments
  }

  # Dispatch BA worker
  GOTO DISPATCH_WORKER
```

## Batch Mode (Polling)

When `--all` is provided (legacy mode, no smart payload):

```
IF ALL_MODE:
  MAX_TASKS = MAX_OVERRIDE OR 10
  Report: "BA Handler: Processing up to {MAX_TASKS} tasks"

  # Fetch all tasks (batch mode doesn't have smart payloads)
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
      project_name: PROJECT_NAME,
      handoff_context: null,
      recent_comments: comments
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
    ## BA Worker - Phase 3 Result Protocol

    Evaluate this task and return a structured result.

    ## Work Package
    ```json
    {JSON.stringify(WORK_PACKAGE, null, 2)}
    ```

    ## Instructions

    You are the BA (Business Analyst) worker.

    ### If mode == "evaluate":
    - Analyze the task requirements
    - Check if requirements are clear and complete
    - If clear: Return result_type "requirements_complete"
    - If unclear: Return result_type "needs_clarification" with questions in comment

    ### If mode == "reevaluate":
    - Read the recent comments for clarification answers
    - Process the answers and update your understanding
    - Return result_type "clarification_processed"

    ## Return Format (Phase 3)

    Return a JSON object with:
    ```json
    {
      "success": true,
      "result_type": "requirements_complete" | "needs_clarification" | "clarification_processed",
      "structured_comment": { ... },
      "output": {
        "questions": ["Question 1?", "Question 2?"]  // Only for needs_clarification
      }
    }
    ```

    ## Structured Comment (server generates ALS format)

    For requirements_complete or clarification_processed:
    ```json
    "structured_comment": {
      "actor": "ba", "intent": "handoff", "action": "context-handoff",
      "from_stage": "ba", "to_stage": "architect",
      "summary": "Brief summary of requirements",
      "key_decisions": ["Decision 1", "Decision 2"],
      "warnings": ["Any concerns"]
    }
    ```

    For needs_clarification:
    ```json
    "structured_comment": {
      "actor": "ba", "intent": "clarification", "action": "needs-clarification",
      "summary": "Why clarification is needed",
      "questions": ["Question 1?", "Question 2?"]
    }
    ```

    IMPORTANT: Do NOT return joan_actions. Joan backend handles state transitions automatically.

WORKER_RESULT = Task.result

# Log worker completion
IF WORKER_RESULT.success:
  logWorkerActivity(".", "BA", "COMPLETE", "task=#{task.id} success result_type={WORKER_RESULT.result_type}")
ELSE:
  logWorkerActivity(".", "BA", "FAIL", "task=#{task.id} error={WORKER_RESULT.error}")

# Process worker result
GOTO PROCESS_RESULT
```

## PROCESS_RESULT (Phase 3)

```
# Use shared result submission (see helpers.md)
submitWorkerResult("ba-worker", WORKER_RESULT, WORK_PACKAGE, PROJECT_ID)
```
