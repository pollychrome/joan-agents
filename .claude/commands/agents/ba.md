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

1. Fetch all actionable tasks:
   - Tasks in "To Do" column
   - Tasks in "Analyse" with "Needs-Clarification" tag and new comments

2. Process each task:
   - Validate before working
   - Evaluate requirements
   - Tag appropriately (Ready or Needs-Clarification)
   - Move to Analyse column

3. Report summary and exit:
   ```
   BA single pass complete:
   - Processed: N tasks
   - Tagged Ready: N
   - Need Clarification: N
   ```

## Loop Mode (--loop)

Invoke the full ba-loop with configuration from .joan-agents.json.

Begin now.
