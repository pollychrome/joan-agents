---
description: Check if coordinator is currently running
argument-hint: [project-name]
allowed-tools: Bash, Read
---

# Check Coordinator Running Status

Checks if the Joan coordinator is currently running for this project.

## How It Works

Monitors the heartbeat file created by the coordinator during each poll cycle.

## Arguments

- No arguments → Check current project (from .joan-agents.json)
- `project-name` → Check specific project by name

## Implementation

```bash
# Load project name
if [ -z "$1" ]; then
  # Get from .joan-agents.json
  if [ ! -f .joan-agents.json ]; then
    echo "❌ No .joan-agents.json found in current directory"
    exit 1
  fi

  PROJECT_NAME=$(cat .joan-agents.json | grep -o '"projectName"[[:space:]]*:[[:space:]]*"[^"]*"' | cut -d'"' -f4)

  if [ -z "$PROJECT_NAME" ]; then
    echo "❌ Could not read projectName from .joan-agents.json"
    exit 1
  fi
else
  PROJECT_NAME="$1"
fi

# Normalize project name (lowercase, replace spaces with hyphens)
NORMALIZED_NAME=$(echo "$PROJECT_NAME" | tr '[:upper:]' '[:lower:]' | tr ' ' '-')
HEARTBEAT_FILE="/tmp/joan-agents-${NORMALIZED_NAME}.heartbeat"

# Check if heartbeat file exists
if [ ! -f "$HEARTBEAT_FILE" ]; then
  echo "✗ Coordinator not running for \"$PROJECT_NAME\""
  echo "  (No heartbeat file found)"
  echo ""
  echo "Start with: /agents:dispatch --loop"
  exit 1
fi

# Read last heartbeat timestamp
LAST_HEARTBEAT=$(cat "$HEARTBEAT_FILE")
CURRENT_TIME=$(date +%s)
AGE=$((CURRENT_TIME - LAST_HEARTBEAT))

# Format age for display
if [ $AGE -lt 60 ]; then
  AGE_DISPLAY="${AGE}s ago"
elif [ $AGE -lt 3600 ]; then
  AGE_DISPLAY="$((AGE / 60))m ago"
else
  AGE_DISPLAY="$((AGE / 3600))h ago"
fi

# Check if heartbeat is fresh (< 10 minutes)
if [ $AGE -gt 600 ]; then
  echo "✗ Coordinator appears stuck for \"$PROJECT_NAME\""
  echo "  Last heartbeat: $AGE_DISPLAY"
  echo ""
  echo "The coordinator may have crashed or been killed."
  echo "Restart with: /agents:dispatch --loop"
  exit 1
else
  echo "✓ Coordinator running for \"$PROJECT_NAME\""
  echo "  Heartbeat: $AGE_DISPLAY"
  echo "  File: $HEARTBEAT_FILE"
  exit 0
fi
```

## Usage Examples

```bash
# Check current project
/agents:running

# Check specific project
/agents:running "LevRizz frontend"
```

## Output Examples

**Running:**
```
✓ Coordinator running for "LevRizz frontend"
  Heartbeat: 23s ago
  File: /tmp/joan-agents-levrizz-frontend.heartbeat
```

**Not running:**
```
✗ Coordinator not running for "LevRizz frontend"
  (No heartbeat file found)

Start with: /agents:dispatch --loop
```

**Stuck:**
```
✗ Coordinator appears stuck for "LevRizz frontend"
  Last heartbeat: 19m ago

The coordinator may have crashed or been killed.
Restart with: /agents:dispatch --loop
```
