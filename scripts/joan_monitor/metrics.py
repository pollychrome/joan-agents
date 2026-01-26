"""
Throughput and cost computation for the Joan Monitor dashboard.

Phase 2: ThroughputMetrics - velocity, bottleneck, completion rates from logs.
Phase 4: CostMetrics - duration-based token cost estimation from worker sessions.
"""

import json
import re
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

from joan_monitor.constants import (
    COST_PER_MTOK,
    PIPELINE_STAGES,
    TOKENS_PER_MINUTE,
)


class ThroughputMetrics:
    """Compute velocity and bottleneck data from worker activity and metrics logs."""

    def __init__(self):
        self._stage_durations = defaultdict(list)  # stage -> [duration_seconds]
        self._completion_times = []  # [(timestamp, stage)]

    def parse_worker_activity_durations(self, worker_log: Path, since: datetime = None) -> dict:
        """Match START/COMPLETE pairs per stage, compute avg/min/max duration.

        Args:
            worker_log: Path to worker-activity.log
            since: If provided, only include events with timestamp >= since.

        Returns dict keyed by stage name with avg_seconds, min_seconds,
        max_seconds, count, and rate_per_hour.
        """
        if not worker_log.exists():
            return {}

        start_times = {}  # worker_type -> timestamp
        stage_durations = defaultdict(list)

        try:
            with open(worker_log, "r") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue

                    match = re.match(
                        r"\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\] \[(\w+)\] \[(\w+)\] (.+)",
                        line,
                    )
                    if not match:
                        continue

                    timestamp_str = match.group(1)
                    worker_type = match.group(2)
                    status = match.group(3)

                    try:
                        timestamp = datetime.strptime(
                            timestamp_str, "%Y-%m-%d %H:%M:%S"
                        )
                    except ValueError:
                        continue

                    # Filter by session start time if provided
                    if since and timestamp < since:
                        continue

                    if status == "START":
                        start_times[worker_type] = timestamp
                    elif status == "COMPLETE" and worker_type in start_times:
                        duration = (timestamp - start_times[worker_type]).total_seconds()
                        if duration > 0:
                            stage_durations[worker_type].append(duration)
                            self._completion_times.append((timestamp, worker_type))
                        del start_times[worker_type]
                    elif status == "FAIL" and worker_type in start_times:
                        del start_times[worker_type]

        except Exception:
            pass

        self._stage_durations = stage_durations
        return self._compute_stage_stats(stage_durations)

    def _compute_stage_stats(self, stage_durations: dict) -> dict:
        """Compute statistics per stage from duration lists."""
        result = {}
        now = datetime.now()

        for stage in PIPELINE_STAGES:
            # Map pipeline stage names to worker types
            worker_key = stage  # BA, Architect, Dev, Reviewer, Ops
            durations = stage_durations.get(worker_key, [])

            if not durations:
                result[stage] = {
                    "avg_seconds": 0,
                    "min_seconds": 0,
                    "max_seconds": 0,
                    "count": 0,
                    "rate_per_hour": 0,
                }
                continue

            avg_secs = sum(durations) / len(durations)
            result[stage] = {
                "avg_seconds": avg_secs,
                "min_seconds": min(durations),
                "max_seconds": max(durations),
                "count": len(durations),
                "rate_per_hour": self._compute_rate(worker_key),
            }

        return result

    def _compute_rate(self, worker_type: str) -> float:
        """Compute completions per hour for a worker type based on timestamps."""
        completions = [
            ts for ts, wt in self._completion_times if wt == worker_type
        ]
        if len(completions) < 2:
            return len(completions)  # 0 or 1

        # Use span between first and last completion
        span_hours = (completions[-1] - completions[0]).total_seconds() / 3600
        if span_hours > 0:
            return len(completions) / span_hours
        return float(len(completions))

    def parse_completion_rate(
        self, metrics_file: Path, window_hours: int = 24
    ) -> dict:
        """Count task_completed events and compute per-hour rates."""
        if not metrics_file.exists():
            return {"last_hour": 0, "last_24h": 0, "total": 0}

        now = datetime.now()
        one_hour_ago = now - timedelta(hours=1)
        window_start = now - timedelta(hours=window_hours)

        last_hour = 0
        in_window = 0
        total = 0

        try:
            with open(metrics_file, "r") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        event = json.loads(line)
                        if event.get("event") != "task_completed":
                            continue
                        total += 1

                        ts_str = event.get("timestamp", "")
                        if ts_str:
                            ts = datetime.fromisoformat(
                                ts_str.replace("Z", "+00:00")
                            )
                            if ts.tzinfo is not None:
                                ts = ts.replace(tzinfo=None)
                            if ts >= one_hour_ago:
                                last_hour += 1
                            if ts >= window_start:
                                in_window += 1
                    except (json.JSONDecodeError, ValueError):
                        continue
        except Exception:
            pass

        return {"last_hour": last_hour, "last_24h": in_window, "total": total}

    def identify_bottleneck(self, stage_durations: dict) -> str | None:
        """Return the stage with the longest average duration (the bottleneck)."""
        bottleneck = None
        max_avg = 0
        for stage, data in stage_durations.items():
            avg = data.get("avg_seconds", 0)
            count = data.get("count", 0)
            if avg > max_avg and count > 0:
                max_avg = avg
                bottleneck = stage
        return bottleneck

    def calculate_pipeline_velocity(self, stage_durations: dict) -> dict:
        """Sum of avg stage times gives end-to-end estimate."""
        total_avg = 0
        total_completed = float("inf")
        total_rate = 0

        for stage, data in stage_durations.items():
            avg = data.get("avg_seconds", 0)
            count = data.get("count", 0)
            rate = data.get("rate_per_hour", 0)
            if count > 0:
                total_avg += avg
                total_completed = min(total_completed, count)
            if rate > 0 and (total_rate == 0 or rate < total_rate):
                total_rate = rate  # Pipeline rate limited by slowest stage

        if total_completed == float("inf"):
            total_completed = 0

        return {
            "total_avg_seconds": total_avg,
            "total_completed": total_completed,
            "rate_per_hour": total_rate,
        }

    def compute_all(self, worker_log: Path, metrics_file: Path, since: datetime = None) -> dict:
        """Compute all throughput metrics. Main entry point.

        Args:
            since: If provided, only include data from after this timestamp.
        """
        stage_durations = self.parse_worker_activity_durations(worker_log, since=since)
        completion_rates = self.parse_completion_rate(metrics_file)
        bottleneck = self.identify_bottleneck(stage_durations)
        pipeline = self.calculate_pipeline_velocity(stage_durations)

        return {
            "stage_durations": stage_durations,
            "bottleneck": bottleneck,
            "pipeline": pipeline,
            "last_hour_completions": completion_rates["last_hour"],
            "last_24h_completions": completion_rates["last_24h"],
        }


class CostMetrics:
    """Duration-based cost estimation per worker from worker_session events."""

    def parse_worker_sessions(self, metrics_file: Path, since: datetime = None) -> list:
        """Read worker_session events from agent-metrics.jsonl.

        Args:
            since: If provided, only include sessions with timestamp >= since.
        """
        sessions = []
        if not metrics_file.exists():
            return sessions

        try:
            with open(metrics_file, "r") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        event = json.loads(line)
                        if event.get("event") != "worker_session":
                            continue

                        # Filter by session start time if provided
                        if since:
                            ts_str = event.get("timestamp", "")
                            if ts_str:
                                try:
                                    ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                                    ts_naive = ts.replace(tzinfo=None) if ts.tzinfo else ts
                                    since_naive = since.replace(tzinfo=None) if since.tzinfo else since
                                    if ts_naive < since_naive:
                                        continue
                                except Exception:
                                    pass

                        sessions.append(
                            {
                                "worker": event.get("worker", "unknown"),
                                "model": event.get("model", "opus"),
                                "task_id": event.get("task_id"),
                                "task_title": event.get("task_title"),
                                "success": event.get("success", True),
                                "duration_seconds": event.get("duration_seconds", 0),
                                "timestamp": event.get("timestamp"),
                            }
                        )
                    except json.JSONDecodeError:
                        continue
        except Exception:
            pass

        return sessions

    def estimate_session_cost(
        self, worker: str, model: str, duration_seconds: float
    ) -> float:
        """Estimate cost for a single session using duration * tokens-per-minute * cost-per-token."""
        minutes = duration_seconds / 60.0
        if minutes <= 0:
            return 0.0

        model_key = model.lower() if model else "opus"
        if model_key not in TOKENS_PER_MINUTE:
            model_key = "opus"

        input_tokens = TOKENS_PER_MINUTE[model_key]["input"] * minutes
        output_tokens = TOKENS_PER_MINUTE[model_key]["output"] * minutes

        input_cost = (input_tokens / 1_000_000) * COST_PER_MTOK[model_key]["input"]
        output_cost = (output_tokens / 1_000_000) * COST_PER_MTOK[model_key]["output"]

        return input_cost + output_cost

    def aggregate_costs(self, sessions: list) -> dict:
        """Aggregate costs by worker and model. Returns summary dict."""
        by_worker = defaultdict(
            lambda: {
                "model": None,
                "sessions": 0,
                "total_seconds": 0,
                "estimated_cost": 0.0,
            }
        )

        total_cost = 0.0
        total_seconds = 0

        for session in sessions:
            worker = session.get("worker", "unknown")
            model = session.get("model", "opus")
            duration = session.get("duration_seconds", 0)

            cost = self.estimate_session_cost(worker, model, duration)

            by_worker[worker]["model"] = model
            by_worker[worker]["sessions"] += 1
            by_worker[worker]["total_seconds"] += duration
            by_worker[worker]["estimated_cost"] += cost

            total_cost += cost
            total_seconds += duration

        return {
            "sessions": sessions,
            "by_worker": dict(by_worker),
            "total_cost": total_cost,
            "total_seconds": total_seconds,
        }

    def compute_all(self, metrics_file: Path, since: datetime = None) -> dict:
        """Compute all cost metrics. Main entry point.

        Args:
            since: If provided, only include data from after this timestamp.
        """
        sessions = self.parse_worker_sessions(metrics_file, since=since)
        if not sessions:
            return {"sessions": [], "by_worker": {}, "total_cost": 0, "total_seconds": 0}
        return self.aggregate_costs(sessions)
