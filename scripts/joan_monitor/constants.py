"""
Constants for the Joan Monitor dashboard.

Pipeline stages, status icons, color mappings, and cost model rates.
"""

PIPELINE_STAGES = ["BA", "Architect", "Dev", "Reviewer", "Ops"]

# Worker activity log status icons and styles
STATUS_ICONS = {
    "START": ("\u25b6", "bold green"),      # ▶
    "PROGRESS": ("\u25c6", "cyan"),          # ◆
    "COMPLETE": ("\u2713", "bold green"),     # ✓
    "FAIL": ("\u2717", "bold red"),           # ✗
}

# Pipeline stage display characters
PIPELINE_ACTIVE_ICON = "\u25cf"    # ●
PIPELINE_INACTIVE_ICON = "\u25cb"  # ○
PIPELINE_WAITING_ICON = "\u25d0"   # ◐

# Doctor/rework thresholds for color coding
DOCTOR_THRESHOLD_YELLOW = 2
DOCTOR_THRESHOLD_RED = 5
REWORK_THRESHOLD_YELLOW = 2
REWORK_THRESHOLD_RED = 5

# Tiered refresh intervals (seconds) for live mode
REFRESH_INTERVALS = {
    "process_discovery": 5,
    "log_parsing": 2,
    "worker_activity": 1,
    "joan_api": 30,
    "throughput_metrics": 5,
    "cost_metrics": 10,
    "event_detection": 1,
}

# Token cost model for duration-based estimation (Phase 4)
TOKENS_PER_MINUTE = {
    "haiku": {"input": 8000, "output": 2000},
    "sonnet": {"input": 12000, "output": 3000},
    "opus": {"input": 15000, "output": 4000},
}

COST_PER_MTOK = {
    "haiku": {"input": 0.25, "output": 1.25},
    "sonnet": {"input": 3.00, "output": 15.00},
    "opus": {"input": 15.00, "output": 75.00},
}

# Default API URL
DEFAULT_API_URL = "https://joan-api.alexbbenson.workers.dev"
