#!/bin/bash

# Joan Coordinator Launcher (iTerm2 - v4 Single Coordinator Pattern)
# Usage: ./start-agents-iterm.sh [--max-idle=N]
#
# Launches a SINGLE coordinator that dispatches single-pass workers.
# Reads configuration from .joan-agents.json

set -e

# Check for config file
if [ ! -f ".joan-agents.json" ]; then
    echo "Error: .joan-agents.json not found."
    echo "Run '/agents:init' first to set up your Joan project."
    exit 1
fi

# Read project name from config
PROJECT_NAME=$(cat .joan-agents.json | grep -o '"projectName"[[:space:]]*:[[:space:]]*"[^"]*"' | cut -d'"' -f4)
if [ -z "$PROJECT_NAME" ]; then
    PROJECT_NAME="joan-project"
fi

# Read dev count from config
NUM_DEVS=$(cat .joan-agents.json | grep -o '"count"[[:space:]]*:[[:space:]]*[0-9]*' | head -1 | grep -o '[0-9]*')
if [ -z "$NUM_DEVS" ]; then
    NUM_DEVS=2
fi

# Parse optional --max-idle argument
MAX_IDLE_ARG=""
for arg in "$@"; do
    if [[ "$arg" == --max-idle=* ]]; then
        MAX_IDLE_ARG="$arg"
    fi
done

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOG_DIR="$SCRIPT_DIR/logs/$PROJECT_NAME"
CURRENT_DIR="$(pwd)"

mkdir -p "$LOG_DIR"

echo "🚀 Starting Joan Coordinator (v4 - iTerm2)"
echo "   Project: $PROJECT_NAME"
echo "   Dev workers available: $NUM_DEVS"
echo ""

# Check iTerm2
if ! osascript -e 'tell application "iTerm2" to version' &>/dev/null; then
    echo "❌ iTerm2 not found. Use ./start-agents.sh instead (uses Terminal.app)."
    exit 1
fi

# Build the command
COMMAND="/agents:start --loop"
if [ -n "$MAX_IDLE_ARG" ]; then
    COMMAND="$COMMAND $MAX_IDLE_ARG"
fi

# Build the AppleScript
APPLESCRIPT="tell application \"iTerm2\"
    activate
    set agentWindow to (create window with default profile)

    tell agentWindow
        -- Single Coordinator Tab
        tell current session
            set name to \"🎯 Coordinator\"
            write text \"cd '$CURRENT_DIR' && echo '🎯 Joan Coordinator' && claude --dangerously-skip-permissions '$COMMAND' 2>&1 | tee '$LOG_DIR/coordinator.log'\"
        end tell
    end tell
end tell"

# Execute
osascript -e "$APPLESCRIPT"

echo ""
echo "✅ Coordinator launched in iTerm2!"
echo ""
echo "┌─────────────────────────────────────────────────────────────┐"
echo "│                    Coordinator Architecture                │"
echo "├─────────────────────────────────────────────────────────────┤"
echo "│  🎯 Coordinator     - Single polling point                 │"
echo "│       └─► Dispatches workers as needed:                    │"
echo "│           • BA Worker (requirements validation)            │"
echo "│           • Architect Worker (planning)                    │"
echo "│           • Dev Worker x$NUM_DEVS (parallel implementation)    │"
echo "│           • Reviewer Worker (code review)                  │"
echo "│           • Ops Worker (merge & deploy)                    │"
echo "└─────────────────────────────────────────────────────────────┘"
echo ""
echo "Workers are single-pass: they process one task and exit."
echo "Feature branches are managed directly in the main directory (strict serial mode)."
echo ""
echo "Logs: $LOG_DIR/coordinator.log"
echo "Stop: Close iTerm2 window or ./stop-agents.sh"
