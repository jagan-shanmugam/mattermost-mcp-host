# Installation Guide - WIP

This guide provides detailed instructions for installing and configuring the Mattermost MCP Host.

## Prerequisites

- Python 3.13.1+
- Mattermost server (local or remote)
- Bot account in Mattermost with appropriate permissions
- Access to at least one LLM API (OpenAI, Azure OpenAI, Anthropic, or Google Gemini)

## Installation Methods

### Option 1: Basic Installation (OpenAI support only)

1. **Create a virtual environment**
```bash
uv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. **Install the package**
```bash
uv sync 
```

3. **Configure environment**
Create a `.env` file with required settings:
```env
MATTERMOST_URL=http://localhost:8065
MATTERMOST_TOKEN=your-bot-token
MATTERMOST_TEAM_NAME=your-team-name
MATTERMOST_CHANNEL_NAME=town-square
OPENAI_API_KEY=your-openai-key
```

### Option 2: Full Installation (All AI Providers)

1. **Install with all dependencies**
```bash
uv sync --dev --all-extras
```

2. **Configure AI providers**
Add relevant API keys to your `.env`.
Refer to `.env.example` for required keys.

### Option 3: Development Installation

1. **Clone the repository**
```bash
git clone <repository-url>
cd mattermost-mcp-host
```

2. **Install dependencies**
```bash
uv sync
```

3. **Configure MCP Servers**
Edit `src/mattermost_mcp_host/mcp-servers.json`:
```json
{
    "mcpServers": {
      "ollama-mcp-server": {
        "command": "python",
        "args": ["ollama-mcp-server/src/ollama_mcp_server/main.py"],
        "type": "stdio"
      },
      "simple-mcp-server": {
        "command": "python",
        "args": ["simple-mcp-server/server.py"],
        "type": "stdio"
      }
    }
}
```

## Mattermost Setup

1. **Create a Bot Account**
- Go to Integrations > Bot Accounts > Add Bot Account
- Give it a name and description
- Save the access token in the .env file

2. **Required Bot Permissions**
- post_all
- create_post
- read_channel
- create_direct_channel
- read_user

3. **Add Bot to Team/Channel**
- Invite the bot to your team
- Add bot to desired channels

## Troubleshooting

1. **Connection Issues**
- Verify Mattermost server is running
- Check bot token permissions
- Ensure correct team/channel names

2. **AI Provider Issues**
- Validate API keys
- Check API quotas and limits
- Verify network access to API endpoints

3. **MCP Server Issues**
- Check server logs
- Verify server configurations
- Ensure required dependencies are installed