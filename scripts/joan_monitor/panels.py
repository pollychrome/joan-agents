"""
Panel and layout generation for the Joan Monitor dashboard.

All functions take explicit parameters (no class state) for testability.
Used by monitor.py to render Rich UI components.
"""

from datetime import datetime, timedelta
from pathlib import Path

from rich.layout import Layout
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich import box

from joan_monitor.constants import PIPELINE_STAGES


def format_duration(duration: timedelta) -> str:
    """Format duration as HH:MM:SS or MM:SS."""
    total_seconds = int(duration.total_seconds())
    if total_seconds < 0:
        return "00:00"
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60

    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    else:
        return f"{minutes:02d}:{seconds:02d}"


def generate_global_table(instances: dict) -> Table:
    """Generate the global status table."""
    table = Table(
        title="Joan Agents - Global Status",
        box=box.ROUNDED,
        show_header=True,
        header_style="bold cyan",
    )

    table.add_column("#", style="dim", width=3)
    table.add_column("Project", style="cyan", width=18)
    table.add_column("Mode", justify="center", width=7)
    table.add_column("Events", justify="right", width=7)
    table.add_column("Active", justify="center", width=6)
    table.add_column("Done", justify="right", width=5)
    table.add_column("\U0001fa7a", justify="right", width=4)  # Doctor
    table.add_column("\u21a9\ufe0f", justify="right", width=4)  # Reworks
    table.add_column("Runtime", justify="right", width=9)
    table.add_column("Status", width=20)

    now = datetime.now()
    for idx, (proj_name, info) in enumerate(sorted(instances.items()), 1):
        stats = info["stats"]
        metrics = info.get("metrics", {})
        mode = info.get("mode", "polling")

        # Format runtime
        if stats.get("started_at"):
            runtime = now - stats["started_at"]
            runtime_str = format_duration(runtime)
        else:
            runtime_str = "N/A"

        # Mode-specific display
        if mode == "webhook":
            mode_str = "[green]\u26a1[/green]"
            events_str = str(stats.get("events_received", 0))
            active_count = len(stats.get("active_workers", []))
            if active_count > 0:
                status = f"\U0001f504 {active_count} worker{'s' if active_count > 1 else ''}"
                status_style = "green"
            else:
                last_event = stats.get("last_event")
                if last_event:
                    elapsed = (now - last_event).total_seconds()
                    if elapsed < 60:
                        status = f"\U0001f4e1 Active ({int(elapsed)}s ago)"
                        status_style = "green"
                    elif elapsed < 300:
                        status = f"\U0001f4e1 Listening ({int(elapsed/60)}m)"
                        status_style = "cyan"
                    else:
                        status = f"\U0001f4e1 Idle ({int(elapsed/60)}m)"
                        status_style = "yellow"
                else:
                    status = "\U0001f4e1 Listening"
                    status_style = "cyan"
        else:
            mode_str = "[dim]\U0001f504[/dim]"
            events_str = str(stats.get("cycle", 0))
            active_count = len(stats.get("active_workers", []))
            if active_count > 0:
                status = f"\U0001f504 {active_count} worker{'s' if active_count > 1 else ''}"
                status_style = "green"
            elif stats.get("coordinator_in_progress"):
                started_at = stats.get("coordinator_started_at")
                if started_at:
                    elapsed = (now - started_at).total_seconds()
                    elapsed_str = f"{int(elapsed)}s"
                    status = f"\u2699\ufe0f Working ({elapsed_str})"
                else:
                    status = "\u2699\ufe0f Working"
                status_style = "green"
            elif stats.get("idle_count", 0) > 0:
                status = f"\U0001f4a4 Idle ({stats['idle_count']}/{stats.get('max_idle', 12)})"
                status_style = "yellow"
            else:
                status = "\u2713 Working"
                status_style = "green"

        doctor_count = metrics.get("doctor_invocations", 0)
        rework_count = metrics.get("reworks", 0)
        doctor_style = "red" if doctor_count >= 5 else "yellow" if doctor_count >= 2 else "dim"
        rework_style = "red" if rework_count >= 5 else "yellow" if rework_count >= 2 else "dim"

        table.add_row(
            str(idx),
            proj_name[:16] + ".." if len(proj_name) > 16 else proj_name,
            mode_str,
            events_str,
            str(active_count),
            str(max(stats.get("tasks_completed", 0), metrics.get("completions", 0))),
            f"[{doctor_style}]{doctor_count}[/{doctor_style}]",
            f"[{rework_style}]{rework_count}[/{rework_style}]",
            runtime_str,
            f"[{status_style}]{status}[/{status_style}]",
        )

    return table


def get_combined_recent_logs(instances: dict, lines: int = 8) -> Text:
    """Get recent log lines from all projects, interleaved by time."""
    import re

    all_logs = []
    for proj_name, info in instances.items():
        log_file = info["log_file"]
        if not log_file.exists():
            continue
        try:
            with open(log_file, "r") as f:
                recent_lines = f.readlines()[-20:]
            for line in recent_lines:
                # Handle both timestamp formats:
                # [2026-01-26 12:28:32] and [2026-01-26T12:28:32]
                ts_match = re.match(
                    r"\[(\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2})\]", line
                )
                if ts_match:
                    try:
                        ts_str = ts_match.group(1).replace(" ", "T")
                        timestamp = datetime.fromisoformat(ts_str)
                    except Exception:
                        continue
                    if any(
                        keyword in line
                        for keyword in [
                            "worker",
                            "Cycle",
                            "dispatched",
                            "Dispatching",
                            "completed",
                            "Idle",
                            "Starting",
                            "Shutdown",
                            "STARTUP",
                            "Smart event",
                            "Event received",
                        ]
                    ):
                        all_logs.append(
                            {
                                "timestamp": timestamp,
                                "project": proj_name,
                                "line": line.strip(),
                            }
                        )
        except Exception:
            pass

    all_logs.sort(key=lambda x: x["timestamp"])
    recent = all_logs[-lines:]

    text = Text()
    now = datetime.now()
    for entry in recent:
        elapsed = now - entry["timestamp"]
        elapsed_str = format_duration(elapsed)
        msg = entry["line"]
        if "[INFO]" in msg:
            msg = msg.split("[INFO]", 1)[1].strip()
        proj_short = entry["project"][:12]
        text.append(f"{elapsed_str:>8} ago ", style="dim")
        text.append(f"[{proj_short:12}] ", style="cyan")
        text.append(msg[:60] + "\n", style="white")

    if not recent:
        text.append("No recent activity", style="dim")

    return text


def generate_global_layout(instances: dict) -> Layout:
    """Generate Rich layout for live global view."""
    if not instances:
        return Panel(
            "[yellow]No running joan-agents instances found[/yellow]\n\n"
            "Start with:\n"
            "  [cyan]./scripts/webhook-receiver.sh --project-dir .[/cyan]  (webhook mode)\n"
            "  [cyan]/agents:dispatch --loop[/cyan]  (polling mode)",
            title="Joan Agents - Global Status",
        )

    layout = Layout()
    layout.split_column(
        Layout(name="header", size=3),
        Layout(name="table"),
        Layout(name="logs", size=12),
    )

    now = datetime.now()
    header_text = Text(
        f"Joan Agents - Global Status (Live)  {now.strftime('%H:%M:%S')}",
        style="bold cyan",
        justify="center",
    )
    layout["header"].update(Panel(header_text, border_style="cyan"))
    layout["table"].update(generate_global_table(instances))

    logs_text = get_combined_recent_logs(instances)
    layout["logs"].update(
        Panel(logs_text, title="Recent Activity (All Projects)", border_style="blue")
    )

    return layout


def generate_pipeline_visual(
    stats: dict,
    worker_activity: dict,
    blink_state: bool,
) -> Text:
    """Generate the pipeline visualization with blinking active stage."""
    text = Text()
    worker_activity = worker_activity or {}

    # Find active stage
    active_stage = None
    active_task = None
    last_progress = None
    doctor_active = False
    waiting_stages = {}

    if worker_activity.get("current_worker") and worker_activity.get("current_status") == "WORKING":
        worker_type = worker_activity["current_worker"]
        stage_map = {
            "BA": "BA", "Architect": "Architect", "Dev": "Dev",
            "Reviewer": "Reviewer", "Ops": "Ops",
        }
        if worker_type in stage_map:
            active_stage = stage_map[worker_type]
            active_task = worker_activity.get("current_task", "")
            last_progress = worker_activity.get("last_message", "")

    if not active_stage:
        for worker in stats.get("active_workers", []):
            worker_type = worker.get("type", "")
            stage_map = {
                "BA": "BA", "Architect": "Architect", "Dev": "Dev",
                "Reviewer": "Reviewer", "Ops": "Ops", "Doctor": None,
            }
            if worker_type == "Doctor":
                doctor_active = True
            elif worker_type in stage_map and stage_map[worker_type]:
                active_stage = stage_map[worker_type]
                active_task = worker.get("task", "")

    pipeline_state = stats.get("pipeline_state", {})

    if not active_stage and pipeline_state:
        waiting_stages = pipeline_state
        for stage in reversed(PIPELINE_STAGES):
            if stage in pipeline_state and pipeline_state[stage] > 0:
                active_stage = stage
                active_task = f"{pipeline_state[stage]} task(s) waiting"
                break

    stages_display = []
    has_active_worker = any(
        w.get("type") in ["BA", "Architect", "Dev", "Reviewer", "Ops"]
        for w in stats.get("active_workers", [])
    )

    for stage in PIPELINE_STAGES:
        is_active = stage == active_stage
        has_waiting = stage in waiting_stages and waiting_stages[stage] > 0

        if is_active and has_active_worker:
            if blink_state:
                style = "bold bright_green on green"
                icon = "\u25cf"
            else:
                style = "bold green"
                icon = "\u25cb"
        elif is_active or has_waiting:
            style = "bold yellow"
            icon = "\u25d0"
        else:
            style = "dim white"
            icon = "\u25cb"

        stages_display.append((stage, style, icon, is_active or has_waiting))

    # Top border
    text.append("  ")
    for i, (stage, style, icon, is_active) in enumerate(stages_display):
        width = max(len(stage) + 2, 8)
        text.append("\u250c" + "\u2500" * width + "\u2510", style if is_active else "dim")
        if i < len(stages_display) - 1:
            text.append("    ", "dim")
    text.append("\n")

    # Stage names with icons
    text.append("  ")
    for i, (stage, style, icon, is_active) in enumerate(stages_display):
        width = max(len(stage) + 2, 8)
        content = f"{icon} {stage}"
        padding = width - len(content)
        left_pad = padding // 2
        right_pad = padding - left_pad
        text.append("\u2502" + " " * left_pad + content + " " * right_pad + "\u2502", style)
        if i < len(stages_display) - 1:
            text.append("\u2500\u2500\u2500\u25b6", "cyan" if is_active else "dim")
    text.append("\n")

    # Bottom border
    text.append("  ")
    for i, (stage, style, icon, is_active) in enumerate(stages_display):
        width = max(len(stage) + 2, 8)
        text.append("\u2514" + "\u2500" * width + "\u2518", style if is_active else "dim")
        if i < len(stages_display) - 1:
            text.append("    ", "dim")
    text.append("\n")

    # Current task indicator
    is_actively_working = has_active_worker or (
        worker_activity.get("current_worker")
        and worker_activity.get("current_status") == "WORKING"
    )

    if active_stage and active_task:
        text.append("\n  ")
        task_display = active_task[:50] + "..." if len(active_task) > 50 else active_task
        if is_actively_working:
            text.append(f"  \u25b6 {active_stage}: ", "bold green")
            text.append(task_display, "white")
            if last_progress and last_progress != active_task:
                progress_display = last_progress[:60] + "..." if len(last_progress) > 60 else last_progress
                text.append("\n     ")
                text.append(f"\u2514\u2500 {progress_display}", "dim cyan")
            if worker_activity.get("last_update"):
                elapsed = datetime.now() - worker_activity["last_update"]
                elapsed_str = format_duration(elapsed)
                text.append(f" ({elapsed_str})", "dim")
        else:
            text.append(f"  \u25d0 {active_stage}: ", "bold yellow")
            text.append(task_display, "dim white")

    if doctor_active:
        text.append("\n\n  ")
        if blink_state:
            text.append("  \U0001f3e5 DOCTOR ", "bold bright_red on red")
        else:
            text.append("  \U0001f3e5 DOCTOR ", "bold red")
        text.append(" Diagnosing issues...", "red")

    # Pipeline blocked indicator from startup dispatch
    startup = stats.get("startup", {})
    if startup.get("pipeline_blocked") and not is_actively_working:
        text.append("\n\n  ")
        if blink_state:
            text.append("  \u26d4 BLOCKED ", "bold bright_yellow on red")
        else:
            text.append("  \u26d4 BLOCKED ", "bold yellow")
        reason = startup.get("pipeline_reason", "")
        if reason:
            text.append(f" {reason[:60]}", "yellow")

    # Startup dispatch summary when idle
    elif not is_actively_working and not active_stage and startup.get("dispatched", 0) > 0:
        text.append("\n\n  ")
        text.append(f"  Startup: {startup['dispatched']} dispatched", "dim green")
        if startup.get("pending_human", 0) > 0:
            text.append(f", {startup['pending_human']} awaiting human", "dim yellow")

    return text


def get_worker_progress_content(
    worker_log: Path,
    worker_type: str = None,
    max_lines: int = 15,
) -> Text:
    """Get formatted worker progress content for display when a worker is active."""
    import re

    text = Text()

    if not worker_log.exists():
        text.append("No worker activity log found\n", "dim")
        text.append(f"Expected: {worker_log}", "dim")
        return text

    try:
        with open(worker_log, "r") as f:
            lines = f.readlines()

        events = []
        now = datetime.now()

        for line in lines[-100:]:
            line = line.strip()
            if not line:
                continue

            # Handle both timestamp formats (brackets + T or space, no brackets)
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
                event_worker = match.group(2)
                status = match.group(3)
                message = match.group(4)

                if worker_type and event_worker != worker_type:
                    continue

                try:
                    timestamp = datetime.fromisoformat(timestamp_str.replace(" ", "T"))
                except Exception:
                    timestamp = now

                events.append(
                    {
                        "timestamp": timestamp,
                        "worker": event_worker,
                        "status": status,
                        "message": message,
                    }
                )

        recent_events = events[-max_lines:]

        if not recent_events:
            text.append("No recent worker activity", "dim")
            if worker_type:
                text.append(f"\n(Filtering for {worker_type} worker)", "dim")
            return text

        for event in recent_events:
            elapsed = now - event["timestamp"]
            elapsed_str = format_duration(elapsed)

            status_config = {
                "START": ("\u25b6", "bold green"),
                "PROGRESS": ("\u25c6", "cyan"),
                "COMPLETE": ("\u2713", "bold green"),
                "FAIL": ("\u2717", "bold red"),
            }
            icon, style = status_config.get(event["status"], ("\u2022", "white"))

            text.append(f"{elapsed_str:>8} ", "dim")
            text.append(f"{icon} ", style)

            if not worker_type:
                text.append(f"[{event['worker']:10}] ", "cyan")

            msg = event["message"]
            max_msg_len = 70 if worker_type else 55
            if len(msg) > max_msg_len:
                msg = msg[: max_msg_len - 3] + "..."
            text.append(f"{msg}\n", "white")

    except Exception as e:
        text.append(f"Error reading worker log: {e}", "red")

    return text


def show_metrics_panel(console, metrics: dict, now: datetime):
    """Display agent health metrics panel (static view)."""
    summary_table = Table(show_header=False, box=None, padding=(0, 2))
    summary_table.add_column("Metric", style="cyan")
    summary_table.add_column("Value")

    doctor_count = metrics.get("doctor_invocations", 0)
    doctor_fixes = metrics.get("doctor_fixes", 0)
    rework_count = metrics.get("reworks", 0)
    completions = metrics.get("completions", 0)
    failures = metrics.get("failures", 0)

    if completions > 0:
        rework_ratio = rework_count / completions
        if rework_ratio < 0.1:
            health = "[green]Excellent[/green]"
        elif rework_ratio < 0.25:
            health = "[yellow]Good[/yellow]"
        elif rework_ratio < 0.5:
            health = "[yellow]Needs Attention[/yellow]"
        else:
            health = "[red]Poor[/red]"
    else:
        health = "[dim]N/A[/dim]"

    summary_table.add_row("Agent Health", health)
    summary_table.add_row("Doctor Invocations", f"{doctor_count} ({doctor_fixes} fixes applied)")
    summary_table.add_row("Rework Requests", str(rework_count))
    summary_table.add_row("Tasks Completed", str(completions))
    summary_table.add_row("Impl. Failures", str(failures) if failures else "[dim]0[/dim]")

    console.print(Panel(summary_table, title="\U0001fa7a Agent Health Metrics", border_style="magenta"))
    console.print()

    workflow_issues = metrics.get("workflow_step_issues", {})
    if workflow_issues:
        issue_table = Table(show_header=True, box=box.SIMPLE)
        issue_table.add_column("Workflow Step", style="cyan")
        issue_table.add_column("Issues", justify="right", style="yellow")
        for step, count in sorted(workflow_issues.items(), key=lambda x: -x[1]):
            issue_table.add_row(step, str(count))
        console.print(Panel(issue_table, title="\U0001f4cd Issues by Workflow Step", border_style="blue"))
        console.print()

    recent_doctor = metrics.get("recent_doctor_events", [])
    if recent_doctor:
        doctor_table = Table(show_header=True, box=box.SIMPLE)
        doctor_table.add_column("When", style="dim", width=12)
        doctor_table.add_column("Trigger", style="cyan", width=15)
        doctor_table.add_column("Found", justify="right", width=6)
        doctor_table.add_column("Fixed", justify="right", width=6)
        doctor_table.add_column("Issues", width=40)

        for event in reversed(recent_doctor[-5:]):
            timestamp = event.get("timestamp")
            if timestamp:
                if timestamp.tzinfo is not None:
                    timestamp = timestamp.replace(tzinfo=None)
                elapsed = now - timestamp
                when = format_duration(elapsed) + " ago"
            else:
                when = "Unknown"

            issues = event.get("issues", [])
            if issues:
                issue_summary = ", ".join(
                    [f"{i.get('type', 'unknown')[:20]}" for i in issues[:2]]
                )
                if len(issues) > 2:
                    issue_summary += f" +{len(issues)-2} more"
            else:
                issue_summary = "-"

            doctor_table.add_row(
                when,
                event.get("trigger", "unknown")[:15],
                str(event.get("issues_found", 0)),
                str(event.get("fixes_applied", 0)),
                issue_summary[:40],
            )

        console.print(Panel(doctor_table, title="\U0001fa7a Recent Doctor Invocations", border_style="yellow"))
        console.print()

    recent_reworks = metrics.get("recent_reworks", [])
    if recent_reworks:
        rework_table = Table(show_header=True, box=box.SIMPLE)
        rework_table.add_column("When", style="dim", width=12)
        rework_table.add_column("Task", style="cyan", width=30)
        rework_table.add_column("Step", style="yellow", width=20)
        rework_table.add_column("Reason", width=25)

        for event in reversed(recent_reworks[-5:]):
            timestamp = event.get("timestamp")
            if timestamp:
                if timestamp.tzinfo is not None:
                    timestamp = timestamp.replace(tzinfo=None)
                elapsed = now - timestamp
                when = format_duration(elapsed) + " ago"
            else:
                when = "Unknown"

            rework_table.add_row(
                when,
                event.get("task_title", "Unknown")[:30],
                event.get("workflow_step", "Review\u2192Dev")[:20],
                event.get("reason", "-")[:25],
            )

        console.print(Panel(rework_table, title="\u21a9\ufe0f  Recent Rework Requests", border_style="red"))
        console.print()


# --- Phase 2: Throughput panel ---

def generate_throughput_panel(throughput_data: dict) -> Panel:
    """Generate throughput metrics panel for live view."""
    table = Table(show_header=True, box=box.SIMPLE, padding=(0, 1))
    table.add_column("Stage", style="cyan", width=12)
    table.add_column("Avg", justify="right", width=8)
    table.add_column("Count", justify="right", width=6)
    table.add_column("Rate", justify="right", width=8)

    stage_durations = throughput_data.get("stage_durations", {})
    bottleneck = throughput_data.get("bottleneck")

    for stage in PIPELINE_STAGES:
        data = stage_durations.get(stage, {})
        avg = data.get("avg_seconds", 0)
        count = data.get("count", 0)
        rate = data.get("rate_per_hour", 0)

        avg_str = format_duration(timedelta(seconds=avg)) if avg > 0 else "--:--"
        rate_str = f"{rate:.1f}/hr" if rate > 0 else "-"
        count_str = str(count) if count > 0 else "-"

        suffix = ""
        style = "white"
        if stage == bottleneck and count > 0:
            suffix = " \u2190 BOTTLENECK"
            style = "bold yellow"

        table.add_row(
            stage,
            avg_str,
            count_str,
            f"[{style}]{rate_str}{suffix}[/{style}]",
        )

    # Pipeline summary row
    pipeline = throughput_data.get("pipeline", {})
    total_avg = pipeline.get("total_avg_seconds", 0)
    total_done = pipeline.get("total_completed", 0)
    pipeline_rate = pipeline.get("rate_per_hour", 0)
    last_hour = throughput_data.get("last_hour_completions", 0)
    last_24h = throughput_data.get("last_24h_completions", 0)

    table.add_section()
    table.add_row(
        "[bold]Pipeline[/bold]",
        format_duration(timedelta(seconds=total_avg)) if total_avg > 0 else "--:--",
        f"{total_done} done",
        f"{pipeline_rate:.1f}/hr" if pipeline_rate > 0 else "-",
    )

    footer = Text()
    footer.append(f"\nLast hour: {last_hour} completed  ", "dim")
    footer.append(f"Last 24h: {last_24h} completed", "dim")

    from rich.console import Group
    return Panel(
        Group(table, footer),
        title="\U0001f4ca Throughput",
        border_style="blue",
    )


# --- Phase 3: Task detail panel ---

def generate_task_detail_panel(task_data: dict, terminal_width: int = 120) -> Panel:
    """Generate task detail panel showing tasks per Kanban column."""
    if not task_data or not task_data.get("columns"):
        return Panel(
            "[dim]Set JOAN_AUTH_TOKEN for task details[/dim]",
            title="\U0001f4cb Tasks",
            border_style="dim",
        )

    columns = task_data["columns"]
    tasks_by_column = task_data.get("tasks_by_column", {})
    now = datetime.now()

    text = Text()

    # Filter columns to show (skip Done unless narrow)
    show_columns = [c for c in columns if c["name"] != "Done"]
    done_col = next((c for c in columns if c["name"] == "Done"), None)

    for col in show_columns:
        col_name = col["name"]
        col_tasks = tasks_by_column.get(col.get("id", col_name), [])

        # Column header
        text.append(f" {col_name}", "bold cyan")
        text.append(f" ({len(col_tasks)})\n", "dim")

        if not col_tasks:
            text.append("  [empty]\n", "dim")
        else:
            for task in col_tasks[:5]:  # Show max 5 per column
                # Priority badge
                priority = task.get("priority", "none")
                priority_badges = {
                    "high": ("\u25b2", "red"),
                    "medium": ("\u25cf", "yellow"),
                    "low": ("\u25bc", "dim"),
                    "none": (" ", "white"),
                }
                icon, icon_style = priority_badges.get(priority, (" ", "white"))

                title = task.get("title", "Untitled")[:40]
                text.append("  ")
                text.append(icon, icon_style)
                text.append(f" {title}\n", "white")

                # Tags (only workflow-relevant ones)
                tags = task.get("tags", [])
                if tags:
                    tag_names = [t["name"] if isinstance(t, dict) else t for t in tags[:3]]
                    tag_str = " ".join(f"[{n}]" for n in tag_names)
                    text.append(f"      {tag_str}\n", "dim cyan")

            if len(col_tasks) > 5:
                text.append(f"    +{len(col_tasks) - 5} more\n", "dim")

        text.append("\n")

    # Done count
    if done_col:
        done_tasks = tasks_by_column.get(done_col.get("id", "Done"), [])
        text.append(f" Done: {len(done_tasks)} tasks\n", "dim green")

    return Panel(text, title="\U0001f4cb Tasks", border_style="blue")


# --- Phase 4: Cost estimation panel ---

def generate_cost_panel(cost_data: dict) -> Panel:
    """Generate token/cost estimation panel."""
    if not cost_data or not cost_data.get("sessions"):
        return Panel(
            "[dim]No worker sessions recorded yet[/dim]",
            title="\U0001f4b0 Cost Estimate",
            border_style="dim",
        )

    table = Table(show_header=True, box=box.SIMPLE, padding=(0, 1))
    table.add_column("Worker", style="cyan", width=12)
    table.add_column("Model", width=8)
    table.add_column("Sessions", justify="right", width=8)
    table.add_column("Time", justify="right", width=8)
    table.add_column("Est. Cost", justify="right", width=10)

    by_worker = cost_data.get("by_worker", {})
    for worker_name in PIPELINE_STAGES:
        wkey = worker_name.lower()
        data = by_worker.get(wkey, {})
        if not data:
            continue

        model = data.get("model", "?")
        sessions = data.get("sessions", 0)
        total_secs = data.get("total_seconds", 0)
        cost = data.get("estimated_cost", 0)

        table.add_row(
            worker_name,
            model,
            str(sessions),
            format_duration(timedelta(seconds=total_secs)),
            f"${cost:.2f}",
        )

    total_cost = cost_data.get("total_cost", 0)
    table.add_section()
    table.add_row(
        "[bold]Total[/bold]", "", "",
        format_duration(timedelta(seconds=cost_data.get("total_seconds", 0))),
        f"[bold]${total_cost:.2f}[/bold]",
    )

    footer = Text()
    footer.append("\nEstimates based on duration \u00d7 tokens-per-minute rates", "dim italic")

    from rich.console import Group
    return Panel(
        Group(table, footer),
        title="\U0001f4b0 Cost Estimate",
        border_style="yellow",
    )


# --- Project layout with all panels ---

def generate_project_layout(
    proj_name: str,
    info: dict,
    blink_state: bool,
    throughput_data: dict = None,
    task_data: dict = None,
    cost_data: dict = None,
    terminal_width: int = 120,
) -> Layout:
    """Generate Rich layout for live project view with all panels."""
    now = datetime.now()
    stats = info["stats"]
    metrics = info.get("metrics", {})
    worker_activity = info.get("worker_activity", {})

    narrow = terminal_width < 100
    wide = terminal_width > 160

    # Build layout structure
    layout = Layout()

    sections = [
        Layout(name="header", size=3),
        Layout(name="pipeline", size=9),
    ]

    # Task detail panel (Phase 3) - hide on narrow terminals
    if not narrow and task_data and task_data.get("columns"):
        sections.append(Layout(name="tasks", size=12))

    sections.append(Layout(name="middle", size=10))
    sections.append(Layout(name="workers", size=12))
    sections.append(Layout(name="logs"))

    layout.split_column(*sections)

    # Split middle into stats, metrics, and new panels side by side
    middle_panels = [
        Layout(name="stats"),
        Layout(name="metrics"),
    ]
    if throughput_data and throughput_data.get("stage_durations"):
        middle_panels.append(Layout(name="throughput"))
    if cost_data and cost_data.get("sessions"):
        middle_panels.append(Layout(name="cost"))

    layout["middle"].split_row(*middle_panels)

    # Header
    header_text = Text(
        f"Joan Agents - {proj_name}  {now.strftime('%H:%M:%S')}",
        style="bold cyan",
        justify="center",
    )
    layout["header"].update(Panel(header_text, border_style="cyan"))

    # Pipeline visualization
    pipeline_visual = generate_pipeline_visual(stats, worker_activity, blink_state)
    layout["pipeline"].update(
        Panel(pipeline_visual, title="\U0001f504 Pipeline Status", border_style="magenta")
    )

    # Task detail panel (Phase 3)
    if "tasks" in [s.name for s in layout.children if hasattr(s, "name")]:
        layout["tasks"].update(
            generate_task_detail_panel(task_data, terminal_width)
        )

    # Stats panel
    stats_table = Table(show_header=False, box=None, padding=(0, 1))
    stats_table.add_column("Key", style="cyan", width=18)
    stats_table.add_column("Value")

    mode = info.get("mode", "polling")
    if mode == "webhook":
        stats_table.add_row("Events", str(stats.get("events_received", 0)))
        stats_table.add_row("Handlers", str(stats.get("handlers_dispatched", 0)))
        if stats.get("last_event"):
            elapsed = (now - stats["last_event"]).total_seconds()
            stats_table.add_row("Last Event", f"{int(elapsed)}s ago")
    else:
        stats_table.add_row("Cycle", str(stats.get("cycle", 0)))
        stats_table.add_row("Idle", f"{stats.get('idle_count', 0)}/{stats.get('max_idle', 12)}")
        stats_table.add_row("Workers Dispatched", str(stats.get("workers_dispatched", 0)))
        if stats.get("last_poll"):
            elapsed = (now - stats["last_poll"]).total_seconds()
            stats_table.add_row("Last Poll", f"{int(elapsed)}s ago")

    tasks_completed = max(stats.get("tasks_completed", 0), metrics.get("completions", 0))
    stats_table.add_row("Tasks Completed", str(tasks_completed))

    if stats.get("started_at"):
        runtime = now - stats["started_at"]
        stats_table.add_row("Runtime", format_duration(runtime))

    # Startup dispatch info (websocket mode)
    startup = stats.get("startup", {})
    if startup.get("total_actionable", 0) > 0 or startup.get("dispatched", 0) > 0:
        stats_table.add_row(
            "Startup",
            f"{startup.get('dispatched', 0)} dispatched / {startup.get('total_actionable', 0)} actionable",
        )
    if startup.get("pipeline_blocked"):
        stats_table.add_row("Pipeline", "[yellow]BLOCKED[/yellow]")
    if startup.get("pending_human", 0) > 0:
        stats_table.add_row("Human Action", f"[yellow]{startup['pending_human']} pending[/yellow]")

    layout["stats"].update(Panel(stats_table, title="Stats", border_style="green"))

    # Metrics panel (Agent Health)
    metrics_table = Table(show_header=False, box=None, padding=(0, 1))
    metrics_table.add_column("Metric", style="cyan", width=18)
    metrics_table.add_column("Value")

    doctor_count = metrics.get("doctor_invocations", 0)
    doctor_fixes = metrics.get("doctor_fixes", 0)
    rework_count = metrics.get("reworks", 0)
    completions = metrics.get("completions", 0)
    failures = metrics.get("failures", 0)

    if completions > 0:
        rework_ratio = rework_count / completions
        if rework_ratio < 0.1:
            health = "[green]Excellent[/green]"
        elif rework_ratio < 0.25:
            health = "[yellow]Good[/yellow]"
        else:
            health = "[red]Needs Attention[/red]"
    else:
        health = "[dim]N/A[/dim]"

    metrics_table.add_row("Health", health)
    doctor_style = "red" if doctor_count >= 5 else "yellow" if doctor_count >= 2 else "white"
    metrics_table.add_row(
        "\U0001fa7a Doctor",
        f"[{doctor_style}]{doctor_count}[/{doctor_style}] ({doctor_fixes} fixes)",
    )
    rework_style = "red" if rework_count >= 5 else "yellow" if rework_count >= 2 else "white"
    metrics_table.add_row("\u21a9\ufe0f  Reworks", f"[{rework_style}]{rework_count}[/{rework_style}]")
    metrics_table.add_row(
        "\u274c Failures",
        f"[red]{failures}[/red]" if failures else "[dim]0[/dim]",
    )

    layout["metrics"].update(Panel(metrics_table, title="Agent Health", border_style="magenta"))

    # Throughput panel (Phase 2)
    if throughput_data and throughput_data.get("stage_durations"):
        layout["throughput"].update(generate_throughput_panel(throughput_data))

    # Cost panel (Phase 4)
    if cost_data and cost_data.get("sessions"):
        layout["cost"].update(generate_cost_panel(cost_data))

    # Workers panel
    workers_content = Text()
    has_worker_info = False

    if worker_activity.get("current_worker") and worker_activity.get("current_status") == "WORKING":
        has_worker_info = True
        wtype = worker_activity["current_worker"]
        task = worker_activity.get("current_task", "Unknown task")[:40]
        last_msg = worker_activity.get("last_message", "")[:50]

        if worker_activity.get("last_update"):
            elapsed = now - worker_activity["last_update"]
            elapsed_str = format_duration(elapsed)
        else:
            elapsed_str = "--:--"

        workers_content.append(f"\U0001f504 {wtype}", "bold green")
        workers_content.append(f"  {task}\n", "white")
        if last_msg and last_msg != task:
            workers_content.append(f"   \u2514\u2500 {last_msg}", "dim cyan")
            workers_content.append(f" ({elapsed_str} ago)\n", "dim")

        recent_events = worker_activity.get("recent_events", [])[-5:]
        if recent_events:
            workers_content.append("\nRecent Activity:\n", "dim")
            for event in reversed(recent_events):
                evt_elapsed = now - event["timestamp"]
                evt_time = format_duration(evt_elapsed)
                status_icon = {"START": "\u25b6", "PROGRESS": "\u25c6", "COMPLETE": "\u2713", "FAIL": "\u2717"}.get(event["status"], "\u2022")
                status_style = {"START": "green", "PROGRESS": "cyan", "COMPLETE": "green", "FAIL": "red"}.get(event["status"], "white")
                workers_content.append(f"  {evt_time:>8} ", "dim")
                workers_content.append(f"{status_icon} ", status_style)
                workers_content.append(f"[{event['worker']}] ", "cyan")
                workers_content.append(f"{event['message'][:35]}\n", "white")

    elif stats.get("active_workers"):
        has_worker_info = True
        for worker in stats["active_workers"]:
            duration = now - worker["started_at"]
            workers_content.append(f"\U0001f504 {worker['type']}", "bold yellow")
            workers_content.append(f"  {worker['task'][:40]}", "white")
            workers_content.append(f"  ({format_duration(duration)})\n", "dim")
        workers_content.append(
            "\nNote: No worker-activity.log - showing webhook log data", "dim"
        )

    if has_worker_info:
        layout["workers"].update(
            Panel(workers_content, title="Active Workers", border_style="yellow")
        )
    else:
        layout["workers"].update(
            Panel("No active workers", title="Active Workers", border_style="dim")
        )

    # Bottom panel: Worker Progress (when active) or Recent Logs (when idle)
    active_worker_type = None
    if worker_activity.get("current_worker") and worker_activity.get("current_status") == "WORKING":
        active_worker_type = worker_activity["current_worker"]
    elif stats.get("active_workers"):
        for w in stats["active_workers"]:
            if w.get("type") in ["BA", "Architect", "Dev", "Reviewer", "Ops"]:
                active_worker_type = w["type"]
                break

    if active_worker_type and info.get("worker_log"):
        progress_content = get_worker_progress_content(
            info["worker_log"],
            worker_type=active_worker_type,
            max_lines=15,
        )
        title = f"\U0001f4cb {active_worker_type} Worker Progress"
        layout["logs"].update(Panel(progress_content, title=title, border_style="green"))
    else:
        if info["log_file"].exists():
            try:
                with open(info["log_file"], "r") as f:
                    lines = f.readlines()
                recent = "".join(lines[-15:])
                layout["logs"].update(
                    Panel(Text(recent, style="dim"), title="Recent Logs", border_style="blue")
                )
            except Exception:
                layout["logs"].update(Panel("Error reading logs", border_style="red"))
        else:
            layout["logs"].update(
                Panel("No logs available", title="Recent Logs", border_style="dim")
            )

    return layout
