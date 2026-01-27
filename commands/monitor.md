---
invocable-by-user: true
argument-hint: "[PROJECT_DIR]"
shell: bash
---

#!/bin/bash
# Joan Agents Live Monitor
# Display a beautiful live dashboard showing agent activity

set -euo pipefail

# Check if Rich library is installed (required)
if ! python3 -c "import rich" 2>/dev/null; then
  echo "Error: Rich library not installed"
  echo ""
  echo "The monitor requires the Rich library for terminal output."
  echo ""
  echo "Install all dashboard dependencies with:"
  echo "  python3 -m pip install --user --break-system-packages -r ~/joan-agents/scripts/requirements.txt"
  echo ""
  echo "Or install Rich alone:"
  echo "  python3 -m pip install --user --break-system-packages rich"
  echo ""
  exit 1
fi

# Check if TTE is installed (optional, enables startup animations)
if ! python3 -c "import terminaltexteffects" 2>/dev/null; then
  echo "Note: terminaltexteffects not installed — dashboard will use basic startup banner."
  echo "  Install for animated effects: python3 -m pip install --user --break-system-packages terminaltexteffects"
  echo ""
fi

# Determine project directory
PROJECT_DIR="${1:-.}"
PROJECT_DIR="$(cd "$PROJECT_DIR" && pwd)"

# Verify project has been initialized
if [[ ! -f "$PROJECT_DIR/.joan-agents.json" ]]; then
  echo "Error: No .joan-agents.json found in $PROJECT_DIR"
  echo "Run '/agents:init' to initialize the project."
  exit 1
fi

# Find the joan-monitor.py script
MONITOR_SCRIPT=""

# Check if we're in the joan-agents directory
if [[ -f "scripts/joan-monitor.py" ]]; then
  MONITOR_SCRIPT="$(pwd)/scripts/joan-monitor.py"
# Check common installation location
elif [[ -f "$HOME/joan-agents/scripts/joan-monitor.py" ]]; then
  MONITOR_SCRIPT="$HOME/joan-agents/scripts/joan-monitor.py"
# Search in parent directories
else
  SEARCH_DIR="$(pwd)"
  while [[ "$SEARCH_DIR" != "/" ]]; do
    if [[ -f "$SEARCH_DIR/joan-agents/scripts/joan-monitor.py" ]]; then
      MONITOR_SCRIPT="$SEARCH_DIR/joan-agents/scripts/joan-monitor.py"
      break
    fi
    SEARCH_DIR="$(dirname "$SEARCH_DIR")"
  done
fi

if [[ -z "$MONITOR_SCRIPT" ]]; then
  echo "Error: Cannot find joan-monitor.py"
  echo "Expected location: \$HOME/joan-agents/scripts/joan-monitor.py"
  exit 1
fi

# Launch the monitor
exec python3 "$MONITOR_SCRIPT" "$PROJECT_DIR"
