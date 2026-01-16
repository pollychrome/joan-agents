---
description: Run Dev agent (single pass or loop)
argument-hint: [dev-id] [--loop] [--max-idle=N]
allowed-tools: mcp__joan__*, mcp__github__*, Read, Write, Edit, Bash, Grep, Glob, Task, View, computer
---

# Dev Agent

Quick invocation of a Dev agent for feature implementation.

## Arguments

- `$1` = Dev ID (default: 1)
- `--loop` → Run continuously with polling (use dev-loop behavior)
- No flag → Single pass (process ALL available tasks, then exit)
- `--max-idle=N` → Override idle threshold (only for loop mode)

## Configuration

Load from `.joan-agents.json`:
- PROJECT_ID = config.projectId
- PROJECT_NAME = config.projectName
- DEV_ID = $1 or 1
- CLAIM_TAG = "Claimed-Dev-{DEV_ID}"

If config missing, report error and exit.

## Single Pass Mode (default)

Process ALL available tasks once, then exit.

### Step 1: Build Task Queue

```
1. Fetch Development column tasks:
   - Use list_tasks for PROJECT_ID
   - Get each task's details using get_task to check column and tags

2. Find workable tasks (TWO categories):

   a. REWORK tasks (PRIORITY):
      - Task is in "Development" column
      - Task has "Rework-Requested" tag
      - Task has NO "Claimed-Dev-*" tag

   b. NEW WORK tasks:
      - Task is in "Development" column
      - Task has "Planned" tag
      - Task has NO "Claimed-Dev-*" tag
      - Task has NO "Implementation-Failed" tag

3. Build queue (rework first):
   TASK_QUEUE = [rework_tasks..., planned_tasks...]

4. If queue empty:
   Report: "Dev #{DEV_ID}: No tasks available."
   Exit.

5. Report: "Dev #{DEV_ID} found {queue.length} tasks to process"
```

### Step 2: Process Each Task in Queue

```
WHILE TASK_QUEUE is not empty:

  current_task = TASK_QUEUE.shift()

  1. Validate task still available:
     - Re-fetch using get_task(current_task.id)
     - Verify still in "Development" column
     - Verify still has "Planned" or "Rework-Requested" tag
     - Verify NO "Claimed-Dev-*" tags

     IF not valid:
       Report: "Task '{title}' no longer available, skipping"
       Continue to next task

  2. Atomic claim:
     - Add tag: CLAIM_TAG
     - Wait 1 second
     - Re-fetch and verify YOUR claim tag is present
     - If claim failed, skip to next task

  3. Implement the task:
     - Setup worktree
     - Execute sub-tasks (DES-*, DEV-*, TEST-*)
     - Create/update PR
     - Cleanup worktree
     - Move to Review column

  4. Report completion for this task

  Continue to next task in queue
```

### Step 3: Report Summary and Exit

```
Dev #{DEV_ID} single pass complete:
- Processed: {N} tasks
- Completed: {N}
- Skipped: {N} (claimed by others or invalid)
- PRs created: {list}
```

Exit.

## Loop Mode (--loop)

Invoke the full dev-loop with configuration from .joan-agents.json.
This adds polling behavior - when queue empties, wait and poll again.

Begin Dev #{DEV_ID} now.
