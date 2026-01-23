# MCP <-> Joan API Map

Base URL: JOAN_API_URL (default includes /api/v1). MCP client paths are relative to the base.

## Tools -> endpoints

### Projects and columns
- list_projects -> GET /projects
- get_project -> GET /projects/:projectId
- create_project -> POST /projects
- update_project -> PATCH /projects/:projectId
- list_columns -> GET /projects/:projectId/columns
- create_column -> POST /projects/:projectId/columns
- update_column -> PATCH /projects/:projectId/columns/:columnId
- delete_column -> DELETE /projects/:projectId/columns/:columnId?move_tasks_to=
- reorder_columns -> PUT /projects/:projectId/columns/reorder

### Tasks
- list_tasks -> GET /tasks (or GET /projects/:projectId/tasks when project_id is provided)
- get_task -> GET /tasks/:taskId/with-subtasks
- create_task -> POST /tasks
- update_task -> PATCH /tasks/:taskId
- complete_task -> POST /tasks/:taskId/complete
- delete_task -> DELETE /tasks/:taskId
- bulk_update_tasks -> POST /tasks/batch-reorder

### Tags
- list_project_tags -> GET /projects/:projectId/tags
- get_project_tag -> GET /projects/:projectId/tags/:tagId
- create_project_tag -> POST /projects/:projectId/tags
- update_project_tag -> PATCH /projects/:projectId/tags/:tagId
- delete_project_tag -> DELETE /projects/:projectId/tags/:tagId
- get_task_tags -> GET /projects/:projectId/tasks/:taskId/tags
- add_tag_to_task -> POST /projects/:projectId/tasks/:taskId/tags/:tagId
- remove_tag_from_task -> DELETE /projects/:projectId/tasks/:taskId/tags/:tagId
- set_task_tags -> PUT /projects/:projectId/tasks/:taskId/tags

### Milestones
- list_milestones -> GET /projects/:projectId/milestones
- get_milestone -> GET /projects/:projectId/milestones/:milestoneId
- create_milestone -> POST /projects/:projectId/milestones
- update_milestone -> PATCH /projects/:projectId/milestones/:milestoneId
- delete_milestone -> DELETE /projects/:projectId/milestones/:milestoneId
- link_tasks_to_milestone -> POST /projects/:projectId/milestones/:milestoneId/tasks
- unlink_task_from_milestone -> DELETE /projects/:projectId/milestones/:milestoneId/tasks/:taskId
- list_milestone_resources -> GET /projects/:projectId/milestones/:milestoneId/resources
- create_milestone_resource -> POST /projects/:projectId/milestones/:milestoneId/resources
- update_milestone_resource -> PATCH /projects/:projectId/milestones/:milestoneId/resources/:resourceId
- delete_milestone_resource -> DELETE /projects/:projectId/milestones/:milestoneId/resources/:resourceId

### Goals
- list_goals -> GET /goals
- get_goal -> GET /goals/:goalId
- create_goal -> POST /goals
- update_goal -> PATCH /goals/:goalId
- delete_goal -> DELETE /goals/:goalId
- link_task_to_goal -> POST /goals/:goalId/tasks
- unlink_task_from_goal -> DELETE /goals/:goalId/tasks/:taskId

### Notes
- list_notes -> GET /notes
- get_note -> GET /notes/:noteId
- create_note -> POST /notes
- update_note -> PATCH /notes/:noteId
- delete_note -> DELETE /notes/:noteId

### Comments
- list_task_comments -> GET /tasks/:taskId/comments
- create_task_comment -> POST /tasks/:taskId/comments
- update_task_comment -> PATCH /tasks/:taskId/comments/:commentId
- delete_task_comment -> DELETE /tasks/:taskId/comments/:commentId
- list_milestone_comments -> GET /projects/:projectId/milestones/:milestoneId/comments
- create_milestone_comment -> POST /projects/:projectId/milestones/:milestoneId/comments
- update_milestone_comment -> PATCH /projects/:projectId/milestones/:milestoneId/comments/:commentId
- delete_milestone_comment -> DELETE /projects/:projectId/milestones/:milestoneId/comments/:commentId

### Attachments
- upload_attachment -> POST /attachments/upload (multipart)
- get_attachment -> GET /attachments/:attachmentId/metadata
- get_attachment_download_url -> GET /attachments/:attachmentId/download?expires=
- update_attachment -> PATCH /attachments/:attachmentId
- delete_attachment -> DELETE /attachments/:attachmentId
- list_attachments -> GET /attachments/entity/:entityType/:entityId
- get_project_attachment_hierarchy -> GET /attachments/project/:projectId/hierarchy
- get_storage_usage -> GET /attachments/usage

### Resources (links/notes)
- list_task_resources -> GET /tasks/:taskId/resources
- create_task_resource -> POST /tasks/:taskId/resources
- update_task_resource -> PATCH /tasks/:taskId/resources/:resourceId
- delete_task_resource -> DELETE /tasks/:taskId/resources/:resourceId
- list_project_resources -> GET /projects/:projectId/resources
- create_project_resource -> POST /projects/:projectId/resources
- update_project_resource -> PATCH /projects/:projectId/resources/:resourceId
- delete_project_resource -> DELETE /projects/:projectId/resources/:resourceId
- list_milestone_resources -> GET /projects/:projectId/milestones/:milestoneId/resources
- create_milestone_resource -> POST /projects/:projectId/milestones/:milestoneId/resources
- update_milestone_resource -> PATCH /projects/:projectId/milestones/:milestoneId/resources/:resourceId
- delete_milestone_resource -> DELETE /projects/:projectId/milestones/:milestoneId/resources/:resourceId

## Resources -> endpoints
- joan://projects -> GET /projects
- joan://projects/{projectId} -> GET /projects/{projectId}
- joan://projects/{projectId}/tasks -> GET /projects/{projectId}/tasks
- joan://projects/{projectId}/milestones -> GET /projects/{projectId}/milestones
- joan://projects/{projectId}/columns -> GET /projects/{projectId}/columns
- joan://projects/{projectId}/analytics -> GET /projects/{projectId}/analytics
- joan://tasks -> GET /tasks
- joan://tasks/{taskId} -> GET /tasks/{taskId}/with-subtasks
- joan://tasks/{taskId}/comments -> GET /tasks/{taskId}/comments
- joan://tasks/{taskId}/attachments -> GET /attachments/entity/task/{taskId}
- joan://tasks/{taskId}/resources -> GET /tasks/{taskId}/resources
- joan://goals -> GET /goals
- joan://goals/{goalId} -> GET /goals/{goalId}
- joan://goals/{goalId}/stats -> GET /goals/{goalId}/stats
- joan://notes -> GET /notes
- joan://notes/{noteId} -> GET /notes/{noteId}
- joan://notes/{noteId}/attachments -> GET /attachments/entity/note/{noteId}
- joan://projects/{projectId}/attachments -> GET /attachments/entity/project/{projectId}
- joan://projects/{projectId}/attachments/hierarchy -> GET /attachments/project/{projectId}/hierarchy
- joan://projects/{projectId}/milestones/{milestoneId}/comments -> GET /projects/{projectId}/milestones/{milestoneId}/comments
- joan://projects/{projectId}/milestones/{milestoneId}/attachments -> GET /attachments/entity/milestone/{milestoneId}
- joan://projects/{projectId}/resources -> GET /projects/{projectId}/resources
- joan://attachments/{attachmentId} -> GET /attachments/{attachmentId}/metadata
- joan://attachments/usage -> GET /attachments/usage

## Sources
- joan-mcp/src/tools/*.ts
- joan-mcp/src/resources/*.ts
- joan-mcp/src/client/api-client.ts
