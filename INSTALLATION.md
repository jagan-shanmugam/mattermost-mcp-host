# Installation Guide

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
pip install mattermost-mcp-host
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
pip install "mattermost-mcp-host[all]"
```

2. **Configure AI providers**
Add relevant API keys to your `.env`:
```env
# OpenAI
OPENAI_API_KEY=your-openai-key

# Azure OpenAI
AZURE_OPENAI_API_KEY=your-azure-key
AZURE_OPENAI_ENDPOINT=your-azure-endpoint

# Anthropic
ANTHROPIC_API_KEY=your-anthropic-key

# Google Gemini
GOOGLE_API_KEY=your-google-key
```

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
- Save the access token for configuration

2. **Required Bot Permissions**
- post_all
- create_post
- read_channel
- create_direct_channel
- read_user

3. **Add Bot to Team/Channel**
- Invite the bot to your team
- Add bot to desired channels

## Verification

Test your installation:

```bash
python -m mattermost_mcp_host verify
```

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
```

For the README.md, we should update the Prerequisites section to match the new Python version requirement and add the detailed installation options. Here are the relevant sections to update:


````32:37:README.md
```

3. **Install dependencies**

```bash
pip install -r requirements.txt
````


Replace with:
```markdown
## Prerequisites

- Python 3.13.1+ 
- Mattermost server (local or remote)
- Bot account in Mattermost with appropriate permissions
- Access to at least one LLM API:
  - OpenAI (default)
  - Azure OpenAI (optional)
  - Anthropic Claude (optional)
  - Google Gemini (optional)
```

The installation section should also be updated:

````38:72:README.md
```

## Configuration

1. **Copy the example environment file**

```bash
cp .env.example .env
```

2. **Configure your environment variables**

Copy `.env.example` to `.env` and edit

## Usage

### Starting the Server

```bash
python src/ollama_mcp_server/main.py
```

### Available Tools

1. **generate**: Generate text using the configured model
   ```json
   {
     "prompt": "Write a short story about a robot",
     "model": "llama3.2:latest",  // optional
     "max_tokens": 500   // optional
   }
   ```

2. **chat**: Have a conversation with the model
   ```json
````


Replace with a reference to the detailed installation guide:
```markdown
## Installation

For detailed installation instructions, see [INSTALLATION.md](INSTALLATION.md).

Quick start:
```bash
pip install mattermost-mcp-host
```

For all AI providers:
```bash
pip install "mattermost-mcp-host[all]"
```

Configure through `.env`:
```env
MATTERMOST_URL=http://localhost:8065
MATTERMOST_TOKEN=your-bot-token
MATTERMOST_TEAM_NAME=your-team
OPENAI_API_KEY=your-openai-key  # Required for basic installation
```
```

These updates provide clearer installation instructions and better align with the project's current state and requirements.