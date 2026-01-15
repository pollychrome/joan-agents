#!/bin/bash

# Joan Multi-Agent Stop Script
# Also cleans up any orphaned worktrees

echo "🛑 Stopping Joan Multi-Agent Orchestration..."
echo ""

# Stop all claude agent processes
pkill -f "claude.*agents:.*-loop" 2>/dev/null || true

echo "✓ Sent stop signal to all agents"

# Check for orphaned worktrees
if [ -d "../worktrees" ]; then
    WORKTREE_COUNT=$(ls -1 ../worktrees 2>/dev/null | wc -l | tr -d ' ')
    if [ "$WORKTREE_COUNT" -gt 0 ]; then
        echo ""
        echo "⚠️  Found $WORKTREE_COUNT worktree(s) in ../worktrees/"
        echo ""
        ls -1 ../worktrees/
        echo ""
        read -p "Clean up worktrees? (y/n) " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            for wt in ../worktrees/*/; do
                if [ -d "$wt" ]; then
                    wt_name=$(basename "$wt")
                    echo "  Removing worktree: $wt_name"
                    git worktree remove "$wt" --force 2>/dev/null || rm -rf "$wt"
                fi
            done
            git worktree prune 2>/dev/null || true
            echo "✓ Worktrees cleaned up"
        else
            echo "Worktrees preserved. Clean up manually with:"
            echo "  git worktree remove ../worktrees/<name> --force"
        fi
    fi
fi

echo ""
echo "✅ Shutdown complete"
echo ""
echo "If agents don't stop within 30 seconds, force kill with:"
echo "  pkill -9 -f 'claude.*agents'"
