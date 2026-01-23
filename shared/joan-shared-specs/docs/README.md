# Documentation Index

Navigate to the relevant section for your use case.

## Categories

| Category | Description | Audience |
|----------|-------------|----------|
| [**workflow/**](./workflow/) | Agent orchestration, tags, transitions, ALS syntax | Agent developers |
| [**human-interface/**](./human-interface/) | Inbox queue, frontend components, UX | Frontend developers |
| [**integration/**](./integration/) | System tags, API mappings, MCP bridge | Backend developers |
| [**reference/**](./reference/) | Alignment gaps, pending decisions | All teams |

## Document Map

```
docs/
├── workflow/
│   ├── agentic-workflow.md       # Core tag-driven workflow
│   ├── als-spec.md               # Comment syntax for auditability
│   └── worker-result-schema.md   # Worker output format and context handoffs
├── human-interface/
│   ├── human-inbox.md         # Unified inbox queue
│   └── frontend-inbox-features.md  # Frontend components
├── integration/
│   ├── system-tags-and-enablement.md  # Tag definitions
│   ├── mcp-api-map.md         # MCP → Joan API mappings
│   └── mcp-column-management.md  # MCP column management behaviors
└── reference/
    └── alignment-gaps.md      # Known gaps and decisions
```

## Cross-Repo Sources

These specs consolidate information from:

| Repo | Source Paths |
|------|--------------|
| joan-agents | `.claude/agents/*.md`, `.claude/commands/agents/*.md`, `README.md` |
| Joan | `workers/src/services/inboxService.ts`, `frontend/src/hooks/useSystemTags.ts`, `migrations/037_system_tags.sql`, `migrations/039_missing_workflow_tags.sql` |
| joan-mcp | `src/tools/*.ts`, `src/resources/*.ts`, `src/client/api-client.ts` |
