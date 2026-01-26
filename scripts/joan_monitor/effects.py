"""
Terminal Text Effects (TTE) for celebrations, transitions, and startup.

Uses the optional `terminaltexteffects` package when available.
Falls back to Rich-styled panels when TTE is not installed.

Install TTE: pip install terminaltexteffects
"""

import os
import sys
import time
from dataclasses import dataclass, field

try:
    from terminaltexteffects.effects.effect_decrypt import Decrypt
    from terminaltexteffects.effects.effect_fireworks import Fireworks
    from terminaltexteffects.effects.effect_slide import Slide

    TTE_AVAILABLE = True
except ImportError:
    TTE_AVAILABLE = False

from rich.console import Console
from rich.panel import Panel
from rich.text import Text


STARTUP_BANNER = r"""
     _  ___    _    _   _
    | |/ _ \  / \  | \ | |
 _  | | | | |/ _ \ |  \| |
| |_| | |_| / ___ \| |\  |
 \___/ \___/_/   \_\_| \_|

       A G E N T S
"""


@dataclass
class DashboardEvent:
    """An event that can trigger a visual effect."""

    event_type: str  # "completion", "transition", "startup"
    task_name: str = ""
    from_stage: str = ""
    to_stage: str = ""
    timestamp: float = 0.0


class EffectManager:
    """Manages TTE animations with Rich fallbacks."""

    def __init__(self, console: Console = None):
        self.console = console or Console()
        self._previous_completions = 0
        self._previous_worker = None
        self._pending_events: list[DashboardEvent] = []

    @property
    def tte_available(self) -> bool:
        return TTE_AVAILABLE

    def play_startup_banner(self):
        """Play startup banner effect."""
        if TTE_AVAILABLE:
            self._play_tte_startup()
        else:
            self._play_rich_startup()

    def _play_tte_startup(self):
        """TTE Decrypt effect on ASCII art banner."""
        try:
            effect = Decrypt(STARTUP_BANNER.strip("\n"))
            effect.effect_config.final_gradient_frames = 5
            with effect.terminal_output() as terminal:
                for frame in effect:
                    terminal.print(frame)
            time.sleep(0.5)
        except Exception:
            self._play_rich_startup()

    def _play_rich_startup(self):
        """Rich fallback: styled banner panel."""
        banner = Text(STARTUP_BANNER.strip("\n"), style="bold cyan")
        self.console.print(
            Panel(banner, border_style="cyan", title="Starting Dashboard")
        )
        time.sleep(0.8)
        # Clear screen after banner
        self.console.clear()

    def play_celebration(self, task_name: str):
        """Play task completion celebration."""
        if TTE_AVAILABLE:
            self._play_tte_celebration(task_name)
        else:
            self._play_rich_celebration(task_name)

    def _play_tte_celebration(self, task_name: str):
        """TTE Fireworks effect with task name."""
        try:
            celebration_text = f"  COMPLETED: {task_name}  "
            effect = Fireworks(celebration_text)
            with effect.terminal_output() as terminal:
                for frame in effect:
                    terminal.print(frame)
            time.sleep(0.5)
        except Exception:
            self._play_rich_celebration(task_name)

    def _play_rich_celebration(self, task_name: str):
        """Rich fallback: green celebration panel."""
        text = Text()
        text.append("\n  \u2713 COMPLETED  ", "bold white on green")
        text.append(f"\n\n  {task_name}\n", "bold green")
        self.console.print(
            Panel(text, border_style="green", title="\U0001f389 Task Complete!")
        )
        time.sleep(1.5)

    def play_transition(self, from_stage: str, to_stage: str, task_name: str):
        """Play stage transition effect."""
        if TTE_AVAILABLE:
            self._play_tte_transition(from_stage, to_stage, task_name)
        else:
            self._play_rich_transition(from_stage, to_stage, task_name)

    def _play_tte_transition(self, from_stage: str, to_stage: str, task_name: str):
        """TTE Slide effect with transition text."""
        try:
            transition_text = f"  {from_stage} >>> {to_stage}: {task_name}  "
            effect = Slide(transition_text)
            with effect.terminal_output() as terminal:
                for frame in effect:
                    terminal.print(frame)
            time.sleep(0.3)
        except Exception:
            self._play_rich_transition(from_stage, to_stage, task_name)

    def _play_rich_transition(self, from_stage: str, to_stage: str, task_name: str):
        """Rich fallback: styled transition panel."""
        text = Text()
        text.append(f"  {from_stage}", "bold yellow")
        text.append("  \u2192  ", "bold white")
        text.append(f"{to_stage}\n", "bold cyan")
        text.append(f"\n  {task_name}\n", "white")
        self.console.print(
            Panel(text, border_style="cyan", title="Stage Transition")
        )
        time.sleep(1.0)

    def detect_events(self, metrics: dict, activity: dict) -> list[DashboardEvent]:
        """Compare current metrics to previous state and detect visual events.

        Call each refresh cycle. Returns list of events to play.
        """
        events = []
        now = time.time()

        # Detect new completions (completion count increase)
        current_completions = metrics.get("completions", 0)
        if (
            self._previous_completions > 0
            and current_completions > self._previous_completions
        ):
            # A task was completed since last check
            task_name = ""
            recent_reworks = metrics.get("recent_reworks", [])
            # Try to get task name from recent doctor events or activity
            if activity.get("last_message"):
                task_name = activity["last_message"]

            events.append(
                DashboardEvent(
                    event_type="completion",
                    task_name=task_name,
                    timestamp=now,
                )
            )
        self._previous_completions = current_completions

        # Detect stage transitions (worker type change)
        current_worker = activity.get("current_worker")
        if (
            current_worker
            and self._previous_worker
            and current_worker != self._previous_worker
            and activity.get("current_status") == "WORKING"
        ):
            task_name = activity.get("current_task", "")
            events.append(
                DashboardEvent(
                    event_type="transition",
                    from_stage=self._previous_worker,
                    to_stage=current_worker,
                    task_name=task_name,
                    timestamp=now,
                )
            )
        if current_worker:
            self._previous_worker = current_worker

        return events

    def play_events(self, events: list[DashboardEvent]):
        """Play all pending events."""
        for event in events:
            if event.event_type == "completion":
                self.play_celebration(event.task_name)
            elif event.event_type == "transition":
                self.play_transition(
                    event.from_stage, event.to_stage, event.task_name
                )

    def has_pending_events(self) -> bool:
        """Check if there are events waiting to be played."""
        return len(self._pending_events) > 0
