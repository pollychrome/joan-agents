# Joan Multi-Agent Orchestration System (v3)

## True Parallel Feature Development with Git Worktrees

This version uses **git worktrees** for genuine parallel development, **intelligent task queuing** for efficient polling, and **automatic idle shutdown** for resource management. Each Dev agent operates in an isolated worktree, allowing multiple features to be developed simultaneously.

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

| Aspect | v1 | v2 | v3 |
|--------|-----|-----|-----|
| Development agents | 3 (Dev, Design, Test) | N Workers | N Devs + Reviewer |
| Parallelism | Time-sliced | True parallel | True parallel |
| Working directory | Single repo | One worktree per task | One worktree per task |
| Task polling | Continuous | Continuous | Smart queue with idle shutdown |
| Code review | Manual | Manual | Automated Reviewer agent |
| Configuration | Hardcoded | Script args | `.joan-agents.json` config file |

## Agents

| Agent | Count | Role |
|-------|-------|------|
| Business Analyst | 1 | Evaluates requirements |
| Architect | 1 | Creates implementation plans |
| **Dev** | **N** | Claims task → creates worktree → implements everything → creates PR → cleans up |
| **Reviewer** | **1** | Code review, quality gate, approves or requests rework |
| Project Manager | 1 | Merges approved PRs to develop, tracks deploys |

## Quick Start

```bash
# Clone or copy to your project
cp -r joan-agents/.claude/agents/ your-project/.claude/agents/
cp -r joan-agents/.claude/commands/ your-project/.claude/commands/

# Initialize configuration (interactive)
cd your-project
/agents:init

# Start agents via slash commands (recommended)
/agents:start all

# Or use shell scripts for iTerm2 tabs
chmod +x joan-agents/*.sh
./joan-agents/start-agents-iterm.sh my-project 4
```

## How Devs Operate

Each Dev agent follows this cycle:

```
1. POLL     → Find unclaimed "Planned" task
2. CLAIM    → Tag task to prevent others from taking it
3. WORKTREE → git worktree add ../worktrees/{task-id} {branch}
4. IMPLEMENT → Execute DES-*, DEV-*, TEST-* in order
5. PR       → Create pull request
6. CLEANUP  → Remove worktree, move task to Review
7. REPEAT   → Go back to step 1
```

## Directory Structure

```
your-project/                    # Main repo
├── .claude/
│   ├── agents/
│   │   ├── business-analyst.md
│   │   ├── architect.md
│   │   ├── developer.md
│   │   ├── reviewer.md
│   │   └── project-manager.md
│   └── commands/agents/
│       ├── ba-loop.md
│       ├── architect-loop.md
│       ├── dev-loop.md
│       ├── reviewer-loop.md
│       └── pm-loop.md
├── src/
└── ...

../worktrees/                    # Created automatically
├── task-123/                    # Dev 1's workspace
├── task-456/                    # Dev 2's workspace
├── task-789/                    # Dev 3's workspace
└── task-012/                    # Dev 4's workspace
```

## Resource Recommendations

| Devs | Terminal Windows | RAM | Use Case |
|------|------------------|-----|----------|
| 2 | 6 | 4-6 GB | Light workload |
| 4 | 8 | 6-10 GB | Standard (recommended) |
| 6 | 10 | 10-14 GB | Heavy workload |

## Workflow

1. **To Do** → BA evaluates, asks questions
2. **Analyse** → Architect creates plan, you approve with `@approve-plan`
3. **Development** → Devs claim tasks, create worktrees, implement, create PRs
4. **Review** → Reviewer validates code, merges develop into feature, comments `@approve` or `@rework`
5. **Review** (on @approve) → PM merges to develop, moves task to Deploy
6. **Deploy** → Tracking only - awaits production deployment
7. **Done** → PM moves after production deploy

## Commands

```bash
# Launch all agents
./start-agents-iterm.sh my-project [num-devs]

# Launch single agent
./start-agent.sh ba my-project
./start-agent.sh architect my-project
./start-agent.sh dev my-project 1
./start-agent.sh dev my-project 2
./start-agent.sh reviewer my-project
./start-agent.sh pm my-project

# Stop all agents
./stop-agents.sh
```

## Documentation

See `docs/` folder for:
- Architecture details
- Setup guide
- Agent reference
- Troubleshooting

## Key Benefits

✅ **True Parallelism** - N features developed simultaneously
✅ **No Conflicts** - Each dev has isolated workspace
✅ **Efficient** - Single dev handles entire task lifecycle
✅ **Scalable** - Add more devs for more throughput
✅ **Quality Gate** - Automated code review before merge
✅ **Clean** - Worktrees auto-created and auto-removed
