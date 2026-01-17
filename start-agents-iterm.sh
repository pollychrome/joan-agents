#!/bin/bash

# Joan Multi-Agent Orchestration Launcher (iTerm2 + Worktrees)
# Usage: ./start-agents-iterm.sh <project-name> [num-devs]

set -e

PROJECT="${1:-}"
NUM_DEVS="${2:-4}"

if [ -z "$PROJECT" ]; then
    echo "Usage: ./start-agents-iterm.sh <project-name> [num-devs]"
    echo ""
    echo "Launches agents in iTerm2 tabs for parallel feature development."
    echo "Default: 4 devs (4 features in parallel)"
    exit 1
fi

# Validate dev count
if [ "$NUM_DEVS" -gt 6 ]; then
    echo "⚠️  Warning: $NUM_DEVS devs may strain system resources."
    echo "   Recommended: 4-6 devs maximum."
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
echo "   Devs: $NUM_DEVS (parallel features)"
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
            write text \"cd '$CURRENT_DIR' && echo '🔍 Business Analyst Agent' && claude --dangerously-skip-permissions '/agents:ba --loop' 2>&1 | tee '$LOG_DIR/ba.log'\"
        end tell
        
        -- Tab 2: Architect Agent
        set newTab to (create tab with default profile)
        tell current session of newTab
            set name to \"📐 Arch\"
            write text \"cd '$CURRENT_DIR' && echo '📐 Architect Agent' && claude --dangerously-skip-permissions '/agents:architect --loop' 2>&1 | tee '$LOG_DIR/architect.log'\"
        end tell"

# Add dev tabs dynamically
for i in $(seq 1 $NUM_DEVS); do
    APPLESCRIPT="$APPLESCRIPT

        -- Tab: Dev $i
        set newTab to (create tab with default profile)
        tell current session of newTab
            set name to \"⚙️ D$i\"
            write text \"cd '$CURRENT_DIR' && echo '⚙️ Dev #$i' && claude --dangerously-skip-permissions '/agents:dev $i --loop' 2>&1 | tee '$LOG_DIR/dev-$i.log'\"
        end tell"
done

# Add Reviewer tab
APPLESCRIPT="$APPLESCRIPT

        -- Tab: Reviewer Agent
        set newTab to (create tab with default profile)
        tell current session of newTab
            set name to \"🔬 Rev\"
            write text \"cd '$CURRENT_DIR' && echo '🔬 Code Reviewer Agent' && claude --dangerously-skip-permissions '/agents:reviewer --loop' 2>&1 | tee '$LOG_DIR/reviewer.log'\"
        end tell"

# Add Ops tab
APPLESCRIPT="$APPLESCRIPT

        -- Tab: Ops Agent
        set newTab to (create tab with default profile)
        tell current session of newTab
            set name to \"🔧 Ops\"
            write text \"cd '$CURRENT_DIR' && echo '🔧 Ops Agent' && claude --dangerously-skip-permissions '/agents:ops --loop' 2>&1 | tee '$LOG_DIR/ops.log'\"
        end tell
    end tell
end tell"

# Execute
osascript -e "$APPLESCRIPT"

TOTAL_AGENTS=$((4 + NUM_DEVS))

echo ""
echo "✅ Launched $TOTAL_AGENTS agents in iTerm2 tabs!"
echo ""
echo "┌─────────────────────────────────────────────────────────────┐"
echo "│  Tab Layout                                                 │"
echo "├─────────────────────────────────────────────────────────────┤"
echo "│  🔍 BA   │ 📐 Arch │ ⚙️ D1-D$NUM_DEVS │ 🔬 Rev │ 🔧 Ops │"
echo "└─────────────────────────────────────────────────────────────┘"
echo ""
echo "Parallel Development:"
echo "  • $NUM_DEVS features can be developed simultaneously"
echo "  • Each dev creates isolated git worktrees"
echo "  • Worktrees location: $WORKTREE_DIR"
echo ""
echo "Logs: $LOG_DIR"
echo "Stop: Close iTerm2 window or ./stop-agents.sh"
