---
description: Run coordinator (single pass or loop) - recommended mode
argument-hint: [--loop] [--max-idle=N]
allowed-tools: mcp__joan__*, Read, Task
---

# Coordinator (Dispatcher)

The coordinator is the **recommended way** to run the Joan agent system. It:
- Polls Joan once per interval (not N times for N agents)
- Dispatches single-pass workers for available tasks
- Claims dev tasks atomically before dispatching
- Uses tags for all state transitions (no comment parsing)

## Arguments

- `--loop` → Run continuously until idle threshold reached
- No flag → Single pass (dispatch once, then exit)
- `--max-idle=N` → Override idle threshold (only applies in loop mode)

## Configuration

Load from `.joan-agents.json`:
```
PROJECT_ID = config.projectId
PROJECT_NAME = config.projectName
POLL_INTERVAL = config.settings.pollingIntervalMinutes (default: 10)
MAX_IDLE = --max-idle override or config.settings.maxIdlePolls (default: 6)
MODEL = config.settings.model (default: "opus")
DEV_COUNT = config.agents.devs.count (default: 2)
```

If config missing, report error and exit.

Parse arguments:
```
LOOP_MODE = true if --loop flag present, else false
```

## Launch Coordinator

Use the Task tool with the coordinator subagent:

```
Task tool call:
  subagent_type: "coordinator"
  model: "{MODEL from config}"  ← CRITICAL: Always pass model
  prompt: |
    You are the coordinator for project {PROJECT_NAME}.

    Configuration:
    - PROJECT_ID: {PROJECT_ID}
    - PROJECT_NAME: {PROJECT_NAME}
    - POLL_INTERVAL: {POLL_INTERVAL}
    - MAX_IDLE: {MAX_IDLE}
    - LOOP_MODE: {LOOP_MODE}
    - DEV_COUNT: {DEV_COUNT}
    - MODEL: {MODEL}

    Begin coordination now.
```

## Examples

```bash
# Single pass - dispatch workers once, then exit
/agents:dispatch

# Continuous loop - dispatch until idle
/agents:dispatch --loop

# Extended idle threshold (2 hours at 10-min intervals)
/agents:dispatch --loop --max-idle=12
```

## Why Coordinator Mode?

| Aspect | v4 Coordinator |
|--------|----------------|
| Polling | 1 agent polls (not N agents) |
| Token usage | ~10x lower overhead |
| State triggers | Tags only (deterministic) |
| Worker lifetime | Single-pass (stateless, easy retry) |

> **Note:** v4 is purely tag-based. Legacy comment parsing (`@approve-plan`, `@rework`) is no longer supported.

**Recommendation:** Use `/agents:dispatch --loop` for production workflows.

Begin coordinator now.
