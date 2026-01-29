#!/usr/bin/env python3
"""
Joan Agents WebSocket Client

A WebSocket client that connects to Joan and receives real-time events.
Replaces the webhook-server.py approach with outbound WebSocket connections
that work through any firewall.

Phase 3 Architecture:
- Smart events include pre-fetched payloads (handlers don't re-fetch)
- Handlers return simple results (success, result_type, output, comment)
- Joan backend applies state transitions via result-processor
- Use submit-result.py to report completion from handlers

Features:
- State-driven startup: queries actionable-tasks API on launch (zero cold start)
- Outbound WebSocket connection (works through firewalls)
- Auto-reconnect with exponential backoff
- Smart event payloads passed to handlers (zero re-fetching)
- JWT-based authentication (shared with joan-mcp)

Usage:
    ./ws-client.py [--project-dir DIR] [--api-url URL]

Environment variables (client config):
    JOAN_API_URL          - Joan API URL (default: https://joan-api.alexbbenson.workers.dev)
    JOAN_PROJECT_DIR      - Project directory (default: current directory)
    JOAN_WORKFLOW_MODE    - Workflow mode: standard or yolo (default: standard)
    JOAN_AUTH_TOKEN       - JWT auth token (optional, falls back to joan-mcp credentials)
    JOAN_WEBSOCKET_DEBUG  - Set to "1" for debug logging

Environment variables (passed to handlers - Phase 3):
    JOAN_PROJECT_ID       - Project ID for result submission
    JOAN_TASK_ID          - Task ID for result submission
    JOAN_SMART_PAYLOAD    - JSON string with pre-fetched task data

Authentication:
    Token is loaded in this order:
    1. JOAN_AUTH_TOKEN environment variable
    2. ~/.joan-mcp/credentials.json (shared with joan-mcp, encrypted)

    To authenticate, run: joan-mcp login
"""

import argparse
import asyncio
import hashlib
import json
import os
import signal
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Optional

try:
    import websockets
    from websockets.exceptions import ConnectionClosed
except ImportError:
    print("Error: websockets library not installed. Run: pip install websockets>=12.0")
    sys.exit(1)

try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from cryptography.hazmat.primitives.kdf.scrypt import Scrypt
    from cryptography.hazmat.backends import default_backend
    CRYPTO_AVAILABLE = True
except ImportError:
    AESGCM = None
    Scrypt = None
    CRYPTO_AVAILABLE = False


# joan-mcp credential file location
JOAN_MCP_CREDENTIALS = Path.home() / '.joan-mcp' / 'credentials.json'


def get_machine_key() -> bytes:
    """
    Get a machine-specific encryption key.
    Must match the key derivation in joan-mcp/src/auth.ts
    """
    # Use home directory and username as salt - stable across sessions
    username = os.environ.get('USER') or os.environ.get('USERNAME') or 'joan'
    salt = f"{Path.home()}-{username}"

    # Use cryptography's Scrypt KDF (more compatible than hashlib.scrypt)
    kdf = Scrypt(
        salt=salt.encode('utf-8'),
        length=32,
        n=16384,  # Node.js scrypt default
        r=8,
        p=1,
        backend=default_backend()
    )
    return kdf.derive(b'joan-mcp-local-encryption')


def decrypt_token(encrypted: str, iv: str, auth_tag: str) -> str:
    """
    Decrypt a stored token from joan-mcp credentials.
    Uses AES-256-GCM with machine-specific key.
    """
    if not CRYPTO_AVAILABLE:
        raise ImportError("cryptography library not installed")

    key = get_machine_key()
    aesgcm = AESGCM(key)

    # Convert hex strings to bytes
    iv_bytes = bytes.fromhex(iv)
    encrypted_bytes = bytes.fromhex(encrypted)
    auth_tag_bytes = bytes.fromhex(auth_tag)

    # AES-GCM expects ciphertext + tag concatenated
    ciphertext_with_tag = encrypted_bytes + auth_tag_bytes

    # Decrypt
    plaintext = aesgcm.decrypt(iv_bytes, ciphertext_with_tag, None)
    return plaintext.decode('utf-8')


def load_joan_mcp_token() -> Optional[str]:
    """
    Load auth token from joan-mcp credentials file.
    Returns None if credentials don't exist or are invalid/expired.
    """
    if not JOAN_MCP_CREDENTIALS.exists():
        return None

    try:
        with open(JOAN_MCP_CREDENTIALS) as f:
            credentials = json.load(f)

        # Check if token is expired
        if credentials.get('expiresAt'):
            expires_at = datetime.fromisoformat(credentials['expiresAt'].replace('Z', '+00:00'))
            if expires_at < datetime.now(expires_at.tzinfo):
                return None  # Token expired

        # Decrypt the token
        token = decrypt_token(
            credentials['token'],
            credentials['iv'],
            credentials['authTag']
        )
        return token

    except Exception as e:
        # Log but don't fail - will fall back to other methods
        print(f"Warning: Could not load joan-mcp credentials: {e}")
        return None


def get_auth_token() -> Optional[str]:
    """
    Get auth token from environment or joan-mcp credentials.
    Priority: 1. JOAN_AUTH_TOKEN env var, 2. joan-mcp credentials
    """
    # First, check environment variable
    env_token = os.environ.get('JOAN_AUTH_TOKEN', '').strip()
    if env_token:
        return env_token

    # Then, check joan-mcp credentials (if cryptography is available)
    if CRYPTO_AVAILABLE:
        mcp_token = load_joan_mcp_token()
        if mcp_token:
            return mcp_token

    return None


class WebSocketConfig:
    """Configuration for the WebSocket client."""

    def __init__(self):
        self.api_url = os.environ.get('JOAN_API_URL', 'https://joan-api.alexbbenson.workers.dev')
        self.project_dir = Path(os.environ.get('JOAN_PROJECT_DIR', '.'))
        self.mode = os.environ.get('JOAN_WORKFLOW_MODE', 'standard')
        self.auth_token = get_auth_token() or ''
        self.debug = os.environ.get('JOAN_WEBSOCKET_DEBUG', '') == '1'

        # Paths
        self.log_dir = self.project_dir / '.claude' / 'logs'
        self.log_file = self.log_dir / 'websocket-client.log'
        self.config_file = self.project_dir / '.joan-agents.json'

        # Project config (loaded from .joan-agents.json)
        self.project_id: Optional[str] = None
        self.project_name: Optional[str] = None

    def parse_args(self, args: list):
        """Parse command line arguments."""
        parser = argparse.ArgumentParser(description='Joan WebSocket Client')
        parser.add_argument('--project-dir', type=str, help='Project directory')
        parser.add_argument('--api-url', type=str, help='Joan API URL')
        parser.add_argument('--mode', type=str, choices=['standard', 'yolo'], help='Workflow mode')
        parser.add_argument('--token', type=str, help='JWT auth token')

        parsed = parser.parse_args(args)

        if parsed.project_dir:
            self.project_dir = Path(parsed.project_dir)
            self.log_dir = self.project_dir / '.claude' / 'logs'
            self.log_file = self.log_dir / 'websocket-client.log'
            self.config_file = self.project_dir / '.joan-agents.json'
        if parsed.api_url:
            self.api_url = parsed.api_url
        if parsed.mode:
            self.mode = parsed.mode
        if parsed.token:
            self.auth_token = parsed.token

    def load_project_config(self):
        """Load project configuration from .joan-agents.json."""
        if not self.config_file.exists():
            raise FileNotFoundError(f".joan-agents.json not found at {self.config_file}")

        with open(self.config_file) as f:
            data = json.load(f)

        self.project_id = data.get('projectId')
        self.project_name = data.get('projectName', 'Unknown')

        if not self.project_id:
            raise ValueError("projectId not found in .joan-agents.json")

        # Check for mode override
        settings = data.get('settings', {})
        if settings.get('mode'):
            self.mode = settings['mode']


# Global config instance
config = WebSocketConfig()

# Shutdown event
shutdown_event = asyncio.Event()


def log(message: str, level: str = "INFO"):
    """Write log entry with timestamp."""
    now = datetime.now()
    iso_timestamp = now.strftime('%Y-%m-%dT%H:%M:%S') or now.isoformat()

    log_line = f"[{iso_timestamp}] [{level}] {message}"

    # Console output
    print(log_line)

    # File output
    try:
        config.log_dir.mkdir(parents=True, exist_ok=True)
        with open(config.log_file, 'a') as f:
            f.write(log_line + '\n')
    except Exception as e:
        print(f"[{iso_timestamp}] [ERROR] Failed to write log: {e}")


def log_debug(message: str):
    """Write debug log entry (only if debug mode enabled)."""
    if config.debug:
        log(message, "DEBUG")


def rotate_log():
    """Rotate existing log file on startup so each session gets a clean log."""
    if not config.log_file.exists() or config.log_file.stat().st_size == 0:
        return

    mtime = datetime.fromtimestamp(config.log_file.stat().st_mtime)
    stamp = mtime.strftime('%Y%m%d-%H%M%S')
    rotated = config.log_dir / f'websocket-client.{stamp}.log'

    # Avoid overwriting if multiple restarts in the same second
    counter = 1
    while rotated.exists():
        rotated = config.log_dir / f'websocket-client.{stamp}-{counter}.log'
        counter += 1

    config.log_file.rename(rotated)


# =============================================================================
# Differential Payload Profiles
# Each handler receives only the fields it actually uses, reducing payload
# size by ~30-40% on average. Handlers already handle missing fields gracefully.
# =============================================================================
HANDLER_PAYLOAD_PROFILES = {
    "handle-ba":        {"desc_max": 2000, "comments_max": 3,  "subtasks": False, "rework": False, "columns": False},
    "handle-architect": {"desc_max": None, "comments_max": 5,  "subtasks": True,  "rework": False, "columns": True},
    "handle-dev":       {"desc_max": None, "comments_max": 0,  "subtasks": True,  "rework": True,  "columns": False},
    "handle-reviewer":  {"desc_max": 1000, "comments_max": 3,  "subtasks": True,  "rework": False, "columns": False},
    "handle-ops":       {"desc_max": 200,  "comments_max": 0,  "subtasks": False, "rework": False, "columns": False},
}


def filter_payload_for_handler(handler: str, smart_payload: dict) -> dict:
    """Filter smart payload to include only fields the handler needs.

    Each handler has a profile defining which fields it uses and size limits.
    This reduces token consumption by ~30-40% per handler invocation while
    maintaining backward compatibility (handlers use OR {} patterns for missing fields).
    """
    profile = HANDLER_PAYLOAD_PROFILES.get(handler)
    if not profile or not smart_payload:
        return smart_payload

    filtered = {}

    # Task - always include, truncate description per profile
    if "task" in smart_payload:
        task = dict(smart_payload["task"])
        max_chars = profile["desc_max"]
        if max_chars and task.get("description") and len(task["description"]) > max_chars:
            original_len = len(task["description"])
            task["description"] = task["description"][:max_chars] + f"\n\n[truncated, {original_len} total chars]"
        filtered["task"] = task

    # Tags + handoff_context - always include (bounded by ALS spec, max 3KB)
    for key in ("tags", "handoff_context"):
        if key in smart_payload:
            filtered[key] = smart_payload[key]

    # Conditional fields based on handler profile
    for key, flag in [("subtasks", "subtasks"), ("rework_feedback", "rework"), ("columns", "columns")]:
        if profile[flag] and key in smart_payload:
            filtered[key] = smart_payload[key]

    # Comments - limit count per profile
    max_c = profile["comments_max"]
    if max_c > 0 and "recent_comments" in smart_payload:
        filtered["recent_comments"] = smart_payload["recent_comments"][:max_c]

    return filtered


def dispatch_handler(event_type: str, task_id: str, tag_name: str = "", triggered_by: str = "user", smart_payload: dict = None, project_id: str = None):
    """Dispatch the appropriate handler based on event type and tag.

    Phase 3 Architecture:
    - Smart events include pre-fetched payloads (handlers don't re-fetch)
    - Handlers return simple results (success, result_type, output, comment)
    - Joan backend applies state transitions via result-processor

    Smart events (Phase 2) are preferred over tag_added events as they:
    - Include pre-fetched task data (no re-fetching needed)
    - Are semantically clearer (task_ready_for_dev vs tag_added:Planned)
    - Skip unnecessary state machine transitions (handled server-side)
    """

    # Skip events triggered by agents to prevent loops
    if triggered_by == "agent":
        log_debug(f"Skipping agent-triggered event: {event_type}")
        return

    handler = ""
    handler_args = []

    # ========================================================================
    # SMART EVENTS (Phase 2/3 - Server-side state machine)
    # These events are emitted by Joan's workflow rules engine after it has
    # already executed the state machine transitions. No tag parsing needed.
    # Payloads include pre-fetched task data for zero-fetch handler execution.
    # ========================================================================
    smart_event_handlers = {
        "task_needs_ba": ("handle-ba", []),
        "task_needs_ba_reevaluation": ("handle-ba", []),
        "task_needs_plan": ("handle-architect", ["--mode=plan"]),
        "task_ready_for_dev": ("handle-dev", []),
        "task_needs_rework": ("handle-dev", []),
        "task_ready_for_review": ("handle-reviewer", []),
        "task_ready_for_merge": ("handle-ops", []),
    }

    if event_type in smart_event_handlers:
        handler, handler_args = smart_event_handlers[event_type]
        log(f"Smart event: {event_type} -> {handler}")

    # ========================================================================
    # LEGACY TAG EVENTS (fallback for backward compatibility)
    # These are still used when workflow rules are disabled or for edge cases.
    # ========================================================================
    elif event_type == "tag_added":
        tag_handlers = {
            "Ready": ("handle-architect", ["--mode=plan"]),
            "Plan-Approved": ("handle-architect", ["--mode=finalize"]),
            "Plan-Rejected": ("handle-architect", ["--mode=revise"]),
            "Planned": ("handle-dev", []),
            "Rework-Requested": ("handle-dev", []),
            "Merge-Conflict": ("handle-dev", []),
            "Dev-Complete": ("handle-reviewer", []),
            "Rework-Complete": ("handle-reviewer", []),
            "Ops-Ready": ("handle-ops", []),
            "Clarification-Answered": ("handle-ba", []),
            "Invoke-Architect": ("handle-architect", ["--mode=advisory-conflict"]),
            "Architect-Assist-Complete": ("handle-ops", ["--mode=merge-with-guidance"]),
        }

        if tag_name in tag_handlers:
            handler, handler_args = tag_handlers[tag_name]
        else:
            log_debug(f"No handler for tag: {tag_name}")
            return

    elif event_type == "task_created":
        handler = "handle-ba"
        handler_args = []

    elif event_type == "task_moved":
        log_debug("Task moved event - relying on tag-based handlers")
        return

    elif event_type == "comment_added":
        log_debug("Comment added - no handler (tag-based system)")
        return

    elif event_type == "connected":
        log("WebSocket connected to Joan backend")
        return

    else:
        log_debug(f"Unknown event type: {event_type}")
        return

    if handler:
        # Skill arguments must be part of the prompt string, not separate argv entries.
        # Claude Code CLI parses --flags as its own options before interpreting the skill.
        # Workflow mode is passed via JOAN_WORKFLOW_MODE env var (already set below).
        skill_args = f"--task={task_id}"
        if handler_args:
            skill_args += " " + " ".join(handler_args)

        cmd = ["claude", f"/agents:dispatch/{handler} {skill_args}"]

        log(f"Dispatching: {handler} {skill_args}")

        # Run handler in background
        try:
            env = os.environ.copy()
            env['JOAN_WORKFLOW_MODE'] = config.mode

            # Pass auth token explicitly (critical: ensures spawned processes authenticate
            # even if this process loaded token from credentials.json instead of env var)
            if config.auth_token:
                env['JOAN_AUTH_TOKEN'] = config.auth_token
                log_debug(f"Auth token passed to handler: {config.auth_token[:20]}...")
            else:
                log(f"WARNING: No auth token available to pass to handler", "WARN")

            # Phase 3: Pass context for result submission
            # Handlers can use submit-result.py to report completion
            env['JOAN_PROJECT_ID'] = project_id or config.project_id or ''
            env['JOAN_TASK_ID'] = task_id
            env['JOAN_API_URL'] = config.api_url

            # Phase 3: Pass smart payload so handlers don't need to re-fetch
            # Apply differential filtering to strip unused fields per handler
            if smart_payload:
                filtered = filter_payload_for_handler(handler, smart_payload)
                env['JOAN_SMART_PAYLOAD'] = json.dumps(filtered)
                original_size = len(json.dumps(smart_payload))
                filtered_size = len(json.dumps(filtered))
                reduction = round((1 - filtered_size / original_size) * 100) if original_size > 0 else 0
                log_debug(f"Payload filtered: {original_size} -> {filtered_size} bytes (-{reduction}%) ({handler})")

            process = subprocess.Popen(
                cmd,
                cwd=str(config.project_dir),
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True
            )

            log(f"Handler dispatched (PID: {process.pid})")

            # Log output in background thread
            def log_output():
                try:
                    for line in process.stdout:
                        line = line.strip()
                        if line:
                            log(f"[{handler}] {line}")
                    process.wait()
                    log(f"Handler {handler} completed (exit code: {process.returncode})")
                except Exception as e:
                    log(f"Error reading handler output: {e}", "ERROR")

            thread = threading.Thread(target=log_output, daemon=True)
            thread.start()

        except Exception as e:
            log(f"Failed to dispatch handler: {e}", "ERROR")


# =============================================================================
# Startup Dispatch (replaces catchup loop)
# =============================================================================

def fetch_actionable_tasks() -> dict:
    """Fetch actionable tasks from Joan API.

    Queries the pre-computed priority queues endpoint which replicates
    the queue-building logic from dispatch.md Steps 1-3b server-side.
    """
    url = f"{config.api_url}/api/v1/projects/{config.project_id}/actionable-tasks"
    url += f"?mode={config.mode}&include_payloads=true&include_recovery=true"

    req = urllib.request.Request(url, headers={
        'Authorization': f'Bearer {config.auth_token}',
        'Content-Type': 'application/json',
        'User-Agent': 'joan-agents-websocket-client/1.0',
    })

    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode('utf-8'))


def dispatch_handler_direct(handler: str, task_id: str, handler_args: list,
                            smart_payload: dict = None, project_id: str = None):
    """Dispatch a handler directly from startup dispatch (bypasses event routing).

    Same subprocess pattern as dispatch_handler() but without event_type mapping.
    """
    skill_args = f"--task={task_id}"
    if handler_args:
        skill_args += " " + " ".join(handler_args)

    cmd = ["claude", f"/agents:dispatch/{handler} {skill_args}"]
    log(f"STARTUP: Dispatching {handler} {skill_args}")

    try:
        env = os.environ.copy()
        env['JOAN_WORKFLOW_MODE'] = config.mode

        # Pass auth token explicitly (critical: ensures spawned processes authenticate
        # even if this process loaded token from credentials.json instead of env var)
        if config.auth_token:
            env['JOAN_AUTH_TOKEN'] = config.auth_token
            log_debug(f"STARTUP: Auth token passed to handler: {config.auth_token[:20]}...")
        else:
            log(f"STARTUP: WARNING: No auth token available to pass to handler", "WARN")

        env['JOAN_PROJECT_ID'] = project_id or config.project_id or ''
        env['JOAN_TASK_ID'] = task_id
        env['JOAN_API_URL'] = config.api_url

        if smart_payload:
            filtered = filter_payload_for_handler(handler, smart_payload)
            env['JOAN_SMART_PAYLOAD'] = json.dumps(filtered)

        process = subprocess.Popen(
            cmd,
            cwd=str(config.project_dir),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True
        )

        log(f"STARTUP: Handler dispatched (PID: {process.pid})")

        def log_output():
            try:
                for line in process.stdout:
                    line = line.strip()
                    if line:
                        log(f"[{handler}] {line}")
                process.wait()
                log(f"Handler {handler} completed (exit code: {process.returncode})")
            except Exception as e:
                log(f"Error reading handler output: {e}", "ERROR")

        thread = threading.Thread(target=log_output, daemon=True)
        thread.start()

    except Exception as e:
        log(f"STARTUP: Failed to dispatch handler: {e}", "ERROR")


def run_startup_dispatch():
    """Query actionable tasks and dispatch handlers immediately.

    Called once at startup before WebSocket connects. Eliminates cold start
    delay by processing existing actionable work without waiting for events.
    """
    log("=== STARTUP: QUERYING ACTIONABLE TASKS ===")

    try:
        data = fetch_actionable_tasks()
    except urllib.error.HTTPError as e:
        log(f"STARTUP: API returned {e.code}: {e.reason}", "ERROR")
        log("STARTUP: Will rely on WebSocket events (cold-start delay possible)")
        return
    except Exception as e:
        log(f"STARTUP: Failed to query actionable tasks: {e}", "ERROR")
        log("STARTUP: Will rely on WebSocket events (cold-start delay possible)")
        return

    summary = data.get('summary', {})
    log(f"STARTUP: {summary.get('total_actionable', 0)} actionable, "
        f"{summary.get('total_recovery_issues', 0)} recovery issues, "
        f"{summary.get('pending_human_action', 0)} pending human action")

    # Log pipeline status
    pipeline = data.get('pipeline', {})
    if pipeline.get('blocked'):
        log(f"STARTUP: Pipeline BLOCKED: '{pipeline.get('blocking_task_title')}' - "
            f"{pipeline.get('blocking_reason')}")

    # Log recovery issues
    recovery = data.get('recovery', {})
    for stale in recovery.get('stale_claims', []):
        log(f"  STALE CLAIM: '{stale['task_title']}' "
            f"({stale['claim_age_minutes']}m, threshold: {stale['threshold_minutes']}m)")
    for anomaly in recovery.get('anomalies', []):
        log(f"  ANOMALY: '{anomaly['task_title']}' "
            f"[{anomaly['type']}] tags={anomaly['stale_tags']} col={anomaly['column']}")
    for invalid in recovery.get('invalid_states', []):
        log(f"  INVALID STATE: '{invalid['task_title']}' "
            f"[{invalid['type']}] tags={invalid['tags']} fix={invalid['remediation']}")

    # Dispatch handlers for each queue item (priority order: ops, reviewer, dev, architect, ba)
    queues = data.get('queues', {})
    dispatched = 0

    for queue_name in ['ops', 'reviewer', 'dev', 'architect', 'ba']:
        for item in queues.get(queue_name, []):
            handler = item['handler']
            handler_args = item.get('handler_args', [])
            mode = item.get('mode', '')

            log(f"STARTUP: {handler} → task {item['task_id'][:8]}... "
                f"'{item.get('task_title', '')}' (mode: {mode})")

            dispatch_handler_direct(
                handler, item['task_id'], handler_args,
                item.get('smart_payload'), config.project_id
            )
            dispatched += 1

    log(f"STARTUP: Dispatched {dispatched} handler(s)")
    log("")


async def websocket_client():
    """Main WebSocket client loop with reconnection."""
    # Build WebSocket URL
    ws_url = config.api_url.replace('https://', 'wss://').replace('http://', 'ws://')
    ws_url = f"{ws_url}/api/v1/projects/{config.project_id}/events/ws?token={config.auth_token}&projectId={config.project_id}"

    reconnect_delay = 1  # Start with 1 second
    max_reconnect_delay = 60  # Max 60 seconds

    while not shutdown_event.is_set():
        try:
            log(f"Connecting to WebSocket...")
            log_debug(f"URL: {ws_url[:100]}...")  # Don't log full URL with token

            async with websockets.connect(
                ws_url,
                ping_interval=30,
                ping_timeout=10,
                close_timeout=10,
            ) as websocket:
                log("WebSocket connected successfully")
                reconnect_delay = 1  # Reset on successful connection

                # Handle incoming messages
                async for message in websocket:
                    try:
                        data = json.loads(message)
                        msg_type = data.get('type', '')

                        if msg_type == 'event':
                            payload = data.get('payload', {})
                            event_type = payload.get('event_type', '')
                            task_id = payload.get('task_id', '')
                            event_project_id = payload.get('project_id', '')
                            triggered_by = payload.get('triggered_by', 'user')
                            metadata = payload.get('metadata', {})
                            smart_payload = metadata.get('smart_payload', None)

                            # Extract tag name for tag events
                            tag_name = ""
                            if event_type in ('tag_added', 'tag_removed'):
                                changes = payload.get('changes', [])
                                if changes:
                                    tag_name = changes[0].get('new_value') or changes[0].get('old_value', '')

                            if event_type != 'connected':
                                is_smart = "smart" if smart_payload else "legacy"
                                log(f"Event received: {event_type} task={task_id} tag={tag_name} ({is_smart})")
                                if config.debug and smart_payload:
                                    log_debug(f"Smart payload keys: {list(smart_payload.keys())}")

                            dispatch_handler(event_type, task_id, tag_name, triggered_by, smart_payload, event_project_id)

                        elif msg_type == 'heartbeat':
                            log_debug("Heartbeat received")

                        elif msg_type == 'error':
                            error_msg = data.get('message', 'Unknown error')
                            log(f"Server error: {error_msg}", "ERROR")

                        else:
                            log_debug(f"Unknown message type: {msg_type}")

                    except json.JSONDecodeError as e:
                        log(f"Invalid JSON message: {e}", "WARN")
                    except Exception as e:
                        log(f"Error processing message: {e}", "ERROR")

        except ConnectionClosed as e:
            log(f"WebSocket connection closed: {e.code} {e.reason}", "WARN")
        except Exception as e:
            log(f"WebSocket error: {e}", "ERROR")

        if not shutdown_event.is_set():
            log(f"Reconnecting in {reconnect_delay}s...")
            try:
                await asyncio.wait_for(
                    shutdown_event.wait(),
                    timeout=reconnect_delay
                )
                # Shutdown requested
                break
            except asyncio.TimeoutError:
                pass

            # Exponential backoff
            reconnect_delay = min(reconnect_delay * 2, max_reconnect_delay)


async def main_async():
    """Async main entry point."""
    # Run WebSocket client (startup dispatch already completed synchronously)
    ws_task = asyncio.create_task(websocket_client())

    # Wait for shutdown
    try:
        await shutdown_event.wait()
    except asyncio.CancelledError:
        pass

    # Cancel tasks
    ws_task.cancel()

    try:
        await asyncio.gather(ws_task, return_exceptions=True)
    except:
        pass


def signal_handler(signum, frame):
    """Handle shutdown signals."""
    log("Shutting down WebSocket client...")
    shutdown_event.set()


def verify_ready():
    """Verify project is ready for WebSocket processing."""
    log("=== VERIFYING PROJECT STATE ===")

    try:
        config.load_project_config()
    except FileNotFoundError:
        log(f"ERROR: .joan-agents.json not found at {config.config_file}", "ERROR")
        log("Run /agents:init first to configure the project.")
        sys.exit(1)
    except json.JSONDecodeError as e:
        log(f"ERROR: .joan-agents.json is not valid JSON: {e}", "ERROR")
        sys.exit(1)
    except ValueError as e:
        log(f"ERROR: {e}", "ERROR")
        sys.exit(1)

    if not config.auth_token:
        log("ERROR: No auth token found", "ERROR")
        log("")
        log("To authenticate, run:")
        log("  joan-mcp login")
        log("")
        log("Or set JOAN_AUTH_TOKEN environment variable manually.")
        if not CRYPTO_AVAILABLE:
            log("")
            log("Note: Install 'cryptography' to enable automatic credential sharing:")
            log("  pip install cryptography")
        sys.exit(1)

    log(f"Project: {config.project_name}")
    log(f"Project ID: {config.project_id}")
    log(f"API URL: {config.api_url}")
    log("Config: Valid")
    log("")


def main():
    """Main entry point."""
    # Parse arguments
    config.parse_args(sys.argv[1:])

    # Set up signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Rotate previous session's log before writing anything
    rotate_log()

    # Verify project
    verify_ready()

    log("=== STARTING WEBSOCKET CLIENT ===")
    log("")

    # Immediate: dispatch existing actionable work (eliminates cold start)
    run_startup_dispatch()

    # Then: connect WebSocket for real-time events
    log("=== CONNECTING TO JOAN ===")
    log(f"API: {config.api_url}")
    log(f"Project: {config.project_name}")
    log("")
    log("WebSocket mode active:")
    log(f"  Real-time events via WebSocket")
    log(f"  No catchup scans (state-driven startup)")
    log(f"  Auto-reconnect with exponential backoff")
    log("")

    # Run async event loop
    try:
        asyncio.run(main_async())
    except KeyboardInterrupt:
        pass
    finally:
        log("WebSocket client stopped")


if __name__ == '__main__':
    main()
