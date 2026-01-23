# Joan: Cloudflare Workers + D1 Migration Plan

## Executive Summary

This document outlines the migration of Joan's FastAPI/SQLite backend to Cloudflare Workers with D1 database for cost optimization while maintaining full functionality.

## Current Architecture

### Backend Stack
- **Runtime**: Python 3.x with FastAPI
- **Database**: SQLite with async SQLAlchemy
- **Auth**: JWT-based authentication with bcrypt password hashing
- **File Storage**: Local filesystem (`./attachments`)
- **LLM Integration**: Multi-provider support (OpenAI, Anthropic, Local Ollama)

### Database Models (15 total)
| Model | Description | Complexity |
|-------|-------------|------------|
| User, UserSettings | Authentication & preferences | Medium |
| Task, TaskActivity, KanbanBoard | Task management | High |
| Goal, TaskGoalLink | Goal tracking | Medium |
| Note | Note-taking with markdown | Low |
| Folder | Hierarchical organization | Low |
| Client, Project, ProjectMembership | Client/project management | High |
| PomodoroSession, PomodoroSettings | Timer functionality | Low |
| DailySchedule, DailyScheduleTask | Schedule management | Medium |
| Ceremony* (Template, Component, Session) | Ceremonies feature | High |
| PersonalActivity | Activity tracking | Low |
| AIWorkflow* (Template, Execution, Step, Config, Metrics, PromptLibrary) | AI orchestration | High |
| TaskResource | Resource attachments | Low |

### API Modules (18 total)
- **Core**: auth, settings, onboarding
- **Features**: tasks, goals, notes, folders, clients, projects
- **Productivity**: pomodoro, daily_schedule, personal_activities
- **AI**: ai_unified, llm_manager
- **Ceremonies**: ceremonies, ceremony_templates, admin_ceremonies
- **Analytics**: analytics

---

## Target Architecture

### Cloudflare Stack
- **Compute**: Cloudflare Workers (JavaScript/TypeScript)
- **Database**: D1 (SQLite-compatible)
- **File Storage**: R2 (S3-compatible object storage)
- **Auth**: Workers + D1 with JWT (jose library)
- **Frontend**: Pages (static assets)

### Architecture Diagram
```
┌─────────────────────┐         ┌─────────────────────┐
│  Cloudflare Pages   │         │  Cloudflare Workers │
│   (React Frontend)  │ ──────> │   (API Backend)     │
└─────────────────────┘         └─────────────────────┘
                                        │
                    ┌───────────────────┼───────────────────┐
                    │                   │                   │
                    v                   v                   v
            ┌──────────────┐   ┌──────────────┐   ┌──────────────┐
            │     D1       │   │     R2       │   │   External   │
            │  (Database)  │   │   (Files)    │   │   LLM APIs   │
            └──────────────┘   └──────────────┘   └──────────────┘
```

---

## Migration Phases

### Phase 1: Infrastructure Setup
**Estimated complexity: Low**

1. **Create Cloudflare resources**
   - [ ] Create D1 database
   - [ ] Create R2 bucket for file attachments
   - [ ] Configure wrangler.toml for Workers + Pages

2. **Project structure**
   ```
   /Joan
   ├── frontend/           # Existing React app
   ├── workers/            # NEW: Cloudflare Workers
   │   ├── src/
   │   │   ├── index.ts    # Main entry point
   │   │   ├── routes/     # API route handlers
   │   │   ├── models/     # D1 query helpers
   │   │   ├── middleware/ # Auth, CORS, etc.
   │   │   └── utils/      # Helpers
   │   ├── wrangler.toml
   │   └── package.json
   └── migrations/         # D1 schema migrations
   ```

3. **Dependencies**
   ```json
   {
     "dependencies": {
       "hono": "^4.0.0",        // Fast web framework for Workers
       "jose": "^5.0.0",         // JWT handling
       "zod": "^3.22.0",         // Schema validation
       "bcryptjs": "^2.4.3"      // Password hashing (pure JS)
     }
   }
   ```

### Phase 2: Database Migration
**Estimated complexity: Medium**

1. **Schema conversion**
   - Convert SQLAlchemy models to D1 SQL schema
   - Preserve UUID primary keys (stored as TEXT)
   - Maintain relationship integrity

2. **Sample D1 Schema**
   ```sql
   -- Users table
   CREATE TABLE users (
     id TEXT PRIMARY KEY,
     email TEXT UNIQUE NOT NULL,
     hashed_password TEXT NOT NULL,
     name TEXT,
     is_active INTEGER DEFAULT 1,
     is_superuser INTEGER DEFAULT 0,
     role TEXT DEFAULT 'member',
     onboarding_completed INTEGER DEFAULT 0,
     onboarding_progress TEXT,  -- JSON string
     first_login_at TEXT,
     created_at TEXT DEFAULT (datetime('now')),
     updated_at TEXT DEFAULT (datetime('now'))
   );

   -- User settings
   CREATE TABLE user_settings (
     id TEXT PRIMARY KEY,
     user_id TEXT UNIQUE REFERENCES users(id),
     theme TEXT DEFAULT 'system',
     notifications_enabled INTEGER DEFAULT 1,
     default_work_duration INTEGER DEFAULT 25,
     default_break_duration INTEGER DEFAULT 5,
     openai_api_key_encrypted TEXT,
     anthropic_api_key_encrypted TEXT,
     local_llm_enabled INTEGER DEFAULT 0,
     local_llm_url TEXT,
     local_llm_model TEXT,
     created_at TEXT DEFAULT (datetime('now')),
     updated_at TEXT DEFAULT (datetime('now'))
   );

   -- Tasks
   CREATE TABLE tasks (
     id TEXT PRIMARY KEY,
     user_id TEXT REFERENCES users(id),
     title TEXT NOT NULL,
     description TEXT,
     status TEXT DEFAULT 'pending',
     priority INTEGER DEFAULT 0,
     due_date TEXT,
     completed_at TEXT,
     folder_id TEXT REFERENCES folders(id),
     project_id TEXT REFERENCES projects(id),
     created_at TEXT DEFAULT (datetime('now')),
     updated_at TEXT DEFAULT (datetime('now'))
   );

   -- Add indexes for common queries
   CREATE INDEX idx_tasks_user_id ON tasks(user_id);
   CREATE INDEX idx_tasks_status ON tasks(status);
   CREATE INDEX idx_tasks_due_date ON tasks(due_date);
   ```

3. **Data migration script**
   - Export existing SQLite data
   - Transform for D1 compatibility
   - Import via wrangler d1 execute

### Phase 3: Core API Implementation
**Estimated complexity: High**

#### Priority 1: Authentication (Critical Path)
```typescript
// workers/src/routes/auth.ts
import { Hono } from 'hono';
import { sign, verify } from 'jose';
import bcrypt from 'bcryptjs';

const auth = new Hono<{ Bindings: Env }>();

auth.post('/register', async (c) => {
  const { email, password, name } = await c.req.json();

  // Check existing user
  const existing = await c.env.DB.prepare(
    'SELECT id FROM users WHERE email = ?'
  ).bind(email).first();

  if (existing) {
    return c.json({ error: 'Email already registered' }, 400);
  }

  // Create user
  const id = crypto.randomUUID();
  const hashedPassword = await bcrypt.hash(password, 10);

  await c.env.DB.prepare(`
    INSERT INTO users (id, email, hashed_password, name)
    VALUES (?, ?, ?, ?)
  `).bind(id, email, hashedPassword, name).run();

  // Create default settings
  await c.env.DB.prepare(`
    INSERT INTO user_settings (id, user_id)
    VALUES (?, ?)
  `).bind(crypto.randomUUID(), id).run();

  return c.json({ id, email, name });
});

auth.post('/login', async (c) => {
  const { email, password } = await c.req.json();

  const user = await c.env.DB.prepare(
    'SELECT * FROM users WHERE email = ?'
  ).bind(email).first();

  if (!user || !await bcrypt.compare(password, user.hashed_password)) {
    return c.json({ error: 'Invalid credentials' }, 401);
  }

  // Generate JWT
  const secret = new TextEncoder().encode(c.env.JWT_SECRET);
  const token = await new jose.SignJWT({
    sub: email,
    user_id: user.id
  })
    .setProtectedHeader({ alg: 'HS256' })
    .setExpirationTime('7d')
    .sign(secret);

  return c.json({ access_token: token, token_type: 'bearer' });
});

export default auth;
```

#### Priority 2: CRUD Operations Pattern
```typescript
// workers/src/routes/tasks.ts
import { Hono } from 'hono';
import { authMiddleware } from '../middleware/auth';

const tasks = new Hono<{ Bindings: Env }>();
tasks.use('*', authMiddleware);

// List tasks
tasks.get('/', async (c) => {
  const userId = c.get('userId');
  const { status, folder_id, limit = 50, offset = 0 } = c.req.query();

  let query = 'SELECT * FROM tasks WHERE user_id = ?';
  const params: any[] = [userId];

  if (status) {
    query += ' AND status = ?';
    params.push(status);
  }

  if (folder_id) {
    query += ' AND folder_id = ?';
    params.push(folder_id);
  }

  query += ' ORDER BY created_at DESC LIMIT ? OFFSET ?';
  params.push(limit, offset);

  const results = await c.env.DB.prepare(query)
    .bind(...params)
    .all();

  return c.json(results.results);
});

// Create task
tasks.post('/', async (c) => {
  const userId = c.get('userId');
  const body = await c.req.json();

  const id = crypto.randomUUID();

  await c.env.DB.prepare(`
    INSERT INTO tasks (id, user_id, title, description, status, priority, due_date, folder_id, project_id)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
  `).bind(
    id, userId, body.title, body.description || null,
    body.status || 'pending', body.priority || 0,
    body.due_date || null, body.folder_id || null, body.project_id || null
  ).run();

  const task = await c.env.DB.prepare(
    'SELECT * FROM tasks WHERE id = ?'
  ).bind(id).first();

  return c.json(task, 201);
});

// Update task
tasks.patch('/:id', async (c) => {
  const userId = c.get('userId');
  const taskId = c.req.param('id');
  const updates = await c.req.json();

  // Build dynamic update query
  const fields = Object.keys(updates);
  const setClause = fields.map(f => `${f} = ?`).join(', ');
  const values = fields.map(f => updates[f]);

  await c.env.DB.prepare(`
    UPDATE tasks
    SET ${setClause}, updated_at = datetime('now')
    WHERE id = ? AND user_id = ?
  `).bind(...values, taskId, userId).run();

  const task = await c.env.DB.prepare(
    'SELECT * FROM tasks WHERE id = ?'
  ).bind(taskId).first();

  return c.json(task);
});

// Delete task
tasks.delete('/:id', async (c) => {
  const userId = c.get('userId');
  const taskId = c.req.param('id');

  await c.env.DB.prepare(
    'DELETE FROM tasks WHERE id = ? AND user_id = ?'
  ).bind(taskId, userId).run();

  return c.json({ message: 'Deleted' });
});

export default tasks;
```

#### Priority 3: File Storage with R2
```typescript
// workers/src/routes/attachments.ts
import { Hono } from 'hono';

const attachments = new Hono<{ Bindings: Env }>();

attachments.post('/upload', async (c) => {
  const formData = await c.req.formData();
  const file = formData.get('file') as File;

  if (!file) {
    return c.json({ error: 'No file provided' }, 400);
  }

  const key = `${crypto.randomUUID()}-${file.name}`;

  await c.env.R2_BUCKET.put(key, file.stream(), {
    httpMetadata: {
      contentType: file.type,
    },
  });

  // Store reference in D1
  const id = crypto.randomUUID();
  await c.env.DB.prepare(`
    INSERT INTO attachments (id, filename, mime_type, storage_key, size)
    VALUES (?, ?, ?, ?, ?)
  `).bind(id, file.name, file.type, key, file.size).run();

  return c.json({ id, filename: file.name, key });
});

attachments.get('/:key', async (c) => {
  const key = c.req.param('key');
  const object = await c.env.R2_BUCKET.get(key);

  if (!object) {
    return c.json({ error: 'Not found' }, 404);
  }

  return new Response(object.body, {
    headers: {
      'Content-Type': object.httpMetadata?.contentType || 'application/octet-stream',
    },
  });
});

export default attachments;
```

### Phase 4: LLM Integration
**Estimated complexity: Medium**

Workers can call external LLM APIs directly:

```typescript
// workers/src/services/ai.ts
export async function callOpenAI(
  apiKey: string,
  prompt: string,
  options: {
    model?: string;
    temperature?: number;
    max_tokens?: number;
  } = {}
) {
  const response = await fetch('https://api.openai.com/v1/chat/completions', {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${apiKey}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      model: options.model || 'gpt-4-turbo-preview',
      messages: [{ role: 'user', content: prompt }],
      temperature: options.temperature || 0.7,
      max_tokens: options.max_tokens || 2048,
    }),
  });

  return response.json();
}

export async function callAnthropic(
  apiKey: string,
  prompt: string,
  options: {
    model?: string;
    max_tokens?: number;
  } = {}
) {
  const response = await fetch('https://api.anthropic.com/v1/messages', {
    method: 'POST',
    headers: {
      'x-api-key': apiKey,
      'anthropic-version': '2023-06-01',
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      model: options.model || 'claude-3-sonnet-20240229',
      max_tokens: options.max_tokens || 2048,
      messages: [{ role: 'user', content: prompt }],
    }),
  });

  return response.json();
}
```

**Note**: Local Ollama integration won't work from Workers (requires network access to localhost). Users will need to use cloud LLM providers (OpenAI, Anthropic, Google) in the deployed version.

### Phase 5: Wrangler Configuration
**Estimated complexity: Low**

```toml
# workers/wrangler.toml
name = "joan-api"
main = "src/index.ts"
compatibility_date = "2024-11-21"

[[d1_databases]]
binding = "DB"
database_name = "joan-production"
database_id = "<your-d1-database-id>"

[[r2_buckets]]
binding = "R2_BUCKET"
bucket_name = "joan-attachments"

[vars]
ENVIRONMENT = "production"

# Secrets (set via wrangler secret put)
# JWT_SECRET
# API_ENCRYPTION_KEY
```

---

## Implementation Order

### Sprint 1: Foundation
1. Infrastructure setup (D1, R2, wrangler config)
2. Database schema migration
3. Auth endpoints (register, login, me, refresh)
4. Auth middleware

### Sprint 2: Core Features
5. Users & Settings CRUD
6. Tasks CRUD + Kanban operations
7. Goals CRUD + TaskGoalLink
8. Notes CRUD
9. Folders CRUD

### Sprint 3: Project Management
10. Clients CRUD
11. Projects CRUD + ProjectMembership
12. File attachments (R2)

### Sprint 4: Productivity
13. Pomodoro (sessions, settings)
14. Daily Schedule
15. Personal Activities

### Sprint 5: Advanced Features
16. Ceremonies (templates, components, sessions)
17. AI Unified endpoint
18. Analytics

### Sprint 6: Polish & Migration
19. Data migration tooling
20. Frontend API client updates
21. Testing & debugging
22. Production deployment

---

## Considerations & Trade-offs

### Limitations on Cloudflare Workers

1. **No Local LLM Support**
   - Workers cannot access localhost services
   - Local Ollama feature must be disabled or marked "development only"
   - Users must use cloud LLM providers (OpenAI, Anthropic)

2. **CPU Time Limits**
   - Workers have 30 second CPU time limit (paid plan)
   - Complex AI workflows may need to be chunked
   - Consider using Durable Objects for long-running operations

3. **Memory Limits**
   - 128MB memory limit
   - Large file uploads need streaming

4. **No subprocess/system calls**
   - `llm_manager.py` service detection won't work
   - Install service features not applicable

### Benefits

1. **Cost Efficiency**
   - D1: 5GB storage, 5M reads, 100K writes free/month
   - R2: 10GB storage, 10M reads, 1M writes free/month
   - Workers: 100K requests/day free

2. **Global Edge Performance**
   - Database at the edge
   - Low latency worldwide

3. **Simplified Operations**
   - No server management
   - Automatic scaling
   - Built-in DDoS protection

4. **Unified Platform**
   - Frontend and backend on same platform
   - Simplified DNS and routing
   - Single deployment pipeline

---

## Migration Checklist

### Pre-Migration
- [ ] Backup existing SQLite database
- [ ] Document all environment variables
- [ ] List all external service dependencies
- [ ] Audit API endpoints for Worker compatibility

### Infrastructure
- [ ] Create Cloudflare account (if needed)
- [ ] Create D1 database
- [ ] Create R2 bucket
- [ ] Generate and store secrets

### Development
- [ ] Set up workers/ project structure
- [ ] Implement auth endpoints
- [ ] Implement all CRUD endpoints
- [ ] Set up R2 file handling
- [ ] Implement LLM service calls

### Testing
- [ ] Unit tests for all endpoints
- [ ] Integration tests with D1
- [ ] Test file upload/download
- [ ] Test LLM integrations
- [ ] Load testing

### Data Migration
- [ ] Export production data
- [ ] Transform for D1 format
- [ ] Import to D1
- [ ] Verify data integrity

### Frontend Updates
- [ ] Update API base URL
- [ ] Test all features
- [ ] Remove/disable local LLM features
- [ ] Update error handling

### Deployment
- [ ] Deploy Workers
- [ ] Update Pages configuration
- [ ] Configure custom domain
- [ ] Set up monitoring
- [ ] Document rollback procedure

---

## Next Steps

1. **Confirm this migration plan** meets your requirements
2. **Choose a starting point** (recommended: Phase 1 infrastructure)
3. **Set up local development** with wrangler dev
4. **Begin implementation** following the sprint order

Would you like to proceed with implementation? I recommend starting with Phase 1 (infrastructure setup) which will establish the foundation for all subsequent work.
