# Development Workflow

This guide explains how to set up and run Joan for local development.

## Prerequisites

- **Node.js 20+**: Required for frontend and Workers development
- **npm**: Package manager (comes with Node.js)
- **Git**: Version control
- **Cloudflare Account**: For wrangler CLI authentication (optional for local dev)

## Quick Start

The fastest way to start development:

```bash
# Clone the repository
git clone https://github.com/yourusername/Joan.git
cd Joan

# Start both Workers API and Frontend
./start-dev.sh
```

This will:
1. Install dependencies for both Workers and Frontend
2. Start the Workers API on port 8787
3. Start the Frontend dev server on port 5174
4. Wait for services to be ready

## Manual Setup

If you prefer to run services individually:

### 1. Workers API (Backend)

```bash
cd workers

# Install dependencies
npm install

# Create local secrets file
cp .dev.vars.example .dev.vars
# Edit .dev.vars with your local secrets

# Start development server
npx wrangler dev --port 8787
```

The API will be available at http://localhost:8787

### 2. Frontend

```bash
cd frontend

# Install dependencies
npm install

# Start development server
npm run dev
```

The frontend will be available at http://localhost:5174

## Local Development URLs

| Service | URL |
|---------|-----|
| Frontend | http://localhost:5174 |
| Workers API | http://localhost:8787 |
| Health Check | http://localhost:8787/health |

## Configuration Files

### Workers Secrets (`.dev.vars`)

Create `workers/.dev.vars` for local development secrets:

```env
JWT_SECRET=your-local-jwt-secret-change-this-in-production
API_ENCRYPTION_KEY=your-32-character-encryption-key-here
RESEND_API_KEY=your-resend-api-key-for-emails
```

### Frontend Environment (`.env`)

The frontend uses Vite's environment variables. For local development, the defaults work out of the box. For custom configuration, create `frontend/.env.local`:

```env
VITE_API_BASE_URL=http://localhost:8787/api/v1
```

## Git Workflow

We use a Gitflow-inspired branching strategy:

```
main ─────────────────────────────────────────► Production
  │
  └─► develop ─────────────────────────────────► Staging
        │
        ├─► feature/my-feature
        │
        └─► fix/bug-description
```

### Starting a New Feature

```bash
# Ensure you're on develop and up-to-date
git checkout develop
git pull origin develop

# Create your feature branch
git checkout -b feature/my-feature-name

# Make your changes, then commit
git add .
git commit -m "feat: add my new feature"

# Push and create a Pull Request
git push origin feature/my-feature-name
```

### Pull Request Flow

1. Create PR from your feature branch to `develop`
2. Await code review
3. After merge to `develop`, changes auto-deploy to staging
4. Test at https://staging.joan.nintai.app
5. When ready, create PR from `develop` to `main`
6. After merge to `main`, changes auto-deploy to production

## Database Migrations

### Creating a New Migration

1. Create a new SQL file in `/migrations/`:
   ```bash
   touch migrations/010_my_migration.sql
   ```

2. Write your migration SQL:
   ```sql
   -- migrations/010_my_migration.sql
   ALTER TABLE users ADD COLUMN new_field TEXT;
   ```

3. Apply to local D1 (if using):
   ```bash
   cd workers
   npx wrangler d1 execute joan-staging --file=../migrations/010_my_migration.sql --local
   ```

4. Apply to staging:
   ```bash
   npx wrangler d1 execute joan-staging --file=../migrations/010_my_migration.sql --remote
   ```

5. After testing, apply to production:
   ```bash
   npx wrangler d1 execute joan-production --file=../migrations/010_my_migration.sql --remote
   ```

## Common Issues

### Port Already in Use

If you see "Port X is already in use", you can:

1. Use the start script which offers to kill existing processes:
   ```bash
   ./start-dev.sh
   ```

2. Manually find and kill the process:
   ```bash
   lsof -i :8787
   kill -9 <PID>
   ```

### CORS Errors

If you get CORS errors in the browser:

1. Ensure the Workers API is running on port 8787
2. Check that your origin is in the allowed list in `workers/src/index.ts`
3. For local development, `http://localhost:5174` should be allowed

### Authentication Issues

If you're having trouble logging in:

1. Clear browser storage:
   ```javascript
   localStorage.clear(); sessionStorage.clear(); location.reload();
   ```

2. Check that `.dev.vars` has a valid `JWT_SECRET`

3. Verify the API is responding:
   ```bash
   curl http://localhost:8787/health
   ```

### Wrangler Authentication

If wrangler commands fail with auth errors:

```bash
npx wrangler login
```

This opens a browser for Cloudflare authentication.

## Deployment

Deployments are automated via GitHub Actions:

- **Push to `develop`** → Deploys to staging
- **Push to `main`** → Deploys to production

For manual deployments:

```bash
# Deploy Workers to staging
cd workers
npx wrangler deploy --env staging

# Deploy Workers to production
npx wrangler deploy --env production
```

See [DEPLOYMENT.md](./DEPLOYMENT.md) for detailed deployment documentation.

## Getting Help

- Check the [CLAUDE.md](./CLAUDE.md) for AI assistant guidance
- Review existing code patterns before implementing new features
- Ask questions in pull request discussions
