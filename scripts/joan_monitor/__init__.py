"""
Joan Monitor - Dashboard for joan-agents instances.

Usage:
    joan status              # Global view of all running agents
    joan status <project>    # Detailed view of specific project
    joan status <project> -f # Live updating dashboard
    joan logs <project>      # Tail logs for specific project
"""

from joan_monitor.monitor import main

__all__ = ["main"]
