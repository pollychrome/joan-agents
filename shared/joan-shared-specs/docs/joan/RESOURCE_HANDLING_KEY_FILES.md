# Resource Handling System - Complete File Reference

## Frontend Type Definitions
**File:** `/Users/alexbenson/Joan/frontend/src/types/task.ts`
- `Resource` interface definition (id, title, description, type, url, content, source, duration)
- `Task` interface with optional `resources?: Resource[]` field
- `TaskCreate` interface with optional resources
- `TaskUpdate` interface with optional resources

## Frontend Components

### ResourceFinder Component
**File:** `/Users/alexbenson/Joan/frontend/src/components/ceremony/components/ResourceFinder.tsx`
- **Size:** 578 lines
- **Key Features:**
  - AI-powered resource search and generation
  - Multi-provider AI model selection
  - Dynamic loading with timeout handling
  - Error handling (timeout, API key, rate limit)
  - Resource type icons and color coding
  - Modal UI with search input and resource list
  - Add/remove resource tracking

### TaskModalNew Component
**File:** `/Users/alexbenson/Joan/frontend/src/components/tasks/TaskModalNew.tsx`
- **Size:** 1,730 lines
- **Resource-Related Code:**
  - Lines 85-86: Resource state initialization
  - Lines 203-206: Load resources from task
  - Lines 291: Include resources in save payload
  - Lines 432-442: Add/remove resource handlers
  - Lines 800-890: Resources section UI rendering
  - Lines 1719-1727: ResourceFinder modal integration

### TaskReviewerWithSchedule Component
**File:** `/Users/alexbenson/Joan/frontend/src/components/ceremony/components/TaskReviewerWithSchedule.tsx`
- **Size:** 1,600+ lines
- **Resource-Related Code:**
  - Line 7: ResourceFinder import
  - Line 30: resources field in ScheduledTask interface
  - Lines 395-460: Resource display with badge and counter
  - Lines 651: resourceFinderTask state
  - Lines 1113-1180: handleAddResource function
  - Lines 1629-1634: ResourceFinder modal integration
  - Resource content markdown rendering

### DailySchedule Component
**File:** `/Users/alexbenson/Joan/frontend/src/components/home/DailySchedule.tsx`
- **Size:** 500+ lines
- **Resource Display:**
  - Lines 16: resources field in ScheduledTask interface
  - Lines 29: total_resources tracking
  - Resource count badges on tasks
  - Expandable resources section

### DailyScheduleEnhanced Component
**File:** `/Users/alexbenson/Joan/frontend/src/components/home/DailyScheduleEnhanced.tsx`
- Resources display in enhanced schedule view
- Resource count per task

## Frontend Services

### Task API Service
**File:** `/Users/alexbenson/Joan/frontend/src/services/taskApi.ts`
- `getTasks()` - Get tasks (resources included)
- `getTask()` - Get single task with resources
- `getTaskWithSubtasks()` - Get task with subtasks and resources
- `createTask()` - Create task with resources payload
- `updateTask()` - Update task with resources
- `deleteTask()` - Delete task
- `reorderTask()` - Reorder task

## Backend Models

### Task Model
**File:** `/Users/alexbenson/Joan/backend/app/models/task.py`
- **Note:** No resources column in Task table
- Resources passed through API payload
- Task accepts resources in request/response

### Daily Schedule Models
**File:** `/Users/alexbenson/Joan/backend/app/models/daily_schedule.py`

#### DailySchedule Class
- `enhanced_count` column: Number of tasks with resources
- `total_resources` column: Total resources count
- `scheduled_tasks` JSON column: Contains resource arrays

#### DailyScheduleTask Class
- **Lines 95-96:** `resources = Column(JSON, default=list)`
- Stores resources as JSON array
- Each scheduled task has independent resources array

## Backend API Endpoints

### Task API
**File:** `/Users/alexbenson/Joan/backend/app/api/tasks.py`

#### Endpoints
- **POST /tasks/** (Lines 114-169)
  - Creates task with resources
  - Resources accepted in payload
  
- **PUT /tasks/{task_id}** (Lines 172-233)
  - Updates task with resources
  - Resources accepted in payload
  
- **GET /tasks/** (Lines 22-70)
  - Returns tasks with resources
  
- **GET /tasks/{task_id}** (Lines 73-88)
  - Returns single task with resources
  
- **GET /tasks/{task_id}/with-subtasks** (Lines 91-111)
  - Returns task with subtasks and resources

### Daily Schedule API
**File:** `/Users/alexbenson/Joan/backend/app/api/daily_schedule.py`

#### Schemas
- **ScheduledTaskInput** (Lines 23-32)
  - `resources: Optional[List[Dict[str, Any]]] = []`
  - Resources field for each scheduled task

- **CreateDailyScheduleRequest** (Lines 35-41)
  - `scheduled_tasks: List[ScheduledTaskInput]`
  - `total_resources: Optional[int] = 0`

- **DailyScheduleResponse** (Lines 56-68)
  - `total_resources: int`
  - Includes scheduled_tasks with resources

#### Endpoints
- **POST /daily-schedule/** (Lines 71-120+)
  - Creates schedule with resources
  - Stores resources in DailyScheduleTask.resources

- **PATCH /daily-schedule/{schedule_id}**
  - Updates scheduled tasks and resources

- **GET /daily-schedule/today**
  - Returns today's schedule with resources

## Backend Schemas

### Task Schemas
**File:** `/Users/alexbenson/Joan/backend/app/schemas/task.py`
- **TaskBase** (Lines 7-17)
  - No resources field (currently)
  
- **TaskCreate** (Lines 20-21)
  - Inherits from TaskBase
  - No explicit resources field
  
- **TaskUpdate** (Lines 24-34)
  - Inherits from BaseModel
  - No explicit resources field
  
- **Task** (Lines 37-47)
  - Pydantic response model
  - No explicit resources field

## Database Schema Files

### Initial Migration
**File:** `/Users/alexbenson/Joan/backend/alembic/versions/24ef106b7e44_initial_migration_with_client_project_.py`
- Initial schema setup

### Daily Schedule Migration
**File:** `/Users/alexbenson/Joan/backend/alembic/versions/add_daily_schedule_tables.py`
- DailySchedule and DailyScheduleTask tables
- Resources JSON column definition

## AI/LLM Integration

### LLM Service
**File:** `/Users/alexbenson/Joan/backend/app/services/llm_service.py`
- Used by ResourceFinder for resource generation
- Supports multiple providers

### Core Prompt Management
**File:** `/Users/alexbenson/Joan/backend/app/core/ceremony_prompts.py`
- Contains resource-related prompts
- Reference to "Suggested learning resources/approach"

## Settings & Configuration

### Available Models Endpoint
- Fetched from: `GET /settings/available-models`
- Returns: List of available AI models with providers
- Used by ResourceFinder for model selection

## Hook Integration

### useAI Hook
- Used by ResourceFinder to query AI
- Supports model selection via options
- Handles JSON parsing and formatting

## Data Structure Examples

### Resource Object (JSON)
```json
{
  "id": "unique-id",
  "title": "Resource Title",
  "description": "Short description",
  "type": "article|video|book|tool|tip|plan|workout|guide|generated",
  "url": "https://example.com",
  "content": "Full content for generated resources",
  "source": "Source attribution",
  "duration": "45 min"
}
```

### Scheduled Task with Resources (JSON)
```json
{
  "taskId": "task-id",
  "startTime": "09:00",
  "duration": 60,
  "task": {...},
  "resources": [
    {...resource object...},
    {...resource object...}
  ]
}
```

## File Relationships Map

```
Task Resources Flow:
  frontend/src/types/task.ts (Resource interface)
    ↓
  frontend/src/components/tasks/TaskModalNew.tsx (Display & manage)
    ↓
  frontend/src/services/taskApi.ts (API calls)
    ↓
  backend/app/api/tasks.py (Handle POST/PUT/GET)
    ↓
  backend/app/models/task.py (Task model)

Daily Schedule Resources Flow:
  frontend/src/types/task.ts (Resource interface)
    ↓
  frontend/src/components/ceremony/components/TaskReviewerWithSchedule.tsx (Manage)
    ↓
  frontend/src/components/ceremony/components/ResourceFinder.tsx (Generate)
    ↓
  backend/app/api/daily_schedule.py (Handle API)
    ↓
  backend/app/models/daily_schedule.py (DailyScheduleTask.resources)
```

## Total Lines of Code

- ResourceFinder component: 578 lines
- TaskModalNew component: 1,730 lines
- TaskReviewerWithSchedule component: 1,600+ lines
- Task API endpoints: 363 lines
- Daily Schedule API endpoints: 300+ lines
- Database models: 100+ lines
- Total resource-related code: 4,600+ lines

## Status Summary

✓ **Implemented:**
- Resource type definitions
- AI-powered resource finder
- Resource display in tasks
- Resource storage in JSON
- Integration with daily schedules
- Multiple AI model support

✗ **Not Implemented:**
- Dedicated resource database table
- Resource normalization
- Resource library/sharing
- Resource search queries
- Resource versioning
- Resource annotations/ratings

## Next Steps for Enhancement

1. Create dedicated `resources` table with proper normalization
2. Add `task_resources` junction table for many-to-many relationships
3. Implement resource library and sharing
4. Add full-text search on resources
5. Create resource annotations/ratings system
6. Implement resource sync across related tasks
