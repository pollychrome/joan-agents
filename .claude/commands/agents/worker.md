---
description: Run Implementation Worker (single task or loop)
argument-hint: [worker-id] [--loop] [--max-idle=N]
allowed-tools: mcp__joan__*, mcp__github__*, Read, Write, Edit, Bash, Grep, Glob, Task, View, computer
---

# Implementation Worker

Quick invocation of an Implementation Worker.

## Arguments

- `$1` = Worker ID (default: 1)
- `--loop` → Run continuously (use worker-loop behavior)
- No flag → Single task (claim one task, complete it, exit)
- `--max-idle=N` → Override idle threshold (only for loop mode)

## Configuration

Load from `.joan-agents.json`:
- PROJECT_ID = config.projectId
- PROJECT_NAME = config.projectName
- WORKER_ID = $1 or 1
- CLAIM_TAG = "Claimed-Worker-{WORKER_ID}"

If config missing, report error and exit.

## Single Task Mode (default)

1. Find one available task:
   - Priority 1: Rework tasks ("Rework-Requested" tag)
   - Priority 2: New tasks ("Planned" tag, no claims)

2. If no tasks available:
   ```
   Worker #{WORKER_ID}: No tasks available.
   ```
   Exit.

3. Claim and implement the task:
   - Atomic claim with verification
   - Setup worktree
   - Execute sub-tasks (or rework)
   - Create/update PR
   - Cleanup and move to Review

4. Report and exit:
   ```
   Worker #{WORKER_ID} completed: '{task title}'
   - Type: {NEW | REWORK}
   - PR: {url}
   ```

## Loop Mode (--loop)

Invoke the full worker-loop with configuration from .joan-agents.json.

Begin Worker #{WORKER_ID} now.
