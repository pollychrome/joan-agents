# Joan Multi-Agent Orchestration System (v2)

## True Parallel Feature Development with Git Worktrees

This version uses **git worktrees** to enable genuine parallel development. Instead of time-slicing agents across tasks, each Implementation Worker operates in an isolated worktree, allowing multiple features to be developed simultaneously.

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         DEVELOPMENT COLUMN                              │
│                                                                         │
│    Task A          Task B          Task C          Task D               │
│       │               │               │               │                 │
│       ▼               ▼               ▼               ▼                 │
│   Worker #1       Worker #2       Worker #3       Worker #4             │
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

## What Changed from v1

| Aspect | v1 | v2 |
|--------|-----|-----|
| Development agents | 3 (Dev, Design, Test) | N Workers |
| Parallelism | Time-sliced | True parallel |
| Working directory | Single repo | One worktree per task |
| Features in parallel | 1 | N (configurable) |

## Agents

| Agent | Count | Role |
|-------|-------|------|
| Business Analyst | 1 | Evaluates requirements |
| Architect | 1 | Creates implementation plans |
| **Implementation Worker** | **N** | Claims task → creates worktree → implements everything → creates PR → cleans up |
| Project Manager | 1 | Merges to develop, tracks deploys |

## Quick Start

```bash
# Extract to your project
unzip joan-agents-v2.zip

# Copy .claude contents to your project
cp -r joan-agents-v2/.claude/agents/ .claude/agents/
cp -r joan-agents-v2/.claude/commands/ .claude/commands/

# Make scripts executable
chmod +x joan-agents-v2/*.sh

# Launch with 4 parallel workers (default)
./joan-agents-v2/start-agents-iterm.sh my-project

# Or specify number of workers
./joan-agents-v2/start-agents-iterm.sh my-project 6
```

## How Workers Operate

Each Implementation Worker follows this cycle:

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
│   │   ├── implementation-worker.md
│   │   └── project-manager.md
│   └── commands/agents/
│       ├── ba-loop.md
│       ├── architect-loop.md
│       ├── worker-loop.md
│       └── pm-loop.md
├── src/
└── ...

../worktrees/                    # Created automatically
├── task-123/                    # Worker 1's workspace
├── task-456/                    # Worker 2's workspace
├── task-789/                    # Worker 3's workspace
└── task-012/                    # Worker 4's workspace
```

## Resource Recommendations

| Workers | Terminal Windows | RAM | Use Case |
|---------|------------------|-----|----------|
| 2 | 5 | 4-6 GB | Light workload |
| 4 | 7 | 6-10 GB | Standard (recommended) |
| 6 | 9 | 10-14 GB | Heavy workload |

## Workflow

1. **To Do** → BA evaluates, asks questions
2. **Analyse** → Architect creates plan, you approve with `@architect`
3. **Development** → Workers claim tasks, create worktrees, implement
4. **Review** → You review the PRs
5. **Deploy** → PM merges to develop
6. **Done** → PM moves after production deploy

## Commands

```bash
# Launch all agents
./start-agents-iterm.sh my-project [num-workers]

# Launch single agent
./start-agent.sh ba my-project
./start-agent.sh architect my-project  
./start-agent.sh worker my-project 1
./start-agent.sh worker my-project 2
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
✅ **No Conflicts** - Each worker has isolated workspace  
✅ **Efficient** - Single worker handles entire task lifecycle  
✅ **Scalable** - Add more workers for more throughput  
✅ **Clean** - Worktrees auto-created and auto-removed
