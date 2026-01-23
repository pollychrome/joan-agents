# Joan CLI - Global Agent Monitoring

Terminal-based monitoring tool for joan-agents across all projects.

## Installation

```bash
cd ~/joan-agents
./scripts/install-joan-cli.sh
```

This creates a global `joan` command accessible from any directory.

## Commands

### `joan status`
Global view of all running agent instances.

```bash
joan status
```

Output:
- List of all active projects
- Current cycle, idle count
- Number of active workers
- Tasks completed
- Total runtime
- Current status

### `joan status <project>`
Detailed view of a specific project.

```bash
joan status yolo-test
```

Shows:
- Configuration (model, mode, poll interval, PID)
- Runtime statistics (started time, current cycle, idle count)
- Tasks completed, workers dispatched
- Active workers with task names and durations
- Log file location

Supports partial matching:
```bash
joan status yolo      # Matches "yolo-test"
```

### `joan logs <project>`
Tail logs for a specific project.

```bash
joan logs yolo-test
```

Equivalent to `tail -f .claude/logs/scheduler.log` but finds the correct project automatically.

Press Ctrl+C to stop.

## How It Works

**Auto-Discovery:**
1. Scans running processes for `joan-scheduler.sh`
2. Extracts project directory from command line args
3. Reads `.joan-agents.json` config
4. Parses scheduler log for statistics

**Metrics Tracking:**
- Current cycle number (from log)
- Idle count / max idle (from log)
- Active workers (from dispatch messages)
- Tasks completed (from completion messages)
- Runtime (from first log timestamp)

**Zero Token Cost:**
- Pure local file operations
- No Claude API calls
- No MCP queries
- Just reads log files and process table

## Examples

```bash
# Quick health check
joan status

# Monitor specific project
joan status my-app

# Watch for activity
watch -n 5 joan status

# Stream logs
joan logs my-app

# Find only active projects
joan status | grep "🔄"
```

## Requirements

- Python 3.9+
- Rich library (`pip install --user --break-system-packages rich`)
- Running joan-agents instances (via `/agents:dispatch --loop`)

## Troubleshooting

**No instances found**
- Make sure `/agents:dispatch --loop` is running
- Check that scheduler process is visible in `ps aux | grep joan-scheduler`

**Project not found**
- Try partial name match: `joan status part-of-name`
- Check spelling

**Metrics not updating**
- Log file must exist (`.claude/logs/scheduler.log`)
- Scheduler must be writing logs
- Check file permissions

## Architecture

```
joan CLI
├── Discovers instances via ps aux
├── Reads config from .joan-agents.json
├── Parses logs from .claude/logs/scheduler.log
└── Renders with Rich library

No dependencies on:
- Claude API
- Joan MCP server
- Running coordinators
```

Pure log-based monitoring for maximum reliability and zero cost.
