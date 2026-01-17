#!/bin/bash

# Joan Multi-Agent Orchestration Launcher (Worktree Edition)
# Usage: ./start-agents.sh [num-devs]
#
# This script launches agents for parallel feature development using git worktrees.
# Reads configuration from .joan-agents.json
# - 1 BA Agent
# - 1 Architect Agent
# - N Dev agents (from config or argument)
# - 1 Reviewer Agent
# - 1 PM Agent

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

# Get dev count from argument or config
NUM_DEVS="${1:-}"
if [ -z "$NUM_DEVS" ]; then
    NUM_DEVS=$(cat .joan-agents.json | grep -o '"count"[[:space:]]*:[[:space:]]*[0-9]*' | head -1 | grep -o '[0-9]*')
    if [ -z "$NUM_DEVS" ]; then
        NUM_DEVS=2
    fi
fi

echo "🚀 Starting Joan Multi-Agent Orchestration"
echo "   Project: $PROJECT_NAME"
echo "   Devs: $NUM_DEVS"
echo ""

# Configuration
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOG_DIR="$SCRIPT_DIR/logs/$PROJECT_NAME"
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

# Launch core agents (using unified commands with --loop flag)
launch_agent "🔍 Business Analyst" "/agents:ba --loop" "ba"
launch_agent "📐 Architect" "/agents:architect --loop" "architect"

# Launch devs
for i in $(seq 1 $NUM_DEVS); do
    launch_agent "⚙️  Dev #$i" "/agents:dev $i --loop" "dev-$i"
done

# Launch Reviewer
launch_agent "🔬 Code Reviewer" "/agents:reviewer --loop" "reviewer"

# Launch Ops
launch_agent "🔧 Ops" "/agents:ops --loop" "ops"

echo ""
echo "✅ All agents launched!"
echo ""
echo "┌─────────────────────────────────────────────────────────────┐"
echo "│                    Agent Overview                          │"
echo "├─────────────────────────────────────────────────────────────┤"
echo "│  🔍 BA Agent        - Evaluating requirements              │"
echo "│  📐 Architect       - Creating implementation plans        │"
for i in $(seq 1 $NUM_DEVS); do
echo "│  ⚙️  Dev #$i          - Ready for parallel development      │"
done
echo "│  🔬 Reviewer        - Code review and quality gate         │"
echo "│  🔧 Ops Agent       - Merging & conflict resolution         │"
echo "└─────────────────────────────────────────────────────────────┘"
echo ""
echo "Worktrees will be created in: $WORKTREE_DIR"
echo ""
echo "To stop: ./stop-agents.sh"
echo "To view logs: tail -f $LOG_DIR/*.log"
