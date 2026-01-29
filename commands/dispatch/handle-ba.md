---
description: Handle BA queue - evaluate requirements, mark tasks Ready
argument-hint: --task=UUID
allowed-tools: Bash, Read, Task, mcp__joan__*, mcp__plugin_agents_joan__*
---

# BA Handler

Process BA queue: evaluate requirements, ask clarifying questions, mark tasks Ready.

## CRITICAL: Smart Payload Check (Do This First!)

**BEFORE calling ANY MCP tools**, check for a pre-fetched smart payload file:

1. First, try to read the file `.claude/smart-payload-{TASK_ID}.json` where TASK_ID comes from the `--task=` argument
2. If the file exists and contains valid JSON with a `"task"` field: Use that data. DO NOT call MCP.
3. If the file doesn't exist or is invalid: Fall back to MCP calls.

This is critical because the coordinator pre-fetches task data to avoid redundant API calls.

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

When `--task=UUID` is provided, first check for a pre-fetched smart payload before using MCP.

### Step 1: Check for Smart Payload

**IMPORTANT**: Before calling any MCP tools, run this Bash command to check for pre-fetched task data:

```bash
echo "$JOAN_SMART_PAYLOAD"
```

If this outputs a JSON string (more than 10 characters), parse it and use that data instead of calling MCP. This avoids redundant API calls since ws-client.py pre-fetches the task data.

### Step 2: Get Task Data

**If smart payload exists** (Bash output was valid JSON):
- Parse the JSON from the env var
- Extract: `task`, `handoff_context`, `recent_comments`, `tags`
- Skip MCP calls entirely

**If no smart payload** (Bash output was empty or short):
- Fall back to MCP: `mcp__joan__get_task(TASK_ID)` and `mcp__joan__list_task_comments(TASK_ID)`

### Step 3: Process Task

```
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
