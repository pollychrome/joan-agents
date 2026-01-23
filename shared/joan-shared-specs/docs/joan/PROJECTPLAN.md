# Joan - Edge-First Productivity Assistant

## Project Overview
Joan is an edge-first productivity assistant (Cloudflare Workers/D1/R2) that combines task management, time tracking, note-taking, and AI-powered ceremonies to help users achieve their goals through structured workflows.

---

## Current Version: MVP v0.3 (Cloudflare Edge + AI Ceremonies)
*Building on v0.2's Notes module, v0.3 runs on Cloudflare Workers/D1/R2 and introduces AI-aware ceremonies.*

---

## 1. System Architecture

### Core Layers

| Layer | Responsibility | Tech Stack |
|-------|--------------|------------|
| **UI** | React-based SPA with ceremony components | React 18, TypeScript, Tailwind CSS, Lucide Icons |
| **API** | Edge REST API with ceremony + productivity features | Cloudflare Workers, Hono, TypeScript, Zod |
| **Storage** | Relational data + file attachments | Cloudflare D1 (SQLite-compatible) + R2 |
| **AI Service** | Multi-provider AI abstraction (cloud) | OpenAI, Anthropic, Groq; Ollama **dev only** |
| **Auth** | JWT-based authentication | jose, bcryptjs |
| **Ops** | Config + routing | Wrangler, Pages |

### New AI Architecture Components (v0.3)

| Component | Purpose | Location |
|-----------|---------|----------|
| **AI Provider Registry** | Configure provider routing/priorities | `workers/schema/ceremonies.sql` |
| **Ceremony AI Query** | Simple AI query endpoint for ceremonies | `workers/src/routes/ceremonies.ts` |
| **Ceremony Orchestrator** | Multi-step AI workflows | `workers/src/routes/ceremonies.ts` |
| **AI Components** | Frontend AI-aware components | `/frontend/src/components/ceremony/components/` |

---

## 2. Data Model (Cloudflare D1)

### Core Entities
```sql
-- Users & Auth
User(id, email, hashed_password, name, role, onboarding_completed, onboarding_progress, first_login_at, created_at)
UserSettings(id, user_id, theme, notifications_enabled, default_work_duration, default_break_duration)

-- Projects & Tasks
Client(id, user_id, name, email, phone, company, status)
Project(id, user_id, client_id, name, description, status, start_date, end_date, budget, hourly_rate)
Task(id, user_id, title, description, status, priority, due_date, completed_at, folder_id, project_id, estimated_minutes, actual_minutes, tags)
TaskActivity(id, task_id, user_id, action, details, created_at)
Goal(id, user_id, title, description, type, status, target_date, completed_at, progress, metrics)
TaskGoalLink(id, task_id, goal_id)

-- Organization
Folder(id, user_id, parent_id, name, description, color, icon, position)
KanbanBoard(id, user_id, name, description, project_id, columns, settings, kanban_position)

-- Notes
Note(id, user_id, folder_id, title, content, content_html, tags, is_pinned, is_archived)

-- Time & Productivity
PomodoroSession(id, user_id, type, duration_minutes, started_at, ended_at, completed, task_id, notes)
PomodoroSettings(id, user_id, work_duration, short_break_duration, long_break_duration, sessions_until_long_break, auto_start_breaks, auto_start_pomodoros, sound_enabled)
DailySchedule(id, user_id, date, blocks)
ScheduleTemplate(id, user_id, name, description, blocks, is_default)
PersonalActivity(id, user_id, type, name, description, duration_minutes, date, time, mood_before, mood_after, energy_before, energy_after, tags, location, weather, goal_id)
ActivityGoal(id, user_id, activity_type, target_frequency, target_count, target_duration_minutes, start_date, end_date, reminder_time, is_active)

-- Attachments (R2 references)
Attachment(id, user_id, filename, mime_type, size, storage_key, entity_type, entity_id, uploaded_at)
```

### AI & Ceremony Entities (v0.3)
```sql
-- Ceremony Framework
CeremonyTemplate(id, name, description, category, component_ids[], icon, estimated_minutes, redirect_path, is_active, order_index)
CeremonyComponent(id, type, name, description, config, ai_provider_id, ai_prompt_template, ai_model_override, ai_temperature_override, ai_max_tokens_override, order_index, is_required, is_active)
CeremonySession(id, user_id, template_id, project_id, task_id, started_at, completed_at, duration_minutes, status, current_step, input_data, output_data, notes, tasks_created, notes_created)

-- AI Configuration
CeremonyAIProvider(id, provider_type, provider_name, api_key, api_endpoint, model_name, max_tokens, temperature, is_active, is_default, priority, total_requests, total_tokens, total_cost, last_used_at)
CeremonyAIRequest(id, component_id, provider_id, prompt, response, model_used, tokens_total, latency_ms, status, error_message, created_at)
```

---

## 3. AI Provider Framework (v0.3)

### Supported Providers
- **Cloud**: OpenAI (GPT-4o/mini), Anthropic (Claude 3), Groq (Llama 3)
- **Dev-only**: Ollama (local) — not reachable from deployed Workers; use only in local dev
- **Planned**: Custom endpoints, Cohere

### Provider Capabilities Matrix
| Provider | Max Context | JSON Mode | Speed | Quality | Cost |
|----------|------------|-----------|--------|---------|------|
| Qwen-32B Local | 32K | Manual | Slow | High | Free |
| GPT-4 Turbo | 128K | Native | Fast | Very High | $$$ |
| Claude-3 Opus | 200K | Native | Medium | Very High | $$$ |
| GPT-3.5 | 16K | Native | Very Fast | Good | $ |

### Unified AI Service Features
1. **Automatic Provider Selection** based on:
   - Task requirements (speed, quality, context)
   - User preferences and budget
   - Provider availability

2. **Response Normalization**:
   - Consistent JSON extraction
   - Markdown formatting
   - Structured data parsing

3. **Intelligent Fallback Chain**:
   - Primary → Secondary → Tertiary
   - Automatic retry with exponential backoff
   - Error aggregation and reporting

---

## 4. Ceremony System

### Core Ceremonies

#### Writing Race (Implemented)
- **Purpose**: Focused writing sessions with AI analysis
- **Components**: Timer, Word Counter, Writing Area, AI Processor
- **AI Features**: Smart summary, task extraction, idea organization

#### Daily Planning (Phase 3)
- **Purpose**: Plan the day's work with AI assistance
- **Components**: Task Review, Calendar Integration, AI Prioritizer
- **AI Features**: Priority suggestions, time estimates, conflict detection

#### Weekly Review (Phase 3)
- **Purpose**: Reflect on progress and plan ahead
- **Components**: Metrics Dashboard, Goal Tracker, AI Analyzer
- **AI Features**: Progress insights, pattern detection, recommendations

### Ceremony Workflow Engine
```yaml
workflow:
  steps:
    - name: collect_input
      type: user_input
      component: WritingArea

    - name: analyze
      type: ai_process
      prompt: "Analyze writing for actionable items"
      requirements:
        needs_quality: true

    - name: extract_tasks
      type: ai_process
      prompt: "Extract tasks from: {previous.analyze}"
      output_format: json

    - name: create_tasks
      type: api_call
      endpoint: /tasks/batch
      data: "{previous.extract_tasks}"
```

---

## 5. Implementation Roadmap

### Phase 1: Core Infrastructure (Done/Current)
- [x] Cloudflare Workers API scaffold (auth, tasks, notes, folders, goals, clients, projects)
- [x] D1 schema for productivity + ceremonies
- [x] R2-backed attachments with access checks
- [x] Kanban boards and task activities
- [x] Daily schedules + templates
- [x] Personal activities + activity goals
- [x] Onboarding status/progress APIs

### Phase 2: AI & Ceremonies (Current)
- [x] Ceremony AI providers registry
- [x] Ceremony AI query endpoint with provider routing
- [ ] AI unified endpoint (non-ceremony) parity with legacy FastAPI
- [ ] Provider registration via environment/secret management
- [ ] AI analytics and cost tracking surface

### Phase 3: Frontend Integration
- [ ] Update frontend API clients to Workers base URL everywhere
- [ ] Wire Kanban/schedule/activities/onboarding screens to Workers API
- [ ] Edge-friendly ceremony runner with AI provider selection UX

### Phase 4: Advanced Features
- [ ] Smart provider routing based on analytics
- [ ] Template builder/visual designer
- [ ] Cost tracking/budgeting UI
- [ ] Prompt optimization system

---

## 6. API Endpoints

### Core APIs (Cloudflare Workers `/api/v1`)
```
# Authentication
POST   /auth/register
POST   /auth/login
GET    /auth/me
POST   /auth/refresh

# Users
GET    /users/profile
PATCH  /users/profile

# Tasks & Projects
GET    /tasks
POST   /tasks
GET    /tasks/:id
PATCH  /tasks/:id
DELETE /tasks/:id
POST   /tasks/:id/complete
GET    /projects
POST   /projects
PATCH  /projects/:id
GET    /clients
POST   /clients

# Notes & Folders
GET    /notes
POST   /notes
GET    /notes/:id
PATCH  /notes/:id
DELETE /notes/:id
GET    /folders
POST   /folders

# Kanban
GET    /kanban/boards
POST   /kanban/boards
PATCH  /kanban/boards/:id
POST   /kanban/boards/:id/move

# Pomodoro
POST   /pomodoro/start
POST   /pomodoro/complete
GET    /pomodoro/sessions
GET    /pomodoro/settings
PATCH  /pomodoro/settings

# Schedules & Templates
GET    /schedule/daily/:date
POST   /schedule/daily
PATCH  /schedule/daily/:date/blocks/:index
DELETE /schedule/daily/:date
GET    /schedule/templates
POST   /schedule/templates

# Personal Activities
GET    /activities
POST   /activities
GET    /activities/:id
PATCH  /activities/:id
DELETE /activities/:id
GET    /activities/goals
POST   /activities/goals

# Attachments (R2)
POST   /attachments/upload
GET    /attachments/:id
DELETE /attachments/:id
GET    /attachments/usage

# Ceremonies & AI
GET    /ceremonies/templates
GET    /ceremonies/templates/:id
POST   /ceremonies/sessions/start
PATCH  /ceremonies/sessions/:id
POST   /ceremonies/sessions/:id/complete
POST   /ceremonies/sessions/:id/cancel
GET    /ceremonies/sessions/history
GET    /ceremonies/ai/config
POST   /ceremonies/ai/query
```

---

## 7. Key Design Principles

### Edge-First
- Data and auth served from Cloudflare D1/Workers
- R2 for attachments; no local filesystem in production
- Local LLM (Ollama) is development-only; cloud LLMs in production

### Progressive Enhancement
- Basic features work without AI
- Enhanced features with AI enabled
- Graceful degradation on failures

### Provider Agnostic
- Consistent behavior across providers
- Automatic optimization per provider
- User choice of provider preference

### Privacy Focused
- Cloud AI keys encrypted; user-controlled
- Local LLM (Ollama) available in development only
- No telemetry without consent

---

## 8. Development Guidelines

### Code Organization
```
/workers
  /src
    /routes      # Hono route handlers (auth, tasks, ceremonies, etc.)
    /middleware  # Auth/CORS
    /models      # D1 helpers
    /services    # AI helpers, utilities
    /types       # Env bindings
  /schema        # D1/ceremony SQL
  wrangler.toml  # Cloudflare config

/frontend
  /src
    /components
      /ceremony  # Ceremony components
      /common    # Shared components
    /hooks       # Custom React hooks
    /services    # API clients
    /stores      # State management
```

### Testing Strategy
- Unit tests for AI provider abstraction
- Integration tests for ceremony workflows
- E2E tests with Puppeteer for full ceremonies
- Mock providers for testing

### Performance Targets
- Simple AI query: <2 seconds
- Complex workflow: <10 seconds
- Ceremony completion: <5 minutes
- Frontend interaction: <100ms

---

## 9. Upcoming Milestone: Onboarding Redesign

### Overview
Complete redesign of the user onboarding experience to provide a guided tour through each major section of the application. The onboarding should feel native to the app's design system and support both light and dark modes.

### Requirements

#### Core Functionality
- [ ] **Tab-by-Tab Navigation**: Guide users through each main tab/page of the app sequentially
  - Dashboard overview
  - Tasks page (creating, organizing, completing tasks)
  - Notes page (creating notes, markdown support, organization)
  - Pomodoro/Timer page (starting sessions, settings)
  - Goals page (setting and tracking goals)
  - Profile/Settings page (customization options)

- [ ] **Feature Highlighting**: On each page, highlight and explain key features
  - Use spotlight/tooltip overlays on specific UI elements
  - Provide brief, actionable descriptions
  - Show keyboard shortcuts where applicable

- [ ] **Dismissible at Any Time**:
  - Prominent X button to close the tour at any step
  - "Skip Tour" option always visible
  - Remember dismissal state so tour doesn't restart unexpectedly

#### Design Requirements
- [ ] **Dark Mode Support**: All onboarding UI must work seamlessly in dark mode
  - Custom CSS overrides for driver.js or alternative library
  - Consistent with app's Tailwind dark mode classes
  - Proper contrast ratios for accessibility

- [ ] **Mobile Responsive**: Tour should work on mobile/tablet viewports
  - Adjust positioning for smaller screens
  - Touch-friendly navigation buttons

#### Technical Implementation
- [ ] **Evaluate Libraries**: Consider alternatives to driver.js or customize it
  - Options: react-joyride, intro.js, shepherd.js, custom implementation
  - Must support: dark mode, custom styling, programmatic control

- [ ] **Step Configuration**: Define steps per page with selectors that match actual UI
  ```typescript
  interface OnboardingStep {
    page: string;           // Route path
    element: string;        // CSS selector for highlight
    title: string;
    description: string;
    position: 'top' | 'bottom' | 'left' | 'right';
    action?: 'click' | 'navigate' | 'input';  // Optional interactive actions
  }
  ```

- [ ] **State Management**: Track onboarding progress properly
  - Store current step in context
  - Persist completion state to backend
  - Handle page navigation during tour

- [ ] **Trigger Options**:
  - Auto-start for new users after email verification (optional, user preference)
  - Manual trigger from Help menu or settings
  - "Restart Tour" option in settings for returning users

### Success Criteria
- Tour completes without errors through all pages
- Dark mode styling matches app theme
- Users can exit at any point without issues
- Tour state persists correctly across sessions
- Mobile experience is usable

### Estimated Effort
- Design & Planning: 2-4 hours
- Library evaluation/setup: 2-3 hours
- Step definitions & UI integration: 4-6 hours
- Dark mode styling: 2-3 hours
- Testing & polish: 2-3 hours

---

## 10. Future Enhancements

### v0.4 - Collaboration
- Team ceremonies
- Shared templates
- Multi-user support

### v0.5 - Analytics
- Productivity insights
- AI usage analytics
- Cost optimization

### v0.6 - Integrations
- Calendar sync (Google, Outlook)
- Project management tools
- Communication platforms

---

## 11. Success Metrics

### Technical
- 99% uptime for edge features
- 95% success rate with fallbacks
- <2s average AI response time
- 100% response normalization

### User Experience
- 5 ceremony templates active
- <1 hour to create new ceremony
- 90% task extraction accuracy
- Zero data loss

### Business
- Support 5+ AI providers
- Cost tracking accuracy
- Template marketplace ready
- Community contributions enabled

---

*Last Updated: December 2024*
*Version: 0.3.0*
*Status: Active Development*
