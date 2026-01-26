"""
Joan REST API client for fetching task data.

Uses urllib.request (no new dependencies). Implements caching to avoid
excessive API calls during live dashboard refresh.
"""

import json
import os
import time
import urllib.error
import urllib.request
from typing import Any

from joan_monitor.constants import DEFAULT_API_URL


class JoanAPIClient:
    """REST API client for Joan task and column data."""

    def __init__(self, api_url: str = None, auth_token: str = None):
        self._api_url = (
            api_url or os.environ.get("JOAN_API_URL", DEFAULT_API_URL)
        ).rstrip("/")
        self._auth_token = auth_token or os.environ.get("JOAN_AUTH_TOKEN")
        self._cache = {}  # key -> (data, timestamp)

    @property
    def available(self) -> bool:
        """Check if the API client has authentication configured."""
        return bool(self._auth_token)

    def _get_cached(self, key: str, max_age: float) -> Any | None:
        """Return cached data if still fresh, otherwise None."""
        if key in self._cache:
            data, ts = self._cache[key]
            if time.time() - ts < max_age:
                return data
        return None

    def _set_cache(self, key: str, data: Any):
        """Store data in cache with current timestamp."""
        self._cache[key] = (data, time.time())

    def _request(self, path: str) -> Any | None:
        """Make an authenticated GET request to the API."""
        if not self._auth_token:
            return None

        url = f"{self._api_url}{path}"
        headers = {
            "Authorization": f"Bearer {self._auth_token}",
            "Content-Type": "application/json",
        }

        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=10) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError, TimeoutError):
            return None

    def fetch_tasks(self, project_id: str) -> list | None:
        """Fetch tasks for a project. Cached for 30 seconds."""
        cache_key = f"tasks:{project_id}"
        cached = self._get_cached(cache_key, max_age=30)
        if cached is not None:
            return cached

        result = self._request(f"/api/v1/projects/{project_id}/tasks")
        if result is not None:
            # Handle both list response and {data: [...]} envelope
            tasks = result if isinstance(result, list) else result.get("data", result.get("tasks", []))
            self._set_cache(cache_key, tasks)
            return tasks
        return None

    def fetch_columns(self, project_id: str) -> list | None:
        """Fetch Kanban columns for a project. Cached for 60 seconds."""
        cache_key = f"columns:{project_id}"
        cached = self._get_cached(cache_key, max_age=60)
        if cached is not None:
            return cached

        result = self._request(f"/api/v1/projects/{project_id}/columns")
        if result is not None:
            columns = result if isinstance(result, list) else result.get("data", result.get("columns", []))
            self._set_cache(cache_key, columns)
            return columns
        return None

    def fetch_task_data(self, project_id: str) -> dict:
        """Fetch both tasks and columns, returning structured data for panel display.

        Returns dict with 'columns', 'tasks_by_column', or empty dict on failure.
        Gracefully degrades when auth token is not set.
        """
        if not self.available:
            return {}

        columns = self.fetch_columns(project_id)
        tasks = self.fetch_tasks(project_id)

        if columns is None or tasks is None:
            return {}

        # Group tasks by column
        tasks_by_column = {}
        for col in columns:
            col_id = col.get("id", col.get("name", ""))
            tasks_by_column[col_id] = []

        for task in tasks:
            col_id = task.get("column_id", task.get("column", {}).get("id", ""))
            if col_id in tasks_by_column:
                tasks_by_column[col_id].append(task)
            else:
                # Fallback: try to match by status
                for col in columns:
                    if col.get("default_status") == task.get("status"):
                        cid = col.get("id", col.get("name", ""))
                        if cid not in tasks_by_column:
                            tasks_by_column[cid] = []
                        tasks_by_column[cid].append(task)
                        break

        # Sort tasks by priority (high first)
        priority_order = {"high": 0, "medium": 1, "low": 2, "none": 3}
        for col_id in tasks_by_column:
            tasks_by_column[col_id].sort(
                key=lambda t: priority_order.get(t.get("priority", "none"), 3)
            )

        return {
            "columns": sorted(columns, key=lambda c: c.get("position", 0)),
            "tasks_by_column": tasks_by_column,
        }
