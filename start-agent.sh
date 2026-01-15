#!/bin/bash

# Joan Single Agent Launcher
# Usage: ./start-agent.sh <agent-type> <project-name> [worker-id]

set -e

AGENT="${1:-}"
PROJECT="${2:-}"
WORKER_ID="${3:-1}"

print_usage() {
    echo "Usage: ./start-agent.sh <agent-type> <project-name> [worker-id]"
    echo ""
    echo "Agent types:"
    echo "  ba          Business Analyst"
    echo "  architect   Software Architect"
    echo "  worker      Implementation Worker (specify worker-id)"
    echo "  pm          Project Manager"
    echo ""
    echo "Examples:"
    echo "  ./start-agent.sh ba my-project"
    echo "  ./start-agent.sh worker my-project 1"
    echo "  ./start-agent.sh worker my-project 2"
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
        COMMAND="/agents:ba-loop $PROJECT"
        LABEL="🔍 Business Analyst"
        LOG_FILE="ba.log"
        ;;
    architect|arch)
        COMMAND="/agents:architect-loop $PROJECT"
        LABEL="📐 Architect"
        LOG_FILE="architect.log"
        ;;
    worker|w)
        COMMAND="/agents:worker-loop $PROJECT $WORKER_ID"
        LABEL="⚙️  Implementation Worker #$WORKER_ID"
        LOG_FILE="worker-$WORKER_ID.log"
        ;;
    pm|project-manager)
        COMMAND="/agents:pm-loop $PROJECT"
        LABEL="📊 Project Manager"
        LOG_FILE="pm.log"
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
