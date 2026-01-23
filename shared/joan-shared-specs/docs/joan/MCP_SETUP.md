# MCP (Model Context Protocol) Setup Guide

## Setting up Linear Integration

1. **Get your Linear API Key**:
   - Go to Linear Settings > API > Personal API Keys
   - Create a new key with name "Joan Project"
   - Copy the generated key

2. **Configure Cursor Environment**:
   Add these to your Cursor environment variables:
   ```bash
   CURSOR_LINEAR_API_KEY=your_linear_api_key_here
   CURSOR_PROJECT_ROOT=/Users/alexbenson/Joan
   CURSOR_GITHUB_TOKEN=your_github_token_here  # Optional, for GitHub integration
   ```

3. **Restart Cursor** to load the MCP servers

## Using MCP in Cursor

Once configured, you can use commands like:
- `@linear create issue "Task title"`
- `@linear list issues`
- `@filesystem read file.txt`
- `@git status`

## Available MCP Servers

1. **Linear**: Issue tracking and project management
2. **Filesystem**: Enhanced file operations
3. **Git**: Version control operations
4. **GitHub**: Repository and PR management

## Troubleshooting

If MCP servers don't load:
1. Check that Node.js is installed: `node --version`
2. Verify environment variables are set
3. Check Cursor logs for MCP errors
4. Try running manually: `npx -y @modelcontextprotocol/server-linear`