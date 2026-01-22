#!/bin/bash

# DEPRECATED: This script is legacy. Use `/agents:dispatch --loop` directly in Claude Code.
# This script is kept for backward compatibility only.

# Joan Coordinator Launcher (v4 - Single Coordinator Pattern)
# Usage: ./start-agents.sh [--max-idle=N]
#
# This script launches a SINGLE coordinator that dispatches workers.
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

echo "🚀 Starting Joan Coordinator (v4)"
echo "   Project: $PROJECT_NAME"
echo "   Dev workers available: $NUM_DEVS"
echo ""

# Configuration
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOG_DIR="$SCRIPT_DIR/logs/$PROJECT_NAME"

# Create directories
mkdir -p "$LOG_DIR"

echo "📁 Log directory: $LOG_DIR"
echo ""

# Build the command
COMMAND="/agents:dispatch --loop"
if [ -n "$MAX_IDLE_ARG" ]; then
    COMMAND="$COMMAND $MAX_IDLE_ARG"
fi

echo "📋 Launching coordinator..."
echo "   Command: $COMMAND"
echo ""

# Launch coordinator in new Terminal window
osascript <<EOF
tell application "Terminal"
    activate
    do script "cd '$(pwd)' && echo '🤖 Joan Coordinator' && script -q '$LOG_DIR/coordinator.log' claude --dangerously-skip-permissions '$COMMAND'"
end tell
EOF

echo ""
echo "✅ Coordinator launched!"
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
echo "To stop: ./stop-agents.sh or Ctrl+C in the coordinator terminal"
echo "To view logs: tail -f $LOG_DIR/coordinator.log"
