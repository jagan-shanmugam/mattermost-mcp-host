# Mattermost MCP Server

A Model Context Protocol (MCP) server implementation that integrates with Mattermost to provide enterprise collaboration capabilities through the MCP protocol. This server enables AI assistants to interact with your Mattermost workspace.

## Features

### Resources
- Access teams, channels, and posts
- View pinned posts for quick reference
- Get channel statistics and member information
- Track discussions across channels

### Tools
- Post messages to any channel
- Create project-specific channels
- Pin important announcements
- Add emoji reactions to posts
- Search across messages

### Prompts
- Generate meeting notes templates
- Create project status updates
- Analyze discussion threads
- Summarize channel activity
- Create team onboarding documentation

## Prerequisites

- Python 3.13+
- Mattermost server (local or remote)
- Mattermost access token

## Installation

1. **Clone the repository**

```bash
git clone <repository-url>
cd mattermost-mcp-server
```

2. **Create and activate a virtual environment**

```bash
uv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. **Install dependencies**

```bash
uv sync
```

## Components

### Resources

The server implements a note storage system with the following features:

- **Custom URI Scheme**: Access notes using `note://` URI scheme
  ```
  note://example-note  # Accesses a note named 'example-note'
  ```

- **Resource Properties**:
  - Name: Unique identifier for the note
  - Description: Brief description of the note's content
  - MIME Type: Always `text/plain` for notes

### Prompts

The server provides a summarization prompt:

- **summarize-notes**: Creates summaries of stored notes
  ```json
  {
    "style": "brief"  # or "detailed" for more comprehensive summaries
  }
  ```

### Tools

The server implements a note management tool:

- **add-note**: Creates a new note
  ```json
  {
    "name": "meeting-notes",
    "content": "Discussion points from today's meeting..."
  }
  ```

## Integration Examples

### Python Client

```python
from mcp import MCPClient

async def main():
    client = MCPClient("python", ["-m", "mattermost_mcp_server"])
    await client.connect()
    
    # Add a new note
    await client.call_tool("add-note", {
        "name": "meeting-notes",
        "content": "1. Discussed project timeline\n2. Assigned tasks\n3. Next steps"
    })
    
    # Generate summary
    summary = await client.call_prompt("summarize-notes", {
        "style": "brief"
    })
    print(f"Notes summary: {summary}")
    
    await client.close()
```

### Command Line

```bash
# Add a note
mcp call add-note '{"name": "todo", "content": "1. Complete documentation\n2. Review code"}'

# Generate summary
mcp call-prompt summarize-notes '{"style": "detailed"}'
```

## Development

### Building and Publishing

1. **Sync dependencies**:
```bash
uv sync
```

2. **Build package**:
```bash
uv build
```

3. **Publish to PyPI**:
```bash
uv publish
```

Note: Set PyPI credentials via:
- Token: `--token` or `UV_PUBLISH_TOKEN`
- Username/password: `--username`/`UV_PUBLISH_USERNAME` and `--password`/`UV_PUBLISH_PASSWORD`

### Debugging

Since MCP servers communicate over stdio, use these debugging approaches:

1. **Enable Debug Logging**:
   ```python
   import logging
   logging.basicConfig(level=logging.DEBUG)
   ```

2. **Use stderr for Debugging**:
   ```python
   import sys
   print("Debug info", file=sys.stderr)
   ```

## Configuration

### Claude Desktop Integration

1. **Location**:
   - MacOS: `~/Library/Application\ Support/Claude/claude_desktop_config.json`
   - Windows: `%APPDATA%/Claude/claude_desktop_config.json`

2. **Development Configuration**:
```json
{
  "mcpServers": {
    "mattermost-mcp-server": {
      "command": "uv",
      "args": [
        "--directory",
        "/path/to/mattermost-mcp-server",
        "run",
        "mattermost-mcp-server"
      ]
    }
  }
}
```

3. **Production Configuration**:
```json
{
  "mcpServers": {
    "mattermost-mcp-server": {
      "command": "uvx",
      "args": [
        "mattermost-mcp-server"
      ]
    }
  }
}
```
