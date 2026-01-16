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

1. Fetch all actionable tasks:
   - Tasks in "Review" column (check for @approve or @rework)
   - Tasks in "Deploy" column (check production status)

2. Process each task:
   - Validate before working
   - Handle @rework → move back to Development
   - Handle @approve → merge to develop, move to Deploy
   - Track Deploy tasks for production deployment

3. Report summary and exit:
   ```
   PM single pass complete:
   - Merged to develop: N
   - Sent for rework: N
   - Deployed to production: N
   - Awaiting action: N
   ```

## Loop Mode (--loop)

Invoke the full pm-loop with configuration from .joan-agents.json.

Begin now.
