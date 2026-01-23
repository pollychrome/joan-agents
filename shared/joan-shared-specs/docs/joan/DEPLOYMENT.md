# Joan Deployment Guide

This guide covers deploying Joan to Cloudflare's edge infrastructure.

## Architecture Overview

Joan runs entirely on Cloudflare's infrastructure:

```
┌─────────────────────────────────────────────────────────────┐
│                     GitHub Repository                        │
│  ┌──────────────┐                    ┌──────────────┐       │
│  │   develop    │ ─── push ────>     │    main      │       │
│  │   branch     │                    │    branch    │       │
│  └──────────────┘                    └──────────────┘       │
│         │                                   │                │
│         ▼                                   ▼                │
│   GitHub Actions                     GitHub Actions          │
└─────────────────────────────────────────────────────────────┘
         │                                   │
         ▼                                   ▼
┌─────────────────────┐         ┌─────────────────────┐
│   STAGING ENV       │         │   PRODUCTION ENV    │
├─────────────────────┤         ├─────────────────────┤
│ Frontend:           │         │ Frontend:           │
│ staging.joan.nintai │         │ joan.nintai.app     │
│                     │         │                     │
│ Workers API:        │         │ Workers API:        │
│ staging-api.joan... │         │ joan-api.alex...    │
│                     │         │                     │
│ D1: joan-staging    │         │ D1: joan-production │
│ R2: attachments-stg │         │ R2: joan-attachments│
└─────────────────────┘         └─────────────────────┘
```

## CI/CD with GitHub Actions

Deployments are automated via GitHub Actions:

- **Push to `develop`** → Deploys to staging environment
- **Push to `main`** → Deploys to production environment

### Required GitHub Secrets

Configure these in your repository settings (Settings → Secrets → Actions):

| Secret | Description |
|--------|-------------|
| `CLOUDFLARE_API_TOKEN` | API token with Workers, Pages, D1, R2 permissions |
| `CLOUDFLARE_ACCOUNT_ID` | Your Cloudflare account ID |

### Workflow Files

- `.github/workflows/deploy-staging.yml` - Staging deployment
- `.github/workflows/deploy-production.yml` - Production deployment

## Manual Deployment

### Deploy Workers API

```bash
cd workers

# Deploy to staging
npx wrangler deploy --env staging

# Deploy to production
npx wrangler deploy --env production
```

### Deploy Frontend

```bash
cd frontend

# Build for staging
VITE_API_BASE_URL=https://staging-api.joan.nintai.app/api/v1 npm run build

# Deploy to staging
npx wrangler pages deploy dist --project-name=joan-staging

# Build for production
VITE_API_BASE_URL=https://joan-api.alexbbenson.workers.dev/api/v1 npm run build

# Deploy to production
npx wrangler pages deploy dist --project-name=joan
```

## Environment Configuration

### Workers Environment Variables

Configured in `workers/wrangler.toml`:

```toml
[env.staging]
vars = { ENVIRONMENT = "staging", FRONTEND_URL = "https://staging.joan.nintai.app" }

[env.production]
vars = { ENVIRONMENT = "production", FRONTEND_URL = "https://joan.nintai.app" }
```

### Workers Secrets

Set secrets for each environment:

```bash
cd workers

# Staging secrets
npx wrangler secret put JWT_SECRET --env staging
npx wrangler secret put API_ENCRYPTION_KEY --env staging
npx wrangler secret put RESEND_API_KEY --env staging

# Production secrets
npx wrangler secret put JWT_SECRET --env production
npx wrangler secret put API_ENCRYPTION_KEY --env production
npx wrangler secret put RESEND_API_KEY --env production
```

### Frontend Environment Variables

Set in Cloudflare Pages dashboard or during build:

| Variable | Staging | Production |
|----------|---------|------------|
| `VITE_API_BASE_URL` | `https://staging-api.joan.nintai.app/api/v1` | `https://joan-api.alexbbenson.workers.dev/api/v1` |

## Database Migrations

### Apply Migrations

```bash
cd workers

# Apply to staging
npx wrangler d1 execute joan-staging --file=../migrations/XXX_migration.sql --remote

# Apply to production
npx wrangler d1 execute joan-production --file=../migrations/XXX_migration.sql --remote
```

### Query Database

```bash
# Query staging
npx wrangler d1 execute joan-staging --command="SELECT COUNT(*) FROM users" --remote

# Query production
npx wrangler d1 execute joan-production --command="SELECT COUNT(*) FROM users" --remote
```

## Custom Domains

### Frontend Domains

Configure in Cloudflare Pages dashboard:

- **Production**: joan.nintai.app
- **Staging**: staging.joan.nintai.app

### Workers Domains

Configure in `wrangler.toml` or Cloudflare dashboard:

```toml
[[env.staging.routes]]
pattern = "staging-api.joan.nintai.app/*"
custom_domain = true
```

## Monitoring

### View Logs

```bash
# Staging logs
npx wrangler tail --env staging

# Production logs
npx wrangler tail --env production
```

### Health Checks

```bash
# Staging
curl https://staging-api.joan.nintai.app/health

# Production
curl https://joan-api.alexbbenson.workers.dev/health
```

### Cloudflare Dashboard

- Workers analytics: Workers & Pages → joan-api → Analytics
- Pages deployments: Workers & Pages → joan → Deployments
- D1 metrics: D1 → Database → Metrics

## Rollback

### Workers Rollback

```bash
# List recent deployments
npx wrangler deployments list --env production

# Rollback to previous deployment
npx wrangler rollback --env production
```

### Pages Rollback

1. Go to Cloudflare Pages dashboard
2. Select your project
3. Go to Deployments
4. Click on a previous deployment
5. Click "Rollback to this deployment"

## Security Checklist

- [ ] Use different secrets for staging and production
- [ ] Generate strong JWT secrets: `openssl rand -hex 32`
- [ ] Generate encryption keys: `openssl rand -base64 32`
- [ ] Enable Cloudflare security features (WAF, rate limiting)
- [ ] Review CORS origins in `workers/src/index.ts`
- [ ] Set up Cloudflare Access for admin routes (optional)

## URLs Reference

| Environment | Frontend | API | Health Check |
|-------------|----------|-----|--------------|
| Local | http://localhost:5174 | http://localhost:8787 | http://localhost:8787/health |
| Staging | https://staging.joan.nintai.app | https://staging-api.joan.nintai.app | https://staging-api.joan.nintai.app/health |
| Production | https://joan.nintai.app | https://joan-api.alexbbenson.workers.dev | https://joan-api.alexbbenson.workers.dev/health |

## Troubleshooting

### Workers Not Deploying

1. Check wrangler authentication:
   ```bash
   npx wrangler whoami
   ```

2. Verify account ID in `wrangler.toml`

3. Check API token permissions

### Pages Build Failing

1. Verify Node.js version (should be 20+)
2. Check build command: `npm run build`
3. Check output directory: `dist`
4. Review build logs in Cloudflare dashboard

### CORS Errors

1. Verify origin is in allowed list (`workers/src/index.ts`)
2. Check that API URL in frontend matches deployment
3. Ensure credentials are handled correctly

### Database Migrations Not Applied

1. Verify you're using `--remote` flag
2. Check database name matches environment
3. Run migrations in order (001, 002, etc.)

## Resources

- [Cloudflare Workers Docs](https://developers.cloudflare.com/workers/)
- [Cloudflare Pages Docs](https://developers.cloudflare.com/pages/)
- [Cloudflare D1 Docs](https://developers.cloudflare.com/d1/)
- [Cloudflare R2 Docs](https://developers.cloudflare.com/r2/)
- [Wrangler CLI Reference](https://developers.cloudflare.com/workers/wrangler/)
