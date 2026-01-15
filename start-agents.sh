#!/bin/bash

# Joan Multi-Agent Orchestration Launcher (Worktree Edition)
# Usage: ./start-agents.sh <project-name> [num-workers]
#
# This script launches agents for parallel feature development using git worktrees.
# - 1 BA Agent
# - 1 Architect Agent
# - N Implementation Workers (default: 4)
# - 1 PM Agent

set -e

PROJECT="${1:-}"
NUM_WORKERS="${2:-4}"

if [ -z "$PROJECT" ]; then
    echo "Usage: ./start-agents.sh <project-name> [num-workers]"
    echo ""
    echo "Arguments:"
    echo "  project-name    Name of your Joan project"
    echo "  num-workers     Number of parallel workers (default: 4)"
    echo ""
    echo "This will launch:"
    echo "  - 1 Business Analyst agent"
    echo "  - 1 Architect agent"
    echo "  - N Implementation Workers (parallel feature development)"
    echo "  - 1 Project Manager agent"
    echo ""
    echo "Each worker creates isolated git worktrees for true parallelism."
    exit 1
fi

echo "🚀 Starting Joan Multi-Agent Orchestration (Worktree Edition)"
echo "   Project: $PROJECT"
echo "   Workers: $NUM_WORKERS"
echo ""

# Configuration
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOG_DIR="$SCRIPT_DIR/logs/$PROJECT"
WORKTREE_DIR="$(pwd)/../worktrees"

# Create directories
mkdir -p "$LOG_DIR"
mkdir -p "$WORKTREE_DIR"

echo "📁 Log directory: $LOG_DIR"
echo "📁 Worktree directory: $WORKTREE_DIR"
echo ""

# Function to launch agent in new Terminal window
launch_agent() {
    local agent_name="$1"
    local command="$2"
    local log_name="$3"

    echo "  Starting $agent_name..."

    # Use 'script' command to capture full terminal output including control codes
    osascript <<EOF
tell application "Terminal"
    activate
    do script "cd '$(pwd)' && echo '🤖 $agent_name' && script -q '$LOG_DIR/${log_name}.log' claude --dangerously-skip-permissions '$command'"
end tell
EOF
    sleep 1
}

echo "📋 Launching agents..."
echo ""

# Launch core agents
launch_agent "🔍 Business Analyst" "/agents:ba-loop $PROJECT" "ba"
launch_agent "📐 Architect" "/agents:architect-loop $PROJECT" "architect"

# Launch workers
for i in $(seq 1 $NUM_WORKERS); do
    launch_agent "⚙️  Worker #$i" "/agents:worker-loop $PROJECT $i" "worker-$i"
done

# Launch PM
launch_agent "📊 Project Manager" "/agents:pm-loop $PROJECT" "pm"

echo ""
echo "✅ All agents launched!"
echo ""
echo "┌─────────────────────────────────────────────────────────────┐"
echo "│                    Agent Overview                          │"
echo "├─────────────────────────────────────────────────────────────┤"
echo "│  🔍 BA Agent        - Evaluating requirements              │"
echo "│  📐 Architect       - Creating implementation plans        │"
for i in $(seq 1 $NUM_WORKERS); do
echo "│  ⚙️  Worker #$i       - Ready for parallel development      │"
done
echo "│  📊 PM Agent        - Managing deployments                 │"
echo "└─────────────────────────────────────────────────────────────┘"
echo ""
echo "Worktrees will be created in: $WORKTREE_DIR"
echo ""
echo "To stop: ./stop-agents.sh"
echo "To view logs: tail -f $LOG_DIR/*.log"
