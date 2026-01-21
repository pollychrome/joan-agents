---
description: Start a Joan agent using repository configuration
argument-hint: [dispatch] [--loop] [--max-idle=N]
allowed-tools: mcp__joan__*, Read, Task
---

# Start Joan Agent

Start the coordinator using configuration from `.joan-agents.json`.

## Arguments

- `$1` - Agent type (optional, defaults to `dispatch`)
- `--loop` - Run in continuous loop mode (poll until idle threshold)
- `--max-idle=N` - Override idle threshold (only applies in loop mode)

## Step 1: Load Configuration

Read `.joan-agents.json` from project root.

If file doesn't exist, report:
```
Configuration not found. Run /agents:init first to set up your Joan project.
```
And exit.

## Step 2: Parse Arguments

Agent type defaults to `dispatch` (coordinator).

Parse optional flags:
- `--loop` → Enable continuous loop mode
- `--max-idle=N` → Override config's maxIdlePolls

## Step 3: Launch Coordinator

Set these variables from config:
- `MODEL` = config.settings.model (default: "opus")
- `PROJECT_ID` = config.projectId
- `PROJECT_NAME` = config.projectName
- `POLL_INTERVAL` = config.settings.pollingIntervalMinutes
- `MAX_IDLE` = override or config.settings.maxIdlePolls
- `LOOP_MODE` = true if --loop flag present

Note: `devs.count` is always 1 (strict serial mode - prevents merge conflicts).

Enabled flags (all default to true):
- `BA_ENABLED` = config.agents.businessAnalyst.enabled
- `ARCHITECT_ENABLED` = config.agents.architect.enabled
- `REVIEWER_ENABLED` = config.agents.reviewer.enabled
- `OPS_ENABLED` = config.agents.ops.enabled
- `DEVS_ENABLED` = config.agents.devs.enabled

Launch the coordinator using the Task tool:

```
Task tool call:
  subagent_type: "coordinator"
  model: "{MODEL from config}"
  prompt: |
    You are the coordinator for project {PROJECT_NAME}.

    Configuration:
    - PROJECT_ID: {PROJECT_ID}
    - PROJECT_NAME: {PROJECT_NAME}
    - POLL_INTERVAL: {POLL_INTERVAL}
    - MAX_IDLE: {MAX_IDLE}
    - LOOP_MODE: {LOOP_MODE}
    - MODEL: {MODEL}
    - MODE: Strict serial (one task at a time through dev pipeline)

    Enabled Agents:
    - BA_ENABLED: {BA_ENABLED}
    - ARCHITECT_ENABLED: {ARCHITECT_ENABLED}
    - REVIEWER_ENABLED: {REVIEWER_ENABLED}
    - OPS_ENABLED: {OPS_ENABLED}
    - DEVS_ENABLED: {DEVS_ENABLED}

    Begin coordination now.
```

## Examples

```bash
# Single pass - process once and exit
/agents:start
/agents:start dispatch

# Continuous loop mode (interactive sessions)
/agents:start --loop
/agents:start dispatch --loop

# Extended idle threshold (2 hours at 10-min intervals)
/agents:start --loop --max-idle=12

# For long-running/overnight operations, use the external scheduler instead:
/agents:scheduler
```

## When to Use Which Mode

| Scenario | Command |
|----------|---------|
| Single test run | `/agents:start` |
| Interactive session | `/agents:start --loop` |
| Overnight/long-running | `/agents:scheduler` (prevents context overflow) |

## How It Works

The coordinator:
1. Polls Joan once per interval (not N times for N agents)
2. Builds priority queues based on tags
3. Claims dev tasks atomically before dispatching
4. Dispatches single-pass workers for each task
5. In loop mode, sleeps and repeats; in single pass, exits

Workers are single-pass: they process one task and exit.

Begin now.
