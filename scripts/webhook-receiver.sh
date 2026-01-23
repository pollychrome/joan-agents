#!/bin/bash
#
# Joan Agents Webhook Receiver (State-Aware)
#
# Lightweight HTTP server that receives webhooks from Joan and dispatches
# the appropriate micro-handler based on the event type and tag changes.
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
#

set -euo pipefail

# Default configuration
PORT="${JOAN_WEBHOOK_PORT:-9847}"
PROJECT_DIR="${JOAN_PROJECT_DIR:-.}"
SECRET="${JOAN_WEBHOOK_SECRET:-}"
MODE="${JOAN_WORKFLOW_MODE:-standard}"
CATCHUP_INTERVAL="${JOAN_CATCHUP_INTERVAL:-60}"
LOG_FILE="${PROJECT_DIR}/.claude/logs/webhook-receiver.log"
CATCHUP_PID=""
LAST_CATCHUP=0

# Parse arguments
while [[ $# -gt 0 ]]; do
  case $1 in
    --port)
      PORT="$2"
      shift 2
      ;;
    --project-dir)
      PROJECT_DIR="$2"
      shift 2
      ;;
    --secret)
      SECRET="$2"
      shift 2
      ;;
    --mode)
      MODE="$2"
      shift 2
      ;;
    --help)
      echo "Joan Agents Webhook Receiver"
      echo ""
      echo "Usage: $0 [OPTIONS]"
      echo ""
      echo "Options:"
      echo "  --port PORT         Port to listen on (default: 9847)"
      echo "  --project-dir DIR   Project directory (default: current directory)"
      echo "  --secret SECRET     HMAC secret for signature verification"
      echo "  --mode MODE         Workflow mode: standard or yolo (default: standard)"
      echo "  --help              Show this help message"
      echo ""
      echo "Note: Run '/agents:clean-project --apply' before starting to integrate"
      echo "      existing tasks into the workflow."
      exit 0
      ;;
    *)
      echo "Unknown option: $1"
      exit 1
      ;;
  esac
done

# Ensure log directory exists
mkdir -p "$(dirname "$LOG_FILE")"

log() {
  local timestamp
  timestamp=$(date -Iseconds)
  echo "[$timestamp] $*" | tee -a "$LOG_FILE"
}

log_debug() {
  if [[ "${JOAN_WEBHOOK_DEBUG:-}" == "1" ]]; then
    log "DEBUG: $*"
  fi
}

# Run catchup scan - check Joan state for actionable work
# This makes the receiver resilient to missed webhooks
# Uses single-pass dispatch which already has all the queue logic
run_catchup_scan() {
  local reason="${1:-scheduled}"

  # Don't run if another catchup is in progress
  if [[ -n "$CATCHUP_PID" ]] && kill -0 "$CATCHUP_PID" 2>/dev/null; then
    log_debug "Catchup scan already in progress (PID: $CATCHUP_PID)"
    return 0
  fi

  log "CATCHUP [$reason]: Running single-pass dispatch to catch missed work..."

  # Run single-pass dispatch in background
  # This processes all actionable items in one go
  (
    cd "$PROJECT_DIR"
    JOAN_WORKFLOW_MODE="$MODE" claude "/agents:dispatch" 2>&1 | tee -a "$LOG_FILE"
    log "CATCHUP [$reason]: Single-pass dispatch complete"
    LAST_CATCHUP=$(date +%s)
  ) &

  CATCHUP_PID=$!
  log "CATCHUP [$reason]: Dispatch started (PID: $CATCHUP_PID)"
}

# Start periodic catchup loop in background
start_catchup_loop() {
  log "Starting periodic catchup (every ${CATCHUP_INTERVAL}s)"

  (
    while true; do
      sleep "$CATCHUP_INTERVAL"
      run_catchup_scan "periodic"
    done
  ) &

  local loop_pid=$!
  log_debug "Catchup loop started (PID: $loop_pid)"

  # Store PID for cleanup
  echo "$loop_pid" > "${PROJECT_DIR}/.claude/catchup-loop.pid"
}

# Verify HMAC signature if secret is configured
verify_signature() {
  local payload="$1"
  local signature="$2"

  if [[ -z "$SECRET" ]]; then
    return 0  # No secret configured, skip verification
  fi

  if [[ -z "$signature" ]]; then
    log "WARN: No signature provided but secret is configured"
    return 1
  fi

  # Extract hash from "sha256=HASH" format
  local expected_hash="${signature#sha256=}"
  local actual_hash
  actual_hash=$(echo -n "$payload" | openssl dgst -sha256 -hmac "$SECRET" | awk '{print $2}')

  if [[ "$expected_hash" != "$actual_hash" ]]; then
    log "WARN: Signature verification failed"
    return 1
  fi

  return 0
}

# Dispatch handler based on event type and changes
dispatch_handler() {
  local event_type="$1"
  local task_id="$2"
  local tag_name="${3:-}"
  local triggered_by="${4:-user}"

  # Skip events triggered by agents to prevent loops
  if [[ "$triggered_by" == "agent" ]]; then
    log_debug "Skipping agent-triggered event"
    return 0
  fi

  local handler=""
  local handler_args=""

  case "$event_type" in
    tag_added)
      case "$tag_name" in
        Ready)
          handler="handle-architect"
          handler_args="--task=$task_id --mode=plan"
          ;;
        Plan-Approved)
          handler="handle-architect"
          handler_args="--task=$task_id --mode=finalize"
          ;;
        Plan-Rejected)
          handler="handle-architect"
          handler_args="--task=$task_id --mode=revise"
          ;;
        Planned|Rework-Requested|Merge-Conflict)
          handler="handle-dev"
          handler_args="--task=$task_id"
          ;;
        Dev-Complete)
          handler="handle-reviewer"
          handler_args="--task=$task_id"
          ;;
        Rework-Complete)
          handler="handle-reviewer"
          handler_args="--task=$task_id"
          ;;
        Ops-Ready)
          handler="handle-ops"
          handler_args="--task=$task_id"
          ;;
        Clarification-Answered)
          handler="handle-ba"
          handler_args="--task=$task_id"
          ;;
        Invoke-Architect)
          handler="handle-architect"
          handler_args="--task=$task_id --mode=advisory-conflict"
          ;;
        Architect-Assist-Complete)
          handler="handle-ops"
          handler_args="--task=$task_id --mode=merge-with-guidance"
          ;;
        *)
          log_debug "No handler for tag: $tag_name"
          return 0
          ;;
      esac
      ;;
    task_moved)
      # Task moved events are handled by tag changes primarily
      # This is a fallback for manual UI moves
      log_debug "Task moved event - relying on tag-based handlers"
      return 0
      ;;
    task_created)
      # New tasks in To Do column need BA evaluation
      handler="handle-ba"
      handler_args="--task=$task_id"
      ;;
    comment_added)
      # Comments don't trigger handlers in v4 (tag-based system)
      log_debug "Comment added - no handler (tag-based system)"
      return 0
      ;;
    *)
      log_debug "Unknown event type: $event_type"
      return 0
      ;;
  esac

  if [[ -n "$handler" ]]; then
    log "Dispatching: $handler $handler_args --mode=$MODE"

    # Run handler in background to not block webhook response
    (
      cd "$PROJECT_DIR"
      JOAN_WORKFLOW_MODE="$MODE" claude "/agents:dispatch/$handler" $handler_args --mode="$MODE" 2>&1 | tee -a "$LOG_FILE"
    ) &

    log "Handler dispatched (PID: $!)"
  fi
}

# Process incoming webhook
process_webhook() {
  local headers="$1"
  local body="$2"

  # Extract headers
  local event_type=""
  local signature=""

  while IFS= read -r header; do
    case "$header" in
      X-Joan-Event:*)
        event_type="${header#X-Joan-Event: }"
        event_type="${event_type%$'\r'}"
        ;;
      X-Joan-Signature:*)
        signature="${header#X-Joan-Signature: }"
        signature="${signature%$'\r'}"
        ;;
    esac
  done <<< "$headers"

  log_debug "Received event: $event_type"

  # Verify signature
  if ! verify_signature "$body" "$signature"; then
    echo "HTTP/1.1 401 Unauthorized"
    echo "Content-Type: application/json"
    echo ""
    echo '{"error": "Invalid signature"}'
    return
  fi

  # Parse JSON payload
  local task_id
  local tag_name=""
  local triggered_by

  task_id=$(echo "$body" | jq -r '.task_id // empty')
  triggered_by=$(echo "$body" | jq -r '.triggered_by // "user"')

  # Extract tag name for tag events
  if [[ "$event_type" == "tag_added" ]] || [[ "$event_type" == "tag_removed" ]]; then
    tag_name=$(echo "$body" | jq -r '.changes[0].new_value // .changes[0].old_value // empty')
  fi

  if [[ -z "$task_id" ]]; then
    log "WARN: No task_id in webhook payload"
    echo "HTTP/1.1 400 Bad Request"
    echo "Content-Type: application/json"
    echo ""
    echo '{"error": "Missing task_id"}'
    return
  fi

  # Dispatch appropriate handler
  dispatch_handler "$event_type" "$task_id" "$tag_name" "$triggered_by"

  # Send success response
  echo "HTTP/1.1 200 OK"
  echo "Content-Type: application/json"
  echo ""
  echo '{"status": "received"}'
}

# Simple HTTP server using netcat
run_server() {
  log "Starting webhook receiver on port $PORT"
  log "Project directory: $PROJECT_DIR"
  log "Workflow mode: $MODE"
  log "Secret configured: $(if [[ -n "$SECRET" ]]; then echo "yes"; else echo "no"; fi)"

  while true; do
    # Read HTTP request
    {
      # Read request line
      read -r request_line

      # Read headers until empty line
      headers=""
      while IFS= read -r header; do
        header="${header%$'\r'}"
        [[ -z "$header" ]] && break
        headers+="$header"$'\n'
      done

      # Extract Content-Length
      content_length=$(echo "$headers" | grep -i "Content-Length:" | awk '{print $2}' | tr -d '\r')
      content_length="${content_length:-0}"

      # Read body if present
      body=""
      if [[ "$content_length" -gt 0 ]]; then
        body=$(dd bs=1 count="$content_length" 2>/dev/null)
      fi

      # Process POST requests to webhook endpoint
      if [[ "$request_line" == "POST /webhook"* ]]; then
        process_webhook "$headers" "$body"
      elif [[ "$request_line" == "GET /health"* ]]; then
        echo "HTTP/1.1 200 OK"
        echo "Content-Type: application/json"
        echo ""
        echo '{"status": "healthy"}'
      else
        echo "HTTP/1.1 404 Not Found"
        echo "Content-Type: application/json"
        echo ""
        echo '{"error": "Not found"}'
      fi
    } | nc -l "$PORT"
  done
}

# Handle signals
cleanup() {
  log "Shutting down webhook receiver"

  # Kill catchup loop if running
  local loop_pid_file="${PROJECT_DIR}/.claude/catchup-loop.pid"
  if [[ -f "$loop_pid_file" ]]; then
    local loop_pid
    loop_pid=$(cat "$loop_pid_file")
    if kill -0 "$loop_pid" 2>/dev/null; then
      log "Stopping catchup loop (PID: $loop_pid)"
      kill "$loop_pid" 2>/dev/null || true
    fi
    rm -f "$loop_pid_file"
  fi

  # Kill any in-progress catchup scan
  if [[ -n "$CATCHUP_PID" ]] && kill -0 "$CATCHUP_PID" 2>/dev/null; then
    log "Stopping catchup scan (PID: $CATCHUP_PID)"
    kill "$CATCHUP_PID" 2>/dev/null || true
  fi

  exit 0
}

trap cleanup SIGINT SIGTERM

# Check dependencies
if ! command -v nc &> /dev/null; then
  echo "Error: netcat (nc) is required but not installed"
  exit 1
fi

if ! command -v jq &> /dev/null; then
  echo "Error: jq is required but not installed"
  exit 1
fi

if ! command -v claude &> /dev/null; then
  echo "Error: claude CLI is required but not installed"
  exit 1
fi

# Verify project is ready for webhook processing
verify_ready() {
  log "=== VERIFYING PROJECT STATE ==="

  # Check config file exists
  local config_file="$PROJECT_DIR/.joan-agents.json"
  if [[ ! -f "$config_file" ]]; then
    log "ERROR: .joan-agents.json not found at $config_file"
    log "Run /agents:init first to configure the project."
    exit 1
  fi

  # Verify config is valid JSON
  if ! jq empty "$config_file" 2>/dev/null; then
    log "ERROR: .joan-agents.json is not valid JSON"
    exit 1
  fi

  # Extract project name for logging
  local project_name
  project_name=$(jq -r '.projectName // "Unknown"' "$config_file")

  log "Project: $project_name"
  log "Config: Valid"
  log "Catchup interval: ${CATCHUP_INTERVAL}s"
  log ""
}

# Start the state-aware receiver
start_receiver() {
  # Verify project is configured
  verify_ready

  log "=== STARTING STATE-AWARE RECEIVER ==="
  log ""

  # Run initial catchup scan to process any missed events
  log "Running startup catchup scan..."
  run_catchup_scan "startup"

  # Give the startup scan a moment to begin
  sleep 2

  # Start periodic catchup loop
  start_catchup_loop

  log ""
  log "=== LISTENING FOR WEBHOOKS ==="
  log "Webhooks: http://localhost:$PORT/webhook"
  log "Health:   http://localhost:$PORT/health"
  log ""
  log "State-aware mode active:"
  log "  • Startup scan: catches missed events"
  log "  • Periodic scan: every ${CATCHUP_INTERVAL}s"
  log "  • Webhook events: immediate response"
  log ""

  # Start HTTP server
  run_server
}

# Main entry point
start_receiver
