#!/bin/bash

# Joan Single Agent Launcher
# Usage: ./start-agent.sh <agent-type> <project-name> [dev-id]

set -e

AGENT="${1:-}"
PROJECT="${2:-}"
DEV_ID="${3:-1}"

print_usage() {
    echo "Usage: ./start-agent.sh <agent-type> <project-name> [dev-id]"
    echo ""
    echo "Agent types:"
    echo "  ba          Business Analyst"
    echo "  architect   Software Architect"
    echo "  dev         Dev agent (specify dev-id)"
    echo "  reviewer    Code Reviewer"
    echo "  ops         Ops"
    echo ""
    echo "Examples:"
    echo "  ./start-agent.sh ba my-project"
    echo "  ./start-agent.sh dev my-project 1"
    echo "  ./start-agent.sh dev my-project 2"
}

if [ -z "$AGENT" ] || [ -z "$PROJECT" ]; then
    print_usage
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOG_DIR="$SCRIPT_DIR/logs/$PROJECT"
mkdir -p "$LOG_DIR"

case "$AGENT" in
    ba|business-analyst)
        COMMAND="/agents:ba --loop"
        LABEL="🔍 Business Analyst"
        LOG_FILE="ba.log"
        ;;
    architect|arch)
        COMMAND="/agents:architect --loop"
        LABEL="📐 Architect"
        LOG_FILE="architect.log"
        ;;
    dev|d)
        COMMAND="/agents:dev $DEV_ID --loop"
        LABEL="⚙️  Dev #$DEV_ID"
        LOG_FILE="dev-$DEV_ID.log"
        ;;
    reviewer|review|r)
        COMMAND="/agents:reviewer --loop"
        LABEL="🔬 Code Reviewer"
        LOG_FILE="reviewer.log"
        ;;
    ops)
        COMMAND="/agents:ops --loop"
        LABEL="🔧 Ops"
        LOG_FILE="ops.log"
        ;;
    *)
        echo "❌ Unknown agent type: $AGENT"
        echo ""
        print_usage
        exit 1
        ;;
esac

echo "$LABEL"
echo "Project: $PROJECT"
echo "═══════════════════════════════════════"
echo ""
echo "Log: $LOG_DIR/$LOG_FILE"
echo "Press Ctrl+C to stop"
echo ""

claude --dangerously-skip-permissions "$COMMAND" 2>&1 | tee "$LOG_DIR/$LOG_FILE"
