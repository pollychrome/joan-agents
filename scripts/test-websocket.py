#!/usr/bin/env python3
"""
Simple WebSocket connectivity test for Joan Events API.

Usage:
    export JOAN_AUTH_TOKEN='your-jwt-token'
    python3 test-websocket.py <project_id>

To get a token:
    1. Log in to Joan web app
    2. Open browser DevTools > Application > Local Storage
    3. Copy the 'token' value
"""

import asyncio
import json
import sys
import os

try:
    import websockets
except ImportError:
    print("Error: websockets library not installed. Run: pip install websockets")
    sys.exit(1)


async def test_connection(project_id: str, token: str):
    """Test WebSocket connection to Joan."""
    api_url = os.environ.get('JOAN_API_URL', 'https://joan-api.alexbbenson.workers.dev')
    ws_url = api_url.replace('https://', 'wss://').replace('http://', 'ws://')
    ws_url = f"{ws_url}/api/v1/projects/{project_id}/events/ws?token={token}&projectId={project_id}"

    print(f"Connecting to Joan WebSocket...")
    print(f"Project ID: {project_id}")
    print(f"API URL: {api_url}")
    print()

    try:
        async with websockets.connect(
            ws_url,
            ping_interval=30,
            ping_timeout=10,
        ) as websocket:
            print("Connected! Waiting for events (Ctrl+C to exit)...")
            print("-" * 50)

            async for message in websocket:
                data = json.loads(message)
                msg_type = data.get('type', '')

                if msg_type == 'event':
                    payload = data.get('payload', {})
                    event_type = payload.get('event_type', '')
                    task_id = payload.get('task_id', '')

                    if event_type == 'connected':
                        print(f"[OK] WebSocket connection confirmed by server")
                    else:
                        print(f"[EVENT] {event_type} | task={task_id}")
                        if payload.get('changes'):
                            for change in payload['changes']:
                                print(f"        {change.get('field')}: {change.get('old_value')} -> {change.get('new_value')}")

                elif msg_type == 'heartbeat':
                    print(f"[HEARTBEAT] {data.get('timestamp', '')}")

                elif msg_type == 'error':
                    print(f"[ERROR] {data.get('message', 'Unknown error')}")

                else:
                    print(f"[{msg_type}] {json.dumps(data, indent=2)}")

    except websockets.exceptions.InvalidStatusCode as e:
        print(f"Connection failed: HTTP {e.status_code}")
        if e.status_code == 401:
            print("  -> Token is invalid or expired. Get a fresh token from Joan web app.")
        elif e.status_code == 403:
            print("  -> Access denied. Check project ID and permissions.")
        elif e.status_code == 426:
            print("  -> WebSocket upgrade failed. Server may not support WebSocket.")
    except Exception as e:
        print(f"Error: {e}")


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 test-websocket.py <project_id>")
        print("\nExample:")
        print("  export JOAN_AUTH_TOKEN='eyJhbGciOiJIUzI1NiIs...'")
        print("  python3 test-websocket.py 12345678-1234-1234-1234-123456789abc")
        sys.exit(1)

    project_id = sys.argv[1]
    token = os.environ.get('JOAN_AUTH_TOKEN', '')

    if not token:
        print("Error: JOAN_AUTH_TOKEN environment variable not set")
        print("\nTo get a token:")
        print("  1. Log in to Joan web app (joan.nintai.app)")
        print("  2. Open browser DevTools > Application > Local Storage")
        print("  3. Copy the 'token' value")
        print("  4. export JOAN_AUTH_TOKEN='<your-token>'")
        sys.exit(1)

    try:
        asyncio.run(test_connection(project_id, token))
    except KeyboardInterrupt:
        print("\n\nTest completed.")


if __name__ == '__main__':
    main()
