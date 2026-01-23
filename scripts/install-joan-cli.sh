#!/bin/bash
# Install joan CLI as a global command
# Usage: ./scripts/install-joan-cli.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
JOAN_SCRIPT="$SCRIPT_DIR/joan"

# Check if script exists
if [[ ! -f "$JOAN_SCRIPT" ]]; then
    echo "Error: joan script not found at $JOAN_SCRIPT"
    exit 1
fi

# Make executable
chmod +x "$JOAN_SCRIPT"

# Determine install location
if [[ -w "/usr/local/bin" ]]; then
    INSTALL_DIR="/usr/local/bin"
    SUDO=""
elif [[ -d "$HOME/.local/bin" ]]; then
    INSTALL_DIR="$HOME/.local/bin"
    SUDO=""
else
    INSTALL_DIR="/usr/local/bin"
    SUDO="sudo"
    echo "Note: Will use sudo to install to /usr/local/bin"
fi

# Create symlink
echo "Installing joan command to $INSTALL_DIR..."
$SUDO ln -sf "$JOAN_SCRIPT" "$INSTALL_DIR/joan"

# Verify installation
if command -v joan &> /dev/null; then
    echo "✓ joan command installed successfully!"
    echo ""
    echo "Usage:"
    echo "  joan status              # Global view of all running agents"
    echo "  joan status <project>    # Detailed view of specific project"
    echo "  joan logs <project>      # Tail logs for specific project"
else
    echo "✓ Symlink created at $INSTALL_DIR/joan"
    echo ""
    echo "Warning: $INSTALL_DIR is not in your PATH"
    echo ""
    echo "Add this to your ~/.zshrc or ~/.bashrc:"
    echo "  export PATH=\"$INSTALL_DIR:\$PATH\""
    echo ""
    echo "Then reload your shell:"
    echo "  source ~/.zshrc  # or source ~/.bashrc"
fi
