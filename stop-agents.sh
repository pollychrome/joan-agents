#!/bin/bash

# Joan Multi-Agent Stop Script

echo "🛑 Stopping Joan Multi-Agent Orchestration..."
echo ""

# Stop all claude agent processes
pkill -f "claude.*agents:.*-loop" 2>/dev/null || true

echo "✓ Sent stop signal to all agents"
echo ""
echo "✅ Shutdown complete"
echo ""
echo "If agents don't stop within 30 seconds, force kill with:"
echo "  pkill -9 -f 'claude.*agents'"
