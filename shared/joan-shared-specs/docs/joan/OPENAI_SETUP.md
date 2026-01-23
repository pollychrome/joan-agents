# OpenAI Setup for Enhanced Resource Finding

## Overview

The Resource Finder in Joan's Daily Planning ceremony can use OpenAI's GPT-4 for enhanced, web-aware resource suggestions. This provides:
- Current, up-to-date resource recommendations
- Better understanding of technical topics
- More relevant web links and documentation
- Higher quality resource descriptions

## Setup Instructions

### 1. Get Your OpenAI API Key

1. Go to [OpenAI Platform](https://platform.openai.com)
2. Sign in or create an account
3. Navigate to API Keys section
4. Create a new API key
5. Copy the key (it starts with `sk-`)

### 2. Configure Joan with Your API Key

#### Option A: Using the Setup Script

```bash
cd /Users/alexbenson/Joan/backend
source venv/bin/activate
python3 scripts/setup_openai_provider.py 'your-openai-api-key-here'
```

#### Option B: Using Environment Variable

```bash
export OPENAI_API_KEY='your-openai-api-key-here'
cd /Users/alexbenson/Joan/backend
source venv/bin/activate
python3 scripts/setup_openai_provider.py
```

### 3. Restart the Backend

The backend will automatically reload if it's running with `--reload` flag. Otherwise:

```bash
# Kill existing backend process
ps aux | grep uvicorn | grep -v grep | awk '{print $2}' | xargs kill -9

# Restart backend
cd /Users/alexbenson/Joan/backend
source venv/bin/activate
uvicorn app.main:app --reload --port 8000
```

## How It Works

### Intelligent Fallback System

Joan uses a smart fallback system for AI providers:

1. **With OpenAI configured**:
   - Resource Finder → OpenAI GPT-4 (best quality, web-aware)
   - Other AI features → OpenAI or Local Ollama based on task

2. **Without OpenAI (fallback mode)**:
   - Resource Finder → Local Ollama (qwen3:32b)
   - Quality is still good but may lack current web knowledge

### Provider Selection

The system automatically selects the best provider:
- **Resource Finding**: Prefers OpenAI for web awareness
- **Summarization**: Can use local model (faster, free)
- **Task Breakdown**: Prefers OpenAI for complex analysis
- **General Queries**: Uses configured default

## Cost Information

- **GPT-4o-mini**: ~$0.15 per 1M input tokens, ~$0.60 per 1M output tokens
- Typical resource query: ~500 tokens input, ~1500 tokens output
- Estimated cost: Less than $0.001 per resource query

## Troubleshooting

### "No AI providers configured" Error
- Run the setup script to configure at least one provider
- Ensure Ollama is running: `ollama serve`

### "Invalid API key" Error
- Check your OpenAI API key is correct
- Ensure you have billing set up on OpenAI

### Slow Resource Generation
- OpenAI queries take 2-10 seconds depending on complexity
- Local Ollama fallback may be slower (10-30 seconds)

## Security Notes

- API keys are stored encrypted in the database
- Never commit API keys to version control
- Use environment variables in production

## Testing Your Setup

1. Open Joan's Daily Planning ceremony
2. Schedule a task
3. Click the ✨ sparkle button on the task
4. Resources should generate using OpenAI (check the console for provider info)

## Questions?

The Resource Finder will work with or without OpenAI configured. OpenAI simply provides better, more current results for web-based resources.