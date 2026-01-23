#!/bin/bash
#
# Joan Agents Webhook Receiver (State-Aware)
#
# Wrapper script that launches the Python webhook server.
# This script maintains backwards compatibility with existing documentation.
#
# STATE-AWARE DESIGN:
# This receiver is resilient to missed events. It checks Joan state:
#   1. On startup - catches any work missed while receiver was down
#   2. After each webhook - catches any related work
#   3. Every CATCHUP_INTERVAL seconds - catches anything that slipped through
#
# This means you can safely restart the receiver at any time without losing work.
#
# Usage:
#   ./webhook-receiver.sh [--port PORT] [--project-dir DIR] [--secret SECRET]
#
# Environment variables:
#   JOAN_WEBHOOK_PORT     - Port to listen on (default: 9847)
#   JOAN_WEBHOOK_SECRET   - HMAC secret for signature verification
#   JOAN_PROJECT_DIR      - Project directory (default: current directory)
#   JOAN_CATCHUP_INTERVAL - Seconds between state scans (default: 60)
#
# The receiver maps webhook events to handler invocations:
#   - tag_added: Ready         → handle-architect --task=ID --mode=plan
#   - tag_added: Plan-Approved → handle-architect --task=ID --mode=finalize
#   - tag_added: Planned       → handle-dev --task=ID
#   - tag_added: Dev-Complete  → handle-reviewer --task=ID
#   - tag_added: Ops-Ready     → handle-ops --task=ID
#   - task_created            → handle-ba --task=ID

set -euo pipefail

# Find the directory containing this script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Default configuration
PORT="${JOAN_WEBHOOK_PORT:-9847}"
PROJECT_DIR="${JOAN_PROJECT_DIR:-.}"
SECRET="${JOAN_WEBHOOK_SECRET:-}"
MODE="${JOAN_WORKFLOW_MODE:-standard}"
CATCHUP_INTERVAL="${JOAN_CATCHUP_INTERVAL:-60}"

# Build arguments for Python server
ARGS=()

# Parse arguments and pass through to Python server
while [[ $# -gt 0 ]]; do
  case $1 in
    --port)
      PORT="$2"
      ARGS+=("--port" "$2")
      shift 2
      ;;
    --project-dir)
      PROJECT_DIR="$2"
      ARGS+=("--project-dir" "$2")
      shift 2
      ;;
    --secret)
      SECRET="$2"
      ARGS+=("--secret" "$2")
      shift 2
      ;;
    --mode)
      MODE="$2"
      ARGS+=("--mode" "$2")
      shift 2
      ;;
    --catchup-interval)
      CATCHUP_INTERVAL="$2"
      ARGS+=("--catchup-interval" "$2")
      shift 2
      ;;
    --help)
      echo "Joan Agents Webhook Receiver (State-Aware)"
      echo ""
      echo "Usage: $0 [OPTIONS]"
      echo ""
      echo "Options:"
      echo "  --port PORT              Port to listen on (default: 9847)"
      echo "  --project-dir DIR        Project directory (default: current directory)"
      echo "  --secret SECRET          HMAC secret for signature verification"
      echo "  --mode MODE              Workflow mode: standard or yolo (default: standard)"
      echo "  --catchup-interval SECS  Seconds between state scans (default: 60)"
      echo "  --help                   Show this help message"
      echo ""
      echo "State-Aware Features:"
      echo "  - Startup scan: catches missed events while receiver was down"
      echo "  - Periodic scan: catches work every CATCHUP_INTERVAL seconds"
      echo "  - Webhook events: immediate response to Joan events"
      echo ""
      echo "This receiver is resilient to missed webhooks - state scans ensure"
      echo "all work eventually gets processed even if webhooks are missed."
      exit 0
      ;;
    *)
      echo "Unknown option: $1"
      exit 1
      ;;
  esac
done

# Check for Python 3
if ! command -v python3 &> /dev/null; then
  echo "Error: python3 is required but not installed"
  exit 1
fi

# Check for claude CLI
if ! command -v claude &> /dev/null; then
  echo "Error: claude CLI is required but not installed"
  exit 1
fi

# Export environment variables for Python server
export JOAN_WEBHOOK_PORT="$PORT"
export JOAN_PROJECT_DIR="$PROJECT_DIR"
export JOAN_WEBHOOK_SECRET="$SECRET"
export JOAN_WORKFLOW_MODE="$MODE"
export JOAN_CATCHUP_INTERVAL="$CATCHUP_INTERVAL"

# Launch Python webhook server
exec python3 "${SCRIPT_DIR}/webhook-server.py" "${ARGS[@]}"
