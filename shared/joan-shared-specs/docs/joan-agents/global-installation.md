# Global Installation Guide

This guide shows how to install the Joan Multi-Agent System globally so the commands are available across all your projects.

## Why Global Installation?

- **Convenience**: Run `/agents:*` commands from any project without copying files
- **Easy Updates**: `git pull` updates agents everywhere instantly
- **Clean Projects**: Only `.joan-agents.json` config file needed per project

## Prerequisites

- Claude Code installed
- Python 3.9+ (`python3 --version`)
- This repository cloned to a permanent location

## Installation

### Step 1: Clone the Repository

Clone to a permanent location (this will be the source of truth):

```bash
# Choose a permanent location
git clone https://github.com/pollychrome/joan-agents.git ~/joan-agents

# Or if you already have it elsewhere
cd /path/to/joan-agents
pwd  # Note this path for Step 2

# Install dashboard dependencies (Rich UI + terminal effects)
python3 -m pip install --user --break-system-packages -r ~/joan-agents/scripts/requirements.txt
```

### Step 2: Create Symlinks

Create symlinks from the global Claude Code directory to this repository:

```bash
# Create commands directory if it doesn't exist
mkdir -p ~/.claude/commands

# Remove any existing installations
rm -rf ~/.claude/commands/agents
rm -rf ~/.claude/agents

# Create symlinks (replace path if your repo is elsewhere)
ln -s ~/joan-agents/.claude/commands/agents ~/.claude/commands/agents
ln -s ~/joan-agents/.claude/agents ~/.claude/agents
```

### Step 3: Set Up Global Instructions

**Option A: Symlink the entire CLAUDE.md** (recommended if you don't have existing global instructions)

```bash
ln -sf ~/joan-agents/.claude/CLAUDE.md ~/.claude/CLAUDE.md
```

**Option B: Include via reference** (if you have existing global instructions)

Add this line to your `~/.claude/CLAUDE.md`:

```markdown
{{~/joan-agents/.claude/CLAUDE.md}}
```

**Option C: Append contents** (if include syntax isn't supported)

```bash
echo "" >> ~/.claude/CLAUDE.md
echo "# Joan Multi-Agent System" >> ~/.claude/CLAUDE.md
cat ~/joan-agents/.claude/CLAUDE.md >> ~/.claude/CLAUDE.md
```

### Step 4: Verify Installation

Open a new Claude Code session in any project:

```bash
cd ~/some-project
claude
```

Then try:
```
/agents:init
```

You should see the initialization wizard, not "Unknown skill".

## Per-Project Setup

After global installation, each project only needs a config file:

```bash
cd ~/your-project
claude

# In Claude Code:
> /agents:init
```

This creates `.joan-agents.json` with your project's Joan configuration.

## Updating

To get the latest agent updates:

```bash
cd ~/joan-agents
git pull
```

Changes are immediately available in all projects - no reinstallation needed.

## Directory Structure

After global installation:

```
~/.claude/
├── CLAUDE.md                    # Global instructions (symlinked or appended)
├── agents/ -> ~/joan-agents/.claude/agents/
│   ├── architect.md
│   ├── business-analyst.md
│   ├── developer.md
│   ├── ops.md
│   └── reviewer.md
└── commands/
    └── agents/ -> ~/joan-agents/.claude/commands/agents/
        ├── init.md
        ├── start.md
        ├── dispatch/              # Coordinator router + handlers
        ├── model.md
        ├── ba-worker.md
        ├── architect-worker.md
        ├── dev-worker.md
        ├── reviewer-worker.md
        └── ops-worker.md

~/joan-agents/                   # Source repository
├── .claude/
│   ├── agents/                  # Agent definitions (symlink target)
│   ├── commands/agents/         # Slash commands (symlink target)
│   └── CLAUDE.md                # System documentation
├── docs/                         # Pointer README to shared specs
├── shared/
│   └── joan-shared-specs/
│       └── docs/                # Shared specs (canonical)
└── README.md

~/your-project/                  # Any project using Joan agents
└── .joan-agents.json            # Project-specific config (created by /agents:init)
```

## Troubleshooting

### "Unknown skill" Error

The symlinks aren't set up correctly. Verify:

```bash
ls -la ~/.claude/commands/agents
ls -la ~/.claude/agents
```

Both should show symlinks pointing to your joan-agents repository.

### Commands Work But Agents Fail

Missing project config. Run `/agents:init` in the project directory.

### Symlink Points to Wrong Location

Remove and recreate:

```bash
rm ~/.claude/commands/agents
rm ~/.claude/agents
ln -s /correct/path/to/joan-agents/.claude/commands/agents ~/.claude/commands/agents
ln -s /correct/path/to/joan-agents/.claude/agents ~/.claude/agents
```

## Uninstalling

To remove global installation:

```bash
rm ~/.claude/commands/agents
rm ~/.claude/agents
# If you symlinked CLAUDE.md:
rm ~/.claude/CLAUDE.md
```

This only removes the symlinks, not the repository itself.
