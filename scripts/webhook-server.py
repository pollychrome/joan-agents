#!/usr/bin/env python3
"""
Joan Agents Webhook Server (State-Aware)

A robust HTTP server that receives webhooks from Joan and dispatches handlers.
Replaces the fragile bash/netcat approach with a proper Python HTTP server.

Features:
- Persistent HTTP listener (handles multiple connections)
- State-aware with periodic catchup scans
- HMAC signature verification
- Consistent logging for joan CLI dashboard
- Graceful shutdown handling

Usage:
    ./webhook-server.py [--port PORT] [--project-dir DIR] [--secret SECRET]

Environment variables:
    JOAN_WEBHOOK_PORT     - Port to listen on (default: 9847)
    JOAN_WEBHOOK_SECRET   - HMAC secret for signature verification
    JOAN_PROJECT_DIR      - Project directory (default: current directory)
    JOAN_CATCHUP_INTERVAL - Seconds between state scans (default: 60)
    JOAN_WORKFLOW_MODE    - Workflow mode: standard or yolo (default: standard)
"""

import argparse
import hashlib
import hmac
import json
import os
import signal
import subprocess
import sys
import threading
import time
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from typing import Optional


class WebhookConfig:
    """Configuration for the webhook server."""

    def __init__(self):
        self.port = int(os.environ.get('JOAN_WEBHOOK_PORT', 9847))
        self.project_dir = Path(os.environ.get('JOAN_PROJECT_DIR', '.'))
        self.secret = os.environ.get('JOAN_WEBHOOK_SECRET', '')
        self.mode = os.environ.get('JOAN_WORKFLOW_MODE', 'standard')
        self.catchup_interval = int(os.environ.get('JOAN_CATCHUP_INTERVAL', 60))
        self.debug = os.environ.get('JOAN_WEBHOOK_DEBUG', '') == '1'

        # Paths
        self.log_dir = self.project_dir / '.claude' / 'logs'
        self.log_file = self.log_dir / 'webhook-receiver.log'
        self.config_file = self.project_dir / '.joan-agents.json'

    def parse_args(self, args: list):
        """Parse command line arguments."""
        parser = argparse.ArgumentParser(description='Joan Webhook Server')
        parser.add_argument('--port', type=int, help='Port to listen on')
        parser.add_argument('--project-dir', type=str, help='Project directory')
        parser.add_argument('--secret', type=str, help='HMAC secret')
        parser.add_argument('--mode', type=str, choices=['standard', 'yolo'], help='Workflow mode')
        parser.add_argument('--catchup-interval', type=int, help='Catchup scan interval in seconds')

        parsed = parser.parse_args(args)

        if parsed.port:
            self.port = parsed.port
        if parsed.project_dir:
            self.project_dir = Path(parsed.project_dir)
            self.log_dir = self.project_dir / '.claude' / 'logs'
            self.log_file = self.log_dir / 'webhook-receiver.log'
            self.config_file = self.project_dir / '.joan-agents.json'
        if parsed.secret:
            self.secret = parsed.secret
        if parsed.mode:
            self.mode = parsed.mode
        if parsed.catchup_interval:
            self.catchup_interval = parsed.catchup_interval


# Global config instance
config = WebhookConfig()

# Track running processes
catchup_process: Optional[subprocess.Popen] = None
catchup_thread: Optional[threading.Thread] = None
shutdown_event = threading.Event()


def log(message: str, level: str = "INFO"):
    """Write log entry with timestamp.

    Uses two timestamp formats for compatibility:
    - ISO format in the first bracket (for webhook log parsing)
    - Human-readable format (for display and worker-activity.log compatibility)
    """
    now = datetime.now()
    iso_timestamp = now.strftime('%Y-%m-%dT%H:%M:%S%z') or now.isoformat()
    human_timestamp = now.strftime('%Y-%m-%d %H:%M:%S')

    # Use ISO format for main log (joan CLI parses this)
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


def verify_signature(payload: bytes, signature: str) -> bool:
    """Verify HMAC signature of webhook payload."""
    if not config.secret:
        return True  # No secret configured, skip verification

    if not signature:
        log("No signature provided but secret is configured", "WARN")
        return False

    # Extract hash from "sha256=HASH" format
    if signature.startswith('sha256='):
        expected_hash = signature[7:]
    else:
        expected_hash = signature

    actual_hash = hmac.new(
        config.secret.encode(),
        payload,
        hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(expected_hash, actual_hash):
        log("Signature verification failed", "WARN")
        return False

    return True


def dispatch_handler(event_type: str, task_id: str, tag_name: str = "", triggered_by: str = "user"):
    """Dispatch the appropriate handler based on event type and tag."""

    # Skip events triggered by agents to prevent loops
    if triggered_by == "agent":
        log_debug(f"Skipping agent-triggered event: {event_type}")
        return

    handler = ""
    handler_args = []

    if event_type == "tag_added":
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

    else:
        log_debug(f"Unknown event type: {event_type}")
        return

    if handler:
        # Build command
        cmd = [
            "claude",
            f"/agents:dispatch/{handler}",
            f"--task={task_id}",
            f"--mode={config.mode}"
        ] + handler_args

        log(f"Dispatching: {handler} --task={task_id} {' '.join(handler_args)}")

        # Run handler in background
        try:
            env = os.environ.copy()
            env['JOAN_WORKFLOW_MODE'] = config.mode

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


def run_catchup_scan(reason: str = "scheduled"):
    """Run a catchup scan using single-pass dispatch."""
    global catchup_process

    # Don't run if another catchup is in progress
    if catchup_process is not None and catchup_process.poll() is None:
        log_debug(f"Catchup scan already in progress (PID: {catchup_process.pid})")
        return

    log(f"CATCHUP [{reason}]: Running single-pass dispatch to catch missed work...")

    try:
        env = os.environ.copy()
        env['JOAN_WORKFLOW_MODE'] = config.mode

        catchup_process = subprocess.Popen(
            ["claude", "/agents:dispatch"],
            cwd=str(config.project_dir),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True
        )

        log(f"CATCHUP [{reason}]: Dispatch started (PID: {catchup_process.pid})")

        # Log output in background thread
        def log_output():
            try:
                for line in catchup_process.stdout:
                    line = line.strip()
                    if line:
                        log(f"[dispatch] {line}")
                catchup_process.wait()
                log(f"CATCHUP [{reason}]: Single-pass dispatch complete")
            except Exception as e:
                log(f"Error reading dispatch output: {e}", "ERROR")

        thread = threading.Thread(target=log_output, daemon=True)
        thread.start()

    except Exception as e:
        log(f"CATCHUP [{reason}]: Failed to start dispatch: {e}", "ERROR")


def catchup_loop():
    """Background thread that runs periodic catchup scans."""
    log(f"Starting periodic catchup (every {config.catchup_interval}s)")

    while not shutdown_event.is_set():
        # Wait for interval or shutdown
        if shutdown_event.wait(timeout=config.catchup_interval):
            break

        if not shutdown_event.is_set():
            run_catchup_scan("periodic")


class WebhookHandler(BaseHTTPRequestHandler):
    """HTTP request handler for webhooks."""

    def log_message(self, format, *args):
        """Override to use our logger."""
        log_debug(f"HTTP: {format % args}")

    def send_json_response(self, status: int, data: dict):
        """Send a JSON response."""
        body = json.dumps(data).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', len(body))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        """Handle GET requests (health check)."""
        if self.path == '/health':
            self.send_json_response(200, {"status": "healthy"})
        else:
            self.send_json_response(404, {"error": "Not found"})

    def do_POST(self):
        """Handle POST requests (webhooks)."""
        if self.path != '/webhook':
            self.send_json_response(404, {"error": "Not found"})
            return

        # Read body
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length)

        # Verify signature
        signature = self.headers.get('X-Joan-Signature', '')
        if not verify_signature(body, signature):
            self.send_json_response(401, {"error": "Invalid signature"})
            return

        # Parse event
        event_type = self.headers.get('X-Joan-Event', '')
        log_debug(f"Received event: {event_type}")

        try:
            payload = json.loads(body.decode())
        except json.JSONDecodeError as e:
            log(f"Invalid JSON payload: {e}", "WARN")
            self.send_json_response(400, {"error": "Invalid JSON"})
            return

        task_id = payload.get('task_id', '')
        triggered_by = payload.get('triggered_by', 'user')

        # Extract tag name for tag events
        tag_name = ""
        if event_type in ('tag_added', 'tag_removed'):
            changes = payload.get('changes', [])
            if changes:
                tag_name = changes[0].get('new_value') or changes[0].get('old_value', '')

        if not task_id:
            log("No task_id in webhook payload", "WARN")
            self.send_json_response(400, {"error": "Missing task_id"})
            return

        # Log the event
        log(f"Webhook received: {event_type} task={task_id} tag={tag_name}")

        # Dispatch handler
        dispatch_handler(event_type, task_id, tag_name, triggered_by)

        # Send success response
        self.send_json_response(200, {"status": "received"})


def verify_ready():
    """Verify project is ready for webhook processing."""
    log("=== VERIFYING PROJECT STATE ===")

    if not config.config_file.exists():
        log(f"ERROR: .joan-agents.json not found at {config.config_file}", "ERROR")
        log("Run /agents:init first to configure the project.")
        sys.exit(1)

    try:
        with open(config.config_file) as f:
            project_config = json.load(f)
    except json.JSONDecodeError as e:
        log(f"ERROR: .joan-agents.json is not valid JSON: {e}", "ERROR")
        sys.exit(1)

    project_name = project_config.get('projectName', 'Unknown')

    log(f"Project: {project_name}")
    log("Config: Valid")
    log(f"Catchup interval: {config.catchup_interval}s")
    log("")


def shutdown_handler(signum, frame):
    """Handle shutdown signals."""
    log("Shutting down webhook server...")
    shutdown_event.set()

    # Kill catchup process if running
    global catchup_process
    if catchup_process is not None and catchup_process.poll() is None:
        log(f"Stopping catchup process (PID: {catchup_process.pid})")
        catchup_process.terminate()
        try:
            catchup_process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            catchup_process.kill()

    sys.exit(0)


def main():
    """Main entry point."""
    # Parse arguments
    config.parse_args(sys.argv[1:])

    # Set up signal handlers
    signal.signal(signal.SIGINT, shutdown_handler)
    signal.signal(signal.SIGTERM, shutdown_handler)

    # Verify project
    verify_ready()

    log("=== STARTING STATE-AWARE WEBHOOK SERVER ===")
    log("")

    # Run initial catchup scan
    log("Running startup catchup scan...")
    run_catchup_scan("startup")

    # Give startup scan a moment to begin
    time.sleep(2)

    # Start catchup loop in background
    global catchup_thread
    catchup_thread = threading.Thread(target=catchup_loop, daemon=True)
    catchup_thread.start()

    log("")
    log("=== LISTENING FOR WEBHOOKS ===")
    log(f"Webhooks: http://localhost:{config.port}/webhook")
    log(f"Health:   http://localhost:{config.port}/health")
    log("")
    log("State-aware mode active:")
    log(f"  - Startup scan: catches missed events")
    log(f"  - Periodic scan: every {config.catchup_interval}s")
    log(f"  - Webhook events: immediate response")
    log("")

    # Start HTTP server
    try:
        server = HTTPServer(('', config.port), WebhookHandler)
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        shutdown_event.set()
        log("Webhook server stopped")


if __name__ == '__main__':
    main()
