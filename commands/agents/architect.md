---
description: Run Architect agent (single pass or loop)
argument-hint: [--loop] [--max-idle=N]
allowed-tools: mcp__joan__*, Read, Write, Grep, Glob, View, Task
---

# Architect Agent

Quick invocation of the Architect agent.

## Mode Selection

Parse arguments:
- `--loop` → Run continuously (use architect-loop behavior)
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
1. Fetch actionable tasks in Analyse column:
   - Tasks with "Ready" tag (need plans)
   - Tasks with "Plan-Pending-Approval" tag + @architect comment (approved)

2. Build queue (plans first, then approvals):
   TASK_QUEUE = [ready_tasks..., approved_tasks...]

3. If queue empty:
   Report: "Architect: No tasks available."
   Exit.

4. Report: "Architect found {queue.length} tasks to process"
```

### Step 2: Process Each Task in Queue

```
WHILE TASK_QUEUE is not empty:

  current_task = TASK_QUEUE.shift()

  1. Validate task still available:
     - Re-fetch using get_task(current_task.id)
     - Verify still in "Analyse" column
     - Verify expected tags still present

     IF not valid:
       Report: "Task '{title}' no longer available, skipping"
       Continue to next task

  2. Determine action needed:

     IF has "Ready" tag (needs plan):
       - Analyze codebase for implementation approach
       - Create implementation plan with sub-tasks (DES-*, DEV-*, TEST-*)
       - Add plan as comment
       - Add "Plan-Pending-Approval" tag
       - Remove "Ready" tag
       - Increment plans_created

     ELSE IF has "Plan-Pending-Approval" + @architect approval:
       - Add "Planned" tag
       - Remove "Plan-Pending-Approval" tag
       - Move to "Development" column
       - Increment plans_approved

  3. Report completion for this task

  Continue to next task in queue
```

### Step 3: Report Summary and Exit

```
Architect single pass complete:
- Plans created: {N}
- Plans approved: {N}
- Awaiting approval: {N} (have plans but no @architect comment yet)
```

Exit.

## Loop Mode (--loop)

Invoke the full architect-loop with configuration from .joan-agents.json.

Begin now.
