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

## Logging

```
def logWorkerActivity(projectDir, workerType, status, message):
  logFile = "{projectDir}/.claude/logs/worker-activity.log"
  timestamp = NOW.strftime("%Y-%m-%d %H:%M:%S")

  Bash: echo "[{timestamp}] [{workerType}] [{status}] {message}" >> {logFile}
```
