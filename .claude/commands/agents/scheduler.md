---
description: [DEPRECATED] Use /agents:dispatch --loop instead
argument-hint: [--interval=N] [--max-idle=N]
allowed-tools: Bash, Read
---

# External Scheduler (DEPRECATED)

**This command is deprecated. Use `/agents:dispatch --loop` instead.**

The functionality of this command has been integrated directly into `/agents:dispatch`. When you run `/agents:dispatch --loop`, it automatically uses the external scheduler approach to prevent context overflow.

## Use Instead

```bash
# Continuous operation with external scheduler
/agents:dispatch --loop

# Custom poll interval (every 3 minutes)
/agents:dispatch --loop --interval=180

# Extended idle threshold
/agents:dispatch --loop --max-idle=24
```

## Why Deprecated?

Having two separate commands (`/agents:dispatch --loop` and `/agents:scheduler`) was confusing. The `--loop` flag now automatically triggers the external scheduler behavior, providing a single, intuitive interface.

## Usage

```bash
# Run with default settings (recommended for overnight runs)
/agents:scheduler

# Custom poll interval (2 minutes)
/agents:scheduler --interval=120

# Extended operation (4 hours at 5-min intervals)
/agents:scheduler --max-idle=48

# All options
/agents:scheduler --interval=300 --stuck-timeout=600 --max-idle=12
```

## Arguments

| Argument | Default | Description |
|----------|---------|-------------|
| `--interval=N` | 300 | Poll interval in seconds between coordinator runs |
| `--stuck-timeout=N` | 600 | Seconds before killing a stuck coordinator |
| `--max-idle=N` | 12 | Max consecutive idle cycles before shutdown |
| `--max-failures=N` | 3 | Max consecutive coordinator failures before scheduler stops |

## When to Use

| Scenario | Use This |
|----------|----------|
| Short interactive session | `/agents:dispatch --loop` |
| Overnight autonomous operation | `/agents:scheduler` |
| Multi-hour background processing | `/agents:scheduler --max-idle=48` |
| Debugging/testing | `/agents:dispatch` (single pass) |

## How It Works

```
External Scheduler (bash script)
├── Cycle 1: spawn fresh claude /agents:dispatch → exits
├── Check heartbeat file for activity
├── Sleep INTERVAL seconds
├── Cycle 2: spawn fresh claude /agents:dispatch → exits
├── ...
└── Stop when max-idle or max-failures reached
```

Each coordinator invocation:
1. Starts with a completely fresh context
2. Writes heartbeat timestamps during operation
3. Exits cleanly after single pass
4. Scheduler detects stuck coordinators via stale heartbeat

## Logs

Scheduler logs to `.claude/logs/scheduler.log`:
- All coordinator output is captured
- Timestamps for each cycle
- Error and warning messages
- Heartbeat health status

## Graceful Shutdown

To stop the scheduler gracefully:

```bash
# Create shutdown signal file
touch /tmp/joan-agents-{project-name}.shutdown

# Or send SIGINT/SIGTERM to the scheduler process
kill <scheduler-pid>
```

The scheduler will:
1. Detect shutdown signal
2. Allow current coordinator to finish
3. Clean up temp files
4. Exit gracefully

---

## Execution

Read configuration from `.joan-agents.json`:

```
PROJECT_NAME = config.projectName
INTERVAL = args.interval or settings.schedulerIntervalSeconds or 300
STUCK_TIMEOUT = args.stuck-timeout or settings.schedulerStuckTimeoutSeconds or 600
MAX_IDLE = args.max-idle or settings.maxIdlePolls or 12
MAX_FAILURES = settings.schedulerMaxConsecutiveFailures or 3
```

Build and execute the scheduler command:

```bash
# Run the external scheduler
./scripts/joan-scheduler.sh . --interval={INTERVAL} --stuck-timeout={STUCK_TIMEOUT} --max-idle={MAX_IDLE} --max-failures={MAX_FAILURES}
```

**IMPORTANT:** This command runs the bash scheduler which then manages coordinator processes. The scheduler itself runs outside of Claude to avoid context accumulation.

Report:
- "External scheduler started for {PROJECT_NAME}"
- "Poll interval: {INTERVAL}s"
- "Stuck timeout: {STUCK_TIMEOUT}s"
- "Max idle polls: {MAX_IDLE}"
- "Max consecutive failures: {MAX_FAILURES}"
- "Logs: .claude/logs/scheduler.log"
- "To stop: touch /tmp/joan-agents-{PROJECT_SLUG}.shutdown"
  (where PROJECT_SLUG = PROJECT_NAME lowercased with non-alphanumeric chars replaced by dashes)
