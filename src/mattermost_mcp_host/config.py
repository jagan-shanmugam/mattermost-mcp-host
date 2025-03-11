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
# MCP_SERVER_NAME is unused and replaced by server configs in mcp-servers.json
MCP_ENV = {}  # Add any environment variables needed for the MCP server

# Command prefix for triggering the bot-client in mattermost
COMMAND_PREFIX = os.environ.get('COMMAND_PREFIX', '/')

# Logging Configuration
LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')

# DEFAULT LLM 
DEFAULT_PROVIDER = os.environ.get('DEFAULT_PROVIDER', 'openai')  # Options: openai, azure, anthropic, gemini
DEFAULT_MODEL = os.environ.get('DEFAULT_MODEL', 'gpt-4o')

# Provider-specific model defaults
OPENAI_MODEL = os.environ.get('OPENAI_MODEL', 'gpt-4o')
AZURE_OPENAI_DEPLOYMENT = os.environ.get('AZURE_OPENAI_DEPLOYMENT', 'gpt-4o')
ANTHROPIC_MODEL = os.environ.get('ANTHROPIC_MODEL', 'claude-3-opus-20240229')
GEMINI_MODEL = os.environ.get('GEMINI_MODEL', 'gemini-1.5-pro')

# LLM System Prompt Configuration
DEFAULT_SYSTEM_PROMPT = os.environ.get('DEFAULT_SYSTEM_PROMPT', 
    "You are an AI assistant integrated with Mattermost and MCP servers. "
    "You can call tools from connected MCP servers to help answer questions. "
    "Always be helpful, accurate, and concise. If you don't know something, say so.")

