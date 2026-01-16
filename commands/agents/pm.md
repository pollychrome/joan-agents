---
description: Run Project Manager agent (single pass or loop)
argument-hint: [--loop] [--max-idle=N]
allowed-tools: mcp__joan__*, mcp__github__*, Read, Bash, Grep, Task
---

# Project Manager Agent

Quick invocation of the Project Manager agent.

## Mode Selection

Parse arguments:
- `--loop` → Run continuously (use pm-loop behavior)
- No flag → Single pass (process queue once, then exit)
- `--max-idle=N` → Override idle threshold (only for loop mode)

## Configuration

Load from `.joan-agents.json`:
- PROJECT_ID = config.projectId
- PROJECT_NAME = config.projectName

If config missing, report error and exit.

## Single Pass Mode (default)

Process ALL available tasks once, then exit.

### Step 1: Build Task Queue

```
1. Fetch actionable tasks:
   - Tasks in "Review" column with @approve or @rework comment
   - Tasks in "Deploy" column (track production status)

2. Build queue (reviews first, then deploys):
   TASK_QUEUE = [review_tasks..., deploy_tasks...]

3. If queue empty:
   Report: "PM: No tasks available."
   Exit.

4. Report: "PM found {queue.length} tasks to process"
```

### Step 2: Process Each Task in Queue

```
WHILE TASK_QUEUE is not empty:

  current_task = TASK_QUEUE.shift()

  1. Validate task still available:
     - Re-fetch using get_task(current_task.id)
     - Verify still in expected column
     - Check comments for triggers

     IF not valid:
       Report: "Task '{title}' no longer available, skipping"
       Continue to next task

  2. Determine action needed:

     IF in Review column with @rework comment:
       - Add "Rework-Requested" tag
       - Move back to "Development" column
       - Increment rework_count

     ELSE IF in Review column with @approve comment:
       - Get PR URL from task
       - Merge PR to develop branch
       - Move to "Deploy" column
       - Increment merged_count

     ELSE IF in Deploy column:
       - Check if deployed to production
       - If deployed, move to "Done" column
       - Increment deployed_count

  3. Report completion for this task

  Continue to next task in queue
```

### Step 3: Report Summary and Exit

```
PM single pass complete:
- Merged to develop: {N}
- Sent for rework: {N}
- Deployed to production: {N}
- Awaiting action: {N}
```

Exit.

## Loop Mode (--loop)

Invoke the full pm-loop with configuration from .joan-agents.json.

Begin now.
