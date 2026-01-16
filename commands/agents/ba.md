---
description: Run Business Analyst agent (single pass or loop)
argument-hint: [--loop] [--max-idle=N]
allowed-tools: mcp__joan__*, Read, Grep, Glob, Task
---

# Business Analyst Agent

Quick invocation of the Business Analyst agent.

## Mode Selection

Parse arguments:
- `--loop` → Run continuously (use ba-loop behavior)
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
   - Tasks in "To Do" column (new tasks)
   - Tasks in "Analyse" with "Needs-Clarification" tag + new comments

2. Build queue:
   TASK_QUEUE = [todo_tasks..., clarification_tasks...]

3. If queue empty:
   Report: "BA: No tasks available."
   Exit.

4. Report: "BA found {queue.length} tasks to process"
```

### Step 2: Process Each Task in Queue

```
WHILE TASK_QUEUE is not empty:

  current_task = TASK_QUEUE.shift()

  1. Validate task still available:
     - Re-fetch using get_task(current_task.id)
     - Verify still in expected column
     - Verify not being worked by another agent

     IF not valid:
       Report: "Task '{title}' no longer available, skipping"
       Continue to next task

  2. Evaluate requirements:
     - Read task description and any attachments
     - Check for completeness
     - Identify missing information

  3. Tag and move:
     IF requirements complete:
       - Add "Ready" tag
       - Move to "Analyse" column
     ELSE:
       - Add "Needs-Clarification" tag
       - Add comment listing questions
       - Leave in current column

  4. Report completion for this task

  Continue to next task in queue
```

### Step 3: Report Summary and Exit

```
BA single pass complete:
- Processed: {N} tasks
- Tagged Ready: {N}
- Need Clarification: {N}
```

Exit.

## Loop Mode (--loop)

Invoke the full ba-loop with configuration from .joan-agents.json.

Begin now.
