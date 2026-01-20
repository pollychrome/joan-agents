#!/bin/bash
# ============================================================================
# Joan Agents External Scheduler
# ============================================================================
# Spawns fresh coordinator processes with clean context to prevent context
# overflow during long-running operations.
#
# Usage:
#   ./joan-scheduler.sh [PROJECT_DIR] [OPTIONS]
#
# Options:
#   --interval=N      Poll interval in seconds (default: 300 = 5 minutes)
#   --stuck-timeout=N Seconds before killing stuck coordinator (default: 600)
#   --max-idle=N      Max idle polls before shutdown (default: 12)
#   --max-failures=N  Max consecutive failures before shutdown (default: 3)
#
# Examples:
#   ./joan-scheduler.sh .                           # Run with defaults
#   ./joan-scheduler.sh . --interval=120            # Poll every 2 minutes
#   ./joan-scheduler.sh /path/to/project --max-idle=24
#
# ============================================================================

set -euo pipefail

# Default values
PROJECT_DIR="${1:-.}"
POLL_INTERVAL=300       # 5 minutes
STUCK_TIMEOUT=600       # 10 minutes
MAX_IDLE=12             # 12 idle polls = 1 hour at 5-min intervals
MAX_FAILURES=3          # Stop after 3 consecutive failures

# Parse named arguments
shift || true
while [[ $# -gt 0 ]]; do
    case $1 in
        --interval=*)
            POLL_INTERVAL="${1#*=}"
            shift
            ;;
        --stuck-timeout=*)
            STUCK_TIMEOUT="${1#*=}"
            shift
            ;;
        --max-idle=*)
            MAX_IDLE="${1#*=}"
            shift
            ;;
        --max-failures=*)
            MAX_FAILURES="${1#*=}"
            shift
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Resolve to absolute path
PROJECT_DIR="$(cd "$PROJECT_DIR" && pwd)"
PROJECT_NAME="$(basename "$PROJECT_DIR")"

# File paths for coordination
HEARTBEAT_FILE="/tmp/joan-agents-${PROJECT_NAME}.heartbeat"
SHUTDOWN_FILE="/tmp/joan-agents-${PROJECT_NAME}.shutdown"
PID_FILE="/tmp/joan-agents-${PROJECT_NAME}.pid"
LOG_DIR="${PROJECT_DIR}/.claude/logs"
LOG_FILE="${LOG_DIR}/scheduler.log"

# Ensure log directory exists
mkdir -p "$LOG_DIR"

# ============================================================================
# Logging
# ============================================================================

log() {
    local level="$1"
    local message="$2"
    local timestamp
    timestamp="$(date '+%Y-%m-%d %H:%M:%S')"
    echo "[${timestamp}] [${level}] ${message}" | tee -a "$LOG_FILE"
}

log_info() { log "INFO" "$1"; }
log_warn() { log "WARN" "$1"; }
log_error() { log "ERROR" "$1"; }

# ============================================================================
# Cleanup
# ============================================================================

cleanup() {
    log_info "Scheduler shutting down (signal received)"

    # Signal coordinator to stop gracefully
    touch "$SHUTDOWN_FILE"

    # Wait briefly for coordinator to notice
    sleep 2

    # Kill coordinator if still running
    if [[ -f "$PID_FILE" ]]; then
        local pid
        pid="$(cat "$PID_FILE")"
        if kill -0 "$pid" 2>/dev/null; then
            log_info "Terminating coordinator (PID: $pid)"
            kill "$pid" 2>/dev/null || true
            sleep 2
            kill -9 "$pid" 2>/dev/null || true
        fi
    fi

    # Cleanup files
    rm -f "$PID_FILE" "$SHUTDOWN_FILE" "$HEARTBEAT_FILE"

    log_info "Scheduler stopped"
    exit 0
}

trap cleanup SIGINT SIGTERM

# ============================================================================
# Health Check
# ============================================================================

check_heartbeat() {
    if [[ ! -f "$HEARTBEAT_FILE" ]]; then
        return 0  # No heartbeat file yet - coordinator just started
    fi

    local last_heartbeat
    local now
    local age

    last_heartbeat="$(cat "$HEARTBEAT_FILE" 2>/dev/null || echo 0)"
    now="$(date +%s)"
    age=$((now - last_heartbeat))

    if [[ $age -gt $STUCK_TIMEOUT ]]; then
        log_error "Coordinator stuck (no heartbeat for ${age}s, threshold: ${STUCK_TIMEOUT}s)"
        return 1
    fi

    return 0
}

# ============================================================================
# Coordinator Management
# ============================================================================

run_coordinator() {
    local exit_code=0

    # Remove stale heartbeat
    rm -f "$HEARTBEAT_FILE"

    log_info "Starting coordinator (fresh context)"

    # Run single-pass coordinator in background
    cd "$PROJECT_DIR"
    claude /agents:dispatch 2>&1 | while IFS= read -r line; do
        echo "$line" | tee -a "$LOG_FILE"
    done &
    local coordinator_pid=$!
    echo "$coordinator_pid" > "$PID_FILE"

    log_info "Coordinator started (PID: $coordinator_pid)"

    # Monitor coordinator with heartbeat checks
    while kill -0 "$coordinator_pid" 2>/dev/null; do
        sleep 10

        # Check for shutdown request
        if [[ -f "$SHUTDOWN_FILE" ]]; then
            log_info "Shutdown requested, terminating coordinator"
            kill "$coordinator_pid" 2>/dev/null || true
            break
        fi

        # Check heartbeat health
        if ! check_heartbeat; then
            log_error "Killing stuck coordinator (PID: $coordinator_pid)"
            kill -9 "$coordinator_pid" 2>/dev/null || true
            exit_code=1
            break
        fi
    done

    # Wait for coordinator to finish
    wait "$coordinator_pid" 2>/dev/null || exit_code=$?

    # Cleanup PID file
    rm -f "$PID_FILE"

    return $exit_code
}

# ============================================================================
# Main Loop
# ============================================================================

main() {
    log_info "=============================================="
    log_info "Joan Agents External Scheduler Starting"
    log_info "=============================================="
    log_info "Project: $PROJECT_DIR"
    log_info "Poll interval: ${POLL_INTERVAL}s"
    log_info "Stuck timeout: ${STUCK_TIMEOUT}s"
    log_info "Max idle polls: $MAX_IDLE"
    log_info "Max consecutive failures: $MAX_FAILURES"
    log_info "=============================================="

    local idle_count=0
    local consecutive_failures=0
    local cycle=0

    # Cleanup any stale files from previous runs
    rm -f "$SHUTDOWN_FILE" "$HEARTBEAT_FILE" "$PID_FILE"

    while true; do
        cycle=$((cycle + 1))

        # Check for manual shutdown request
        if [[ -f "$SHUTDOWN_FILE" ]]; then
            log_info "Shutdown file detected, stopping scheduler"
            break
        fi

        log_info "────────────────────────────────────────────"
        log_info "Cycle $cycle starting"

        # Run coordinator (single pass with fresh context)
        if run_coordinator; then
            consecutive_failures=0
            log_info "Coordinator completed successfully"

            # Check heartbeat file for activity indicator
            # If heartbeat exists and is recent, work was done
            if [[ -f "$HEARTBEAT_FILE" ]]; then
                local last_heartbeat now age
                last_heartbeat="$(cat "$HEARTBEAT_FILE" 2>/dev/null || echo 0)"
                now="$(date +%s)"
                age=$((now - last_heartbeat))

                # If heartbeat was within last 60 seconds, assume work was done
                if [[ $age -lt 60 ]]; then
                    idle_count=0
                    log_info "Work detected (recent heartbeat), idle count reset"
                else
                    idle_count=$((idle_count + 1))
                    log_info "No work detected, idle count: $idle_count/$MAX_IDLE"
                fi
            else
                # No heartbeat file = very quick exit = likely no work
                idle_count=$((idle_count + 1))
                log_info "No heartbeat file, idle count: $idle_count/$MAX_IDLE"
            fi
        else
            consecutive_failures=$((consecutive_failures + 1))
            idle_count=$((idle_count + 1))
            log_warn "Coordinator failed (exit code), consecutive failures: $consecutive_failures/$MAX_FAILURES"
        fi

        # Check failure threshold
        if [[ $consecutive_failures -ge $MAX_FAILURES ]]; then
            log_error "Too many consecutive failures ($consecutive_failures), stopping scheduler"
            exit 1
        fi

        # Check idle threshold
        if [[ $idle_count -ge $MAX_IDLE ]]; then
            log_info "Max idle polls reached ($idle_count), stopping scheduler gracefully"
            break
        fi

        log_info "Sleeping ${POLL_INTERVAL}s before next cycle..."
        sleep "$POLL_INTERVAL"
    done

    log_info "=============================================="
    log_info "Scheduler finished normally"
    log_info "=============================================="

    # Final cleanup
    rm -f "$SHUTDOWN_FILE" "$HEARTBEAT_FILE" "$PID_FILE"
}

# ============================================================================
# Entry Point
# ============================================================================

# Verify project directory exists and has config
if [[ ! -d "$PROJECT_DIR" ]]; then
    echo "ERROR: Project directory does not exist: $PROJECT_DIR"
    exit 1
fi

if [[ ! -f "${PROJECT_DIR}/.joan-agents.json" ]]; then
    echo "ERROR: No .joan-agents.json found in $PROJECT_DIR"
    echo "Run '/agents:init' to create the configuration file."
    exit 1
fi

main
