# Mattermost MCP Client

A Python-based MCP (Model Context Protocol) client that connects Mattermost with MCP servers, enabling command execution and tool management through Mattermost channels.

## Demo

<img src="data/demo.gif" alt="MCP Client Demo" width="800"/>


## Prerequisites

- Python 3.13.1+ 
- Mattermost server (local or remote)
- Bot account in Mattermost with appropriate permissions

## Installation

1. **Create a virtual environment**

```bash
uv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
# On fish shell - source .venv/bin/activate.fish
```

2. **Install required packages**

```bash
uv sync # Installs all dependencies
```

3. **Set up configuration**

Create a `.env` file with your Mattermost and MCP server settings:

```env
MATTERMOST_URL=http://localhost:8065
MATTERMOST_TOKEN=your-bot-token
MATTERMOST_SCHEME=http
MATTERMOST_PORT=8065
MATTERMOST_TEAM_NAME=your-team-name
MATTERMOST_CHANNEL_NAME=town-square
MCP_SERVER_TYPE=stdio
MCP_COMMAND=python
MCP_ARGS=mcp_server.py
LOG_LEVEL=INFO
```
For a complete list of configuration options and their default values, refer to the [config.py](src/mattermost_mcp_client/config.py).

## Configuration Options

All configuration options can be set through environment variables or in the `.env` file. Here are the available options:

- `COMMAND_PREFIX` - Prefix for bot commands (default: '!mcp')
- `LOG_LEVEL` - Logging level (default: 'INFO')

4. **Configure MCP Servers**

Create or modify [mcp-servers.json](src/mattermost_mcp_client/mcp-servers.json) in the src/mattermost_mcp_client directory:

```json
{
    "mcpServers": {
      "ollama-mcp-server":{
        "command": "python",
        "args": ["ollama-mcp-server/src/ollama_mcp_server/main.py"],
        "type": "stdio"
      },
      "simple-mcp-server": {
        "command": "python",
        "args": ["simple-mcp-server/server.py"],
        "type": "stdio"
      },
      "mattermost-mcp-server": {
        "command": "python",
        "args": ["mattermost-mcp-server/src/mattermost_mcp_server/server.py"],
        "type": "stdio"
      }
    }
}
```

## Mattermost Setup

1. **Start a local Mattermost server** (if not already running)

You can use Docker to run Mattermost locally:

```bash
docker run --name mattermost-preview -d --publish 8065:8065 mattermost/mattermost-preview
```

2. **Create a Bot Account**

- Go to Integrations > Bot Accounts > Add Bot Account
- Give it a name and description
- Note the access token provided

3. **Add the bot to your team and channel**

## Running the Integration

1. **Start the Mattermost MCP Client**

```bash
python src/mattermost_mcp_client/main.py
```

## Using the MCP Tool Caller Utility

The `mcp_tool_caller.py` utility allows you to interact with MCP servers directly from the command line:

1. **List server capabilities**
```bash
python utils/mcp_tool_caller.py list --server-name simple-mcp-server
```

2. **Call specific tools**
```bash
python utils/mcp_tool_caller.py call --server-name simple-mcp-server --tool echo --tool-args '{"input": "Hello World"}'
```

## Mattermost Commands

Once the integration is running, use these commands in your Mattermost channel:

- `!mcp help` - Display help information
- `!mcp servers` - List available MCP servers
- `!mcp <server_name> tools` - List available tools for a specific server
- `!mcp <server_name> call <tool_name> <args>` - Call a specific tool
- `!mcp <server_name> resources` - List available resources
- `!mcp <server_name> prompts` - List available prompts

Example:
```
!mcp simple-mcp-server call echo message "Hello World"
```
```
!mcp mattermost-mcp-server call post-message {"channel_id": "5q39mmzqji8bddxyjzsqbziy9a", "message": "Hello from Demo!"}'


!mcp ollama-mcp-server call generate {"prompt": "Write a short poem about AI", "model": "llama3.2:latest"}


```

## MCP Servers included
This repository includes three MCP servers:
- **simple-mcp-server**: A simple MCP server that has two simple tools
- **ollama-mcp-server**: A MCP server that uses Ollama locally to generate text
- **mattermost-mcp-server**: A MCP server that wraps Mattermost API and performs various actions

## Troubleshooting

1. **Connection Issues:**
   - Verify Mattermost URL and port
   - Check the bot token is valid
   - Ensure the MCP server is running

2. **Permission Issues:**
   - Make sure the bot has appropriate permissions in Mattermost
   - Check that the bot is a member of the channel

3. **MCP Tool Errors:**
   - Verify that the tools are properly defined in the MCP server
   - Check the input format for tool calls
   - Use the mcp_tool_caller.py utility to test tools directly

## Next Steps

1. **Add support for npx based** MCP servers
2. **Using Tool calling Agent** to orchstrate tools in MCP servers
2. **Implement authentication** for secure communication
3. **Add support for file uploads** and other Mattermost features


### Watch the full demo video:

<a href="https://www.youtube.com/watch?v=YPtfqUstfTI" target="_blank">
  <img src="https://img.youtube.com/vi/YPtfqUstfTI/maxresdefault.jpg" alt="Watch the demo video" width="800"/>
</a>


