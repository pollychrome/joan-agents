---
description: Shared helper functions for coordinator modules (internal)
---

# Coordinator Helpers

Shared functions used by all handler modules.

## Tag Helpers

```
# Build tag index for O(1) lookups
def buildTagIndex(tasks):
  index = {}
  FOR task IN tasks:
    tagSet = Set()
    FOR tag IN task.tags:
      tagSet.add(tag.name)
    index[task.id] = tagSet
  RETURN index

# O(1) tag check using index
def hasTag(taskId, tagName, TAG_INDEX):
  RETURN TAG_INDEX[taskId]?.has(tagName) OR false

# Check if task is claimed by any dev
def isClaimedByAnyDev(taskId, TAG_INDEX, devCount=1):
  FOR n IN 1..devCount:
    IF hasTag(taskId, "Claimed-Dev-{n}", TAG_INDEX):
      RETURN true
  RETURN false
```

## Column Helpers

```
# Build column cache from MCP
def buildColumnCache(projectId):
  columns = mcp__joan__list_columns(projectId)
  cache = {}
  FOR col IN columns:
    cache[col.name] = col.id
  RETURN cache

# Check if task is in column
def inColumn(task, columnName, COLUMN_CACHE):
  RETURN task.column_id == COLUMN_CACHE[columnName]

# Get column name from ID
def getColumnName(columnId, COLUMN_CACHE):
  FOR name, id IN COLUMN_CACHE:
    IF id == columnId:
      RETURN name
  RETURN "Unknown"
```

## Workflow Tags

```
WORKFLOW_TAGS = [
  "Ready",
  "Needs-Clarification",
  "Clarification-Answered",
  "Plan-Pending-Approval",
  "Plan-Approved",
  "Plan-Rejected",
  "Planned",
  "Claimed-Dev-1",
  "Dev-Complete",
  "Design-Complete",
  "Test-Complete",
  "Review-In-Progress",
  "Review-Approved",
  "Rework-Requested",
  "Rework-Complete",
  "Ops-Ready",
  "Merge-Conflict",
  "Invoke-Architect",
  "Architect-Assist-Complete",
  "Implementation-Failed",
  "Branch-Setup-Failed"
]
```

## Context Handoff Helpers

```
# Extract stage context from last matching handoff comment
def extractStageContext(comments, fromStage, toStage):
  FOR comment IN reversed(comments):
    content = comment.content
    IF "intent: handoff" IN content AND "action: context-handoff" IN content:
      # Parse from_stage and to_stage
      parsedFrom = extractField(content, "from_stage:")
      parsedTo = extractField(content, "to_stage:")

      IF parsedFrom == fromStage AND parsedTo == toStage:
        RETURN parseHandoffContent(content)

  RETURN null  # No matching handoff found

# Format handoff for ALS comment
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

  RETURN lines.join("\n")
```

## Heartbeat

```
def writeHeartbeat(projectSlug):
  heartbeatFile = "/tmp/joan-agents-{projectSlug}.heartbeat"
  timestamp = NOW.toISOString()

  Bash: echo "{timestamp}" > {heartbeatFile}
```

## Smart Payload Extraction

```
# Extract task data from smart payload or fall back to MCP fetch.
# Used by all handlers in single-task (event-driven) mode.
def extractSmartPayload(TASK_ID, PROJECT_ID):
  # Read environment variable via Bash (Claude Code can't access env vars directly)
  SMART_PAYLOAD = Bash: echo "$JOAN_SMART_PAYLOAD"
  HAS_SMART_PAYLOAD = SMART_PAYLOAD AND SMART_PAYLOAD.length > 2

  IF HAS_SMART_PAYLOAD:
    smart_data = JSON.parse(SMART_PAYLOAD)
    Report: "Phase 3: Using smart payload (zero MCP fetching)"
    RETURN {
      task: {
        id: smart_data.task.id,
        title: smart_data.task.title,
        description: smart_data.task.description,
        column_id: smart_data.task.column_id,
        column_name: smart_data.task.column_name,
        tags: smart_data.tags
      },
      handoff_context: smart_data.handoff_context,
      recent_comments: smart_data.recent_comments,
      subtasks: smart_data.subtasks,
      rework_feedback: smart_data.rework_feedback,
      COLUMN_CACHE: smart_data.columns OR {},
      HAS_SMART_PAYLOAD: true
    }
  ELSE:
    Report: "No smart payload found, falling back to MCP fetch"
    RETURN fetchTaskViaMCP(TASK_ID, PROJECT_ID)

# MCP fallback path when no smart payload is available.
def fetchTaskViaMCP(TASK_ID, PROJECT_ID):
  task = mcp__joan__get_task(TASK_ID)
  comments = mcp__joan__list_task_comments(TASK_ID)
  columns = mcp__joan__list_columns(PROJECT_ID)

  COLUMN_CACHE = {}
  FOR col IN columns:
    COLUMN_CACHE[col.name] = col.id

  RETURN {
    task: task,
    handoff_context: null,
    recent_comments: comments,
    subtasks: null,
    rework_feedback: null,
    COLUMN_CACHE: COLUMN_CACHE,
    HAS_SMART_PAYLOAD: false
  }
```

## Tag Extraction

```
# Build a Set of tag names from tags array.
# Handles both string arrays (from smart payload) and {name, id} objects (from MCP).
def buildTagSet(tags):
  TAG_SET = Set()
  FOR tag IN tags:
    IF typeof tag == "string":
      TAG_SET.add(tag)
    ELSE:
      TAG_SET.add(tag.name)
  RETURN TAG_SET

# Extract tag name strings from {name, id} objects.
def extractTagNames(tags):
  names = []
  FOR tag IN tags:
    names.push(tag.name)
  RETURN names
```

## Result Submission

```
# Submit worker result to Joan API via submit-result.py.
# Handles both success and failure paths. Used by all handlers in PROCESS_RESULT.
# Supports both raw ALS comments (legacy) and structured comments (preferred).
def submitWorkerResult(WORKER_NAME, WORKER_RESULT, WORK_PACKAGE, PROJECT_ID):
  IF NOT WORKER_RESULT.success:
    Report: "{WORKER_NAME} worker failed: {WORKER_RESULT.error}"
    Bash: python3 ~/joan-agents/scripts/submit-result.py {WORKER_NAME} "{WORKER_RESULT.result_type}" false \
      --project-id "{PROJECT_ID}" \
      --task-id "{WORK_PACKAGE.task_id}" \
      --error "{WORKER_RESULT.error}"
    RETURN

  result_type = WORKER_RESULT.result_type
  output_json = JSON.stringify(WORKER_RESULT.output OR {})

  Report: "Submitting result: {result_type}"

  # Prefer structured_comment (server generates ALS) over raw comment string
  IF WORKER_RESULT.structured_comment:
    sc_json = JSON.stringify(WORKER_RESULT.structured_comment)
    Bash: python3 ~/joan-agents/scripts/submit-result.py {WORKER_NAME} "{result_type}" true \
      --project-id "{PROJECT_ID}" \
      --task-id "{WORK_PACKAGE.task_id}" \
      --output '{output_json}' \
      --structured-comment '{sc_json}'
  ELSE:
    comment = WORKER_RESULT.comment OR ""
    Bash: python3 ~/joan-agents/scripts/submit-result.py {WORKER_NAME} "{result_type}" true \
      --project-id "{PROJECT_ID}" \
      --task-id "{WORK_PACKAGE.task_id}" \
      --output '{output_json}' \
      --comment '{comment}'

  Report: "**{WORKER_NAME} completed for '{WORK_PACKAGE.task_title}' - {result_type}**"
```

## Logging

```
def logWorkerActivity(projectDir, workerType, status, message):
  logFile = "{projectDir}/.claude/logs/worker-activity.log"
  timestamp = NOW.strftime("%Y-%m-%d %H:%M:%S")

  Bash: echo "[{timestamp}] [{workerType}] [{status}] {message}" >> {logFile}
```
