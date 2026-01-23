# Joan MVP v0.1 - Task List

## Project Setup & Infrastructure (8-10 hours)

### Backend Setup
- [x] Initialize Python project with FastAPI structure (1h)
  - Create virtual environment
  - Set up requirements.txt with FastAPI, SQLAlchemy, python-multipart
  - Create basic project structure
  
- [x] Set up SQLite database with SQLAlchemy models (2h)
  - Define base models for Notebook, Note, NoteAttachment
  - Add Pomodoro session tracking model
  - [ ] Configure FTS5 for search
  
- [ ] Create database migration system with Alembic (1h)
  - Initialize Alembic
  - Create initial migration scripts
  
- [x] Set up environment configuration (0.5h)
  - Create .env.example
  - Configure local paths for attachments
  - Set up CORS for local development

### Frontend Setup
- [x] Initialize React TypeScript project (1h)
  - Set up Vite or Create React App
  - Configure TypeScript with strict mode
  - Install core dependencies (react-router, axios, react-query)
  
- [x] Set up component library and styling (1.5h)
  - Choose and configure UI library (Tailwind/MUI/Ant Design)
  - Set up global styles and theme
  - Create basic layout components
  
- [x] Configure state management (1h)
  - Set up React Query for API calls
  - Create context for app-wide state
  - [ ] Implement offline-first data strategy

### DevOps & Tooling
- [x] Set up development scripts (0.5h)
  - [ ] Create docker-compose for local development
  - Add concurrent frontend/backend start script
  
- [ ] Configure testing infrastructure (1h)
  - Set up Jest for frontend
  - Set up pytest for backend
  - Create GitHub Actions workflow

## Pomodoro Timer Feature (12-14 hours)

### Backend - Pomodoro API
- [x] Create Pomodoro data models (1h)
  ```python
  PomodoroSession(id, started_at, ended_at, duration_minutes, type, completed)
  PomodoroSettings(id, work_duration, short_break, long_break, sessions_until_long)
  ```

- [x] Implement Pomodoro REST API endpoints (3h)
  - POST /api/pomodoro/start
  - POST /api/pomodoro/stop
  - GET /api/pomodoro/current
  - GET /api/pomodoro/history
  - PUT /api/pomodoro/settings
  
- [x] Add Pomodoro-Note linking capability (1h)
  - Create PomodoroNoteLink model
  - API to associate active session with notes

### Frontend - Pomodoro UI
- [x] Create Pomodoro timer component (3h)
  - Visual countdown timer
  - Start/pause/stop controls
  - Work/break mode indicator
  - Sound notifications
  
- [x] Build Pomodoro settings page (2h)
  - Customizable work/break durations
  - Notification preferences
  - Theme selection for timer
  
- [ ] Implement Pomodoro history view (2h)
  - Daily/weekly statistics
  - Productivity charts
  - Export functionality
  
- [x] Create Pomodoro-Note integration UI (2h)
  - Quick note creation during sessions
  - Link existing notes to sessions
  - Show notes created during specific Pomodoros

## Notes Module (16-18 hours)

### Backend - Notes API
- [ ] Implement Notes CRUD endpoints (3h)
  - POST /api/notes
  - GET /api/notes/{id}
  - PUT /api/notes/{id}
  - DELETE /api/notes/{id}
  - GET /api/notes (with pagination)
  
- [ ] Create Notebook management endpoints (2h)
  - CRUD for notebooks
  - Hierarchical folder structure
  - Archive functionality
  
- [ ] Implement file attachment system (3h)
  - POST /api/notes/{id}/attachments
  - GET /api/attachments/{id}
  - DELETE /api/attachments/{id}
  - File validation and storage
  
- [ ] Add search functionality (2h)
  - GET /api/search?q=query
  - FTS5 integration
  - Search result ranking

### Frontend - Notes UI
- [ ] Create markdown editor component (4h)
  - Integration with react-markdown
  - Live preview
  - Toolbar for formatting
  - Drag-and-drop image support
  
- [ ] Build notes list/grid view (2h)
  - Sortable columns
  - Filter by notebook
  - Search integration
  - Bulk operations
  
- [ ] Implement notebook tree navigation (2h)
  - Collapsible folder structure
  - Drag-and-drop reorganization
  - Context menus
  
- [ ] Create attachment management UI (2h)
  - File upload with react-dropzone
  - Attachment preview
  - Download/delete capabilities

## LLM Integration (6-8 hours)

### Backend - LLM Service
- [ ] Create LLM service abstraction (2h)
  - Interface for different LLM providers
  - Local Qwen-32B integration
  - Prompt template management
  
- [ ] Implement markdown formatting endpoint (2h)
  - POST /api/llm/format-note
  - Streaming response support
  - Error handling for LLM failures
  
- [ ] Add task extraction capability (2h)
  - POST /api/llm/extract-tasks
  - Parse natural language to structured data
  - Link extracted tasks to notes

### Frontend - LLM Features
- [ ] Create "Format with AI" button in editor (1h)
  - Loading states
  - Preview formatted result
  - Accept/reject mechanism
  
- [ ] Build task extraction UI (1h)
  - Highlight potential tasks in notes
  - One-click task creation
  - Bulk task import

## Polish & MVP Completion (4-6 hours)

- [ ] Implement error handling and loading states (2h)
  - Global error boundary
  - Toast notifications
  - Offline indicators
  
- [ ] Add keyboard shortcuts (1h)
  - Pomodoro start/stop
  - Note creation
  - Search focus
  
- [ ] Create onboarding flow (1h)
  - Initial setup wizard
  - Sample data generation
  - Feature tour
  
- [ ] Performance optimization (2h)
  - API response caching
  - Lazy loading
  - Bundle optimization

## Total Estimated Time: 46-56 hours

## Priority Order for Development

1. **Week 1**: Project setup + Pomodoro timer (backend & frontend)
2. **Week 2**: Notes CRUD + Basic editor
3. **Week 3**: File attachments + Search
4. **Week 4**: LLM integration + Polish

## Notes for Linear Import

- Create 4 epics: Infrastructure, Pomodoro, Notes, LLM Integration
- Set up milestones for each week
- Add labels: frontend, backend, database, ui/ux
- Priority: P0 for Pomodoro, P1 for Notes core, P2 for LLM features