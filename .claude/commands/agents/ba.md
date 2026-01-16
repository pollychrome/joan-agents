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

### Step 1: Fetch Actionable Tasks

Fetch tasks from two sources:
- **To Do column**: New tasks needing evaluation
- **Analyse column**: Tasks with "Needs-Clarification" tag that have new comments

Filter out tasks that already have "Ready" tag (already processed).

### Step 2: Process Each Task

For each task, validate it's still actionable, then:

#### If task is in "To Do" column → Evaluate Requirements

```
1. Evaluate the task:
   - Is the description complete and unambiguous?
   - Are acceptance criteria defined?
   - Are there open questions that need answers?

2. Move task to "Analyse" column

3. Based on evaluation:

   IF requirements are INCOMPLETE:
     - Add "Needs-Clarification" tag
     - Comment with specific questions:
       "## Clarification Needed

       Before this task can be planned, please clarify:
       1. {question 1}
       2. {question 2}
       ..."
     - Report: "Task '{title}' needs clarification"

   IF requirements are COMPLETE:
     - Add "Ready" tag
     - Comment: "Requirements validated. Task ready for planning."
     - Report: "Task '{title}' marked Ready"
```

#### If task has "Needs-Clarification" tag → Check for Answers

```
1. Fetch task comments using list_task_comments(task_id)

2. Find your "## Clarification Needed" comment timestamp

3. Look for new comments AFTER your questions:
   - Check for "## Answers" section, OR
   - Any substantive response addressing your questions

4. Evaluate the answers:

   IF answers are SATISFACTORY:
     - Remove "Needs-Clarification" tag  ← CRITICAL: Must remove old tag!
     - Add "Ready" tag
     - Comment: "Clarification received. Requirements validated. Task ready for planning."
     - Report: "Task '{title}' clarified and marked Ready"

   IF answers are INCOMPLETE or raise more questions:
     - Keep "Needs-Clarification" tag
     - Comment with follow-up questions:
       "## Follow-up Questions

       Thank you for the response. I have additional questions:
       1. {follow-up question}
       ..."
     - Report: "Task '{title}' needs more clarification"

   IF no new comments since your questions:
     - Report: "Task '{title}' still awaiting clarification"
     - Skip to next task
```

### Step 3: Report Summary and Exit

```
BA single pass complete:
- Processed: N tasks
- Tagged Ready: N
- Need Clarification: N
- Awaiting Response: N
```

## Task Validation Rules

A task is valid for BA processing if:
- Task exists and is accessible
- Task is in "To Do" column, OR
- Task is in "Analyse" column with "Needs-Clarification" tag AND has new comments
- Task does NOT have "Ready" tag (already processed)

## Loop Mode (--loop)

Invoke the full ba-loop with configuration from .joan-agents.json.

Begin now.
