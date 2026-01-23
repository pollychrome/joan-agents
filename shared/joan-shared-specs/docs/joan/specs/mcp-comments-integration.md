# MCP Server Comments Integration Specification

## Overview

This specification documents the updates made to the Joan MCP server (`joan-mcp`) to support comments on tasks and milestones. These changes enable AI assistants to read, create, update, and delete comments through the Model Context Protocol.

## API Endpoints

The MCP server integrates with the following Joan API endpoints:

### Task Comments

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/tasks/:taskId/comments` | List all comments on a task |
| POST | `/api/v1/tasks/:taskId/comments` | Create a new comment |
| PATCH | `/api/v1/tasks/:taskId/comments/:commentId` | Update a comment |
| DELETE | `/api/v1/tasks/:taskId/comments/:commentId` | Delete a comment |

### Milestone Comments

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/projects/:projectId/milestones/:milestoneId/comments` | List comments |
| POST | `/api/v1/projects/:projectId/milestones/:milestoneId/comments` | Create comment |
| PATCH | `/api/v1/projects/:projectId/milestones/:milestoneId/comments/:commentId` | Update comment |
| DELETE | `/api/v1/projects/:projectId/milestones/:milestoneId/comments/:commentId` | Delete comment |

---

## Type Definitions

Added to `src/client/types.ts`:

```typescript
/**
 * Comment on a task or milestone
 */
export interface Comment {
  id: string;
  entity_type: 'task' | 'milestone';
  entity_id: string;
  user_id: string;
  user_name?: string;
  content: string;
  created_at: string;
  updated_at: string;
}

/**
 * Input for creating a comment
 */
export interface CreateCommentInput {
  content: string;
}

/**
 * Input for updating a comment
 */
export interface UpdateCommentInput {
  content: string;
}
```

---

## API Client Methods

Added to `src/client/api-client.ts`:

### Task Comment Methods

```typescript
// List all comments on a task
async listTaskComments(taskId: string): Promise<Comment[]>

// Create a comment on a task
async createTaskComment(taskId: string, input: CreateCommentInput): Promise<Comment>

// Update a task comment
async updateTaskComment(taskId: string, commentId: string, input: UpdateCommentInput): Promise<Comment>

// Delete a task comment
async deleteTaskComment(taskId: string, commentId: string): Promise<void>
```

### Milestone Comment Methods

```typescript
// List all comments on a milestone
async listMilestoneComments(projectId: string, milestoneId: string): Promise<Comment[]>

// Create a comment on a milestone
async createMilestoneComment(projectId: string, milestoneId: string, input: CreateCommentInput): Promise<Comment>

// Update a milestone comment
async updateMilestoneComment(projectId: string, milestoneId: string, commentId: string, input: UpdateCommentInput): Promise<Comment>

// Delete a milestone comment
async deleteMilestoneComment(projectId: string, milestoneId: string, commentId: string): Promise<void>
```

---

## MCP Tools

File: `src/tools/comments.ts`

### Task Comment Tools

| Tool Name | Description | Parameters |
|-----------|-------------|------------|
| `list_task_comments` | List all comments on a task | `task_id: string (uuid)` |
| `create_task_comment` | Add a comment to a task | `task_id: string (uuid)`, `content: string (1-10000 chars)` |
| `update_task_comment` | Edit an existing comment | `task_id: string (uuid)`, `comment_id: string (uuid)`, `content: string` |
| `delete_task_comment` | Remove a comment | `task_id: string (uuid)`, `comment_id: string (uuid)` |

### Milestone Comment Tools

| Tool Name | Description | Parameters |
|-----------|-------------|------------|
| `list_milestone_comments` | List all comments on a milestone | `project_id: string (uuid)`, `milestone_id: string (uuid)` |
| `create_milestone_comment` | Add a comment to a milestone | `project_id: string (uuid)`, `milestone_id: string (uuid)`, `content: string` |
| `update_milestone_comment` | Edit a milestone comment | `project_id: string (uuid)`, `milestone_id: string (uuid)`, `comment_id: string (uuid)`, `content: string` |
| `delete_milestone_comment` | Remove a milestone comment | `project_id: string (uuid)`, `milestone_id: string (uuid)`, `comment_id: string (uuid)` |

### Tool Response Format

All list tools return formatted markdown:

```
Found 3 comment(s):

- **John Doe** (1/7/2026, 3:45:00 PM):
  "This is the comment content"

- **Jane Smith** (1/7/2026, 4:00:00 PM):
  "Another comment here"
```

Create/update/delete tools return confirmation messages:

```
Comment added to task abc123.
Comment ID: def456
```

---

## MCP Resources

File: `src/resources/comments.ts`

| URI Pattern | Description |
|-------------|-------------|
| `joan://tasks/{taskId}/comments` | Read-only access to task comments |
| `joan://projects/{projectId}/milestones/{milestoneId}/comments` | Read-only access to milestone comments |

### Resource Response Format

Resources return JSON with the full comment array:

```json
[
  {
    "id": "uuid",
    "entity_type": "task",
    "entity_id": "task-uuid",
    "user_id": "user-uuid",
    "user_name": "John Doe",
    "content": "Comment text",
    "created_at": "2026-01-07T15:45:00Z",
    "updated_at": "2026-01-07T15:45:00Z"
  }
]
```

---

## Registration

### Tools Registration

In `src/tools/index.ts`:

```typescript
import { registerCommentTools } from './comments.js';

export function registerAllTools(server: McpServer, client: JoanApiClient): void {
  // ... existing registrations
  registerCommentTools(server, client);
}
```

### Resources Registration

In `src/resources/index.ts`:

```typescript
import { registerCommentResources } from './comments.js';

export function registerAllResources(server: McpServer, client: JoanApiClient): void {
  // ... existing registrations
  registerCommentResources(server, client);
}
```

---

## Server Instructions Update

Added to `SERVER_INSTRUCTIONS` in `src/index.ts`:

```markdown
### Comments
- list_task_comments: Get all comments on a task (requires task_id)
- create_task_comment: Add a comment to a task (requires task_id, content)
- update_task_comment: Edit a task comment (requires task_id, comment_id, content)
- delete_task_comment: Remove a task comment (requires task_id, comment_id)
- list_milestone_comments: Get all comments on a milestone (requires project_id, milestone_id)
- create_milestone_comment: Add a comment to a milestone (requires project_id, milestone_id, content)
- update_milestone_comment: Edit a milestone comment
- delete_milestone_comment: Remove a milestone comment
```

---

## Permissions Model

Comments inherit permissions from their parent entity:

| Action | Owner/Admin | Contributor | Read-Only |
|--------|-------------|-------------|-----------|
| View comments | ✅ | ✅ | ✅ |
| Create comment | ✅ | ✅ | ❌ |
| Edit own comment | ✅ | ✅ | - |
| Edit others' comment | ✅ | ❌ | ❌ |
| Delete own comment | ✅ | ✅ | - |
| Delete others' comment | ✅ | ❌ | ❌ |

---

## Error Handling

All tools use the `formatErrorForMcp` utility for consistent error responses:

```typescript
try {
  // ... operation
} catch (error) {
  return { content: formatErrorForMcp(error) };
}
```

Common error scenarios:
- `404`: Task/milestone/comment not found
- `403`: Insufficient permissions to modify comment
- `400`: Invalid input (content too long, missing required fields)

---

## Files Changed

| File | Change Type |
|------|-------------|
| `src/client/types.ts` | Modified - Added Comment interfaces |
| `src/client/api-client.ts` | Modified - Added 8 API methods |
| `src/tools/comments.ts` | Created - 8 comment tools |
| `src/resources/comments.ts` | Created - 2 comment resources |
| `src/tools/index.ts` | Modified - Import and register |
| `src/resources/index.ts` | Modified - Import and register |
| `src/index.ts` | Modified - Updated SERVER_INSTRUCTIONS |

---

## Usage Examples

### List comments on a task

```
Tool: list_task_comments
Input: { "task_id": "abc123-..." }
```

### Add a comment

```
Tool: create_task_comment
Input: {
  "task_id": "abc123-...",
  "content": "This task needs review before we can proceed."
}
```

### Read comments via resource

```
Resource URI: joan://tasks/abc123-.../comments
```

---

## Version

- **joan-mcp version**: 1.2.0
- **Implementation date**: 2026-01-07
- **Backend migration**: `migrations/031_comments.sql`
