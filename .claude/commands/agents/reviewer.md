---
description: Run Code Reviewer agent (single pass or loop)
argument-hint: [--loop] [--max-idle=N]
allowed-tools: mcp__joan__*, mcp__github__*, Read, Bash, Grep, Glob, Task
---

# Code Reviewer Agent

Quick invocation of the Code Reviewer agent - the quality gate between implementation and deployment.

## Mode Selection

Parse arguments:
- `--loop` → Run continuously (use reviewer-loop behavior)
- No flag → Single pass (process queue once, then exit)
- `--max-idle=N` → Override idle threshold (only for loop mode)

## Configuration

Load from `.joan-agents.json`:
- PROJECT_ID = config.projectId
- PROJECT_NAME = config.projectName

If config missing, report error and exit.

## Single Pass Mode (default)

1. Fetch all reviewable tasks:
   - Tasks in "Review" column
   - With ALL completion tags: Dev-Complete, Design-Complete, Test-Complete
   - WITHOUT Review-In-Progress tag

2. For each task:
   - Add Review-In-Progress tag
   - Merge develop into feature branch (push if successful)
   - Perform deep code review (see reviewer-loop for full checklist)
   - Render verdict: @approve or @rework
   - Update tags appropriately

3. Report summary and exit:
   ```
   Reviewer single pass complete:
   - Approved: N
   - Sent for rework: N
   - Merge conflicts: N
   - Awaiting review: N
   ```

## Loop Mode (--loop)

Invoke the full reviewer-loop with configuration from .joan-agents.json.

Begin now.
