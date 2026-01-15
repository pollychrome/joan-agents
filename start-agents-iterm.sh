#!/bin/bash

# Joan Multi-Agent Orchestration Launcher (iTerm2 + Worktrees)
# Usage: ./start-agents-iterm.sh <project-name> [num-workers]

set -e

PROJECT="${1:-}"
NUM_WORKERS="${2:-4}"

if [ -z "$PROJECT" ]; then
    echo "Usage: ./start-agents-iterm.sh <project-name> [num-workers]"
    echo ""
    echo "Launches agents in iTerm2 tabs for parallel feature development."
    echo "Default: 4 workers (4 features in parallel)"
    exit 1
fi

# Validate worker count
if [ "$NUM_WORKERS" -gt 6 ]; then
    echo "⚠️  Warning: $NUM_WORKERS workers may strain system resources."
    echo "   Recommended: 4-6 workers maximum."
    read -p "Continue? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOG_DIR="$SCRIPT_DIR/logs/$PROJECT"
WORKTREE_DIR="$(pwd)/../worktrees"
CURRENT_DIR="$(pwd)"

mkdir -p "$LOG_DIR"
mkdir -p "$WORKTREE_DIR"

echo "🚀 Starting Joan Multi-Agent Orchestration"
echo "   Project: $PROJECT"
echo "   Workers: $NUM_WORKERS (parallel features)"
echo ""

# Check iTerm2
if ! osascript -e 'tell application "iTerm2" to version' &>/dev/null; then
    echo "❌ iTerm2 not found. Use ./start-agents.sh instead."
    exit 1
fi

# Build the AppleScript dynamically
APPLESCRIPT="tell application \"iTerm2\"
    activate
    set agentWindow to (create window with default profile)
    
    tell agentWindow
        -- Tab 1: BA Agent
        tell current session
            set name to \"🔍 BA\"
            write text \"cd '$CURRENT_DIR' && echo '🔍 Business Analyst Agent' && claude --dangerously-skip-permissions '/agents:ba-loop $PROJECT' 2>&1 | tee '$LOG_DIR/ba.log'\"
        end tell
        
        -- Tab 2: Architect Agent
        set newTab to (create tab with default profile)
        tell current session of newTab
            set name to \"📐 Arch\"
            write text \"cd '$CURRENT_DIR' && echo '📐 Architect Agent' && claude --dangerously-skip-permissions '/agents:architect-loop $PROJECT' 2>&1 | tee '$LOG_DIR/architect.log'\"
        end tell"

# Add worker tabs dynamically
for i in $(seq 1 $NUM_WORKERS); do
    APPLESCRIPT="$APPLESCRIPT
        
        -- Tab: Worker $i
        set newTab to (create tab with default profile)
        tell current session of newTab
            set name to \"⚙️ W$i\"
            write text \"cd '$CURRENT_DIR' && echo '⚙️ Implementation Worker #$i' && claude --dangerously-skip-permissions '/agents:worker-loop $PROJECT $i' 2>&1 | tee '$LOG_DIR/worker-$i.log'\"
        end tell"
done

# Add PM tab
APPLESCRIPT="$APPLESCRIPT
        
        -- Tab: PM Agent
        set newTab to (create tab with default profile)
        tell current session of newTab
            set name to \"📊 PM\"
            write text \"cd '$CURRENT_DIR' && echo '📊 Project Manager Agent' && claude --dangerously-skip-permissions '/agents:pm-loop $PROJECT' 2>&1 | tee '$LOG_DIR/pm.log'\"
        end tell
    end tell
end tell"

# Execute
osascript -e "$APPLESCRIPT"

TOTAL_AGENTS=$((3 + NUM_WORKERS))

echo ""
echo "✅ Launched $TOTAL_AGENTS agents in iTerm2 tabs!"
echo ""
echo "┌─────────────────────────────────────────────────────────────┐"
echo "│  Tab Layout                                                 │"
echo "├─────────────────────────────────────────────────────────────┤"
echo "│  🔍 BA      │ 📐 Arch   │ ⚙️ W1-W$NUM_WORKERS   │ 📊 PM       │"
echo "└─────────────────────────────────────────────────────────────┘"
echo ""
echo "Parallel Development:"
echo "  • $NUM_WORKERS features can be developed simultaneously"
echo "  • Each worker creates isolated git worktrees"
echo "  • Worktrees location: $WORKTREE_DIR"
echo ""
echo "Logs: $LOG_DIR"
echo "Stop: Close iTerm2 window or ./stop-agents.sh"
