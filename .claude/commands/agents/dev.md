---
description: Run Dev agent (single task or loop)
argument-hint: [dev-id] [--loop] [--max-idle=N]
allowed-tools: mcp__joan__*, mcp__github__*, Read, Write, Edit, Bash, Grep, Glob, Task, View, computer
---

# Dev Agent

Quick invocation of a Dev agent for feature implementation.

## Arguments

- `$1` = Dev ID (default: 1)
- `--loop` → Run continuously (use dev-loop behavior)
- No flag → Single task (claim one task, complete it, exit)
- `--max-idle=N` → Override idle threshold (only for loop mode)

## Configuration

Load from `.joan-agents.json`:
- PROJECT_ID = config.projectId
- PROJECT_NAME = config.projectName
- DEV_ID = $1 or 1
- CLAIM_TAG = "Claimed-Dev-{DEV_ID}"

If config missing, report error and exit.

## Single Task Mode (default)

1. Find one available task:
   - Priority 1: Rework tasks ("Rework-Requested" tag)
   - Priority 2: New tasks ("Planned" tag, no claims)

2. If no tasks available:
   ```
   Dev #{DEV_ID}: No tasks available.
   ```
   Exit.

3. Claim and implement the task:
   - Atomic claim with verification
   - Setup worktree
   - Execute sub-tasks (DES-*, DEV-*, TEST-*)
   - Create/update PR
   - Cleanup and move to Review

4. Report and exit:
   ```
   Dev #{DEV_ID} completed: '{task title}'
   - Type: {NEW | REWORK}
   - PR: {url}
   ```

## Loop Mode (--loop)

Invoke the full dev-loop with configuration from .joan-agents.json.

Begin Dev #{DEV_ID} now.
