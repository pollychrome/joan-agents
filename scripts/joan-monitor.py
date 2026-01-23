#!/usr/bin/env python3
"""
Joan Agents Live Monitor
========================
Beautiful terminal dashboard for monitoring joan-agents activity.

Usage:
    python scripts/joan-monitor.py [PROJECT_DIR]
    /agents:monitor
"""

import sys
import os
import re
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict
import time

try:
    from rich.console import Console
    from rich.live import Live
    from rich.table import Table
    from rich.panel import Panel
    from rich.layout import Layout
    from rich.text import Text
    from rich.progress import Progress, BarColumn, TextColumn, TimeElapsedColumn
except ImportError:
    print("Error: Rich library not installed")
    print("Install with: pip install rich")
    sys.exit(1)


class AgentMonitor:
    """Monitors joan-agents activity from scheduler logs."""

    WORKER_TYPES = ["BA", "Architect", "Dev", "Reviewer", "Ops"]
    PIPELINE_STAGES = ["BA", "Architect", "Dev", "Reviewer", "Ops"]

    def __init__(self, project_dir: Path):
        self.project_dir = project_dir
        self.log_file = project_dir / ".claude/logs/scheduler.log"
        self.console = Console()

        # State tracking
        self.cycle = 0
        self.idle_count = 0
        self.max_idle = 12
        self.last_poll = None
        self.active_workers = {}  # worker_type -> {task, started_at, task_name}
        self.recent_events = []
        self.dispatched_count = 0
        self.doctor_active = False
        self.doctor_task = None
        self.blink_state = False  # For animation

        if not self.log_file.exists():
            raise FileNotFoundError(f"No log file found at {self.log_file}")

    def parse_log(self):
        """Parse the scheduler log to extract current state."""
        with open(self.log_file, 'r') as f:
            lines = f.readlines()

        # Reset state for fresh parse
        self.active_workers = {}
        self.recent_events = []
        self.doctor_active = False
        self.doctor_task = None

        for i, line in enumerate(lines):
            self._parse_line(line, i, lines)

        # Clean up recent events (keep last 10)
        self.recent_events = self.recent_events[-10:]

        # Toggle blink state for animation
        self.blink_state = not self.blink_state

    def _parse_line(self, line: str, idx: int, all_lines: list):
        """Parse a single log line."""
        # Extract timestamp
        ts_match = re.match(r'\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\]', line)
        if ts_match:
            timestamp = datetime.strptime(ts_match.group(1), '%Y-%m-%d %H:%M:%S')
        else:
            timestamp = None

        # Cycle number
        if "Cycle" in line and "starting" in line:
            match = re.search(r'Cycle (\d+)', line)
            if match:
                self.cycle = int(match.group(1))
                if timestamp:
                    self.last_poll = timestamp

        # Idle count
        if "idle count reset" in line:
            self.idle_count = 0
        elif "idle count:" in line:
            match = re.search(r'idle count: (\d+)/(\d+)', line)
            if match:
                self.idle_count = int(match.group(1))
                self.max_idle = int(match.group(2))

        # Max idle polls from startup
        if "Max idle polls:" in line:
            match = re.search(r'Max idle polls: (\d+)', line)
            if match:
                self.max_idle = int(match.group(1))

        # Worker dispatches (look for markdown bold pattern)
        if "**" in line and "worker" in line.lower():
            # Pattern: **BA worker dispatched for 'Task Name'**
            # Pattern: **Dev worker completed for 'Task Name'**
            match = re.search(r'\*\*(\w+) worker (dispatched|completed|claimed) for [\'"]([^\'"]+)[\'"]\*\*', line)
            if match:
                worker_type = match.group(1)
                action = match.group(2)
                task_name = match.group(3)

                if action == "dispatched" or action == "claimed":
                    self.active_workers[worker_type] = {
                        'task_name': task_name,
                        'started_at': timestamp or datetime.now()
                    }
                    if timestamp:
                        self.recent_events.append({
                            'timestamp': timestamp,
                            'message': f"{worker_type} worker started: {task_name}"
                        })
                elif action == "completed":
                    if worker_type in self.active_workers:
                        del self.active_workers[worker_type]
                    if timestamp:
                        self.recent_events.append({
                            'timestamp': timestamp,
                            'message': f"{worker_type} worker completed: {task_name}"
                        })

        # Dispatched count
        if "Dispatched **" in line or "dispatched **" in line:
            match = re.search(r'[Dd]ispatched \*\*(\d+)\*\* worker', line)
            if match:
                self.dispatched_count = int(match.group(1))

        # Doctor activity
        if "Doctor" in line or "DOCTOR" in line:
            if "triggered" in line.lower() or "running" in line.lower() or "diagnosing" in line.lower():
                self.doctor_active = True
                # Try to extract task being diagnosed
                task_match = re.search(r"Task[:\s#]+(\d+|['\"]([^'\"]+)['\"])", line)
                if task_match:
                    self.doctor_task = task_match.group(1) or task_match.group(2)
                if timestamp:
                    self.recent_events.append({
                        'timestamp': timestamp,
                        'message': f"🏥 Doctor diagnosing issues"
                    })
            elif "complete" in line.lower() or "finished" in line.lower():
                self.doctor_active = False
                self.doctor_task = None

        # Generic events
        if timestamp and "[INFO]" in line:
            msg = line.split("[INFO]", 1)[1].strip()
            if any(keyword in msg for keyword in ["Coordinator started", "Sleeping", "Shutdown"]):
                self.recent_events.append({
                    'timestamp': timestamp,
                    'message': msg
                })

    def generate_pipeline_visual(self) -> Text:
        """Generate the pipeline visualization with blinking active stage."""
        text = Text()

        # Find active stage
        active_stage = None
        active_task = None
        for stage in self.PIPELINE_STAGES:
            if stage in self.active_workers:
                active_stage = stage
                active_task = self.active_workers[stage].get('task_name', '')
                break

        # Build pipeline visualization
        #  ┌─────┐    ┌──────────┐    ┌─────┐    ┌──────────┐    ┌─────┐
        #  │ BA  │───►│ Architect│───►│ Dev │───►│ Reviewer │───►│ Ops │
        #  └─────┘    └──────────┘    └─────┘    └──────────┘    └─────┘

        stages_display = []
        for stage in self.PIPELINE_STAGES:
            is_active = (stage == active_stage)

            if is_active:
                # Blinking effect - alternate between bright green and dim
                if self.blink_state:
                    style = "bold bright_green on green"
                    icon = "●"
                else:
                    style = "bold green"
                    icon = "○"
            else:
                style = "dim white"
                icon = "○"

            stages_display.append((stage, style, icon, is_active))

        # Top border
        text.append("  ")
        for i, (stage, style, icon, is_active) in enumerate(stages_display):
            width = max(len(stage) + 2, 8)
            text.append("┌" + "─" * width + "┐", style if is_active else "dim")
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
            text.append("│" + " " * left_pad + content + " " * right_pad + "│", style)
            if i < len(stages_display) - 1:
                text.append("───►", "cyan" if is_active else "dim")
        text.append("\n")

        # Bottom border
        text.append("  ")
        for i, (stage, style, icon, is_active) in enumerate(stages_display):
            width = max(len(stage) + 2, 8)
            text.append("└" + "─" * width + "┘", style if is_active else "dim")
            if i < len(stages_display) - 1:
                text.append("    ", "dim")
        text.append("\n")

        # Current task indicator
        if active_stage and active_task:
            text.append("\n  ")
            task_display = active_task[:50] + "..." if len(active_task) > 50 else active_task
            text.append(f"  ▶ {active_stage}: ", "bold green")
            text.append(task_display, "white")

        # Doctor indicator (separate, on the right)
        if self.doctor_active:
            text.append("\n\n  ")
            if self.blink_state:
                text.append("  🏥 DOCTOR ", "bold bright_red on red")
            else:
                text.append("  🏥 DOCTOR ", "bold red")
            text.append(" Diagnosing issues...", "red")
            if self.doctor_task:
                text.append(f" (Task: {self.doctor_task})", "dim red")

        return text

    def generate_layout(self) -> Layout:
        """Generate the Rich layout for display."""
        layout = Layout()
        layout.split_column(
            Layout(name="header", size=3),
            Layout(name="pipeline", size=9),
            Layout(name="body"),
            Layout(name="events", size=10)
        )

        # Header
        now = datetime.now()
        header_text = Text("Joan Agents - Live Monitor", style="bold cyan", justify="center")
        layout["header"].update(Panel(header_text, border_style="cyan"))

        # Pipeline visualization
        pipeline_visual = self.generate_pipeline_visual()
        layout["pipeline"].update(
            Panel(pipeline_visual, title="🔄 Pipeline Status", border_style="magenta")
        )

        # Body: Coordinator + Workers
        body_layout = Layout()
        body_layout.split_row(
            Layout(name="coordinator", ratio=1),
            Layout(name="workers", ratio=2)
        )

        # Coordinator status
        coord_table = Table(show_header=False, box=None, padding=(0, 1))
        coord_table.add_column("Key", style="cyan")
        coord_table.add_column("Value")

        coord_table.add_row("Cycle", str(self.cycle))
        coord_table.add_row("Idle Count", f"{self.idle_count}/{self.max_idle}")

        if self.last_poll:
            elapsed = (now - self.last_poll).total_seconds()
            coord_table.add_row("Last Poll", f"{int(elapsed)}s ago")
        else:
            coord_table.add_row("Last Poll", "N/A")

        coord_table.add_row("Active Workers", str(len(self.active_workers)))

        body_layout["coordinator"].update(
            Panel(coord_table, title="📊 Coordinator", border_style="blue")
        )

        # Workers table
        workers_table = Table(show_header=True, box=None)
        workers_table.add_column("Worker", style="cyan", width=12)
        workers_table.add_column("Task", style="white", width=30)
        workers_table.add_column("Duration", style="yellow", width=10)
        workers_table.add_column("Progress", width=20)

        for worker_type in self.WORKER_TYPES:
            if worker_type in self.active_workers:
                worker_info = self.active_workers[worker_type]
                task_name = worker_info['task_name']
                started_at = worker_info['started_at']
                duration = now - started_at

                # Format duration
                duration_str = self._format_duration(duration)

                # Progress bar (estimate based on typical durations)
                progress_bar = self._generate_progress_bar(worker_type, duration)

                workers_table.add_row(
                    f"🔄 {worker_type}",
                    task_name[:28] + "..." if len(task_name) > 28 else task_name,
                    duration_str,
                    progress_bar
                )
            else:
                workers_table.add_row(
                    f"💤 {worker_type}",
                    "Idle",
                    "-",
                    ""
                )

        body_layout["workers"].update(
            Panel(workers_table, title="🔧 Active Workers", border_style="green")
        )

        # Assign body_layout to layout
        layout["body"].update(body_layout)

        # Recent events
        events_table = Table(show_header=False, box=None, padding=(0, 1))
        events_table.add_column("Time", style="dim", width=12)
        events_table.add_column("Event", style="white")

        for event in reversed(self.recent_events):
            elapsed = now - event['timestamp']
            time_str = self._format_duration(elapsed) + " ago"
            events_table.add_row(time_str, event['message'][:70])

        layout["events"].update(
            Panel(events_table, title="📋 Recent Events", border_style="yellow")
        )

        return layout

    def _format_duration(self, duration: timedelta) -> str:
        """Format duration as HH:MM:SS."""
        total_seconds = int(duration.total_seconds())
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60

        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        else:
            return f"{minutes:02d}:{seconds:02d}"

    def _generate_progress_bar(self, worker_type: str, duration: timedelta) -> str:
        """Generate a simple progress bar based on expected duration."""
        # Expected durations (in minutes)
        expected = {
            "BA": 10,
            "Architect": 20,
            "Dev": 60,
            "Reviewer": 20,
            "Ops": 15
        }

        expected_minutes = expected.get(worker_type, 30)
        elapsed_minutes = duration.total_seconds() / 60
        progress = min(elapsed_minutes / expected_minutes, 1.0)

        bar_width = 10
        filled = int(progress * bar_width)
        empty = bar_width - filled

        bar = "█" * filled + "░" * empty

        if progress >= 1.0:
            return f"[red]{bar}[/red] ⚠️"
        elif progress >= 0.8:
            return f"[yellow]{bar}[/yellow]"
        else:
            return f"[green]{bar}[/green]"

    def run(self):
        """Run the live monitor."""
        try:
            with Live(self.generate_layout(), refresh_per_second=1, console=self.console) as live:
                while True:
                    self.parse_log()
                    live.update(self.generate_layout())
                    time.sleep(1)
        except KeyboardInterrupt:
            self.console.print("\n[yellow]Monitor stopped[/yellow]")


def main():
    """Entry point."""
    # Determine project directory
    if len(sys.argv) > 1:
        project_dir = Path(sys.argv[1]).resolve()
    else:
        project_dir = Path.cwd()

    if not project_dir.exists():
        print(f"Error: Project directory does not exist: {project_dir}")
        sys.exit(1)

    config_file = project_dir / ".joan-agents.json"
    if not config_file.exists():
        print(f"Error: No .joan-agents.json found in {project_dir}")
        print("Run '/agents:init' to initialize the project.")
        sys.exit(1)

    try:
        monitor = AgentMonitor(project_dir)
        monitor.run()
    except FileNotFoundError as e:
        print(f"Error: {e}")
        print("The scheduler must be running to use the monitor.")
        print("Start with: /agents:dispatch --loop")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
