---
description: Build priority queues from task list (internal module)
---

# Queue Builder Module

Builds priority queues from fetched tasks using tag-based routing.
Each task goes into AT MOST one queue.

## Input

- `tasks`: Array of tasks from Joan MCP
- `TAG_INDEX`: Pre-built tag index for O(1) lookups
- `COLUMN_CACHE`: Column name to ID mapping

## Queue Building Logic

```
def buildQueues(tasks, TAG_INDEX, COLUMN_CACHE):

  BA_QUEUE = []
  ARCHITECT_QUEUE = []
  DEV_QUEUE = []
  REVIEWER_QUEUE = []
  OPS_QUEUE = []

  FOR task IN tasks:
    taskId = task.id

    # P0: Invocations (highest priority)
    IF inColumn(task, "Review", COLUMN_CACHE) AND
       hasTag(taskId, "Invoke-Architect", TAG_INDEX) AND
       NOT hasTag(taskId, "Architect-Assist-Complete", TAG_INDEX):
      ARCHITECT_QUEUE.unshift({task, mode: "advisory-conflict"})
      CONTINUE

    IF inColumn(task, "Review", COLUMN_CACHE) AND
       hasTag(taskId, "Architect-Assist-Complete", TAG_INDEX):
      OPS_QUEUE.unshift({task, mode: "merge-with-guidance"})
      CONTINUE

    # P1-3: Dev tasks (priority order: conflict > rework > implement)
    IF inColumn(task, "Development", COLUMN_CACHE) AND
       hasTag(taskId, "Merge-Conflict", TAG_INDEX) AND
       NOT isClaimedByAnyDev(taskId, TAG_INDEX):
      DEV_QUEUE.push({task, mode: "conflict"})
      CONTINUE

    IF inColumn(task, "Development", COLUMN_CACHE) AND
       hasTag(taskId, "Rework-Requested", TAG_INDEX) AND
       NOT isClaimedByAnyDev(taskId, TAG_INDEX) AND
       NOT hasTag(taskId, "Merge-Conflict", TAG_INDEX):
      DEV_QUEUE.push({task, mode: "rework"})
      CONTINUE

    IF inColumn(task, "Development", COLUMN_CACHE) AND
       hasTag(taskId, "Planned", TAG_INDEX) AND
       NOT isClaimedByAnyDev(taskId, TAG_INDEX) AND
       NOT hasTag(taskId, "Rework-Requested", TAG_INDEX) AND
       NOT hasTag(taskId, "Implementation-Failed", TAG_INDEX) AND
       NOT hasTag(taskId, "Branch-Setup-Failed", TAG_INDEX):
      DEV_QUEUE.push({task, mode: "implement"})
      CONTINUE

    # P4-5: Architect tasks
    IF inColumn(task, "Analyse", COLUMN_CACHE) AND
       hasTag(taskId, "Plan-Pending-Approval", TAG_INDEX) AND
       hasTag(taskId, "Plan-Approved", TAG_INDEX) AND
       NOT hasTag(taskId, "Plan-Rejected", TAG_INDEX):
      ARCHITECT_QUEUE.push({task, mode: "finalize"})
      CONTINUE

    IF inColumn(task, "Analyse", COLUMN_CACHE) AND
       hasTag(taskId, "Plan-Pending-Approval", TAG_INDEX) AND
       hasTag(taskId, "Plan-Rejected", TAG_INDEX):
      ARCHITECT_QUEUE.push({task, mode: "revise"})
      CONTINUE

    IF inColumn(task, "Analyse", COLUMN_CACHE) AND
       hasTag(taskId, "Ready", TAG_INDEX) AND
       NOT hasTag(taskId, "Plan-Pending-Approval", TAG_INDEX):
      ARCHITECT_QUEUE.push({task, mode: "plan"})
      CONTINUE

    # P6-7: BA tasks
    IF inColumn(task, "Analyse", COLUMN_CACHE) AND
       hasTag(taskId, "Needs-Clarification", TAG_INDEX) AND
       hasTag(taskId, "Clarification-Answered", TAG_INDEX):
      BA_QUEUE.push({task, mode: "reevaluate"})
      CONTINUE

    IF inColumn(task, "To Do", COLUMN_CACHE) AND
       NOT hasTag(taskId, "Ready", TAG_INDEX):
      BA_QUEUE.push({task, mode: "evaluate"})
      CONTINUE

    # P8: Reviewer tasks
    IF inColumn(task, "Review", COLUMN_CACHE) AND
       hasTag(taskId, "Dev-Complete", TAG_INDEX) AND
       hasTag(taskId, "Design-Complete", TAG_INDEX) AND
       hasTag(taskId, "Test-Complete", TAG_INDEX) AND
       NOT hasTag(taskId, "Review-In-Progress", TAG_INDEX) AND
       NOT hasTag(taskId, "Review-Approved", TAG_INDEX) AND
       NOT hasTag(taskId, "Rework-Requested", TAG_INDEX):
      REVIEWER_QUEUE.push({task, mode: "review"})
      CONTINUE

    IF inColumn(task, "Review", COLUMN_CACHE) AND
       hasTag(taskId, "Rework-Complete", TAG_INDEX) AND
       NOT hasTag(taskId, "Review-In-Progress", TAG_INDEX) AND
       NOT hasTag(taskId, "Review-Approved", TAG_INDEX) AND
       NOT hasTag(taskId, "Rework-Requested", TAG_INDEX):
      REVIEWER_QUEUE.push({task, mode: "review"})
      CONTINUE

    # P9-10: Ops tasks
    IF (inColumn(task, "Review", COLUMN_CACHE) OR inColumn(task, "Deploy", COLUMN_CACHE)) AND
       hasTag(taskId, "Review-Approved", TAG_INDEX) AND
       hasTag(taskId, "Ops-Ready", TAG_INDEX):
      OPS_QUEUE.push({task, mode: "merge"})
      CONTINUE

  RETURN {
    ba: BA_QUEUE,
    architect: ARCHITECT_QUEUE,
    dev: DEV_QUEUE,
    reviewer: REVIEWER_QUEUE,
    ops: OPS_QUEUE
  }
```

## Output

Returns object with five queues:
- `ba`: Tasks for BA evaluation
- `architect`: Tasks for planning/finalization
- `dev`: Tasks for implementation
- `reviewer`: Tasks for code review
- `ops`: Tasks for merge/deployment
