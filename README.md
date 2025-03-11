# Mattermost MCP Host

A Mattermost integration with Model Context Protocol (MCP) servers that leverages AI language models to provide an intelligent interface for managing and executing tools through Mattermost.

![Version](https://img.shields.io/badge/version-0.1.0-blue)
![Python](https://img.shields.io/badge/python-3.13.1%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)

## Features

- 🤖 **AI-Powered Assistance**: Integrates with multiple AI providers (Azure OpenAI, OpenAI, Anthropic Claude, Google Gemini)
- 🔌 **MCP Server Integration**: Connect to any Model Context Protocol (MCP) server
- 🧰 **Tool Management**: Access and execute tools from connected MCP servers
- 💬 **Thread-Based Conversations**: Maintains context within Mattermost threads
- 🔄 **Tool Chaining**: AI can call multiple tools in sequence to accomplish complex tasks
- 🔍 **Resource Discovery**: List available tools, resources, and prompts from MCP servers
- 📚 **Multiple Provider Support**: Choose your preferred AI provider with a simple configuration change

## Quick Start

1. Install the package:
```bash
pip install mattermost-mcp-host
```

2. Configure environment:
```env
MATTERMOST_URL=http://localhost:8065
MATTERMOST_TOKEN=your-bot-token
MATTERMOST_TEAM_NAME=your-team
OPENAI_API_KEY=your-openai-key
```

3. Start the integration:
```bash
python -m mattermost_mcp_host
```

For detailed installation instructions and additional configuration options, see [INSTALLATION.md](INSTALLATION.md).

## Prerequisites

- Python 3.13.1+
- Mattermost server (local or remote)
- Bot account in Mattermost with appropriate permissions
- Access to at least one LLM API:
  - OpenAI (default)
  - Azure OpenAI (optional)
  - Anthropic Claude (optional)
  - Google Gemini (optional)

## Available Commands

Once the integration is running, use these commands in your Mattermost channel:

- `/help` - Display help information
- `/servers` - List available MCP servers
- `/<server_name> tools` - List available tools for a specific server
- `/<server_name> call <tool_name> <args>` - Call a specific tool


## MCP Tool Caller Utility

The `mcp_tool_caller.py` utility allows direct command-line interaction with MCP servers:

1. List server capabilities:
```bash
python utils/mcp_tool_caller.py list --server-name simple-mcp-server
```

2. Call specific tools:
```bash
python utils/mcp_tool_caller.py call --server-name simple-mcp-server --tool echo --tool-args '{"input": "Hello World"}'
```

## Contributing

Please read our [Contributing Guidelines](CONTRIBUTING.md) for details on submitting pull requests.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.