# Ceremony Feature Setup Guide

## Overview
The ceremony feature provides guided productivity workflows with flexible AI provider support. Each ceremony component can use a different AI provider and model based on the specific task requirements.

## 🔧 Administrative Setup Steps

### Step 1: Get Your OpenAI API Key

1. **Sign up or log in** to OpenAI: https://platform.openai.com
2. **Navigate to API Keys**: https://platform.openai.com/api-keys
3. **Create a new API key**:
   - Click "Create new secret key"
   - Give it a name like "Joan Ceremonies"
   - Copy the key immediately (you won't see it again!)
4. **Add billing**: https://platform.openai.com/account/billing
   - Add a payment method
   - Set a monthly budget (suggested: $10 for personal use)

### Step 2: Configure Environment Variables

You need to add the API key to your Cloudflare Worker:

```bash
# Using Wrangler CLI (from the workers directory)
cd workers
npx wrangler secret put OPENAI_API_KEY
# Paste your OpenAI API key when prompted
```

### Step 3: Apply Database Migrations

The ceremony tables need to be created in your D1 database:

```bash
# From the workers directory
cd workers

# Apply the ceremony schema to your D1 database
npx wrangler d1 execute joan-db --file=./schema/ceremonies.sql

# For production:
npx wrangler d1 execute joan-db --file=./schema/ceremonies.sql --env production
```

### Step 4: Update AI Provider Configuration

After the tables are created, we need to update the OpenAI provider with your API key:

```sql
-- Run this SQL in your D1 database console or via Wrangler
UPDATE ceremony_ai_providers
SET api_key = 'your-openai-api-key-here',
    is_active = TRUE
WHERE id = 'provider-openai-default';
```

Or use the Wrangler CLI:

```bash
npx wrangler d1 execute joan-db --command="UPDATE ceremony_ai_providers SET is_active = TRUE WHERE id = 'provider-openai-default'"
```

## 🎯 Provider Configuration Options

### Default Setup (OpenAI GPT-4o-mini)
- **Provider**: OpenAI
- **Model**: gpt-4o-mini
- **Cost**: ~$0.002 per ceremony
- **Best for**: General purpose, fast responses

### Alternative Providers

You can add additional providers for specific use cases:

#### Anthropic Claude (for complex analysis)
```sql
UPDATE ceremony_ai_providers
SET api_key = 'your-anthropic-key',
    is_active = TRUE,
    model_name = 'claude-3-sonnet-20240229'
WHERE id = 'provider-anthropic-default';
```

#### Groq (for ultra-fast responses)
```sql
UPDATE ceremony_ai_providers
SET api_key = 'your-groq-key',
    is_active = TRUE,
    model_name = 'mixtral-8x7b-32768'
WHERE id = 'provider-groq-default';
```

#### Local Ollama (free, private)
```sql
UPDATE ceremony_ai_providers
SET api_endpoint = 'http://localhost:11434',
    is_active = TRUE,
    model_name = 'llama2'
WHERE id = 'provider-ollama-local';
```

## 🔄 Assigning Providers to Components

You can assign specific AI providers to ceremony components based on their needs:

```sql
-- Use GPT-4 for complex analysis
UPDATE ceremony_components
SET ai_provider_id = 'provider-openai-default',
    ai_model_override = 'gpt-4',
    ai_temperature_override = 0.3
WHERE id = 'comp-ai-processor';

-- Use Claude for creative writing
UPDATE ceremony_components
SET ai_provider_id = 'provider-anthropic-default',
    ai_temperature_override = 0.8
WHERE id = 'comp-writing-area';

-- Use Groq for quick task extraction
UPDATE ceremony_components
SET ai_provider_id = 'provider-groq-default',
    ai_max_tokens_override = 500
WHERE id = 'comp-task-generator';
```

## 📊 Cost Optimization

### Token Usage by Component
- **Writing Analysis**: 500-1000 tokens
- **Task Extraction**: 200-500 tokens
- **Daily Planning**: 1000-2000 tokens
- **Prioritization**: 300-600 tokens

### Estimated Monthly Costs
- **Light use** (5 ceremonies/day): ~$3/month
- **Regular use** (10 ceremonies/day): ~$6/month
- **Heavy use** (20+ ceremonies/day): ~$12/month

### Cost Saving Tips
1. Use smaller models for simple tasks (gpt-3.5-turbo, claude-haiku)
2. Set appropriate max_tokens limits per component
3. Use local Ollama for non-critical tasks
4. Enable provider routing rules for cost optimization

## 🚀 Testing Your Setup

After configuration, test the ceremony feature:

1. **Check AI Configuration**:
   ```bash
   curl https://joan-api.alexbbenson.workers.dev/api/v1/ceremonies/ai/config
   ```

2. **Test AI Query**:
   ```bash
   curl -X POST https://joan-api.alexbbenson.workers.dev/api/v1/ceremonies/ai/query \
     -H "Authorization: Bearer YOUR_AUTH_TOKEN" \
     -H "Content-Type: application/json" \
     -d '{"prompt": "Test query"}'
   ```

3. **Try a Ceremony**:
   - Go to the Ceremonies page in the app
   - Select "Writing Session"
   - Complete the workflow

## 🛠️ Troubleshooting

### "No AI provider configured"
- Ensure you've set the API key in the database
- Check that is_active = TRUE for at least one provider
- Verify the environment variables are set

### "API rate limit exceeded"
- Add multiple providers for load balancing
- Implement provider rotation
- Upgrade to higher tier API plan

### "High costs"
- Review token usage in ceremony_ai_requests table
- Adjust max_tokens limits
- Switch to cheaper models for simple tasks

## 📈 Monitoring Usage

Query to check AI usage:

```sql
-- Check provider usage
SELECT
  provider_name,
  total_requests,
  total_tokens,
  total_cost
FROM ceremony_ai_providers
ORDER BY total_requests DESC;

-- Recent AI requests
SELECT
  created_at,
  provider_id,
  tokens_total,
  latency_ms,
  status
FROM ceremony_ai_requests
ORDER BY created_at DESC
LIMIT 20;
```

## 🔐 Security Notes

1. **Never commit API keys** to version control
2. **Use environment variables** for all sensitive data
3. **Set spending limits** on AI provider dashboards
4. **Rotate keys regularly** (every 90 days)
5. **Monitor usage** for unusual activity

## Next Steps

Once you have your OpenAI API key:

1. Let me know you have it (don't share the actual key!)
2. I'll help you run the database migrations
3. We'll configure the environment variables
4. Test the ceremony feature
5. Deploy to production

Ready to proceed? Let me know when you have your OpenAI API key!