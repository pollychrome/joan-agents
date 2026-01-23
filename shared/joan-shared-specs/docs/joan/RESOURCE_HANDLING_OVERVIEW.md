# Joan Resource Handling System - Comprehensive Overview

## 1. Resource Type Definitions

### Frontend Type Definition (TypeScript)
**File:** `/Users/alexbenson/Joan/frontend/src/types/task.ts`

```typescript
export interface Resource {
  id: string;
  title: string;
  description: string;
  type: 'article' | 'video' | 'book' | 'tool' | 'tip' | 'plan' | 'workout' | 'guide' | 'generated';
  url?: string;           // External link (optional)
  content?: string;       // Full content for generated resources
  source?: string;        // Source attribution
  duration?: string;      // Estimated time (e.g., "45 min workout")
}
```

### Resource Type Categorization
Resources are classified into 9 types:
- **article** - Web articles and documentation
- **video** - Video tutorials and content
- **book** - Books and longer-form reading material
- **tool** - Tools and utilities
- **tip** - Quick tips and advice
- **plan** - Structured plans (e.g., study plans, meal plans)
- **workout** - Exercise routines and fitness content
- **guide** - Step-by-step guides
- **generated** - AI-generated content

### Visual Representation
Each resource type has:
- **Icon** - Lucide icon for quick visual identification
- **Color Scheme** - Tailwind colors for light/dark mode differentiation

Color mappings:
- article: Blue
- video: Red
- book: Purple
- tool: Green
- tip: Yellow
- plan: Indigo
- workout: Orange
- guide: Cyan
- generated: Purple

---

## 2. Resource Finder AI Component Implementation

### Component Location
**File:** `/Users/alexbenson/Joan/frontend/src/components/ceremony/components/ResourceFinder.tsx`

### Core Features

#### Props Interface
```typescript
interface ResourceFinderProps {
  taskTitle: string;
  taskDescription?: string;
  onAddResource: (resource: Resource) => void;
  isOpen: boolean;
  onClose: () => void;
}
```

#### Key Capabilities

1. **Dynamic AI Model Selection**
   - Fetches available AI models from `/settings/available-models` endpoint
   - Supports multiple providers:
     - `local_ollama:qwen3:32b` (local AI)
     - `openai:*` (OpenAI models)
     - `anthropic:*` (Anthropic models)
   - User can select model before searching
   - Falls back to local Qwen3 32B if no models available

2. **Resource Generation Methods**
   - **Automatic:** Click "Find Resources" to generate resources based on task title/description
   - **Custom Query:** User can enter custom search query
   - Prompt is context-aware and includes task information

3. **Resource Generation Prompt**
   - Analyzes user intent to determine whether to:
     - Generate content (for "create", "generate", "write" requests)
     - Find resources (for "find", "search", "tutorials" requests)
     - Provide both (default for ambiguous queries)
   - Returns JSON with array of resources
   - Supports both generated content and external links

#### Search Process
```typescript
const handleSearch = async (overrideQuery?: string) => {
  // 1. Build prompt with task context
  const prompt = generateResourcePrompt(query);
  
  // 2. Call AI with model options
  const aiResponse = await queryAI(prompt, {
    outputFormat: 'json',
    preferProvider: provider,
    preferModel: model
  });
  
  // 3. Parse JSON response
  const parsedResources = JSON.parse(aiResponse);
  
  // 4. Set unique IDs and update state
  setResources(parsedResources);
}
```

#### Error Handling
- **Timeout (90 seconds):** Shows user-friendly timeout message with local AI processing note
- **401 Unauthorized:** API key error with suggestion to update settings
- **429 Rate Limit:** Rate limit exceeded message
- **Generic Errors:** Shows detailed error with provider information
- **Parse Errors:** Falls back to creating single resource from raw response

#### UI/UX Features
- **Loading States:** Shows animated spinner with loading messages
- **Time-based Messages:** Changes message after 5 seconds to indicate progress
- **Added Resources Tracking:** Tracks which resources have been added with visual feedback
- **Expandable Content:** Shows generated content in collapsible sections
- **Resource Preview:** 
  - Title and description
  - Optional URL link (opens in new tab)
  - Optional duration indicator
  - Optional source attribution
- **Resource Actions:**
  - Add resource (disabled after added)
  - Open external link
  - Close finder

---

## 3. Storage & Persistence Architecture

### Frontend State Management

#### Task Modal State (TaskModalNew.tsx)
```typescript
const [taskResources, setTaskResources] = useState<Resource[]>([]);

// Handlers
const handleAddResource = (resource: Resource) => {
  // Check for duplicates
  const exists = taskResources.some(r => r.id === resource.id);
  if (!exists) {
    setTaskResources(prev => [...prev, resource]);
  }
};

const handleRemoveResource = (resourceId: string) => {
  setTaskResources(prev => prev.filter(r => r.id !== resourceId));
};
```

#### Daily Schedule State (TaskReviewerWithSchedule.tsx)
```typescript
const handleAddResource = async (resource: any) => {
  setScheduledTasks(scheduledTasks.map((st, idx) => {
    if (idx === selectedTaskIndex) {
      const currentResources = st.resources || [];
      return {
        ...st,
        resources: [...currentResources, resource]
      };
    }
    return st;
  }));
};
```

### Backend Data Models

#### Task Model
**File:** `/Users/alexbenson/Joan/backend/app/models/task.py`

Note: Resources are NOT stored directly in the Task model. Instead:
- Task model accepts `resources` in API requests
- Resources are passed through as part of TaskCreate/TaskUpdate payloads
- Currently handled as JSON data in request/response

#### Daily Schedule Task Model
**File:** `/Users/alexbenson/Joan/backend/app/models/daily_schedule.py`

```python
class DailyScheduleTask(Base):
    __tablename__ = "daily_schedule_tasks"
    
    # Task details
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    start_time = Column(String, nullable=False)
    duration_minutes = Column(Integer, nullable=False)
    
    # Resources stored as JSON
    resources = Column(JSON, default=list)  # Array of resource objects
    
    # Metadata
    enhanced_count = Column(Integer, default=0)  # Number of tasks with resources
    total_resources = Column(Integer, default=0)  # Total resources count
```

#### Daily Schedule Aggregation
```python
class DailySchedule(Base):
    __tablename__ = "daily_schedules"
    
    # Track resource statistics
    enhanced_count = Column(Integer, default=0)  # Number of tasks with resources
    total_resources = Column(Integer, default=0)  # Total resources across all tasks
    
    # Scheduled tasks and completion tracking
    scheduled_tasks = Column(JSON, nullable=False)  # Array of scheduled task objects
    completed_tasks = Column(JSON, default=list)
```

### API Request/Response Schema

#### TaskCreate Schema
**File:** `/Users/alexbenson/Joan/backend/app/schemas/task.py`

```python
class TaskCreate(TaskBase):
    project_id: str
    # Note: resources field is NOT in the pydantic schema
    # but can be passed in request and will be handled
```

#### Daily Schedule Schemas
**File:** `/Users/alexbenson/Joan/backend/app/api/daily_schedule.py`

```python
class ScheduledTaskInput(BaseModel):
    taskId: str
    startTime: str
    duration: int
    task: Optional[Dict[str, Any]] = None
    isLifestyle: Optional[bool] = False
    lifestyleType: Optional[str] = None
    customTitle: Optional[str] = None
    resources: Optional[List[Dict[str, Any]]] = []  # Resources for scheduled task

class CreateDailyScheduleRequest(BaseModel):
    scheduled_tasks: List[ScheduledTaskInput]
    enhanced_count: Optional[int] = 0
    total_resources: Optional[int] = 0
    ceremony_session_id: Optional[str] = None
```

---

## 4. API Endpoints for Resource Handling

### Task Endpoints
**File:** `/Users/alexbenson/Joan/backend/app/api/tasks.py`

#### Create Task with Resources
```
POST /tasks/
Request Body:
{
  "project_id": "string",
  "title": "string",
  "description": "string",
  "resources": [
    {
      "id": "string",
      "title": "string",
      "type": "article|video|...",
      "url": "string (optional)",
      "content": "string (optional)",
      "source": "string (optional)",
      "duration": "string (optional)"
    }
  ]
}

Response: Task with embedded resources
```

#### Update Task with Resources
```
PUT /tasks/{task_id}
Request Body: Same as above
Response: Updated Task with resources
```

#### Get Task with Resources
```
GET /tasks/{task_id}
Response:
{
  "id": "string",
  "title": "string",
  "resources": [...]
}

GET /tasks/{task_id}/with-subtasks
Response: Task with subtasks and resources
```

### Daily Schedule Endpoints
**File:** `/Users/alexbenson/Joan/backend/app/api/daily_schedule.py`

#### Create Daily Schedule
```
POST /daily-schedule/
Request Body:
{
  "scheduled_tasks": [
    {
      "taskId": "string",
      "startTime": "HH:MM",
      "duration": number,
      "resources": [...]
    }
  ],
  "total_resources": number,
  "ceremony_session_id": "string (optional)"
}

Response: DailyScheduleResponse with resources aggregated
```

#### Update Daily Schedule
```
PATCH /daily-schedule/{schedule_id}
Updates: scheduled_tasks, completed_tasks, is_active
```

#### Get Today's Schedule
```
GET /daily-schedule/today
Response: DailyScheduleResponse with all scheduled tasks and their resources
```

---

## 5. Component Integration - Resource Display on Tasks

### TaskModalNew Component
**File:** `/Users/alexbenson/Joan/frontend/src/components/tasks/TaskModalNew.tsx`

#### Resources Section (Lines 800-890)
```typescript
{(taskResources.length > 0 || isEditMode) && (
  <div className="mb-4">
    <label className="flex items-center justify-between mb-2">
      <Sparkles className="w-4 h-4 inline mr-1" />
      Resources
      
      {isEditMode && (
        <button onClick={() => setShowResourceFinder(true)}>
          Add Resource
        </button>
      )}
    </label>
    
    {taskResources.length > 0 ? (
      <div className="space-y-2">
        {taskResources.map((resource) => (
          <ResourceCard 
            resource={resource}
            isEditMode={isEditMode}
            onRemove={handleRemoveResource}
          />
        ))}
      </div>
    ) : isEditMode ? (
      <div>No resources added yet...</div>
    ) : null}
  </div>
)}
```

#### Resource Card Rendering
- Displays type icon and colored badge
- Shows title, description, duration
- Has external link button (if URL present)
- Has delete button (in edit mode)
- Color-coded by resource type

#### ResourceFinder Modal Integration
```typescript
{showResourceFinder && (
  <ResourceFinder
    taskTitle={formData.title}
    taskDescription={formData.description}
    onAddResource={handleAddResource}
    isOpen={showResourceFinder}
    onClose={() => setShowResourceFinder(false)}
  />
)}
```

### Daily Schedule Component
**File:** `/Users/alexbenson/Joan/frontend/src/components/home/DailySchedule.tsx`

#### Resource Display
```typescript
// Shows resource count in task header
{task.resources && task.resources.length > 0 && (
  <span className="text-xs bg-purple-100 text-purple-700 px-2 py-1 rounded">
    {task.resources.length} resources
  </span>
)}

// Expandable resources section when task is expanded
{isExpanded && task.resources && task.resources.length > 0 && (
  <div className="mt-2 p-2 bg-purple-50 rounded">
    Resources ({task.resources.length})
    {task.resources.map((resource) => (
      <ResourcePreview resource={resource} />
    ))}
  </div>
)}
```

### TaskReviewerWithSchedule Component (Ceremony)
**File:** `/Users/alexbenson/Joan/frontend/src/components/ceremony/components/TaskReviewerWithSchedule.tsx`

#### Resource Management in Ceremony
- Shows resource count with sparkles icon
- Resource finder modal for each scheduled task
- Updates resources in scheduled_tasks state
- Persists resources to daily schedule on creation

---

## 6. Data Flow Diagram

### Creating/Updating Task with Resources

```
Frontend (TaskModalNew)
  ↓
[User clicks "Add Resource"]
  ↓
ResourceFinder Modal Opens
  ↓
[User searches or generates resources]
  ↓
AI Service (via useAI hook)
  ↓
[Returns JSON with resources array]
  ↓
handleAddResource() in TaskModalNew
  ↓
taskResources state updated
  ↓
[User clicks "Create/Update Task"]
  ↓
TaskCreate/TaskUpdate with resources field
  ↓
API: POST /tasks/ or PUT /tasks/{id}
  ↓
Backend: Creates/Updates task with resources
  ↓
Returns Task with resources embedded
  ↓
Frontend: Updates local state and closes modal
```

### Daily Schedule with Resources

```
Frontend (TaskReviewerWithSchedule - Ceremony)
  ↓
[Schedule created with scheduled_tasks]
  ↓
[User clicks sparkles for AI resources]
  ↓
ResourceFinder Modal Opens (specific to that scheduled task)
  ↓
[Resources generated based on task title/description]
  ↓
handleAddResource() updates scheduled_tasks[index].resources
  ↓
[All scheduled tasks persisted together]
  ↓
CreateDailyScheduleRequest {
    scheduled_tasks: [{..., resources: [...]}, ...]
}
  ↓
API: POST /daily-schedule/
  ↓
Backend: Stores in DailyScheduleTask.resources (JSON)
  ↓
Also updates DailySchedule.total_resources aggregate
```

---

## 7. Resource State Management Strategy

### Approach
- **Frontend-first:** Resources are managed in React component state
- **No dedicated database table:** Resources stored as JSON within task/schedule records
- **Inline storage:** Part of Task and DailyScheduleTask JSON columns
- **Ephemeral in memory:** Added/removed via UI before save

### Key Points
1. **In TaskModalNew:**
   - `taskResources` state tracks resources added by user
   - Resources only persisted when "Create/Update Task" button clicked
   - Resources sent as part of TaskCreate/TaskUpdate payload

2. **In Daily Schedule:**
   - Each scheduled task has its own `resources` array
   - Resources managed per-task within the schedule
   - All resources persisted when daily schedule is created/updated

3. **Backend Handling:**
   - Resources received as part of JSON payload
   - Stored as JSON in database (no normalization)
   - Returned as-is in GET responses
   - No separate resource table (currently)

---

## 8. Key Files Summary

| File | Purpose |
|------|---------|
| `frontend/src/types/task.ts` | Resource & Task TypeScript interfaces |
| `frontend/src/components/ceremony/components/ResourceFinder.tsx` | AI resource search/generation UI |
| `frontend/src/components/tasks/TaskModalNew.tsx` | Task editor with resources section |
| `frontend/src/components/home/DailySchedule.tsx` | Daily schedule with resource display |
| `frontend/src/components/ceremony/components/TaskReviewerWithSchedule.tsx` | Ceremony task reviewer with resource addition |
| `backend/app/models/task.py` | Task model (resources as payload) |
| `backend/app/models/daily_schedule.py` | DailyScheduleTask with JSON resources column |
| `backend/app/schemas/task.py` | Pydantic schemas for task API |
| `backend/app/api/tasks.py` | Task CRUD endpoints |
| `backend/app/api/daily_schedule.py` | Daily schedule endpoints |
| `frontend/src/services/taskApi.ts` | Task API client |

---

## 9. Current Limitations & Considerations

1. **No Resource Normalization**
   - Each resource is stored as duplicate JSON
   - No shared resource library
   - Potential for data redundancy

2. **No Resource Relationships**
   - Resources not linked to notes or other entities
   - Only associated with tasks/schedules

3. **No Search/Filter on Resources**
   - Can't query resources independently
   - No full-text search across all resources

4. **No Resource Versioning**
   - Updated task resources replace previous ones
   - No history tracking

5. **AI Model Dependency**
   - Resource generation requires LLM service
   - Quality depends on AI model selected

---

## 10. Future Enhancements Opportunities

1. **Dedicated Resource Table**
   - Normalize resources to avoid duplication
   - Allow sharing resources across tasks
   - Enable resource library/management

2. **Resource Annotations**
   - User notes on resources
   - Completion status
   - Rating/usefulness tracking

3. **Resource Search**
   - Full-text search across all resources
   - Filter by type, source, date

4. **Resource Sync**
   - Link resources between related tasks
   - Propagate to subtasks

5. **Export/Share**
   - Export resources as links/list
   - Share resource list with others

