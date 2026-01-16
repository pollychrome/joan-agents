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

1. Fetch all actionable tasks in Analyse column:
   - Tasks with "Ready" tag (need plans)
   - Tasks with "Plan-Pending-Approval" tag (check for @approve-plan)

2. Process each task:
   - Validate before working
   - Create plans for Ready tasks
   - Finalize approved plans (move to Development)

3. Report summary and exit:
   ```
   Architect single pass complete:
   - Plans created: N
   - Plans approved: N
   - Awaiting approval: N
   ```

## Loop Mode (--loop)

Invoke the full architect-loop with configuration from .joan-agents.json.

Begin now.
