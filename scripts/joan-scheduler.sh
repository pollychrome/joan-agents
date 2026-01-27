#!/bin/bash
# ============================================================================
# Joan Agents External Scheduler
# ============================================================================
# Orchestrates dispatch cycles by querying Joan's actionable-tasks API
# (deterministic, <1s) and dispatching individual handlers via Claude CLI
# (intelligent work only). Each handler runs as a separate process with
# its own timeout — no heartbeat mechanism needed.
#
# Usage:
#   ./joan-scheduler.sh [PROJECT_DIR] [OPTIONS]
#
# Options:
#   --interval=N      Poll interval in seconds (default: 300 = 5 minutes)
#   --max-idle=N      Max idle polls before shutdown (default: 12)
#   --max-failures=N  Max consecutive failures before shutdown (default: 3)
#   --mode=MODE       Override mode (standard/yolo)
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
MAX_IDLE=12             # 12 idle polls = 1 hour at 5-min intervals
MAX_FAILURES=3          # Stop after 3 consecutive failures
MODE=""                 # Empty = read from config

# Parse named arguments
shift || true
while [[ $# -gt 0 ]]; do
    case $1 in
        --interval=*)
            POLL_INTERVAL="${1#*=}"
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
        --mode=*)
            MODE="${1#*=}"
            shift
            ;;
        --stuck-timeout=*)
            # Accepted for backwards compatibility, but no longer used
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

# File paths
LOG_DIR="${PROJECT_DIR}/.claude/logs"
LOG_FILE="${LOG_DIR}/scheduler.log"
SHUTDOWN_FILE="/tmp/joan-agents-${PROJECT_NAME}.shutdown"
HEARTBEAT_FILE="/tmp/joan-agents-${PROJECT_NAME}.heartbeat"
PID_FILE="/tmp/joan-agents-${PROJECT_NAME}.pid"
RESPONSE_FILE="/tmp/joan-dispatch-${PROJECT_NAME}.json"

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
# Configuration
# ============================================================================

load_config() {
    local config_file="${PROJECT_DIR}/.joan-agents.json"

    PROJECT_ID=$(jq -r '.projectId' "$config_file")
    CONFIG_MODE=$(jq -r '.settings.mode // "standard"' "$config_file")
    STALE_CLAIM_MINUTES=$(jq -r '.settings.staleClaimMinutes // 120' "$config_file")
    API_URL="https://joan-api.alexbbenson.workers.dev"

    # Use --mode flag if provided, otherwise use config
    if [[ -z "$MODE" ]]; then
        MODE="$CONFIG_MODE"
    fi

    # Worker timeouts (convert minutes → seconds)
    TIMEOUT_BA=$(( $(jq -r '.settings.workerTimeouts.ba // 10' "$config_file") * 60 ))
    TIMEOUT_ARCHITECT=$(( $(jq -r '.settings.workerTimeouts.architect // 20' "$config_file") * 60 ))
    TIMEOUT_DEV=$(( $(jq -r '.settings.workerTimeouts.dev // 60' "$config_file") * 60 ))
    TIMEOUT_REVIEWER=$(( $(jq -r '.settings.workerTimeouts.reviewer // 20' "$config_file") * 60 ))
    TIMEOUT_OPS=$(( $(jq -r '.settings.workerTimeouts.ops // 15' "$config_file") * 60 ))

    # Agent enabled flags
    BA_ENABLED=$(jq -r '.agents.businessAnalyst.enabled // true' "$config_file")
    ARCHITECT_ENABLED=$(jq -r '.agents.architect.enabled // true' "$config_file")
    REVIEWER_ENABLED=$(jq -r '.agents.reviewer.enabled // true' "$config_file")
    OPS_ENABLED=$(jq -r '.agents.ops.enabled // true' "$config_file")
    DEVS_ENABLED=$(jq -r '.agents.devs.enabled // true' "$config_file")
}

# ============================================================================
# Cleanup
# ============================================================================

cleanup() {
    log_info "Scheduler shutting down (signal received)"

    # Kill any running handler
    if [[ -f "$PID_FILE" ]]; then
        local pid
        pid="$(cat "$PID_FILE")"
        if kill -0 "$pid" 2>/dev/null; then
            log_info "Terminating handler (PID: $pid)"
            kill "$pid" 2>/dev/null || true
            sleep 2
            kill -9 "$pid" 2>/dev/null || true
        fi
    fi

    rm -f "$PID_FILE" "$SHUTDOWN_FILE" "$HEARTBEAT_FILE" "$RESPONSE_FILE"
    log_info "Scheduler stopped"
    exit 0
}

trap cleanup SIGINT SIGTERM

# ============================================================================
# API Query
# ============================================================================

query_api() {
    local http_code
    http_code=$(curl -sf -w '%{http_code}' \
        -H "Authorization: Bearer $JOAN_AUTH_TOKEN" \
        "${API_URL}/api/v1/projects/${PROJECT_ID}/actionable-tasks?mode=${MODE}&include_payloads=true&include_recovery=true&stale_claim_minutes=${STALE_CLAIM_MINUTES}" \
        -o "$RESPONSE_FILE" 2>/dev/null) || http_code="000"

    if [[ "$http_code" != "200" ]]; then
        log_error "API request failed (HTTP $http_code)"
        return 1
    fi
    return 0
}

# ============================================================================
# Handler Dispatch
# ============================================================================

run_handler() {
    local handler="$1"
    local task_id="${2:-}"
    local timeout_secs="$3"
    local exit_code=0

    local args="--handler=$handler"
    if [[ -n "$task_id" ]]; then
        args="$args --task=$task_id"
    fi

    log_info "  → Dispatching $handler${task_id:+ (task: ${task_id:0:8}...)}"

    # Write heartbeat for external monitoring
    echo "$(date +%s)" > "$HEARTBEAT_FILE"

    # Run handler in background so we can monitor timeout + shutdown
    cd "$PROJECT_DIR"
    claude --dangerously-skip-permissions "/agents:dispatch $args" >> "$LOG_FILE" 2>&1 &
    local handler_pid=$!
    echo "$handler_pid" > "$PID_FILE"

    # Wait for completion, timeout, or shutdown
    local elapsed=0
    while kill -0 "$handler_pid" 2>/dev/null; do
        sleep 5
        elapsed=$((elapsed + 5))

        # Update heartbeat
        echo "$(date +%s)" > "$HEARTBEAT_FILE"

        # Check shutdown
        if [[ -f "$SHUTDOWN_FILE" ]]; then
            log_info "  Shutdown requested, terminating $handler"
            kill "$handler_pid" 2>/dev/null || true
            wait "$handler_pid" 2>/dev/null || true
            rm -f "$PID_FILE"
            return 1
        fi

        # Check timeout
        if [[ $elapsed -ge $timeout_secs ]]; then
            log_error "  Handler $handler timed out after ${elapsed}s"
            kill -9 "$handler_pid" 2>/dev/null || true
            wait "$handler_pid" 2>/dev/null || true
            rm -f "$PID_FILE"
            return 1
        fi
    done

    wait "$handler_pid" 2>/dev/null || exit_code=$?
    rm -f "$PID_FILE"

    if [[ $exit_code -ne 0 ]]; then
        log_warn "  Handler $handler exited with code $exit_code"
        return 1
    fi

    log_info "  ✓ Handler $handler completed"
    return 0
}

# ============================================================================
# Dispatch Cycle
# ============================================================================

dispatch_cycle() {
    local dispatched=0
    local total_dispatched=0
    local max_repoll=3
    local repoll=0

    # ── Query API ──────────────────────────────────────────────────────
    if ! query_api; then
        return 1
    fi

    # ── Parse queues ───────────────────────────────────────────────────
    local ops_q=$(jq '.queues.ops // [] | length' "$RESPONSE_FILE" 2>/dev/null || echo 0)
    local rev_q=$(jq '.queues.reviewer // [] | length' "$RESPONSE_FILE" 2>/dev/null || echo 0)
    local dev_q=$(jq '.queues.dev // [] | length' "$RESPONSE_FILE" 2>/dev/null || echo 0)
    local arch_q=$(jq '.queues.architect // [] | length' "$RESPONSE_FILE" 2>/dev/null || echo 0)
    local ba_q=$(jq '.queues.ba // [] | length' "$RESPONSE_FILE" 2>/dev/null || echo 0)
    local blocked=$(jq -r '.pipeline.blocked // false' "$RESPONSE_FILE" 2>/dev/null || echo "false")

    # ── Log summary ────────────────────────────────────────────────────
    local total=$(jq -r '.summary.total_actionable // 0' "$RESPONSE_FILE" 2>/dev/null || echo 0)
    local recovery=$(jq -r '.summary.total_recovery_issues // 0' "$RESPONSE_FILE" 2>/dev/null || echo 0)
    local pending=$(jq -r '.summary.pending_human_action // 0' "$RESPONSE_FILE" 2>/dev/null || echo 0)

    log_info "API: ${total} actionable, ${recovery} recovery, ${pending} pending human"
    log_info "Queues: Ops=$ops_q Rev=$rev_q Dev=$dev_q Arch=$arch_q BA=$ba_q | Pipeline: ${blocked}"

    if [[ "$blocked" == "true" ]]; then
        local block_task=$(jq -r '.pipeline.blocking_task_title // "?"' "$RESPONSE_FILE" 2>/dev/null)
        log_info "Pipeline blocked by: $block_task"
    fi

    # Log recovery issues
    jq -r '.recovery.stale_claims[]? | "  RECOVERY: stale claim — \(.task_title) (\(.claim_age_minutes)m)"' "$RESPONSE_FILE" 2>/dev/null | while IFS= read -r line; do
        [[ -n "$line" ]] && log_info "$line"
    done
    jq -r '.recovery.anomalies[]? | "  RECOVERY: anomaly — \(.task_title) [\(.type)]"' "$RESPONSE_FILE" 2>/dev/null | while IFS= read -r line; do
        [[ -n "$line" ]] && log_info "$line"
    done

    # ── Dispatch in priority order ─────────────────────────────────────
    dispatched=0

    # P1: Ops (finish what's started)
    if [[ "$ops_q" -gt 0 && "$OPS_ENABLED" == "true" ]]; then
        run_handler "ops" "" "$TIMEOUT_OPS" && dispatched=$((dispatched + 1))
    fi

    # P2: Reviewer
    if [[ "$rev_q" -gt 0 && "$REVIEWER_ENABLED" == "true" ]]; then
        run_handler "reviewer" "" "$TIMEOUT_REVIEWER" && dispatched=$((dispatched + 1))
    fi

    # P3: Dev (API pre-filters — if task is in dev queue, it's actionable)
    if [[ "$dev_q" -gt 0 && "$DEVS_ENABLED" == "true" ]]; then
        local dev_task_id
        dev_task_id=$(jq -r '.queues.dev[0].task_id // empty' "$RESPONSE_FILE" 2>/dev/null)
        if [[ -n "$dev_task_id" ]]; then
            run_handler "dev" "$dev_task_id" "$TIMEOUT_DEV" && dispatched=$((dispatched + 1))
        fi
    fi

    # P4: Architect (pipeline gate — don't plan new work while dev/review active)
    if [[ "$arch_q" -gt 0 && "$ARCHITECT_ENABLED" == "true" && "$blocked" != "true" ]]; then
        run_handler "architect" "" "$TIMEOUT_ARCHITECT" && dispatched=$((dispatched + 1))
    fi

    # P5: BA
    if [[ "$ba_q" -gt 0 && "$BA_ENABLED" == "true" ]]; then
        run_handler "ba" "" "$TIMEOUT_BA" && dispatched=$((dispatched + 1))
    fi

    total_dispatched=$dispatched

    # ── Re-poll for downstream work ────────────────────────────────────
    while [[ $dispatched -gt 0 && $repoll -lt $max_repoll ]]; do
        repoll=$((repoll + 1))
        sleep 5
        log_info "Re-poll $repoll/$max_repoll (checking downstream)"

        if ! query_api; then
            log_warn "Re-poll API failed, ending dispatch loop"
            break
        fi

        ops_q=$(jq '.queues.ops // [] | length' "$RESPONSE_FILE" 2>/dev/null || echo 0)
        rev_q=$(jq '.queues.reviewer // [] | length' "$RESPONSE_FILE" 2>/dev/null || echo 0)
        dev_q=$(jq '.queues.dev // [] | length' "$RESPONSE_FILE" 2>/dev/null || echo 0)
        arch_q=$(jq '.queues.architect // [] | length' "$RESPONSE_FILE" 2>/dev/null || echo 0)
        ba_q=$(jq '.queues.ba // [] | length' "$RESPONSE_FILE" 2>/dev/null || echo 0)
        blocked=$(jq -r '.pipeline.blocked // false' "$RESPONSE_FILE" 2>/dev/null || echo "false")

        log_info "Re-poll queues: Ops=$ops_q Rev=$rev_q Dev=$dev_q Arch=$arch_q BA=$ba_q"

        dispatched=0

        if [[ "$ops_q" -gt 0 && "$OPS_ENABLED" == "true" ]]; then
            run_handler "ops" "" "$TIMEOUT_OPS" && dispatched=$((dispatched + 1))
        fi

        if [[ "$rev_q" -gt 0 && "$REVIEWER_ENABLED" == "true" ]]; then
            run_handler "reviewer" "" "$TIMEOUT_REVIEWER" && dispatched=$((dispatched + 1))
        fi

        if [[ "$dev_q" -gt 0 && "$DEVS_ENABLED" == "true" ]]; then
            local dev_task_id
            dev_task_id=$(jq -r '.queues.dev[0].task_id // empty' "$RESPONSE_FILE" 2>/dev/null)
            if [[ -n "$dev_task_id" ]]; then
                run_handler "dev" "$dev_task_id" "$TIMEOUT_DEV" && dispatched=$((dispatched + 1))
            fi
        fi

        if [[ "$arch_q" -gt 0 && "$ARCHITECT_ENABLED" == "true" && "$blocked" != "true" ]]; then
            run_handler "architect" "" "$TIMEOUT_ARCHITECT" && dispatched=$((dispatched + 1))
        fi

        if [[ "$ba_q" -gt 0 && "$BA_ENABLED" == "true" ]]; then
            run_handler "ba" "" "$TIMEOUT_BA" && dispatched=$((dispatched + 1))
        fi

        total_dispatched=$((total_dispatched + dispatched))

        if [[ $dispatched -eq 0 ]]; then
            log_info "No new downstream work"
        fi
    done

    log_info "Cycle result: $total_dispatched handlers dispatched"
    rm -f "$RESPONSE_FILE"

    # Return dispatched count via exit code (0 = no work, 1+ = work done)
    # We use a file since bash functions can't return values > 255
    echo "$total_dispatched" > "/tmp/joan-agents-${PROJECT_NAME}.dispatched"
    return 0
}

# ============================================================================
# Main Loop
# ============================================================================

main() {
    # Load project config
    load_config

    log_info "=============================================="
    log_info "Joan Agents Scheduler v2 (API-driven)"
    log_info "=============================================="
    log_info "Project: $PROJECT_DIR ($PROJECT_NAME)"
    log_info "Project ID: $PROJECT_ID"
    log_info "Mode: $MODE"
    log_info "Poll interval: ${POLL_INTERVAL}s"
    log_info "Max idle: $MAX_IDLE | Max failures: $MAX_FAILURES"
    log_info "Timeouts: BA=${TIMEOUT_BA}s Arch=${TIMEOUT_ARCHITECT}s Dev=${TIMEOUT_DEV}s Rev=${TIMEOUT_REVIEWER}s Ops=${TIMEOUT_OPS}s"
    log_info "=============================================="

    local idle_count=0
    local consecutive_failures=0
    local cycle=0

    # Cleanup stale files
    rm -f "$SHUTDOWN_FILE" "$HEARTBEAT_FILE" "$PID_FILE" "$RESPONSE_FILE"

    while true; do
        cycle=$((cycle + 1))

        if [[ -f "$SHUTDOWN_FILE" ]]; then
            log_info "Shutdown file detected, stopping"
            break
        fi

        log_info "────────────────────────────────────────────"
        log_info "Cycle $cycle"

        # Write heartbeat at cycle start
        echo "$(date +%s)" > "$HEARTBEAT_FILE"

        if dispatch_cycle; then
            consecutive_failures=0

            # Read dispatched count
            local dispatched=0
            if [[ -f "/tmp/joan-agents-${PROJECT_NAME}.dispatched" ]]; then
                dispatched=$(cat "/tmp/joan-agents-${PROJECT_NAME}.dispatched" 2>/dev/null || echo 0)
                rm -f "/tmp/joan-agents-${PROJECT_NAME}.dispatched"
            fi

            if [[ "$dispatched" -gt 0 ]]; then
                idle_count=0
                log_info "Work completed ($dispatched handlers) — re-polling in 5s"
                sleep 5
            else
                idle_count=$((idle_count + 1))
                log_info "No work, idle count: $idle_count/$MAX_IDLE"
                log_info "Sleeping ${POLL_INTERVAL}s..."
                sleep "$POLL_INTERVAL"
            fi
        else
            consecutive_failures=$((consecutive_failures + 1))
            idle_count=$((idle_count + 1))
            log_warn "Cycle failed, consecutive failures: $consecutive_failures/$MAX_FAILURES"
            log_info "Sleeping ${POLL_INTERVAL}s..."
            sleep "$POLL_INTERVAL"
        fi

        if [[ $consecutive_failures -ge $MAX_FAILURES ]]; then
            log_error "Too many consecutive failures ($consecutive_failures), stopping"
            exit 1
        fi

        if [[ $idle_count -ge $MAX_IDLE ]]; then
            log_info "Max idle reached ($idle_count), stopping gracefully"
            break
        fi
    done

    log_info "=============================================="
    log_info "Scheduler finished"
    log_info "=============================================="
    rm -f "$SHUTDOWN_FILE" "$HEARTBEAT_FILE" "$PID_FILE" "$RESPONSE_FILE"
}

# ============================================================================
# Entry Point
# ============================================================================

if [[ ! -d "$PROJECT_DIR" ]]; then
    echo "ERROR: Project directory does not exist: $PROJECT_DIR"
    exit 1
fi

if [[ ! -f "${PROJECT_DIR}/.joan-agents.json" ]]; then
    echo "ERROR: No .joan-agents.json found in $PROJECT_DIR"
    echo "Run '/agents:init' to create the configuration file."
    exit 1
fi

# Resolve auth token (env var or decrypt from joan-mcp credentials)
resolve_token() {
    if [[ -n "${JOAN_AUTH_TOKEN:-}" ]]; then
        return 0
    fi

    local creds_file="$HOME/.joan-mcp/credentials.json"
    if [[ ! -f "$creds_file" ]]; then
        echo "ERROR: JOAN_AUTH_TOKEN not set and no credentials found at $creds_file"
        echo "Run 'joan-mcp login' or set JOAN_AUTH_TOKEN environment variable"
        exit 1
    fi

    # Decrypt using Node.js (matches joan-mcp's AES-256-GCM encryption)
    JOAN_AUTH_TOKEN=$(node -e "
        const fs = require('fs');
        const crypto = require('crypto');
        const os = require('os');
        const path = require('path');
        const creds = JSON.parse(fs.readFileSync(path.join(os.homedir(), '.joan-mcp', 'credentials.json'), 'utf8'));
        const salt = os.homedir() + '-' + (process.env.USER || process.env.USERNAME || 'joan');
        const key = crypto.scryptSync('joan-mcp-local-encryption', salt, 32);
        const decipher = crypto.createDecipheriv('aes-256-gcm', key, Buffer.from(creds.iv, 'hex'));
        decipher.setAuthTag(Buffer.from(creds.authTag, 'hex'));
        let token = decipher.update(creds.token, 'hex', 'utf8');
        token += decipher.final('utf8');
        process.stdout.write(token);
    " 2>/dev/null) || {
        echo "ERROR: Failed to decrypt token from $creds_file"
        exit 1
    }

    if [[ -z "$JOAN_AUTH_TOKEN" ]]; then
        echo "ERROR: Decrypted token is empty"
        exit 1
    fi

    export JOAN_AUTH_TOKEN
}

resolve_token

# Verify jq is available
if ! command -v jq &> /dev/null; then
    echo "ERROR: jq is required but not installed"
    echo "Install with: brew install jq"
    exit 1
fi

main
