# Joan Multi-Agent Orchestration System (v4)

## Tag-Driven Orchestration with Single Coordinator

This version introduces **tag-based state transitions** (no comment parsing), a **single coordinator** that dispatches workers, and **10x lower polling overhead**. Combined with git worktrees for parallel development and automatic idle shutdown.

### What's New in v4

| Feature | v3 | v4 |
|---------|-----|-----|
| Orchestration | N agents poll independently | Single coordinator dispatches workers |
| State triggers | Comment parsing (@approve-plan) | Tag-based (Plan-Approved tag) |
| Human workflow | Add comments | Add tags in Joan UI |
| Polling overhead | N polls per interval | 1 poll per interval |
| Worker lifetime | Continuous loops | Single-pass (exit after task) |

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         DEVELOPMENT COLUMN                              │
│                                                                         │
│    Task A          Task B          Task C          Task D               │
│       │               │               │               │                 │
│       ▼               ▼               ▼               ▼                 │
│    Dev #1          Dev #2          Dev #3          Dev #4               │
│       │               │               │               │                 │
│       ▼               ▼               ▼               ▼                 │
│  ┌─────────┐     ┌─────────┐     ┌─────────┐     ┌─────────┐           │
│  │Worktree │     │Worktree │     │Worktree │     │Worktree │           │
│  │ task-a  │     │ task-b  │     │ task-c  │     │ task-d  │           │
│  └─────────┘     └─────────┘     └─────────┘     └─────────┘           │
│                                                                         │
│  4 features developed IN PARALLEL                                       │
└─────────────────────────────────────────────────────────────────────────┘
```

## What Changed

| Aspect | v1-v2 | v3 | v4 |
|--------|-------|-----|-----|
| Development agents | Varied | N Devs + Reviewer | N Devs + Reviewer |
| Orchestration | N/A | N independent loops | Single coordinator |
| State triggers | Manual | Comment parsing | Tag-based |
| Polling | N agents polling | N agents polling | 1 coordinator polls |
| Worker lifetime | Continuous | Continuous | Single-pass |
| Token usage | High | High | ~10x lower |

## Agents

| Agent | Count | Role |
|-------|-------|------|
| Business Analyst | 1 | Evaluates requirements |
| Architect | 1 | Creates implementation plans |
| **Dev** | **N** | Claims task → creates worktree → implements everything → creates PR → cleans up |
| **Reviewer** | **1** | Code review, quality gate, approves or requests rework |
| Ops | 1 | Merges approved PRs to develop, tracks deploys |

## Quick Start

### Global Installation (Recommended)

Install once, use in all projects. Updates via `git pull`.

```bash
# 1. Clone to a permanent location
git clone https://github.com/pollychrome/joan-agents.git ~/joan-agents

# 2. Create symlinks to global Claude Code config
mkdir -p ~/.claude/commands
ln -s ~/joan-agents/.claude/commands/agents ~/.claude/commands/agents
ln -s ~/joan-agents/.claude/agents ~/.claude/agents
ln -sf ~/joan-agents/.claude/CLAUDE.md ~/.claude/CLAUDE.md

# 3. Initialize any project
cd ~/your-project
claude
> /agents:init    # Creates .joan-agents.json config and tags

# 4. Run agents
> /agents:start --loop
```

See `shared/joan-shared-specs/docs/joan-agents/global-installation.md` for detailed instructions.

### Per-Project Installation

Copy files to each project individually:

```bash
cp -r joan-agents/.claude/agents/ your-project/.claude/agents/
cp -r joan-agents/.claude/commands/ your-project/.claude/commands/
cp joan-agents/.claude/CLAUDE.md your-project/.claude/CLAUDE.md

cd your-project
claude
> /agents:init
> /agents:start --loop
```

### Shell Scripts (iTerm2)

For launching agents in separate terminal tabs:

```bash
chmod +x ~/joan-agents/*.sh
~/joan-agents/start-agents-iterm.sh
```

## How Devs Operate

The coordinator dispatches Dev workers, each following this cycle:

```
1. RECEIVE  → Coordinator assigns task (already claimed)
2. WORKTREE → git worktree add ../worktrees/{task-id} {branch}
3. IMPLEMENT → Execute DES-*, DEV-*, TEST-* in order
4. PR       → Create pull request
5. CLEANUP  → Remove worktree, move task to Review
6. EXIT     → Worker exits, coordinator dispatches next
```

Devs are single-pass workers: they process one task and exit.

## Directory Structure

```
your-project/                    # Main repo
├── .claude/
│   ├── agents/
│   │   ├── coordinator.md       # Central orchestrator
│   │   ├── business-analyst.md  # BA subagent
│   │   ├── architect.md         # Architect subagent
│   │   ├── developer.md         # Dev subagent
│   │   ├── reviewer.md          # Reviewer subagent
│   │   └── ops.md               # Ops subagent
│   └── commands/agents/
│       ├── init.md              # Initialize project
│       ├── start.md             # Start coordinator
│       ├── dispatch.md          # Alias for start
│       ├── ba-worker.md         # BA single-pass worker
│       ├── architect-worker.md  # Architect single-pass worker
│       ├── dev-worker.md        # Dev single-pass worker
│       ├── reviewer-worker.md   # Reviewer single-pass worker
│       └── ops-worker.md        # Ops single-pass worker
├── src/
└── ...

../worktrees/                    # Created automatically
├── {task-id-1}/                 # Dev 1's workspace
├── {task-id-2}/                 # Dev 2's workspace
└── ...
```

## Resource Recommendations

| Devs | Terminal Windows | RAM | Use Case |
|------|------------------|-----|----------|
| 2 | 6 | 4-6 GB | Light workload |
| 4 | 8 | 6-10 GB | Standard (recommended) |
| 6 | 10 | 10-14 GB | Heavy workload |

## Workflow (Tag-Based)

1. **To Do** → BA evaluates, asks questions if unclear
2. **Analyse** → Architect creates plan → **you add `Plan-Approved` tag**
3. **Development** → Coordinator assigns devs, they implement in worktrees, create PRs
4. **Review** → Reviewer validates code, merges develop into feature
5. **Review** (approved) → Reviewer adds `Review-Approved` tag → Ops merges to develop
6. **Review** (rejected) → Reviewer adds `Rework-Requested` tag → back to Development
7. **Deploy** → Tracking only - awaits production deployment
8. **Done** → Ops moves after production deploy

### Human Actions (Tag-Based)

| When | Add This Tag |
|------|--------------|
| To approve a plan | `Plan-Approved` |
| After answering BA questions | `Clarification-Answered` |
| To recover a failed task | Remove `Implementation-Failed`, ensure `Planned` exists |

### ALS Comments (Breadcrumbs)

All manual comments should use ALS blocks for consistency. Tags still drive behavior.
See `shared/joan-shared-specs/docs/als-spec.md` for the format.

## Commands

```bash
# Run coordinator (single pass)
/agents:start
/agents:dispatch

# Run coordinator (continuous - recommended)
/agents:start --loop
/agents:dispatch --loop

# Extended idle threshold (2 hours at 10-min intervals)
/agents:start --loop --max-idle=12
```

### Shell Scripts

```bash
./start-agents-iterm.sh [--max-idle=N]
./start-agents.sh [--max-idle=N]
./stop-agents.sh
```

## Documentation

See `shared/joan-shared-specs/docs/joan-agents/README.md` for:
- Architecture - `shared/joan-shared-specs/docs/joan-agents/architecture.md`
- Setup Guide - `shared/joan-shared-specs/docs/joan-agents/setup.md`
- Global Installation - `shared/joan-shared-specs/docs/joan-agents/global-installation.md`
- Troubleshooting - `shared/joan-shared-specs/docs/joan-agents/troubleshooting.md`
- Best Practices - `shared/joan-shared-specs/docs/joan-agents/best-practices.md`
- Orchestration Spec - `shared/joan-shared-specs/docs/orchestration-spec.md`
- Human Inbox Spec - `shared/joan-shared-specs/docs/human-inbox.md`
- ALS Spec - `shared/joan-shared-specs/docs/als-spec.md`
- [Shared Specs](shared/joan-shared-specs) - Cross-repo agentic workflow alignment

## Key Benefits

✅ **Tag-Based Orchestration** - Deterministic state machine, no comment parsing
✅ **10x Lower Overhead** - Single coordinator vs N independent polling agents
✅ **True Parallelism** - N features developed simultaneously in worktrees
✅ **No Conflicts** - Each dev has isolated workspace
✅ **Single-Pass Workers** - Stateless workers, easy to retry on failure
✅ **Quality Gate** - Automated code review before merge
✅ **Clean** - Worktrees auto-created and auto-removed
