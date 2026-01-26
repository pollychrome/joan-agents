"""
JoanMonitor - Main orchestration for the Joan dashboard.

Handles process discovery, data refresh scheduling, and delegates
to parsers/panels for data extraction and rendering.
"""

import argparse
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

try:
    from rich.console import Console
    from rich.live import Live
    from rich.panel import Panel
    from rich.text import Text
    from rich import box
except ImportError:
    print("Error: Rich library not installed")
    print("Install with: python3 -m pip install --user --break-system-packages rich")
    sys.exit(1)

from joan_monitor.constants import REFRESH_INTERVALS
from joan_monitor.parsers import (
    parse_log_stats,
    parse_metrics,
    parse_webhook_log_stats,
    parse_worker_activity,
)
from joan_monitor.panels import (
    format_duration,
    generate_global_layout,
    generate_global_table,
    generate_project_layout,
    get_combined_recent_logs,
    show_metrics_panel,
)
from joan_monitor.metrics import CostMetrics, ThroughputMetrics
from joan_monitor.api import JoanAPIClient
from joan_monitor.effects import EffectManager


class RefreshThrottler:
    """Tracks last refresh time per data source for tiered refresh rates."""

    def __init__(self):
        self._last_refresh = {}  # source_name -> monotonic timestamp

    def should_refresh(self, source: str) -> bool:
        """Check if a data source should be refreshed based on its interval."""
        interval = REFRESH_INTERVALS.get(source, 5)
        now = time.monotonic()
        last = self._last_refresh.get(source, 0)
        if now - last >= interval:
            self._last_refresh[source] = now
            return True
        return False

    def mark_refreshed(self, source: str):
        """Explicitly mark a source as just refreshed."""
        self._last_refresh[source] = time.monotonic()


class JoanMonitor:
    """Global monitor for all running joan-agents instances."""

    def __init__(self):
        self.console = Console()
        self.instances = {}
        self.blink_state = False
        self._throttler = RefreshThrottler()
        self._throughput = ThroughputMetrics()
        self._cost = CostMetrics()
        self._api = JoanAPIClient()
        self._effects = EffectManager(self.console)

        # Cached data for tiered refresh
        self._throughput_data = {}
        self._task_data = {}
        self._cost_data = {}

    def discover_instances(self):
        """Find all running joan-agents processes."""
        self.instances = {}

        try:
            result = subprocess.run(
                ["ps", "aux"],
                capture_output=True,
                text=True,
                check=True,
            )

            for line in result.stdout.splitlines():
                is_python_webhook = (
                    "webhook-server.py" in line and "grep" not in line
                )
                is_bash_webhook = (
                    "webhook-receiver.sh" in line and "grep" not in line
                )
                is_ws_client = "ws-client.py" in line and "grep" not in line
                is_scheduler = "joan-scheduler.sh" in line and "grep" not in line

                is_webhook = is_python_webhook or is_bash_webhook or is_ws_client

                if is_webhook or is_scheduler:
                    pid_match = re.match(r"\S+\s+(\d+)", line)
                    if is_webhook:
                        path_match = re.search(
                            r"--project-dir[=\s]+([^\s]+)", line
                        )
                    else:
                        path_match = re.search(
                            r"joan-scheduler\.sh\s+([^\s]+)", line
                        )

                    if path_match and pid_match:
                        raw_path = path_match.group(1)
                        pid = pid_match.group(1)

                        if not raw_path.startswith("/"):
                            try:
                                lsof_result = subprocess.run(
                                    ["lsof", "-p", pid],
                                    capture_output=True,
                                    text=True,
                                    timeout=5,
                                )
                                for lsof_line in lsof_result.stdout.splitlines():
                                    if "\tcwd\t" in lsof_line or " cwd " in lsof_line:
                                        parts = lsof_line.split()
                                        if len(parts) >= 9:
                                            process_cwd = parts[-1]
                                            project_dir = (
                                                Path(process_cwd) / raw_path
                                            )
                                            project_dir = project_dir.resolve()
                                            break
                                else:
                                    project_dir = Path(raw_path).resolve()
                            except (subprocess.TimeoutExpired, Exception):
                                project_dir = Path(raw_path).resolve()
                        else:
                            project_dir = Path(raw_path).resolve()

                        if project_dir.exists():
                            self._add_instance(
                                project_dir,
                                line,
                                is_webhook=is_webhook,
                                is_ws_client=is_ws_client,
                            )

        except subprocess.CalledProcessError:
            pass

    def _add_instance(
        self,
        project_dir: Path,
        ps_line: str,
        is_webhook: bool = False,
        is_ws_client: bool = False,
    ):
        """Add a discovered instance to the tracking dict."""
        config_file = project_dir / ".joan-agents.json"
        if not config_file.exists():
            return

        try:
            with open(config_file) as f:
                config = json.load(f)
        except Exception:
            return

        project_name = config.get("projectName", project_dir.name)

        if is_ws_client:
            log_file = project_dir / ".claude/logs/websocket-client.log"
        elif is_webhook:
            log_file = project_dir / ".claude/logs/webhook-receiver.log"
        else:
            log_file = project_dir / ".claude/logs/scheduler.log"

        if is_webhook:
            stats = parse_webhook_log_stats(log_file) if log_file.exists() else {}
        else:
            stats = parse_log_stats(log_file) if log_file.exists() else {}

        metrics_file = project_dir / ".claude/logs/agent-metrics.jsonl"
        metrics = parse_metrics(metrics_file) if metrics_file.exists() else {}

        worker_log = project_dir / ".claude/logs/worker-activity.log"
        worker_activity = (
            parse_worker_activity(worker_log) if worker_log.exists() else {}
        )

        pid_match = re.match(r"\S+\s+(\d+)", ps_line)
        pid = pid_match.group(1) if pid_match else "unknown"

        self.instances[project_name] = {
            "project_dir": project_dir,
            "config": config,
            "log_file": log_file,
            "metrics_file": metrics_file,
            "worker_log": worker_log,
            "pid": pid,
            "stats": stats,
            "metrics": metrics,
            "worker_activity": worker_activity,
            "mode": "webhook" if is_webhook else "polling",
        }

    # --- Public view methods ---

    def show_global_view(self, live_mode: bool = False):
        """Display global view of all running instances."""
        if live_mode:
            try:
                with Live(
                    generate_global_layout(self.instances),
                    refresh_per_second=2,
                    console=self.console,
                ) as live:
                    while True:
                        self.discover_instances()
                        live.update(generate_global_layout(self.instances))
                        time.sleep(0.5)
            except KeyboardInterrupt:
                self.console.print("\n[yellow]Stopped monitoring[/yellow]\n")
            return

        # Static view
        self.discover_instances()

        if not self.instances:
            self.console.print(
                "\n[yellow]No running joan-agents instances found[/yellow]"
            )
            self.console.print("\nStart agents with:")
            self.console.print(
                "  [cyan]./scripts/webhook-receiver.sh --project-dir .[/cyan]  (webhook mode - recommended)"
            )
            self.console.print(
                "  [cyan]/agents:dispatch --loop[/cyan]  (polling mode - legacy)\n"
            )
            return

        self.console.print()
        self.console.print(generate_global_table(self.instances))
        self.console.print()
        self.console.print(
            "[dim]Run [cyan]joan status <project> -f[/cyan] for live view[/dim]"
        )
        self.console.print(
            "[dim]Run [cyan]joan status -f[/cyan] for live global view[/dim]"
        )
        self.console.print(
            "[dim]Run [cyan]joan logs <project>[/cyan] to tail logs[/dim]\n"
        )

    def show_project_view(self, project_name: str, follow: bool = False):
        """Display detailed view for a specific project."""
        self.discover_instances()

        matches = [
            (name, info)
            for name, info in self.instances.items()
            if project_name.lower() in name.lower()
        ]

        if not matches:
            self.console.print(
                f"\n[red]No running instance found for '{project_name}'[/red]\n"
            )
            return

        if len(matches) > 1:
            self.console.print("\n[yellow]Multiple matches found:[/yellow]")
            for name, _ in matches:
                self.console.print(f"  - {name}")
            self.console.print("\n[dim]Be more specific[/dim]\n")
            return

        proj_name, info = matches[0]

        if follow:
            self._show_live_project_view(proj_name, info)
        else:
            self._show_static_project_view(proj_name, info)

    def _show_static_project_view(self, proj_name: str, info: dict):
        """Show a static snapshot of project details."""
        stats = info["stats"]
        config = info["config"]
        mode = info.get("mode", "polling")
        now = datetime.now()

        self.console.print()
        mode_icon = "\u26a1" if mode == "webhook" else "\U0001f504"
        self.console.rule(
            f"[bold cyan]{proj_name}[/bold cyan] {mode_icon}", style="cyan"
        )
        self.console.print()

        # Config info
        from rich.table import Table

        config_table = Table(show_header=False, box=None, padding=(0, 2))
        config_table.add_column("Key", style="cyan")
        config_table.add_column("Value")

        config_table.add_row("Project Directory", str(info["project_dir"]))
        config_table.add_row("PID", info["pid"])
        config_table.add_row(
            "Dispatch Mode",
            "[green]Webhook (event-driven)[/green]"
            if mode == "webhook"
            else "[dim]Polling (legacy)[/dim]",
        )

        # Model display - show per-worker models if configured
        settings = config.get("settings", {})
        models = settings.get("models", {})
        if models:
            model_parts = [f"{k}: {v}" for k, v in models.items()]
            config_table.add_row("Models", ", ".join(model_parts))
        else:
            config_table.add_row("Model", settings.get("model", "N/A"))

        config_table.add_row(
            "Workflow Mode", settings.get("mode", "standard")
        )
        if mode == "polling":
            config_table.add_row(
                "Poll Interval",
                f"{settings.get('pollingIntervalMinutes', 1)} min",
            )

        self.console.print(
            Panel(config_table, title="Configuration", border_style="blue")
        )
        self.console.print()

        # Runtime stats
        stats_table = Table(show_header=False, box=None, padding=(0, 2))
        stats_table.add_column("Metric", style="cyan")
        stats_table.add_column("Value")

        if stats.get("started_at"):
            runtime = now - stats["started_at"]
            stats_table.add_row("Runtime", format_duration(runtime))
            stats_table.add_row(
                "Started", stats["started_at"].strftime("%Y-%m-%d %H:%M:%S")
            )
        else:
            stats_table.add_row("Runtime", "N/A")

        if mode == "webhook":
            stats_table.add_row(
                "Events Received", str(stats.get("events_received", 0))
            )
            stats_table.add_row(
                "Handlers Dispatched",
                str(stats.get("handlers_dispatched", 0)),
            )
            handlers_by_type = stats.get("handlers_by_type", {})
            if handlers_by_type:
                breakdown = ", ".join(
                    [f"{k}: {v}" for k, v in handlers_by_type.items()]
                )
                stats_table.add_row("Handler Breakdown", breakdown)
            if stats.get("last_event"):
                elapsed = (now - stats["last_event"]).total_seconds()
                if elapsed < 60:
                    last_event_str = f"{int(elapsed)}s ago"
                else:
                    last_event_str = f"{int(elapsed / 60)}m ago"
                stats_table.add_row("Last Event", last_event_str)
        else:
            stats_table.add_row("Current Cycle", str(stats.get("cycle", 0)))
            stats_table.add_row(
                "Idle Count",
                f"{stats.get('idle_count', 0)}/{stats.get('max_idle', 12)}",
            )
            stats_table.add_row(
                "Workers Dispatched",
                str(stats.get("workers_dispatched", 0)),
            )
            if stats.get("last_poll"):
                elapsed = (now - stats["last_poll"]).total_seconds()
                stats_table.add_row("Last Poll", f"{int(elapsed)}s ago")

        stats_table.add_row(
            "Tasks Completed", str(stats.get("tasks_completed", 0))
        )

        self.console.print(
            Panel(stats_table, title="Runtime Statistics", border_style="green")
        )
        self.console.print()

        # Catchup scan info (webhook mode)
        catchup = stats.get("catchup", {})
        last_scan = catchup.get("last_scan") or {}
        if catchup.get("in_progress") or last_scan:
            from joan_monitor.constants import PIPELINE_STAGES

            scan_table = Table(show_header=False, box=None, padding=(0, 2))
            scan_table.add_column("Key", style="cyan")
            scan_table.add_column("Value")

            if catchup.get("in_progress"):
                scan_start = catchup.get("started_at")
                if scan_start:
                    elapsed = int((now - scan_start).total_seconds())
                    scan_table.add_row("Status", f"[bold cyan]Scanning ({elapsed}s)[/bold cyan]")
                else:
                    scan_table.add_row("Status", "[bold cyan]Scanning[/bold cyan]")
            elif catchup.get("last_completed_at"):
                elapsed = int((now - catchup["last_completed_at"]).total_seconds())
                if elapsed < 60:
                    scan_table.add_row("Last Scan", f"{elapsed}s ago")
                else:
                    scan_table.add_row("Last Scan", f"{int(elapsed / 60)}m ago")

            if last_scan.get("tasks_scanned"):
                scan_table.add_row("Tasks Scanned", str(last_scan["tasks_scanned"]))

            scan_queues = last_scan.get("queues", {})
            if scan_queues:
                active_queues = [
                    f"{s}: {scan_queues[s]}" for s in PIPELINE_STAGES if scan_queues.get(s, 0) > 0
                ]
                if active_queues:
                    scan_table.add_row("Active Queues", ", ".join(active_queues))
                else:
                    scan_table.add_row("Active Queues", "[dim]All empty[/dim]")

            gate = last_scan.get("pipeline_gate", "")
            if gate:
                gate_style = "yellow" if gate == "BLOCKED" else "green"
                scan_table.add_row("Pipeline Gate", f"[{gate_style}]{gate}[/{gate_style}]")

            dispatched = last_scan.get("dispatched", 0)
            if dispatched:
                scan_table.add_row("Workers Dispatched", str(dispatched))

            pending = last_scan.get("pending_human", 0)
            if pending:
                scan_table.add_row("Awaiting Human", f"[yellow]{pending}[/yellow]")

            healing = last_scan.get("self_healing", {})
            issues = sum(healing.values()) if healing else 0
            if issues > 0:
                scan_table.add_row("Self-Healing", f"[yellow]{issues} issues found[/yellow]")

            self.console.print(
                Panel(scan_table, title="\U0001f50d Catchup Scan", border_style="cyan")
            )
            self.console.print()

        # Active workers
        if stats.get("active_workers"):
            workers_table = Table(show_header=True, box=box.ROUNDED)
            workers_table.add_column("Worker", style="cyan")
            workers_table.add_column("Task", style="white")
            workers_table.add_column("Duration", style="yellow")

            for worker in stats["active_workers"]:
                duration = now - worker["started_at"]
                workers_table.add_row(
                    worker["type"],
                    worker["task"],
                    format_duration(duration),
                )

            self.console.print(
                Panel(
                    workers_table,
                    title="Active Workers",
                    border_style="yellow",
                )
            )
            self.console.print()

        # Agent Health Metrics
        metrics = info.get("metrics", {})
        if metrics:
            show_metrics_panel(self.console, metrics, now)

        # Throughput metrics (Phase 2)
        worker_log = info.get("worker_log")
        metrics_file = info.get("metrics_file")
        if worker_log and worker_log.exists():
            tp = ThroughputMetrics()
            throughput_data = tp.compute_all(worker_log, metrics_file)
            if throughput_data.get("stage_durations"):
                has_data = any(
                    d.get("count", 0) > 0
                    for d in throughput_data["stage_durations"].values()
                )
                if has_data:
                    from joan_monitor.panels import generate_throughput_panel
                    self.console.print(generate_throughput_panel(throughput_data))
                    self.console.print()

        # Cost metrics (Phase 4)
        if metrics_file and metrics_file.exists():
            cm = CostMetrics()
            cost_data = cm.compute_all(metrics_file)
            if cost_data.get("sessions"):
                from joan_monitor.panels import generate_cost_panel
                self.console.print(generate_cost_panel(cost_data))
                self.console.print()

        # Task detail (Phase 3)
        project_id = config.get("projectId")
        if project_id and self._api.available:
            task_data = self._api.fetch_task_data(project_id)
            if task_data.get("columns"):
                from joan_monitor.panels import generate_task_detail_panel
                self.console.print(generate_task_detail_panel(task_data))
                self.console.print()

        # Log file location
        self.console.print(f"[dim]Log file: {info['log_file']}[/dim]")
        self.console.print(
            f"[dim]Metrics file: {info.get('metrics_file', 'N/A')}[/dim]"
        )
        self.console.print(
            f"[dim]Tail logs: [cyan]joan logs {proj_name}[/cyan][/dim]\n"
        )

    def _show_live_project_view(self, proj_name: str, info: dict):
        """Show live-updating project view with effects and tiered refresh."""
        terminal_width = self.console.width

        # Refresh all data once upfront
        self._refresh_slow_data(info)

        # Play startup banner (Phase 5)
        self._effects.play_startup_banner()

        try:
            live = Live(
                self._build_project_layout(proj_name, info, terminal_width),
                refresh_per_second=1,
                console=self.console,
            )
            live.start()

            try:
                while True:
                    # Tiered refresh
                    if self._throttler.should_refresh("process_discovery"):
                        self.discover_instances()
                        if proj_name not in self.instances:
                            self.console.print(
                                "\n[yellow]Instance stopped[/yellow]\n"
                            )
                            break
                        info = self.instances[proj_name]

                    if self._throttler.should_refresh("log_parsing"):
                        # Re-parse logs (parsers already called in discover_instances
                        # when process_discovery fires, so this is for intermediate updates)
                        self._refresh_logs(info)

                    if self._throttler.should_refresh("throughput_metrics"):
                        self._refresh_throughput(info)

                    if self._throttler.should_refresh("cost_metrics"):
                        self._refresh_cost(info)

                    if self._throttler.should_refresh("joan_api"):
                        self._refresh_task_data(info)

                    # Toggle blink state
                    self.blink_state = not self.blink_state

                    # Detect events (Phase 5)
                    if self._throttler.should_refresh("event_detection"):
                        metrics = info.get("metrics", {})
                        activity = info.get("worker_activity", {})
                        events = self._effects.detect_events(metrics, activity)
                        if events:
                            # Stop live, play effects, restart
                            live.stop()
                            self._effects.play_events(events)
                            live.start()

                    # Update terminal width
                    terminal_width = self.console.width

                    # Update display
                    live.update(
                        self._build_project_layout(
                            proj_name, info, terminal_width
                        )
                    )
                    time.sleep(1)

            finally:
                live.stop()

        except KeyboardInterrupt:
            self.console.print("\n[yellow]Stopped monitoring[/yellow]\n")

    def _build_project_layout(
        self, proj_name: str, info: dict, terminal_width: int
    ):
        """Build the project layout with all panels."""
        return generate_project_layout(
            proj_name=proj_name,
            info=info,
            blink_state=self.blink_state,
            throughput_data=self._throughput_data,
            task_data=self._task_data,
            cost_data=self._cost_data,
            terminal_width=terminal_width,
        )

    def _refresh_slow_data(self, info: dict):
        """Refresh all slow data sources (called once at startup)."""
        self._refresh_throughput(info)
        self._refresh_cost(info)
        self._refresh_task_data(info)

    def _refresh_logs(self, info: dict):
        """Re-parse log files for updated stats."""
        log_file = info.get("log_file")
        if log_file and log_file.exists():
            mode = info.get("mode", "polling")
            if mode == "webhook":
                info["stats"] = parse_webhook_log_stats(log_file)
            else:
                info["stats"] = parse_log_stats(log_file)

        metrics_file = info.get("metrics_file")
        if metrics_file and metrics_file.exists():
            info["metrics"] = parse_metrics(metrics_file)

        worker_log = info.get("worker_log")
        if worker_log and worker_log.exists():
            info["worker_activity"] = parse_worker_activity(worker_log)

    def _refresh_throughput(self, info: dict):
        """Refresh throughput metrics (Phase 2)."""
        worker_log = info.get("worker_log")
        metrics_file = info.get("metrics_file")
        if worker_log and worker_log.exists():
            self._throughput = ThroughputMetrics()  # Reset for fresh computation
            self._throughput_data = self._throughput.compute_all(
                worker_log, metrics_file
            )
        self._throttler.mark_refreshed("throughput_metrics")

    def _refresh_cost(self, info: dict):
        """Refresh cost metrics (Phase 4)."""
        metrics_file = info.get("metrics_file")
        if metrics_file and metrics_file.exists():
            self._cost = CostMetrics()
            self._cost_data = self._cost.compute_all(metrics_file)
        self._throttler.mark_refreshed("cost_metrics")

    def _refresh_task_data(self, info: dict):
        """Refresh task data from Joan API (Phase 3)."""
        config = info.get("config", {})
        project_id = config.get("projectId")
        if project_id and self._api.available:
            self._task_data = self._api.fetch_task_data(project_id)
        self._throttler.mark_refreshed("joan_api")

    def tail_logs(self, project_name: str):
        """Tail logs for a specific project."""
        self.discover_instances()

        matches = [
            (name, info)
            for name, info in self.instances.items()
            if project_name.lower() in name.lower()
        ]

        if not matches:
            self.console.print(
                f"\n[red]No running instance found for '{project_name}'[/red]\n"
            )
            return

        if len(matches) > 1:
            self.console.print("\n[yellow]Multiple matches found:[/yellow]")
            for name, _ in matches:
                self.console.print(f"  - {name}")
            self.console.print("\n[dim]Be more specific[/dim]\n")
            return

        proj_name, info = matches[0]
        log_file = info["log_file"]

        if not log_file.exists():
            self.console.print(
                f"\n[red]Log file not found: {log_file}[/red]\n"
            )
            return

        self.console.print(f"\n[cyan]Tailing logs for {proj_name}[/cyan]")
        self.console.print(f"[dim]{log_file}[/dim]\n")
        self.console.print("[dim]Press Ctrl+C to stop[/dim]\n")

        try:
            subprocess.run(["tail", "-f", str(log_file)])
        except KeyboardInterrupt:
            self.console.print("\n[yellow]Stopped tailing logs[/yellow]\n")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Joan Agents - Global monitoring and management",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "command", choices=["status", "logs"], help="Command to run"
    )
    parser.add_argument(
        "project", nargs="?", help="Project name (partial match supported)"
    )
    parser.add_argument(
        "-f",
        "--follow",
        action="store_true",
        help="Follow/live update (for status command)",
    )

    args = parser.parse_args()
    monitor = JoanMonitor()

    if args.command == "status":
        if args.project:
            monitor.show_project_view(args.project, follow=args.follow)
        else:
            monitor.show_global_view(live_mode=args.follow)
    elif args.command == "logs":
        if not args.project:
            print("Error: Project name required for logs command")
            sys.exit(1)
        monitor.tail_logs(args.project)
