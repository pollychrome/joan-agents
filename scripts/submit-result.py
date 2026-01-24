#!/usr/bin/env python3
"""
Submit Worker Result to Joan API

A helper script that handlers can call to submit their results to Joan.
Joan's result-processor then applies the appropriate state transitions.

Usage:
    submit-result.py <worker> <result_type> <success> [options]

Arguments:
    worker       - Worker name: ba-worker, architect-worker, dev-worker, reviewer-worker, ops-worker
    result_type  - Result type (e.g., requirements_complete, plan_created, implementation_complete)
    success      - true or false

Options:
    --project-id ID   - Project ID (default: from JOAN_PROJECT_ID env var)
    --task-id ID      - Task ID (default: from JOAN_TASK_ID env var)
    --output JSON     - JSON output object (optional)
    --comment TEXT    - ALS comment to add to task (optional)
    --error TEXT      - Error message if success=false (optional)

Environment variables:
    JOAN_API_URL      - Joan API URL
    JOAN_AUTH_TOKEN   - JWT auth token
    JOAN_PROJECT_ID   - Default project ID
    JOAN_TASK_ID      - Default task ID

Examples:
    # BA marks requirements complete
    submit-result.py ba-worker requirements_complete true --comment "ALS/1..."

    # Dev reports implementation complete with PR info
    submit-result.py dev-worker implementation_complete true \
        --output '{"pr_number": 42, "pr_url": "https://..."}' \
        --comment "ALS/1..."

    # Dev reports failure
    submit-result.py dev-worker implementation_failed false \
        --error "Build failed: missing dependency"
"""

import argparse
import json
import os
import sys
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError


def get_auth_token() -> str:
    """Get auth token from environment."""
    token = os.environ.get('JOAN_AUTH_TOKEN', '').strip()
    if not token:
        print("Error: JOAN_AUTH_TOKEN environment variable not set", file=sys.stderr)
        sys.exit(1)
    return token


def submit_result(
    api_url: str,
    project_id: str,
    task_id: str,
    worker: str,
    result_type: str,
    success: bool,
    output: dict = None,
    comment: str = None,
    error: str = None
):
    """Submit worker result to Joan API."""
    url = f"{api_url}/api/v1/projects/{project_id}/tasks/{task_id}/worker-result"

    payload = {
        "worker": worker,
        "success": success,
        "result_type": result_type,
    }

    if output:
        payload["output"] = output
    if comment:
        payload["comment"] = comment
    if error:
        payload["error"] = error

    token = get_auth_token()

    req = Request(
        url,
        data=json.dumps(payload).encode('utf-8'),
        headers={
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {token}',
        },
        method='POST'
    )

    try:
        with urlopen(req) as response:
            result = json.loads(response.read().decode('utf-8'))
            print(f"Result submitted successfully: {result.get('message', 'OK')}")
            if result.get('actions_applied'):
                print(f"Actions applied: {', '.join(result['actions_applied'])}")
            return True
    except HTTPError as e:
        error_body = e.read().decode('utf-8')
        try:
            error_json = json.loads(error_body)
            print(f"Error: {error_json.get('error', error_body)}", file=sys.stderr)
        except:
            print(f"Error: {e.code} {e.reason}: {error_body}", file=sys.stderr)
        return False
    except URLError as e:
        print(f"Network error: {e.reason}", file=sys.stderr)
        return False


def main():
    parser = argparse.ArgumentParser(
        description='Submit worker result to Joan API',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )

    parser.add_argument('worker', help='Worker name (ba-worker, architect-worker, dev-worker, reviewer-worker, ops-worker)')
    parser.add_argument('result_type', help='Result type (e.g., requirements_complete)')
    parser.add_argument('success', choices=['true', 'false'], help='Success status')

    parser.add_argument('--project-id', help='Project ID (default: JOAN_PROJECT_ID env var)')
    parser.add_argument('--task-id', help='Task ID (default: JOAN_TASK_ID env var)')
    parser.add_argument('--output', help='JSON output object')
    parser.add_argument('--comment', help='ALS comment to add')
    parser.add_argument('--error', help='Error message if success=false')
    parser.add_argument('--api-url', help='Joan API URL (default: JOAN_API_URL env var)')

    args = parser.parse_args()

    # Get required values
    api_url = args.api_url or os.environ.get('JOAN_API_URL', 'https://joan-api.alexbbenson.workers.dev')
    project_id = args.project_id or os.environ.get('JOAN_PROJECT_ID')
    task_id = args.task_id or os.environ.get('JOAN_TASK_ID')

    if not project_id:
        print("Error: Project ID required (--project-id or JOAN_PROJECT_ID env var)", file=sys.stderr)
        sys.exit(1)

    if not task_id:
        print("Error: Task ID required (--task-id or JOAN_TASK_ID env var)", file=sys.stderr)
        sys.exit(1)

    # Parse output JSON if provided
    output = None
    if args.output:
        try:
            output = json.loads(args.output)
        except json.JSONDecodeError as e:
            print(f"Error: Invalid JSON in --output: {e}", file=sys.stderr)
            sys.exit(1)

    # Submit result
    success = submit_result(
        api_url=api_url,
        project_id=project_id,
        task_id=task_id,
        worker=args.worker,
        result_type=args.result_type,
        success=args.success == 'true',
        output=output,
        comment=args.comment,
        error=args.error
    )

    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
