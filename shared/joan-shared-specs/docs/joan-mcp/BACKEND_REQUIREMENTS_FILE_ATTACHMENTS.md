# Backend API Requirements: File Attachments & Document Uploads

## Overview

This document outlines the backend API requirements needed to support file uploads and document attachments within the Joan MCP server. These endpoints would enable users to attach files/documents to **projects**, **milestones**, and **tasks**.

---

## 1. Data Models

### 1.1 Attachment Entity

```typescript
interface Attachment {
  id: string;                          // Unique identifier (UUID)

  // Relationship (one of these will be set)
  project_id?: string;                 // If attached to a project
  milestone_id?: string;               // If attached to a milestone
  task_id?: string;                    // If attached to a task

  // File metadata
  filename: string;                    // Original filename
  display_name: string;                // User-friendly display name
  description?: string;                // Optional description
  mime_type: string;                   // e.g., "application/pdf", "image/png"
  file_size: number;                   // Size in bytes
  file_extension: string;              // e.g., "pdf", "docx", "png"

  // Storage
  storage_url: string;                 // URL to access the file (signed URL or CDN)
  storage_key: string;                 // Internal storage reference (S3 key, etc.)

  // Classification
  category?: AttachmentCategory;       // Optional categorization
  tags?: string[];                     // Optional tags for organization

  // Audit
  created_by: string;                  // User ID who uploaded
  created_at: string;                  // ISO 8601 timestamp
  updated_at: string;                  // ISO 8601 timestamp
}

type AttachmentCategory =
  | 'document'      // PDFs, Word docs, spreadsheets
  | 'image'         // PNG, JPG, GIF, SVG
  | 'video'         // MP4, MOV, etc.
  | 'audio'         // MP3, WAV, etc.
  | 'archive'       // ZIP, TAR, etc.
  | 'code'          // Source files
  | 'other';        // Uncategorized
```

### 1.2 Resource Entity (Links - Existing Enhancement)

Enhance the existing resource model to differentiate from file attachments:

```typescript
interface Resource {
  id: string;

  // Relationship
  project_id?: string;
  milestone_id?: string;
  task_id?: string;

  // Resource data
  type: 'link' | 'note' | 'article' | 'video' | 'book' | 'tool' | 'guide';
  title: string;
  url?: string;                        // External URL
  content?: string;                    // For notes/inline content
  description?: string;
  source?: string;                     // Source attribution

  // Audit
  created_by: string;
  created_at: string;
  updated_at: string;
}
```

---

## 2. API Endpoints

### 2.1 File Upload Endpoints

#### Upload Attachment

```
POST /api/v1/attachments/upload
Content-Type: multipart/form-data
```

**Request Body (multipart/form-data):**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `file` | File | Yes | The file to upload |
| `project_id` | string | Conditional | Project to attach to (one of project_id, milestone_id, or task_id required) |
| `milestone_id` | string | Conditional | Milestone to attach to |
| `task_id` | string | Conditional | Task to attach to |
| `display_name` | string | No | Custom display name (defaults to filename) |
| `description` | string | No | Description of the attachment |
| `category` | string | No | Category classification |
| `tags` | string[] | No | Tags for organization |

**Response (201 Created):**
```json
{
  "id": "att_abc123",
  "filename": "project-spec.pdf",
  "display_name": "Project Specification",
  "description": "Initial project specification document",
  "mime_type": "application/pdf",
  "file_size": 245678,
  "file_extension": "pdf",
  "storage_url": "https://storage.joan.app/attachments/att_abc123/project-spec.pdf?token=...",
  "category": "document",
  "tags": ["specification", "planning"],
  "project_id": "proj_xyz789",
  "created_by": "user_123",
  "created_at": "2025-01-09T10:30:00Z",
  "updated_at": "2025-01-09T10:30:00Z"
}
```

**Error Responses:**
- `400 Bad Request` - Invalid file or missing required fields
- `413 Payload Too Large` - File exceeds size limit
- `415 Unsupported Media Type` - File type not allowed
- `404 Not Found` - Parent entity (project/milestone/task) not found

---

#### Get Upload URL (Pre-signed URL for Direct Upload)

For large files, support direct-to-storage uploads:

```
POST /api/v1/attachments/upload-url
Content-Type: application/json
```

**Request Body:**
```json
{
  "filename": "large-video.mp4",
  "mime_type": "video/mp4",
  "file_size": 104857600,
  "project_id": "proj_xyz789"
}
```

**Response (200 OK):**
```json
{
  "upload_url": "https://storage.googleapis.com/joan-uploads/...",
  "upload_method": "PUT",
  "upload_headers": {
    "Content-Type": "video/mp4"
  },
  "attachment_id": "att_pending_123",
  "expires_at": "2025-01-09T11:30:00Z"
}
```

---

#### Confirm Upload (After Direct Upload)

```
POST /api/v1/attachments/{attachmentId}/confirm
```

**Request Body:**
```json
{
  "display_name": "Project Demo Video",
  "description": "Demo of the new feature",
  "tags": ["demo", "video"]
}
```

**Response (200 OK):** Returns the completed Attachment object

---

### 2.2 Attachment Management Endpoints

#### List Attachments

```
GET /api/v1/projects/{projectId}/attachments
GET /api/v1/projects/{projectId}/milestones/{milestoneId}/attachments
GET /api/v1/tasks/{taskId}/attachments
```

**Query Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| `category` | string | Filter by category |
| `mime_type` | string | Filter by MIME type |
| `tags` | string[] | Filter by tags |
| `limit` | number | Pagination limit (default: 20, max: 100) |
| `offset` | number | Pagination offset |
| `sort` | string | Sort field: `created_at`, `filename`, `file_size` |
| `order` | string | Sort order: `asc`, `desc` |

**Response (200 OK):**
```json
{
  "attachments": [
    {
      "id": "att_abc123",
      "filename": "project-spec.pdf",
      "display_name": "Project Specification",
      "mime_type": "application/pdf",
      "file_size": 245678,
      "storage_url": "https://...",
      "category": "document",
      "created_at": "2025-01-09T10:30:00Z"
    }
  ],
  "total": 15,
  "limit": 20,
  "offset": 0
}
```

---

#### Get Attachment

```
GET /api/v1/attachments/{attachmentId}
```

**Response (200 OK):** Returns full Attachment object

---

#### Update Attachment Metadata

```
PATCH /api/v1/attachments/{attachmentId}
```

**Request Body:**
```json
{
  "display_name": "Updated Name",
  "description": "Updated description",
  "category": "document",
  "tags": ["updated", "tags"]
}
```

**Response (200 OK):** Returns updated Attachment object

---

#### Delete Attachment

```
DELETE /api/v1/attachments/{attachmentId}
```

**Response (204 No Content)**

---

#### Download Attachment (Generate Download URL)

```
GET /api/v1/attachments/{attachmentId}/download
```

**Query Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| `expires` | number | URL expiration in seconds (default: 3600) |

**Response (200 OK):**
```json
{
  "download_url": "https://storage.joan.app/...",
  "expires_at": "2025-01-09T11:30:00Z",
  "filename": "project-spec.pdf"
}
```

---

### 2.3 Resource Management Endpoints (Links/Notes)

#### Create Resource

```
POST /api/v1/projects/{projectId}/resources
POST /api/v1/projects/{projectId}/milestones/{milestoneId}/resources
POST /api/v1/tasks/{taskId}/resources
```

**Request Body:**
```json
{
  "type": "link",
  "title": "Design Reference",
  "url": "https://figma.com/file/...",
  "description": "Main design file for the project"
}
```

**Response (201 Created):** Returns Resource object

---

#### List Resources

```
GET /api/v1/projects/{projectId}/resources
GET /api/v1/projects/{projectId}/milestones/{milestoneId}/resources
GET /api/v1/tasks/{taskId}/resources
```

**Response (200 OK):**
```json
{
  "resources": [...],
  "total": 5
}
```

---

#### Update Resource

```
PATCH /api/v1/resources/{resourceId}
```

---

#### Delete Resource

```
DELETE /api/v1/resources/{resourceId}
```

---

## 3. File Handling Requirements

### 3.1 Supported File Types

| Category | Extensions | MIME Types |
|----------|------------|------------|
| Documents | pdf, doc, docx, xls, xlsx, ppt, pptx, txt, rtf, odt, ods, odp | application/pdf, application/msword, ... |
| Images | png, jpg, jpeg, gif, svg, webp, bmp | image/* |
| Videos | mp4, mov, avi, mkv, webm | video/* |
| Audio | mp3, wav, ogg, m4a, flac | audio/* |
| Archives | zip, tar, gz, rar, 7z | application/zip, ... |
| Code | js, ts, py, java, go, rs, rb, php, c, cpp, h, json, yaml, yml, md, html, css | text/*, application/json, ... |

### 3.2 Size Limits

| Upload Method | Maximum Size | Notes |
|---------------|--------------|-------|
| Direct upload (`/upload`) | 25 MB | For typical documents |
| Pre-signed URL upload | 5 GB | For large files (video, archives) |

### 3.3 Storage Requirements

- Files should be stored in a cloud storage service (S3, GCS, Azure Blob)
- Generate signed URLs for secure, time-limited access
- Support for CDN distribution for frequently accessed files
- Automatic virus/malware scanning on upload
- File deduplication (optional, based on content hash)

### 3.4 Security Requirements

- Validate MIME type matches file extension
- Scan files for malware before making available
- Signed URLs should expire (default: 1 hour)
- Enforce per-user and per-project storage quotas
- Audit logging for all file operations

---

## 4. MCP Server Integration

Once these endpoints are available, the MCP server will expose the following tools:

### 4.1 Attachment Tools

```typescript
// Tool: upload_attachment
{
  name: "upload_attachment",
  description: "Upload a file attachment to a project, milestone, or task",
  inputSchema: {
    type: "object",
    properties: {
      file_path: { type: "string", description: "Local path to the file to upload" },
      project_id: { type: "string" },
      milestone_id: { type: "string" },
      task_id: { type: "string" },
      display_name: { type: "string" },
      description: { type: "string" },
      category: { type: "string" },
      tags: { type: "array", items: { type: "string" } }
    },
    required: ["file_path"]
  }
}

// Tool: list_attachments
{
  name: "list_attachments",
  description: "List attachments for a project, milestone, or task",
  inputSchema: {
    type: "object",
    properties: {
      project_id: { type: "string" },
      milestone_id: { type: "string" },
      task_id: { type: "string" },
      category: { type: "string" },
      limit: { type: "number" }
    }
  }
}

// Tool: get_attachment
{
  name: "get_attachment",
  description: "Get details of a specific attachment",
  inputSchema: {
    type: "object",
    properties: {
      attachment_id: { type: "string" }
    },
    required: ["attachment_id"]
  }
}

// Tool: delete_attachment
{
  name: "delete_attachment",
  description: "Delete an attachment",
  inputSchema: {
    type: "object",
    properties: {
      attachment_id: { type: "string" }
    },
    required: ["attachment_id"]
  }
}

// Tool: get_attachment_download_url
{
  name: "get_attachment_download_url",
  description: "Get a temporary download URL for an attachment",
  inputSchema: {
    type: "object",
    properties: {
      attachment_id: { type: "string" }
    },
    required: ["attachment_id"]
  }
}
```

### 4.2 Resource Tools

```typescript
// Tool: create_resource
{
  name: "create_resource",
  description: "Create a link or note resource attached to a project, milestone, or task",
  inputSchema: {
    type: "object",
    properties: {
      type: { type: "string", enum: ["link", "note", "article", "video", "book", "tool", "guide"] },
      title: { type: "string" },
      url: { type: "string" },
      content: { type: "string" },
      description: { type: "string" },
      project_id: { type: "string" },
      milestone_id: { type: "string" },
      task_id: { type: "string" }
    },
    required: ["type", "title"]
  }
}

// Tool: list_resources
// Tool: update_resource
// Tool: delete_resource
```

### 4.3 MCP Resources (Read-Only Access)

```typescript
// Expose attachment lists as readable resources
"joan://projects/{projectId}/attachments"
"joan://projects/{projectId}/milestones/{milestoneId}/attachments"
"joan://tasks/{taskId}/attachments"
```

---

## 5. Implementation Priority

### Phase 1: Core Attachment Support
1. Attachment data model and database schema
2. Direct upload endpoint (`POST /attachments/upload`)
3. List attachments by parent entity
4. Get single attachment
5. Delete attachment

### Phase 2: Enhanced Features
1. Pre-signed URL upload for large files
2. Download URL generation
3. Attachment metadata updates
4. Category and tag support

### Phase 3: Resource Management
1. Create resource endpoint
2. Update/delete resource endpoints
3. Resource listing with filters

### Phase 4: Advanced Features
1. Storage quotas and limits
2. Virus scanning integration
3. Thumbnail generation for images/videos
4. Full-text search in documents

---

## 6. Questions for Backend Team

1. **Storage Provider**: Which cloud storage will be used (S3, GCS, Azure)?
2. **Authentication**: How should file access be authenticated? (JWT in URL, separate auth header?)
3. **Quotas**: What are the storage limits per user/project?
4. **Retention**: Should deleted files be soft-deleted with a retention period?
5. **Versioning**: Should file versioning be supported?
6. **Thumbnails**: Should the backend generate thumbnails for images/videos?
7. **Search**: Should file contents be indexed for search (e.g., PDF text extraction)?

---

## 7. API Response Codes Summary

| Code | Meaning | When Used |
|------|---------|-----------|
| 200 | OK | Successful GET, PATCH |
| 201 | Created | Successful POST (new resource) |
| 204 | No Content | Successful DELETE |
| 400 | Bad Request | Invalid request body, missing fields |
| 401 | Unauthorized | Invalid/missing authentication |
| 403 | Forbidden | No permission to access resource |
| 404 | Not Found | Resource/parent entity doesn't exist |
| 409 | Conflict | Duplicate resource (if applicable) |
| 413 | Payload Too Large | File exceeds size limit |
| 415 | Unsupported Media Type | File type not allowed |
| 429 | Too Many Requests | Rate limit exceeded |
| 500 | Internal Server Error | Server-side error |
