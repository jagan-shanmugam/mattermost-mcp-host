import os
from dotenv import load_dotenv

# Load environment variables from .env file if it exists
load_dotenv()

# Mattermost Configuration
MATTERMOST_URL = os.environ.get('MATTERMOST_URL', 'localhost')
MATTERMOST_TOKEN = os.environ.get('MATTERMOST_TOKEN', '1234')
MATTERMOST_SCHEME = os.environ.get('MATTERMOST_SCHEME', 'http')
MATTERMOST_PORT = int(os.environ.get('MATTERMOST_PORT', '8065'))
MATTERMOST_TEAM_NAME = os.environ.get('MATTERMOST_TEAM_NAME', 'test')
MATTERMOST_CHANNEL_NAME = os.environ.get('MATTERMOST_CHANNEL_NAME', 'mcp-client')
MATTERMOST_CHANNEL_ID = os.environ.get('MATTERMOST_CHANNEL_ID', '1234')  # Will be auto-detected if empty

# MCP Server Configuration
MCP_SERVER_TYPE = os.environ.get('MCP_SERVER_TYPE', 'stdio')  # 'stdio' or 'http'

# For stdio server
MCP_SERVER_NAME = os.environ.get('MCP_SERVER_NAME', 'simple-mcp-server')

MCP_COMMAND = os.environ.get('MCP_COMMAND', 'python')
MCP_ARGS = os.environ.get('MCP_ARGS', 'simple-mcp-server/server.py').split()

# MCP_COMMAND = os.environ.get('MCP_COMMAND', 'python')
# MCP_ARGS = os.environ.get('MCP_ARGS', 'mcp_server/server.py').split()
MCP_ENV = {}  # Add any environment variables needed for the MCP server

# For HTTP server
# MCP_SERVER_URL = os.environ.get('MCP_SERVER_URL', 'http://localhost:8080')

# Command prefix for triggering the bot-client in mattermost
COMMAND_PREFIX = os.environ.get('COMMAND_PREFIX', '!mcp')

# Logging Configuration
LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')