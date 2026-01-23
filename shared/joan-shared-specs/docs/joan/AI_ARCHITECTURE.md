# Joan AI Architecture

## Overview

This document describes the unified AI architecture that powers all AI features in Joan. The architecture is designed around a **Tiered Context System** that provides consistent, efficient context to all AI handlers while minimizing token usage and database queries.

## Design Philosophy

### Problem Statement

Before this architecture, each AI feature (Global Chat, Ceremonies, Resource AI) built context independently, leading to:

- **Redundant database queries** - Same data fetched multiple ways
- **Inconsistent context** - Different AI features had different views of user data
- **Token waste** - AI often received more context than needed, or too little
- **Multiple tool calls** - AI had to make many queries to understand the user's situation
- **Fragmented insights** - No shared intelligence layer

### Solution: Tiered Context Architecture

We solved this by creating a unified context layer with three tiers:

```
┌─────────────────────────────────────────────────────────────┐
│                    AI Request Router                         │
│  (Determines which handler + context requirements)           │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│                   AIContextService                           │
│  ┌─────────────────┐ ┌─────────────────┐ ┌───────────────┐ │
│  │   Layer 1       │ │   Layer 2       │ │   Layer 3     │ │
│  │   User Profile  │ │   Active Entity │ │   Insights    │ │
│  │   (~200 tokens) │ │   (~500-1k tok) │ │   (computed)  │ │
│  │                 │ │                 │ │               │ │
│  │ - Basic info    │ │ - Project data  │ │ - Warnings    │ │
│  │ - Stats/metrics │ │ - Milestones    │ │ - Suggestions │ │
│  │ - Always loaded │ │ - Tasks         │ │ - Achievements│ │
│  └─────────────────┘ └─────────────────┘ └───────────────┘ │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│                    AI Handlers                               │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ GlobalChat   │  │ Ceremony     │  │ Resource     │      │
│  │ Handler      │  │ Handler      │  │ Handler      │      │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘      │
└─────────┼─────────────────┼─────────────────┼───────────────┘
          │                 │                 │
┌─────────▼─────────────────▼─────────────────▼───────────────┐
│                Unified Tool Executor                         │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────────────┐   │
│  │ Query Tools │ │ Action Tools│ │ Compound Tools      │   │
│  │ (read only) │ │ (mutations) │ │ (multi-step)        │   │
│  └─────────────┘ └─────────────┘ └─────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

## Core Components

### 1. AIContextService (`/workers/src/services/ai/ai-context-service.ts`)

The central service that builds context for all AI features.

**Responsibilities:**
- Load user profile context (always included)
- Load active entity context based on current page
- Compute insights and recommendations
- Format context for AI prompt injection

**Usage:**
```typescript
import { createAIContextService } from '../services/ai';

const contextService = createAIContextService(db, userId);
const context = await contextService.buildContext({
  page: 'project',
  projectId: '...',
  milestoneId: '...'  // optional
});

// Format for system prompt
const contextString = contextService.formatForPrompt(context);
```

**Tiered Loading:**

| Tier | What's Included | When Loaded | Token Cost |
|------|-----------------|-------------|------------|
| Layer 1 | User name, stats, metrics | Always | ~200 |
| Layer 2 | Project/milestone/task details | Based on page context | ~500-1000 |
| Layer 3 | Deep insights, recommendations | Computed from L1+L2 | ~100-200 |

### 2. AIInsightsEngine (`/workers/src/services/ai/ai-insights-engine.ts`)

Generates computed recommendations and pattern detection.

**Capabilities:**
- Workload analysis (capacity assessment)
- Deadline tracking (overdue, at-risk items)
- Progress monitoring (velocity, trends)
- Priority suggestions
- Daily focus recommendations

**Usage:**
```typescript
import { createAIInsightsEngine } from '../services/ai';

const insightsEngine = createAIInsightsEngine(db, userId);
const insights = await insightsEngine.generateEnhancedInsights();

// For ceremonies that need deep analysis
const formatted = insightsEngine.formatInsightsForPrompt(insights);
```

### 3. AIToolRegistry (`/workers/src/services/ai/ai-tool-registry.ts`)

Centralized registry of all tools available to AI.

**Tool Categories:**

| Category | Purpose | Examples |
|----------|---------|----------|
| Query | Read operations | `get_user_tasks`, `get_project_milestones` |
| Action | Write operations | `create_task`, `update_milestone` |
| Compound | Multi-step operations | `plan_milestone`, `analyze_workload` |

**Features:**
- Schema validation for all tool inputs
- Context requirement checking
- Format conversion for OpenAI/Anthropic APIs
- Sanitization and error handling

**Usage:**
```typescript
import { getToolRegistry } from '../services/ai';

const registry = getToolRegistry();

// Get tools formatted for AI provider
const tools = registry.formatForAnthropic();

// Validate tool input before execution
const validation = registry.validateInput('create_task', input);
if (!validation.valid) {
  console.error(validation.errors);
}

// Check if tool can execute with current context
const { canExecute, missingContext } = registry.canExecuteWithContext('get_project_milestones', context);
```

## Data Flow

### Request Flow

```
1. User sends message (frontend)
        │
        ▼
2. API receives request with context
   {
     message: "Help me plan this milestone",
     context: { page: 'project', projectId: '...' }
   }
        │
        ▼
3. AIContextService builds tiered context
   - Load user profile (Layer 1)
   - Load project + milestones (Layer 2)
   - Compute insights (Layer 3)
        │
        ▼
4. Handler builds system prompt with:
   - Base identity/guidelines
   - Formatted context
   - Tool definitions
        │
        ▼
5. AI Provider called with message + tools
        │
        ▼
6. If tool calls returned:
   - Validate input via AIToolRegistry
   - Execute via Tool Executor
   - Return results to AI
   - Continue conversation
        │
        ▼
7. Response sent to user
```

### Context Request Interface

```typescript
interface ContextRequest {
  // Which page the user is on
  page: 'dashboard' | 'project' | 'milestone' | 'task' | 'goals' | 'notes' | 'schedule' | 'ceremony' | 'other';

  // Entity IDs for context loading
  projectId?: string;
  milestoneId?: string;
  taskId?: string;
  ceremonyId?: string;

  // Optional: Frontend can pass preloaded data to avoid re-fetching
  preloadedData?: {
    project?: { name: string; description?: string; status?: string };
    milestone?: { name: string; targetDate?: string; progress?: number };
    task?: { title: string; status?: string; priority?: string };
  };
}
```

## Tool Design Philosophy

### Semantic vs CRUD Tools

**Old Approach (CRUD):**
```
User: "Help me plan the authentication feature"

AI needs to:
1. get_user_projects → find project
2. get_project_milestones → check existing
3. create_milestone → make new one
4. create_task × 5 → add tasks

= 8 tool calls, slow, error-prone
```

**New Approach (Semantic):**
```
User: "Help me plan the authentication feature"

AI uses:
1. plan_milestone {
     project_id: <from context>,
     title: "User Authentication",
     suggested_tasks: [...]
   }

= 1 tool call, fast, validated
```

### Tool Definition Structure

```typescript
interface ToolDefinition {
  name: string;
  category: 'query' | 'action' | 'compound';
  description: string;  // For AI understanding
  parameters: JSONSchema;
  requiresContext: ('project' | 'milestone' | 'task')[];
  examples?: Array<{
    userIntent: string;
    toolCall: Record<string, any>;
  }>;
}
```

## Integration Points

### Global Chat Handler

```typescript
// In GlobalChatHandler
async handleMessage(message: string, context: ContextRequest) {
  // Build unified context
  const aiContext = await this.contextService.buildContext(context);

  // Build system prompt with context
  const systemPrompt = this.buildSystemPrompt(aiContext);

  // Get tools from registry
  const tools = getToolRegistry().formatForAnthropic();

  // Call AI provider...
}
```

### Ceremony Handler

```typescript
// Ceremonies get enhanced insights for planning
async handleCeremonyChat(sessionId: string, message: string) {
  const context = await this.contextService.buildContext({
    page: 'ceremony',
    ceremonyId: sessionId
  });

  // For planning ceremonies, add deep insights
  if (this.ceremonyRequiresInsights()) {
    const insights = await this.insightsEngine.generateEnhancedInsights();
    const insightsText = this.insightsEngine.formatInsightsForPrompt(insights);
    // Add to system prompt...
  }
}
```

### Resource AI

```typescript
// Resource generation uses focused context
async generateResources(milestoneId: string) {
  const context = await this.contextService.buildContext({
    page: 'milestone',
    milestoneId
  });

  // Use milestone context + project context for resource suggestions
}
```

## File Structure

```
workers/src/services/ai/
├── index.ts                 # Public exports
├── ai-context-service.ts    # Tiered context building
├── ai-insights-engine.ts    # Computed recommendations
├── ai-tool-registry.ts      # Tool definitions & validation
│
├── handlers/
│   ├── global-chat-handler.ts    # Conversational AI
│   ├── ceremony-handler.ts       # Ceremony-specific AI
│   └── resource-handler.ts       # Resource generation AI
│
└── tools/
    ├── query-tools.ts       # Read operations
    ├── action-tools.ts      # Write operations
    └── compound-tools.ts    # Multi-step operations
```

## Performance Considerations

### Context Caching

Within a conversation, context can be cached to avoid re-fetching:

```typescript
class AIContextService {
  private cache: Map<string, { context: AIContext; expiry: number }>;

  async buildContext(request: ContextRequest): Promise<AIContext> {
    const cacheKey = this.getCacheKey(request);
    const cached = this.cache.get(cacheKey);

    if (cached && cached.expiry > Date.now()) {
      return cached.context;
    }

    // Build fresh context...
  }
}
```

### Parallel Loading

Context tiers are loaded in parallel where possible:

```typescript
const [userProfile, activeEntity] = await Promise.all([
  this.getUserProfile(),
  this.getActiveEntity(request)
]);
```

### Token Optimization

- Layer 1 is always compact (~200 tokens)
- Layer 2 includes only relevant entities
- Insights are computed summaries, not raw data
- Tool results are sanitized to remove unnecessary fields

## Future Enhancements

### Phase 2: Context Enrichment
- Add conversation memory summaries
- Implement cross-session learning
- Add user preference learning

### Phase 3: Proactive AI
- Background pattern detection
- Push-based suggestions
- Risk alerts before deadlines

### Phase 4: Team Context
- Multi-user project context
- Role-based tool access
- Collaborative AI sessions

## Related Documentation

- [Agentic Ceremony Architecture](./AGENTIC_CEREMONY_ARCHITECTURE.md) - Ceremony-specific AI details
- [MCP Setup](./MCP_SETUP.md) - External AI tool integration
- [OpenAI Setup](./OPENAI_SETUP.md) - Provider configuration

## Changelog

- **2024-11-29**: Initial unified AI architecture implemented
  - Created AIContextService with tiered context
  - Created AIInsightsEngine for computed recommendations
  - Created AIToolRegistry for centralized tool management
