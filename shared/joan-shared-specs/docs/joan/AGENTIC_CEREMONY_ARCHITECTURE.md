# Agentic Ceremony Architecture

## Overview

This document describes the architecture for adding **chat-based, agentic AI** capabilities to Joan's ceremony system. The AI assistant can have multi-turn conversations, access user data through tools, ask clarifying questions, and help users accomplish ceremony goals more naturally.

## Design Principles

1. **Additive, not Replacement** - Chat enhances existing ceremonies, doesn't replace them
2. **Tool-Based Access** - AI accesses data through defined tools, not raw DB access
3. **Streaming First** - All AI responses stream for better UX
4. **Context Aware** - Conversations maintain context across turns
5. **Provider Agnostic** - Works with OpenAI, Anthropic, or other providers

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                        FRONTEND                                      │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │                    CeremonyChatRunner                         │  │
│  │  ┌─────────────┐  ┌────────────────────────────────────────┐ │  │
│  │  │  Ceremony   │  │           Chat Panel                    │ │  │
│  │  │  Component  │  │  ┌──────────────────────────────────┐  │ │  │
│  │  │  (optional) │  │  │ AI: I'll help plan your day...   │  │ │  │
│  │  │             │  │  │ [fetching tasks...]              │  │ │  │
│  │  │ ┌─────────┐ │  │  │ AI: You have 8 tasks. I notice   │  │ │  │
│  │  │ │Schedule │ │  │  │     Task X has no estimate...    │  │ │  │
│  │  │ │ Preview │ │  │  │ User: About 2 hours              │  │ │  │
│  │  │ └─────────┘ │  │  │ AI: Got it! Here's my suggested  │  │ │  │
│  │  │             │  │  │     schedule: [schedule card]    │  │ │  │
│  │  └─────────────┘  │  └──────────────────────────────────┘  │ │  │
│  │                    │  ┌──────────────────────────────────┐  │ │  │
│  │                    │  │ [Type message...] [Send]         │  │ │  │
│  │                    │  └──────────────────────────────────┘  │ │  │
│  └──────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    │ WebSocket / SSE
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        BACKEND (Workers)                             │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │                   Ceremony Chat Handler                       │  │
│  │                                                               │  │
│  │  1. Receive user message                                      │  │
│  │  2. Load conversation history from DB                         │  │
│  │  3. Build prompt with tools + context                         │  │
│  │  4. Call AI provider (streaming)                              │  │
│  │  5. If tool_use → Execute tool → Feed result back             │  │
│  │  6. Stream response to frontend                               │  │
│  │  7. Save messages to DB                                       │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                          │                                          │
│                          ▼                                          │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │                     Tool Executor                             │  │
│  │                                                               │  │
│  │  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐             │  │
│  │  │ get_tasks   │ │get_projects │ │get_schedule │             │  │
│  │  └─────────────┘ └─────────────┘ └─────────────┘             │  │
│  │  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐             │  │
│  │  │create_task  │ │update_task  │ │add_schedule │             │  │
│  │  └─────────────┘ └─────────────┘ │   _block    │             │  │
│  │  ┌─────────────┐ ┌─────────────┐ └─────────────┘             │  │
│  │  │ get_goals   │ │ get_notes   │                             │  │
│  │  └─────────────┘ └─────────────┘                             │  │
│  └──────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        AI PROVIDERS                                  │
│                                                                      │
│   ┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐        │
│   │ OpenAI  │    │Anthropic│    │  Groq   │    │ Ollama  │        │
│   │ GPT-4o  │    │ Claude  │    │ Llama   │    │ Local   │        │
│   └─────────┘    └─────────┘    └─────────┘    └─────────┘        │
│                                                                      │
│   All providers support:                                            │
│   - Tool/Function calling                                           │
│   - Streaming responses                                             │
│   - Multi-turn conversations                                        │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Database Schema Changes

### New Table: `ceremony_chat_messages`

```sql
CREATE TABLE ceremony_chat_messages (
  id TEXT PRIMARY KEY,
  session_id TEXT NOT NULL REFERENCES ceremony_sessions(id) ON DELETE CASCADE,
  role TEXT NOT NULL CHECK(role IN ('user', 'assistant', 'tool', 'system')),
  content TEXT,  -- Text content (null for tool calls)
  tool_calls TEXT,  -- JSON array of tool calls (for assistant messages)
  tool_call_id TEXT,  -- For tool result messages
  tool_name TEXT,  -- For tool result messages
  created_at TEXT NOT NULL DEFAULT (datetime('now')),

  -- Metadata
  model_used TEXT,
  tokens_input INTEGER,
  tokens_output INTEGER,
  latency_ms INTEGER
);

CREATE INDEX idx_chat_messages_session ON ceremony_chat_messages(session_id, created_at);
```

### New Table: `ceremony_tool_executions`

```sql
CREATE TABLE ceremony_tool_executions (
  id TEXT PRIMARY KEY,
  session_id TEXT NOT NULL REFERENCES ceremony_sessions(id) ON DELETE CASCADE,
  message_id TEXT REFERENCES ceremony_chat_messages(id),
  tool_name TEXT NOT NULL,
  tool_input TEXT NOT NULL,  -- JSON
  tool_output TEXT,  -- JSON
  execution_ms INTEGER,
  status TEXT NOT NULL CHECK(status IN ('pending', 'success', 'error')),
  error_message TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
```

### Modify: `ceremony_sessions`

```sql
ALTER TABLE ceremony_sessions ADD COLUMN chat_mode INTEGER DEFAULT 0;
ALTER TABLE ceremony_sessions ADD COLUMN chat_context TEXT;  -- JSON for persistent context
```

---

## Tool Definitions

### Core Tools

```typescript
// workers/src/services/ceremony-tools.ts

export interface ToolDefinition {
  name: string;
  description: string;
  parameters: {
    type: 'object';
    properties: Record<string, any>;
    required?: string[];
  };
}

export const CEREMONY_TOOLS: Record<string, ToolDefinition> = {
  // ============= READ TOOLS =============

  get_user_tasks: {
    name: 'get_user_tasks',
    description: 'Get the user\'s tasks. Can filter by project, status, due date, or priority.',
    parameters: {
      type: 'object',
      properties: {
        project_id: {
          type: 'string',
          description: 'Filter by specific project ID'
        },
        status: {
          type: 'string',
          enum: ['todo', 'in_progress', 'done', 'blocked'],
          description: 'Filter by task status'
        },
        due_date: {
          type: 'string',
          description: 'Filter tasks due on or before this date (ISO format)'
        },
        priority: {
          type: 'string',
          enum: ['low', 'medium', 'high', 'urgent'],
          description: 'Filter by priority level'
        },
        limit: {
          type: 'number',
          description: 'Maximum number of tasks to return (default 20)'
        }
      }
    }
  },

  get_user_projects: {
    name: 'get_user_projects',
    description: 'Get the user\'s active projects with their priority and task counts.',
    parameters: {
      type: 'object',
      properties: {
        include_archived: {
          type: 'boolean',
          description: 'Include archived projects (default false)'
        }
      }
    }
  },

  get_task_details: {
    name: 'get_task_details',
    description: 'Get detailed information about a specific task including subtasks, notes, and time estimates.',
    parameters: {
      type: 'object',
      properties: {
        task_id: {
          type: 'string',
          description: 'The ID of the task to retrieve'
        }
      },
      required: ['task_id']
    }
  },

  get_daily_schedule: {
    name: 'get_daily_schedule',
    description: 'Get the user\'s scheduled blocks for a specific date.',
    parameters: {
      type: 'object',
      properties: {
        date: {
          type: 'string',
          description: 'The date to get schedule for (ISO format, defaults to today)'
        }
      }
    }
  },

  get_user_goals: {
    name: 'get_user_goals',
    description: 'Get the user\'s active goals with progress information.',
    parameters: {
      type: 'object',
      properties: {
        timeframe: {
          type: 'string',
          enum: ['daily', 'weekly', 'monthly', 'quarterly', 'yearly'],
          description: 'Filter by goal timeframe'
        }
      }
    }
  },

  get_recent_notes: {
    name: 'get_recent_notes',
    description: 'Get the user\'s recent notes, optionally filtered by folder.',
    parameters: {
      type: 'object',
      properties: {
        folder_id: {
          type: 'string',
          description: 'Filter by specific folder'
        },
        limit: {
          type: 'number',
          description: 'Maximum number of notes to return (default 10)'
        }
      }
    }
  },

  // ============= WRITE TOOLS =============

  update_task: {
    name: 'update_task',
    description: 'Update a task\'s properties like estimate, priority, due date, or status.',
    parameters: {
      type: 'object',
      properties: {
        task_id: {
          type: 'string',
          description: 'The ID of the task to update'
        },
        estimated_minutes: {
          type: 'number',
          description: 'Time estimate in minutes'
        },
        priority: {
          type: 'string',
          enum: ['low', 'medium', 'high', 'urgent']
        },
        due_date: {
          type: 'string',
          description: 'Due date (ISO format)'
        },
        status: {
          type: 'string',
          enum: ['todo', 'in_progress', 'done', 'blocked']
        }
      },
      required: ['task_id']
    }
  },

  create_task: {
    name: 'create_task',
    description: 'Create a new task for the user.',
    parameters: {
      type: 'object',
      properties: {
        title: {
          type: 'string',
          description: 'The task title'
        },
        description: {
          type: 'string',
          description: 'Task description or notes'
        },
        project_id: {
          type: 'string',
          description: 'Project to assign the task to'
        },
        priority: {
          type: 'string',
          enum: ['low', 'medium', 'high', 'urgent']
        },
        due_date: {
          type: 'string',
          description: 'Due date (ISO format)'
        },
        estimated_minutes: {
          type: 'number',
          description: 'Time estimate in minutes'
        }
      },
      required: ['title']
    }
  },

  create_schedule_block: {
    name: 'create_schedule_block',
    description: 'Add a time block to the user\'s daily schedule.',
    parameters: {
      type: 'object',
      properties: {
        task_id: {
          type: 'string',
          description: 'Optional task ID to link to this block'
        },
        title: {
          type: 'string',
          description: 'Block title (required if no task_id)'
        },
        date: {
          type: 'string',
          description: 'Date for the block (ISO format)'
        },
        start_time: {
          type: 'string',
          description: 'Start time (HH:MM format)'
        },
        duration_minutes: {
          type: 'number',
          description: 'Duration in minutes'
        },
        block_type: {
          type: 'string',
          enum: ['work', 'break', 'meeting', 'personal'],
          description: 'Type of schedule block'
        }
      },
      required: ['date', 'start_time', 'duration_minutes']
    }
  },

  create_note: {
    name: 'create_note',
    description: 'Create a new note for the user.',
    parameters: {
      type: 'object',
      properties: {
        title: {
          type: 'string',
          description: 'Note title'
        },
        content: {
          type: 'string',
          description: 'Note content (markdown supported)'
        },
        folder_id: {
          type: 'string',
          description: 'Folder to save the note in'
        }
      },
      required: ['title', 'content']
    }
  },

  // ============= CEREMONY-SPECIFIC TOOLS =============

  save_ceremony_output: {
    name: 'save_ceremony_output',
    description: 'Save structured output from the ceremony session (like a generated schedule or plan).',
    parameters: {
      type: 'object',
      properties: {
        output_type: {
          type: 'string',
          enum: ['schedule', 'task_list', 'summary', 'plan'],
          description: 'Type of output being saved'
        },
        data: {
          type: 'object',
          description: 'The structured data to save'
        }
      },
      required: ['output_type', 'data']
    }
  },

  complete_ceremony: {
    name: 'complete_ceremony',
    description: 'Mark the ceremony as complete. Call this when the user is satisfied with the results.',
    parameters: {
      type: 'object',
      properties: {
        summary: {
          type: 'string',
          description: 'Brief summary of what was accomplished'
        }
      }
    }
  }
};
```

---

## Backend API Design

### New Endpoints

```typescript
// workers/src/routes/ceremony-chat.ts

// POST /ceremonies/sessions/:id/chat
// Send a message and get AI response (streaming)
interface ChatRequest {
  message: string;
  context?: Record<string, any>;  // Additional context for this turn
}

// Response is Server-Sent Events (SSE) stream:
// event: message_start
// data: {"id": "msg_123"}
//
// event: content_delta
// data: {"delta": "I'll help you"}
//
// event: tool_use
// data: {"tool": "get_user_tasks", "input": {...}}
//
// event: tool_result
// data: {"tool": "get_user_tasks", "result": [...]}
//
// event: message_end
// data: {"tokens_input": 150, "tokens_output": 200}


// GET /ceremonies/sessions/:id/chat/history
// Get conversation history for a session
interface ChatHistoryResponse {
  messages: ChatMessage[];
  context: Record<string, any>;
}

// POST /ceremonies/sessions/:id/chat/regenerate
// Regenerate the last assistant response
interface RegenerateRequest {
  message_id: string;
}
```

### Chat Handler Service

```typescript
// workers/src/services/ceremony-chat-handler.ts

export class CeremonyChatHandler {
  constructor(
    private db: D1Database,
    private userId: string,
    private sessionId: string
  ) {}

  async handleMessage(
    userMessage: string,
    onStream: (chunk: StreamChunk) => void
  ): Promise<void> {
    // 1. Load conversation history
    const history = await this.loadHistory();

    // 2. Load ceremony context (template, current state)
    const context = await this.loadCeremonyContext();

    // 3. Build system prompt with tools
    const systemPrompt = this.buildSystemPrompt(context);

    // 4. Save user message
    await this.saveMessage('user', userMessage);

    // 5. Call AI with streaming
    const response = await this.callAI({
      systemPrompt,
      messages: history,
      tools: this.getToolsForCeremony(context.template),
      onStream
    });

    // 6. Handle tool calls if any
    while (response.stopReason === 'tool_use') {
      for (const toolCall of response.toolCalls) {
        // Execute tool
        const result = await this.executeTool(toolCall);

        // Stream tool result to frontend
        onStream({ type: 'tool_result', tool: toolCall.name, result });

        // Continue conversation with tool result
        response = await this.continueWithToolResult(toolCall, result, onStream);
      }
    }

    // 7. Save assistant response
    await this.saveMessage('assistant', response.content, response.toolCalls);
  }

  private async executeTool(toolCall: ToolCall): Promise<any> {
    const executor = new ToolExecutor(this.db, this.userId, this.sessionId);
    return executor.execute(toolCall.name, toolCall.input);
  }
}
```

---

## Frontend Components

### CeremonyChatRunner

```typescript
// frontend/src/components/ceremony/CeremonyChatRunner.tsx

interface CeremonyChatRunnerProps {
  sessionId: string;
  template: CeremonyTemplate;
  onComplete: () => void;
}

export function CeremonyChatRunner({ sessionId, template, onComplete }: Props) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [currentOutput, setCurrentOutput] = useState<CeremonyOutput | null>(null);

  const sendMessage = async (content: string) => {
    // Add user message immediately
    setMessages(prev => [...prev, { role: 'user', content }]);
    setIsStreaming(true);

    // Create EventSource for streaming
    const response = await fetch(`/api/v1/ceremonies/sessions/${sessionId}/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: content })
    });

    const reader = response.body?.getReader();
    let assistantMessage = { role: 'assistant', content: '' };

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      const chunk = parseSSE(value);

      if (chunk.type === 'content_delta') {
        assistantMessage.content += chunk.delta;
        setMessages(prev => [...prev.slice(0, -1), assistantMessage]);
      }

      if (chunk.type === 'tool_use') {
        // Show tool execution indicator
      }

      if (chunk.type === 'ceremony_output') {
        setCurrentOutput(chunk.data);
      }
    }

    setIsStreaming(false);
  };

  return (
    <div className="flex h-full">
      {/* Optional: Side panel with ceremony output preview */}
      {currentOutput && (
        <div className="w-1/3 border-r">
          <CeremonyOutputPreview output={currentOutput} />
        </div>
      )}

      {/* Chat panel */}
      <div className="flex-1 flex flex-col">
        <ChatMessageList messages={messages} isStreaming={isStreaming} />
        <ChatInput onSend={sendMessage} disabled={isStreaming} />
      </div>
    </div>
  );
}
```

### ChatMessageList

```typescript
// frontend/src/components/ceremony/chat/ChatMessageList.tsx

export function ChatMessageList({ messages, isStreaming }: Props) {
  return (
    <div className="flex-1 overflow-y-auto p-4 space-y-4">
      {messages.map((msg, i) => (
        <ChatMessage key={i} message={msg} />
      ))}
      {isStreaming && <StreamingIndicator />}
    </div>
  );
}

function ChatMessage({ message }: { message: ChatMessage }) {
  if (message.role === 'user') {
    return (
      <div className="flex justify-end">
        <div className="bg-purple-600 text-white rounded-lg px-4 py-2 max-w-[80%]">
          {message.content}
        </div>
      </div>
    );
  }

  return (
    <div className="flex gap-3">
      <div className="w-8 h-8 bg-purple-100 rounded-full flex items-center justify-center">
        <Sparkles className="w-4 h-4 text-purple-600" />
      </div>
      <div className="flex-1">
        <Markdown content={message.content} />
        {message.toolCalls && (
          <ToolCallsDisplay toolCalls={message.toolCalls} />
        )}
      </div>
    </div>
  );
}
```

---

## Ceremony-Specific System Prompts

```typescript
// workers/src/services/ceremony-chat-prompts.ts

export const CEREMONY_SYSTEM_PROMPTS: Record<string, string> = {
  'daily-planning': `You are Joan, a productivity assistant helping the user plan their day.

Your goal is to help create an effective daily schedule by:
1. Understanding the user's tasks and priorities
2. Identifying tasks with missing information (estimates, priorities)
3. Suggesting an optimized schedule based on energy patterns
4. Creating schedule blocks for approved tasks

IMPORTANT GUIDELINES:
- Always start by fetching the user's tasks for today
- Ask about missing time estimates for important tasks
- Consider energy patterns (deep work in morning, admin in afternoon)
- Leave buffer time between blocks (10-15 min)
- Suggest breaks every 90 minutes of focused work
- Don't schedule more than 6 hours of focused work

When you have enough information, propose a schedule and ask for approval before creating it.`,

  'weekly-review': `You are Joan, helping the user conduct their weekly review.

Guide them through:
1. Reviewing completed tasks from the past week
2. Identifying incomplete tasks and deciding their fate
3. Celebrating wins and acknowledging challenges
4. Setting intentions for the upcoming week

Be encouraging but realistic. Help them learn from patterns.`,

  'brainstorm': `You are Joan, facilitating a brainstorming session.

Help the user:
1. Generate ideas freely without judgment
2. Organize ideas into themes
3. Identify actionable items
4. Convert promising ideas into tasks

Use techniques like "Yes, and..." to build on ideas.`
};
```

---

## Implementation Phases

### Phase 1: Foundation (Week 1)
- [ ] Create database migration for chat tables
- [ ] Implement basic chat endpoint (non-streaming)
- [ ] Create tool executor service
- [ ] Implement 3 core tools: get_tasks, get_projects, get_schedule

### Phase 2: Streaming & UI (Week 2)
- [ ] Add SSE streaming to chat endpoint
- [ ] Create CeremonyChatRunner component
- [ ] Create ChatMessageList and ChatInput components
- [ ] Add tool execution indicators in UI

### Phase 3: Full Tool Set (Week 3)
- [ ] Implement all read tools
- [ ] Implement write tools with confirmation UI
- [ ] Add ceremony output preview panel
- [ ] Implement save_ceremony_output tool

### Phase 4: Polish & Integration (Week 4)
- [ ] Add ceremony-specific system prompts
- [ ] Integrate with existing ceremony templates
- [ ] Add "chat mode" toggle to ceremonies
- [ ] Error handling and edge cases
- [ ] Mobile responsiveness

---

## Example Conversation Flow

### Daily Planning Ceremony

```
SYSTEM: [Daily Planning prompt with tools]

AI: Good morning! I'll help you plan your day. Let me check your tasks...
    [Tool: get_user_tasks] → 12 tasks found

AI: You have 12 tasks across 3 projects. I notice a few things:

    **High Priority:**
    - "Finish API documentation" (Project: Joan) - No time estimate
    - "Review PR #42" (Project: Joan) - 30 min estimate

    **Missing Estimates:**
    - "Research caching strategies" - How long do you think this will take?

USER: The API docs will probably take about 2 hours. The research maybe 45 minutes.

AI: Got it, I'll update those estimates.
    [Tool: update_task {task_id: "...", estimated_minutes: 120}]
    [Tool: update_task {task_id: "...", estimated_minutes: 45}]

AI: Based on your tasks and typical energy patterns, here's my suggested schedule:

    **Morning (High Focus)**
    - 9:00 - 11:00: Finish API documentation (2h)
    - 11:00 - 11:15: Break
    - 11:15 - 12:00: Research caching strategies (45m)

    **Afternoon**
    - 1:00 - 1:30: Review PR #42 (30m)
    - 1:30 - 2:30: [Open block for meetings/admin]

    Would you like me to create this schedule, or would you like to adjust anything?

USER: Looks good, but can we swap the research and PR review? I have a meeting at 11.

AI: Of course! Updated schedule:

    **Morning**
    - 9:00 - 11:00: Finish API documentation (2h)
    - 11:00 - 12:00: Meeting

    **Afternoon**
    - 1:00 - 1:30: Review PR #42 (30m)
    - 1:30 - 2:15: Research caching strategies (45m)

    Should I create these schedule blocks now?

USER: Yes, please!

AI: [Tool: create_schedule_block {...}] x4

    Done! I've added 4 blocks to your schedule for today.
    You can view them in the Schedule tab.

    Is there anything else you'd like to adjust, or shall we wrap up?

USER: That's perfect, thanks!

AI: [Tool: complete_ceremony {summary: "Created daily schedule with 4 focused blocks..."}]

    Great! Your day is planned. Good luck with the API documentation!
    Remember to take that break at 11:15 - your brain will thank you.
```

---

## Security Considerations

1. **Tool Authorization**: All tools validate user ownership of resources
2. **Rate Limiting**: Max 50 messages per session, 10 tool calls per message
3. **Input Validation**: All tool inputs validated with Zod schemas
4. **Audit Logging**: All tool executions logged to `ceremony_tool_executions`
5. **Session Isolation**: Users can only access their own sessions

---

## Future Enhancements

1. **Voice Input**: Add speech-to-text for hands-free planning
2. **Proactive Suggestions**: AI notices patterns and suggests improvements
3. **Cross-Ceremony Context**: Reference past ceremonies in new ones
4. **Team Ceremonies**: Collaborative planning sessions
5. **MCP Server**: Expose tools via MCP for external AI clients
