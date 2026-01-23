# Joan Admin Portal Access Guide

## Overview
The Joan application includes a comprehensive admin portal for managing ceremonies, AI providers, user profiles, and system configuration. This document provides instructions for accessing and using the admin portal.

## Access URL
- **Admin Portal URL**: http://localhost:5174/admin/ceremonies
- **Main Application**: http://localhost:5174/

## Admin Credentials

### Default Admin Account
```
Email:    admin@admin.com
Password: admin
```

⚠️ **Security Note**: These are development credentials. Change them immediately for any production deployment.

## Setting Up Admin Access

### Step 1: Ensure Backend is Running
```bash
cd backend
uvicorn main:app --reload --port 8000
```

### Step 2: Create/Reset Admin Account
Navigate to the backend directory and run the admin creation script:

```bash
cd backend
python create_admin.py
```

This script will:
- Create a new admin user if none exists
- Update the first existing user to admin credentials if users exist
- Reset the admin password if the admin account already exists

Expected output:
```
Joan Admin Account Setup
==================================================
✓ Created new admin user: admin@admin.com

==================================================
Admin account ready!
==================================================
Email:    admin@admin.com
Password: admin
==================================================

You can now log in with these credentials.
```

### Step 3: Start Frontend Development Server
```bash
cd frontend
npm run dev
```

### Step 4: Access the Admin Portal
1. Open your browser and navigate to http://localhost:5174/
2. Click the login button or navigate to the login page
3. Enter the admin credentials:
   - Email: admin@admin.com
   - Password: admin
4. After successful login, navigate to: http://localhost:5174/admin/ceremonies

## Admin Portal Features

### 1. Ceremony Templates
- **Location**: Main tab in admin portal
- **Features**:
  - View all ceremony templates (system and custom)
  - Create new ceremony templates
  - Edit existing templates (name, description, AI prompts, workflow steps)
  - Toggle template active/inactive status
  - Delete custom templates (system templates cannot be deleted)
  - Test templates with sample data

### 2. Components Management
- **Location**: Components tab
- **Features**:
  - View all ceremony components
  - Filter by type and AI-enabled status
  - Edit component configurations
  - Modify AI base prompts for AI-enabled components
  - Set model overrides for specific components

### 3. AI Provider Management
- **Location**: AI Providers tab
- **Features**:
  - View all configured AI providers (OpenAI, Anthropic, Groq, Ollama)
  - Check provider status (active/inactive)
  - View usage statistics (request count, total cost)
  - Set default provider
  - Configure provider priorities
  - Add new provider configurations
  - Update API keys and endpoints

### 4. Prompt Library
- **Location**: Prompt Library tab
- **Features**:
  - Manage reusable AI prompt templates
  - Create and edit prompt templates
  - Categorize prompts for easy access
  - Version control for prompts

### 5. Smart Routing Configuration
- **Location**: Smart Routing tab
- **Features**:
  - Configure routing rules for different task types
  - Set up fallback chains for provider failures
  - Define provider selection based on:
    - Quality requirements
    - Speed requirements
    - JSON output needs
    - Context length requirements

### 6. Metrics Dashboard
- **Location**: Metrics tab
- **Features**:
  - View AI usage statistics across all providers
  - Monitor success rates
  - Track response times
  - Analyze costs per provider
  - Export metrics for reporting

## User Profile Management

### Accessing User Profiles
While the current admin portal focuses on ceremony and AI management, user profile administration can be done through:

1. **Direct Database Access** (Development):
   - Use database management tools to directly modify user records
   - Update fields like `is_superuser`, `is_active`, payment status

2. **API Endpoints** (Recommended):
   - Use the backend API endpoints for user management
   - Example endpoints:
     - GET `/api/users` - List all users
     - PATCH `/api/users/{user_id}` - Update user details
     - GET `/api/users/{user_id}/profile` - View user profile

3. **Future Enhancement**: A dedicated user management interface is planned for the admin portal.

## Common Administrative Tasks

### Making a User an Admin
1. Access the database or use the API
2. Set `is_superuser = true` for the user
3. User will have access to admin features on next login

### Enabling/Disabling User Features
- Set `is_active` to control login access
- Update custom user properties for feature flags
- Modify user subscription/payment status as needed

### Testing Ceremonies
1. Navigate to Ceremony Templates tab
2. Click on a template to expand details
3. Click "Test Template" button
4. Enter test data in the modal
5. Review test results and AI responses

## Troubleshooting

### Cannot Access Admin Portal
1. Verify you're logged in with admin credentials
2. Check that `is_superuser = true` in the database
3. Clear browser cache and cookies
4. Restart both frontend and backend servers

### Admin Account Issues
1. Re-run `python create_admin.py` to reset credentials
2. Check database connection in backend logs
3. Verify no authentication middleware is blocking access

### Missing Admin Features
1. Ensure you're on the latest code version
2. Check that all database migrations have run
3. Verify API routes are properly registered in backend

## Security Recommendations

1. **Change Default Password**: Immediately change the default admin password after first login
2. **Use Environment Variables**: Store sensitive configuration in environment variables
3. **Enable HTTPS**: Use HTTPS in production environments
4. **Implement Rate Limiting**: Add rate limiting to admin endpoints
5. **Audit Logging**: Enable detailed logging for all admin actions
6. **Regular Backups**: Maintain regular database backups before major changes

## API Documentation

For direct API access to admin functions, the following endpoints are available:

### Ceremony Management
- `GET /api/admin/ceremonies/templates` - List all templates
- `POST /api/admin/ceremonies/templates` - Create template
- `PATCH /api/admin/ceremonies/templates/{id}` - Update template
- `DELETE /api/admin/ceremonies/templates/{id}` - Delete template

### AI Provider Management
- `GET /api/admin/ceremonies/ai/providers` - List providers
- `POST /api/admin/ceremonies/ai/providers` - Add provider
- `PATCH /api/admin/ceremonies/ai/providers/{id}` - Update provider

### Metrics
- `GET /api/admin/ceremonies/ai/metrics` - Get usage metrics
- `GET /api/admin/ceremonies/ai/metrics/summary` - Get summary statistics

## Support and Further Development

For additional admin features or custom requirements:
1. Check the project roadmap in PROJECTPLAN.md
2. Review existing issues in the project repository
3. Contact the development team for custom feature requests

---

**Last Updated**: November 2024
**Version**: 1.0.0