#!/bin/bash

# Joan Coordinator Launcher (current terminal)
# Usage: ./start-agent.sh [--max-idle=N]
#
# Runs the coordinator in this terminal using .joan-agents.json.

set -e

print_usage() {
    echo "Usage: ./start-agent.sh [--max-idle=N]"
    echo ""
    echo "Examples:"
    echo "  ./start-agent.sh"
    echo "  ./start-agent.sh --max-idle=12"
}

for arg in "$@"; do
    if [[ "$arg" == "-h" || "$arg" == "--help" ]]; then
        print_usage
        exit 0
    fi
done

if [ ! -f ".joan-agents.json" ]; then
    echo "Error: .joan-agents.json not found."
    echo "Run '/agents:init' first to set up your Joan project."
    exit 1
fi

PROJECT_NAME=$(cat .joan-agents.json | grep -o '"projectName"[[:space:]]*:[[:space:]]*"[^"]*"' | cut -d'"' -f4)
if [ -z "$PROJECT_NAME" ]; then
    PROJECT_NAME="joan-project"
fi

MAX_IDLE_ARG=""
for arg in "$@"; do
    if [[ "$arg" == --max-idle=* ]]; then
        MAX_IDLE_ARG="$arg"
    fi
done

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOG_DIR="$SCRIPT_DIR/logs/$PROJECT_NAME"
mkdir -p "$LOG_DIR"

COMMAND="/agents:start --loop"
if [ -n "$MAX_IDLE_ARG" ]; then
    COMMAND="$COMMAND $MAX_IDLE_ARG"
fi

echo "🎯 Joan Coordinator"
echo "Project: $PROJECT_NAME"
echo "Log: $LOG_DIR/coordinator.log"
echo "Press Ctrl+C to stop"
echo ""

claude --dangerously-skip-permissions "$COMMAND" 2>&1 | tee "$LOG_DIR/coordinator.log"
