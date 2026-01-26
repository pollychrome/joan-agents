"""
Log file parsers for the Joan Monitor dashboard.

Extracts runtime statistics from scheduler logs, webhook receiver logs,
agent metrics files, and worker activity logs.
"""

import json
import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path


def parse_log_stats(log_file: Path) -> dict:
    """Parse scheduler/polling log file to extract runtime statistics."""
    if not log_file.exists():
        return {}

    stats = {
        "cycle": 0,
        "idle_count": 0,
        "max_idle": 12,
        "last_poll": None,
        "started_at": None,
        "active_workers": [],
        "tasks_completed": 0,
        "workers_dispatched": 0,
        "recent_events": [],
        "pipeline_state": {},
        "coordinator_in_progress": False,
        "coordinator_started_at": None,
    }

    try:
        with open(log_file, "r") as f:
            lines = f.readlines()

        # Find start time
        if lines:
            ts_match = re.match(
                r"\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\]", lines[0]
            )
            if ts_match:
                stats["started_at"] = datetime.strptime(
                    ts_match.group(1), "%Y-%m-%d %H:%M:%S"
                )

        # Track which workers have completed
        completed_workers = set()

        # Check coordinator running state from last 100 lines
        coordinator_last_started = None
        coordinator_last_completed = None
        for line in lines[-100:]:
            ts_match = re.match(
                r"\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\]", line
            )
            if ts_match:
                line_ts = datetime.strptime(
                    ts_match.group(1), "%Y-%m-%d %H:%M:%S"
                )
                if "Starting coordinator" in line:
                    coordinator_last_started = line_ts
                elif "Coordinator completed" in line:
                    coordinator_last_completed = line_ts

        if coordinator_last_started:
            if (
                coordinator_last_completed is None
                or coordinator_last_started > coordinator_last_completed
            ):
                stats["coordinator_in_progress"] = True
                stats["coordinator_started_at"] = coordinator_last_started

        # Parse from end for most recent info
        for line in reversed(lines[-200:]):
            ts_match = re.match(
                r"\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\]", line
            )
            timestamp = None
            if ts_match:
                timestamp = datetime.strptime(
                    ts_match.group(1), "%Y-%m-%d %H:%M:%S"
                )

            # Cycle number
            if "Cycle" in line and "starting" in line and stats["cycle"] == 0:
                match = re.search(r"Cycle (\d+)", line)
                if match:
                    stats["cycle"] = int(match.group(1))
                    if timestamp:
                        stats["last_poll"] = timestamp

            # Idle count
            if "idle count:" in line:
                match = re.search(r"idle count: (\d+)/(\d+)", line)
                if match:
                    stats["idle_count"] = int(match.group(1))
                    stats["max_idle"] = int(match.group(2))

            # Active workers - detect from dispatch events
            if "**" in line and "worker" in line.lower():
                match = re.search(
                    r"\*\*(\w+) worker (dispatched|claimed) for ['\"]([^'\"]+)['\"]\*\*",
                    line,
                )
                if match:
                    worker_type = match.group(1)
                    task_name = match.group(3)
                    if worker_type not in completed_workers and worker_type not in [
                        w["type"] for w in stats["active_workers"]
                    ]:
                        stats["active_workers"].append(
                            {
                                "type": worker_type,
                                "task": task_name,
                                "started_at": timestamp or datetime.now(),
                            }
                        )

            # Detect from "still running" diagnostic messages
            if (
                "still running" in line.lower()
                or "presumably still running" in line.lower()
            ):
                match = re.search(
                    r"(\w+) worker (?:that )?claimed", line, re.IGNORECASE
                )
                task_match = re.search(r"task #?(\d+)|['\"]([^'\"]+)['\"]", line)
                if match:
                    worker_type = match.group(1).capitalize()
                    task_name = ""
                    if task_match:
                        task_name = task_match.group(1) or task_match.group(2) or ""
                        if task_match.group(1):
                            task_name = f"Task #{task_name}"
                    if worker_type not in completed_workers and worker_type not in [
                        w["type"] for w in stats["active_workers"]
                    ]:
                        stats["active_workers"].append(
                            {
                                "type": worker_type,
                                "task": task_name,
                                "started_at": timestamp or datetime.now(),
                            }
                        )

            # Detect from "actively being implemented" messages
            if (
                "actively being implemented" in line.lower()
                or "is implementing" in line.lower()
            ):
                match = re.search(
                    r"by (Dev|BA|Architect|Reviewer|Ops)[-\s]?(\d)?",
                    line,
                    re.IGNORECASE,
                )
                task_match = re.search(r"['\"]([^'\"]+)['\"]|Task #?(\d+)", line)
                if match:
                    worker_type = match.group(1).capitalize()
                    task_name = ""
                    if task_match:
                        task_name = (
                            task_match.group(1)
                            or f"Task #{task_match.group(2)}"
                            or ""
                        )
                    if worker_type not in completed_workers and worker_type not in [
                        w["type"] for w in stats["active_workers"]
                    ]:
                        stats["active_workers"].append(
                            {
                                "type": worker_type,
                                "task": task_name,
                                "started_at": timestamp or datetime.now(),
                            }
                        )

            # Detect from "is claimed by Dev-N" pattern
            if "is claimed by" in line.lower():
                match = re.search(
                    r"is claimed by (Dev|BA|Architect|Reviewer|Ops)[-\s]?(\d)?",
                    line,
                    re.IGNORECASE,
                )
                task_match = re.search(
                    r"Task #?(\d+)\s*['\"]([^'\"]+)['\"]|['\"]([^'\"]+)['\"]", line
                )
                if match:
                    worker_type = match.group(1).capitalize()
                    task_name = ""
                    if task_match:
                        if task_match.group(1) and task_match.group(2):
                            task_name = (
                                f"#{task_match.group(1)} {task_match.group(2)}"
                            )
                        elif task_match.group(3):
                            task_name = task_match.group(3)
                    if worker_type not in completed_workers and worker_type not in [
                        w["type"] for w in stats["active_workers"]
                    ]:
                        stats["active_workers"].append(
                            {
                                "type": worker_type,
                                "task": task_name,
                                "started_at": timestamp or datetime.now(),
                            }
                        )

            # Completed workers
            if "**" in line and "completed" in line:
                match = re.search(r"\*\*(\w+) worker completed", line)
                if match:
                    stats["tasks_completed"] += 1
                    worker_type = match.group(1)
                    completed_workers.add(worker_type)
                    stats["active_workers"] = [
                        w
                        for w in stats["active_workers"]
                        if w["type"] != worker_type
                    ]

            # Dispatched count
            if "dispatched" in line.lower():
                match = re.search(
                    r"dispatched[:\s]+(\d+)\s+worker", line, re.IGNORECASE
                )
                if not match:
                    match = re.search(
                        r"dispatched\s+\*\*(\d+)\*\*\s+worker", line, re.IGNORECASE
                    )
                if match:
                    stats["workers_dispatched"] += int(match.group(1))

            # Pipeline state
            if (
                "in active development" in line.lower()
                or "in development" in line.lower()
            ):
                match = re.search(
                    r"(\d+)\s+(?:tasks?\s+)?in\s+(?:active\s+)?development",
                    line,
                    re.IGNORECASE,
                )
                if match and int(match.group(1)) > 0:
                    stats["pipeline_state"]["Dev"] = int(match.group(1))

            if "in review" in line.lower():
                match = re.search(
                    r"(\d+)\s+(?:tasks?\s+)?in\s+review", line, re.IGNORECASE
                )
                if match and int(match.group(1)) > 0:
                    stats["pipeline_state"]["Reviewer"] = int(match.group(1))

            if "in analyse" in line.lower() or "in analysis" in line.lower():
                match = re.search(
                    r"(\d+)\s+(?:tasks?\s+)?in\s+analy[sz]e?", line, re.IGNORECASE
                )
                if match and int(match.group(1)) > 0:
                    stats["pipeline_state"]["Architect"] = int(match.group(1))

            if "ready for ba" in line.lower() or "in to do" in line.lower():
                match = re.search(
                    r"(\d+)\s+(?:tasks?\s+)?(?:ready\s+for\s+ba|in\s+to\s+do)",
                    line,
                    re.IGNORECASE,
                )
                if match and int(match.group(1)) > 0:
                    stats["pipeline_state"]["BA"] = int(match.group(1))

            if "ready to deploy" in line.lower() or "in deploy" in line.lower():
                match = re.search(
                    r"(\d+)\s+(?:tasks?\s+)?(?:ready\s+to\s+deploy|in\s+deploy)",
                    line,
                    re.IGNORECASE,
                )
                if match and int(match.group(1)) > 0:
                    stats["pipeline_state"]["Ops"] = int(match.group(1))

    except Exception:
        pass

    return stats


def parse_webhook_log_stats(log_file: Path) -> dict:
    """Parse webhook/websocket receiver log file to extract runtime statistics."""
    if not log_file.exists():
        return {}

    stats = {
        "mode": "webhook",
        "started_at": None,
        "last_event": None,
        "events_received": 0,
        "handlers_dispatched": 0,
        "active_workers": [],
        "tasks_completed": 0,
        "recent_events": [],
        "handlers_by_type": {},
        "startup": {
            "total_actionable": 0,
            "recovery_issues": 0,
            "pending_human": 0,
            "pipeline_blocked": False,
            "pipeline_reason": "",
            "dispatched": 0,
        },
    }

    try:
        with open(log_file, "r") as f:
            lines = f.readlines()

        # Find start time
        if lines:
            ts_match = re.match(r"\[([^\]]+)\]", lines[0])
            if ts_match:
                try:
                    ts_str = ts_match.group(1)
                    ts_str = (
                        ts_str.replace("+00:00", "")
                        .replace("-05:00", "")
                        .replace("-04:00", "")
                    )
                    stats["started_at"] = datetime.fromisoformat(ts_str)
                except Exception:
                    pass

        # Parse lines for events
        for line in lines:
            ts_match = re.match(r"\[([^\]]+)\]", line)
            timestamp = None
            if ts_match:
                try:
                    ts_str = ts_match.group(1)
                    ts_str = (
                        ts_str.replace("+00:00", "")
                        .replace("-05:00", "")
                        .replace("-04:00", "")
                    )
                    timestamp = datetime.fromisoformat(ts_str)
                except Exception:
                    pass

            # Count received events
            if (
                "Received event:" in line
                or "Webhook received:" in line
                or "Event received:" in line
            ):
                stats["events_received"] += 1
                if timestamp:
                    stats["last_event"] = timestamp

            # Count dispatched handlers
            if "Dispatching:" in line:
                stats["handlers_dispatched"] += 1
                match = re.search(r"Dispatching: (handle-\w+)", line)
                if match:
                    handler_type = match.group(1).replace("handle-", "").capitalize()
                    stats["handlers_by_type"][handler_type] = (
                        stats["handlers_by_type"].get(handler_type, 0) + 1
                    )

            # Track completions
            if "completed" in line.lower() and (
                "worker" in line.lower() or "handler" in line.lower()
            ):
                stats["tasks_completed"] += 1

            # STARTUP dispatch messages — parse actionable-tasks API results
            if "STARTUP:" in line:
                startup_msg = line.split("STARTUP:", 1)[1].strip()

                # Summary: "3 actionable, 0 recovery issues, 1 pending human action"
                summary_match = re.search(
                    r"(\d+) actionable.*?(\d+) recovery issues.*?(\d+) pending human",
                    startup_msg,
                )
                if summary_match:
                    stats["startup"]["total_actionable"] = int(summary_match.group(1))
                    stats["startup"]["recovery_issues"] = int(summary_match.group(2))
                    stats["startup"]["pending_human"] = int(summary_match.group(3))

                # Pipeline blocked: "Pipeline BLOCKED: 'task name' - reason"
                if "Pipeline BLOCKED:" in startup_msg:
                    stats["startup"]["pipeline_blocked"] = True
                    reason_match = re.search(r"Pipeline BLOCKED:\s*(.+)", startup_msg)
                    if reason_match:
                        stats["startup"]["pipeline_reason"] = reason_match.group(1)

                # Dispatched count: "Dispatched 3 handler(s)"
                dispatched_match = re.search(r"Dispatched (\d+) handler", startup_msg)
                if dispatched_match:
                    stats["startup"]["dispatched"] = int(dispatched_match.group(1))

                # Individual handler dispatches count toward handlers_dispatched
                if "Dispatching" in startup_msg:
                    stats["handlers_dispatched"] += 1
                    handler_match = re.search(r"Dispatching (handle-\w+)", startup_msg)
                    if handler_match:
                        handler_type = handler_match.group(1).replace("handle-", "").capitalize()
                        stats["handlers_by_type"][handler_type] = (
                            stats["handlers_by_type"].get(handler_type, 0) + 1
                        )

            # Build recent events list
            if any(
                kw in line
                for kw in [
                    "Dispatching:",
                    "Received event:",
                    "Webhook received:",
                    "Event received:",
                    "Smart event:",
                    "completed",
                    "error",
                    "STARTUP:",
                    "Handler",
                ]
            ):
                if timestamp:
                    stats["recent_events"].append(
                        {"timestamp": timestamp, "line": line.strip()}
                    )

        stats["recent_events"] = stats["recent_events"][-20:]

    except Exception:
        pass

    return stats


def parse_metrics(metrics_file: Path) -> dict:
    """Parse agent-metrics.jsonl for Doctor invocations, reworks, and worker sessions."""
    if not metrics_file.exists():
        return {}

    metrics = {
        "doctor_invocations": 0,
        "doctor_fixes": 0,
        "reworks": 0,
        "completions": 0,
        "failures": 0,
        "recent_doctor_events": [],
        "recent_reworks": [],
        "workflow_step_issues": defaultdict(int),
        "worker_sessions": [],
    }

    try:
        with open(metrics_file, "r") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    event = json.loads(line)
                    event_type = event.get("event")
                    timestamp_str = event.get("timestamp", "")

                    timestamp = None
                    if timestamp_str:
                        try:
                            timestamp = datetime.fromisoformat(
                                timestamp_str.replace("Z", "+00:00")
                            )
                        except Exception:
                            pass

                    if event_type == "doctor_invocation":
                        metrics["doctor_invocations"] += 1
                        metrics["doctor_fixes"] += event.get("fixes_applied", 0)

                        for issue in event.get("issues", []):
                            step = issue.get("workflow_step", "Unknown")
                            metrics["workflow_step_issues"][step] += 1

                        metrics["recent_doctor_events"].append(
                            {
                                "timestamp": timestamp,
                                "trigger": event.get("trigger", "unknown"),
                                "issues_found": event.get("issues_found", 0),
                                "fixes_applied": event.get("fixes_applied", 0),
                                "mode": event.get("mode", "fix"),
                                "issues": event.get("issues", [])[:3],
                            }
                        )
                        metrics["recent_doctor_events"] = metrics[
                            "recent_doctor_events"
                        ][-5:]

                    elif event_type == "rework_requested":
                        metrics["reworks"] += 1
                        metrics["recent_reworks"].append(
                            {
                                "timestamp": timestamp,
                                "task_title": event.get("task_title", "Unknown"),
                                "workflow_step": event.get(
                                    "workflow_step", "Review\u2192Development"
                                ),
                                "reason": event.get("reason", "")[:100],
                            }
                        )
                        metrics["recent_reworks"] = metrics["recent_reworks"][-5:]

                    elif event_type == "task_completed":
                        metrics["completions"] += 1

                    elif event_type == "implementation_failed":
                        metrics["failures"] += 1

                    elif event_type == "worker_session":
                        metrics["worker_sessions"].append(
                            {
                                "timestamp": timestamp,
                                "worker": event.get("worker"),
                                "model": event.get("model"),
                                "task_id": event.get("task_id"),
                                "task_title": event.get("task_title"),
                                "success": event.get("success"),
                                "duration_seconds": event.get("duration_seconds", 0),
                            }
                        )

                except json.JSONDecodeError:
                    continue

    except Exception:
        pass

    return metrics


def parse_worker_activity(worker_log: Path) -> dict:
    """Parse worker-activity.log for real-time worker status."""
    if not worker_log.exists():
        return {}

    activity = {
        "current_worker": None,
        "current_task": None,
        "current_status": None,
        "last_message": None,
        "last_update": None,
        "recent_events": [],
    }

    try:
        with open(worker_log, "r") as f:
            lines = f.readlines()

        for line in lines[-50:]:
            line = line.strip()
            if not line:
                continue

            # Handle both timestamp formats:
            # [2026-01-26 12:28:32] [Dev] [PROGRESS] message  (brackets, space)
            # [2026-01-26T12:28:32] [Dev] [PROGRESS] message  (brackets, T-separator)
            # 2026-01-26 12:28:32 [Dev] [PROGRESS] message    (no brackets)
            match = re.match(
                r"\[(\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2})\] \[(\w+)\] \[(\w+)\] (.+)",
                line,
            )
            if not match:
                match = re.match(
                    r"(\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}) \[(\w+)\] \[(\w+)\] (.+)",
                    line,
                )
            if match:
                timestamp_str = match.group(1)
                worker_type = match.group(2)
                status = match.group(3)
                message = match.group(4)

                try:
                    # Handle both space and T separators
                    timestamp = datetime.fromisoformat(timestamp_str.replace(" ", "T"))
                except Exception:
                    timestamp = datetime.now()

                event = {
                    "timestamp": timestamp,
                    "worker": worker_type,
                    "status": status,
                    "message": message,
                }

                activity["recent_events"].append(event)

                if status == "START":
                    activity["current_worker"] = worker_type
                    activity["current_status"] = "WORKING"
                    activity["current_task"] = message
                    activity["last_update"] = timestamp
                    activity["last_message"] = message
                elif status == "PROGRESS":
                    activity["current_status"] = "WORKING"
                    activity["last_update"] = timestamp
                    activity["last_message"] = message
                elif status in ("COMPLETE", "FAIL"):
                    activity["current_worker"] = None
                    activity["current_status"] = status
                    activity["current_task"] = None
                    activity["last_update"] = timestamp
                    activity["last_message"] = f"{worker_type}: {message}"

        activity["recent_events"] = activity["recent_events"][-10:]

    except Exception:
        pass

    return activity
