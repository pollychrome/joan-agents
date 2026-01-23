# Resource Handling System - Documentation Index

## Overview

Joan has implemented a comprehensive resource handling system that allows users to attach AI-generated or manually found resources to tasks. This documentation covers the complete architecture, implementation details, and integration points.

## Documentation Files

### 1. RESOURCE_HANDLING_OVERVIEW.md (591 lines)
**Comprehensive architectural documentation**
- Complete resource type definitions
- ResourceFinder AI component implementation details
- Storage and persistence architecture
- API endpoints documentation
- Component integration guide
- Data flow diagrams
- State management strategy
- Future enhancement opportunities

**Best for:** Understanding the complete system architecture and design decisions.

### 2. RESOURCE_SYSTEM_QUICK_REFERENCE.txt (155 lines)
**Quick lookup reference**
- ASCII tree-formatted structure
- Key components summary
- Data flow at a glance
- API endpoints quick list
- File mapping
- State flow simplified
- Current implementation status
- Limitations and considerations

**Best for:** Quick lookups, high-level overview, and decision making.

### 3. RESOURCE_HANDLING_KEY_FILES.md (291 lines)
**Complete file reference with line numbers**
- All frontend components with file paths
- All backend models and APIs with line numbers
- Frontend services and hooks
- Backend schemas and migrations
- Database schema files
- AI/LLM integration points
- Settings and configuration
- Data structure examples
- File relationships map

**Best for:** Finding specific code locations, file structure, and implementation details.

## Quick Start Guide

### For Understanding the System
1. Start with RESOURCE_SYSTEM_QUICK_REFERENCE.txt for high-level overview
2. Read RESOURCE_HANDLING_OVERVIEW.md section 1-3 for concepts
3. Check RESOURCE_HANDLING_KEY_FILES.md for exact file locations

### For Implementation Work
1. Use RESOURCE_HANDLING_KEY_FILES.md to locate files
2. Refer to line numbers for specific sections
3. Check RESOURCE_HANDLING_OVERVIEW.md for architectural context

### For Integration
1. See RESOURCE_HANDLING_OVERVIEW.md section 5-6 for component integration
2. Check API endpoints in section 4
3. Reference data flow diagrams in section 6

## System Architecture Summary

### Frontend Components
- **ResourceFinder** - AI-powered resource search/generation modal
- **TaskModalNew** - Task editor with resources section
- **TaskReviewerWithSchedule** - Ceremony planner with resources
- **DailySchedule** - Schedule view with resource display

### Backend Components
- **Task API** - CRUD operations with resource payload handling
- **Daily Schedule API** - Schedule management with embedded resources
- **Models** - Task and DailyScheduleTask with JSON resource columns

### Key Integration Points
1. ResourceFinder generates resources via AI
2. Resources added to task/schedule state
3. Resources persisted with save action
4. Resources displayed with type-specific styling
5. Resources loaded with task/schedule retrieval

## Resource Type System

9 types with color-coded visual representation:
1. **article** - Blue (FileText icon)
2. **video** - Red (Video icon)
3. **book** - Purple (Book icon)
4. **tool** - Green (Link icon)
5. **tip** - Yellow (Lightbulb icon)
6. **plan** - Indigo (Brain icon)
7. **workout** - Orange (Brain icon)
8. **guide** - Cyan (FileText icon)
9. **generated** - Purple (Sparkles icon)

## Core Features

### Currently Implemented
- AI-powered resource generation with multiple provider support
- Custom search queries for resources
- Type-based visual categorization
- Generated content display with markdown
- External link support
- Resource display in task modals
- Resource management in daily schedules
- Ceremony planner resource integration

### Not Yet Implemented
- Dedicated resource database table
- Resource library/sharing
- Full-text search on resources
- Resource versioning
- Resource annotations/ratings
- Resource deduplication

## API Endpoints

### Task Endpoints
- `POST /tasks/` - Create with resources
- `PUT /tasks/{id}` - Update with resources
- `GET /tasks/` - List with resources
- `GET /tasks/{id}` - Get with resources
- `GET /tasks/{id}/with-subtasks` - Get with subtasks

### Daily Schedule Endpoints
- `POST /daily-schedule/` - Create schedule with resources
- `PATCH /daily-schedule/{id}` - Update resources
- `GET /daily-schedule/today` - Today's schedule

### Settings Endpoints
- `GET /settings/available-models` - Available AI models

## Data Structure Examples

### Resource Object
```json
{
  "id": "string",
  "title": "string",
  "description": "string",
  "type": "article|video|book|tool|tip|plan|workout|guide|generated",
  "url": "string (optional)",
  "content": "string (optional - for generated)",
  "source": "string (optional)",
  "duration": "string (optional)"
}
```

### Task with Resources
```json
{
  "id": "string",
  "title": "string",
  "resources": [
    { "Resource object" }
  ]
}
```

### Scheduled Task with Resources
```json
{
  "taskId": "string",
  "startTime": "HH:MM",
  "duration": number,
  "resources": [
    { "Resource object" }
  ]
}
```

## File Structure

```
frontend/src/
├── types/task.ts                              - Resource interface
├── components/
│   ├── ceremony/components/ResourceFinder.tsx - AI resource finder
│   ├── tasks/TaskModalNew.tsx                 - Task editor
│   ├── ceremony/components/TaskReviewerWithSchedule.tsx
│   └── home/DailySchedule.tsx                 - Schedule view
└── services/taskApi.ts                        - Task API client

backend/app/
├── models/
│   ├── task.py                                - Task model
│   └── daily_schedule.py                      - Schedule models
├── schemas/task.py                            - Pydantic schemas
└── api/
    ├── tasks.py                               - Task endpoints
    └── daily_schedule.py                      - Schedule endpoints
```

## State Management

### Frontend State Flow
1. User opens ResourceFinder
2. ResourceFinder queries AI with task context
3. AI returns resource array (JSON)
4. Resources displayed in ResourceFinder modal
5. User adds resources to task/schedule
6. Resources stored in component state (taskResources/scheduled_tasks)
7. On save, resources included in API payload
8. Backend accepts and stores resources

### Backend Storage
- Resources stored as JSON in DailyScheduleTask.resources column
- Resources passed through Task API as payload
- No dedicated database table (currently)

## Integration Points

1. **AI Integration** - ResourceFinder uses useAI hook with configurable models
2. **Task Integration** - TaskModalNew manages task with resources
3. **Schedule Integration** - TaskReviewerWithSchedule manages schedule resources
4. **API Integration** - Task API accepts/returns resources in payload
5. **Database Integration** - DailyScheduleTask stores resources as JSON

## Error Handling

ResourceFinder handles:
- API timeouts (90 second limit)
- Authentication failures (401)
- Rate limiting (429)
- JSON parsing errors
- Network errors

## Performance Considerations

1. Resources stored as JSON - efficient for small datasets
2. No indexing on resource fields - queries not optimized
3. Duplicate storage - same resource stored multiple times
4. AI queries can be slow (local AI: 30-60 seconds)

## Future Enhancements

1. Create dedicated `resources` table
2. Add `task_resources` junction table
3. Implement resource library
4. Add resource search capability
5. Create resource annotations system
6. Implement resource versioning
7. Add resource deduplication
8. Create resource sharing features

## Development Guidelines

### Adding New Resource Types
1. Update Resource interface in frontend/src/types/task.ts
2. Add icon in ResourceFinder.tsx (line 27-37)
3. Add color mapping in ResourceFinder.tsx (line 39-49)
4. Add type config in TaskModalNew.tsx (line 824-834)

### Modifying Resource Storage
1. Update resource schema if needed
2. Check API endpoints for impact
3. Test with both task and schedule flows
4. Ensure backward compatibility

### Testing Resources
1. Test AI generation with different models
2. Test custom search queries
3. Test resource add/remove flows
4. Test persistence (save and reload)
5. Test display in all contexts

## Common Tasks

### Finding Resource Code
Use RESOURCE_HANDLING_KEY_FILES.md with line numbers

### Understanding Data Flow
See RESOURCE_HANDLING_OVERVIEW.md sections 6

### Quick Component Reference
See RESOURCE_SYSTEM_QUICK_REFERENCE.txt

### API Details
See RESOURCE_HANDLING_OVERVIEW.md section 4

### Implementation Details
See specific file sections in RESOURCE_HANDLING_KEY_FILES.md

---

**Last Updated:** November 7, 2025
**Documentation Scope:** Complete resource handling system
**Version:** 1.0
