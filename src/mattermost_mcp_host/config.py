import os
from pathlib import Path
from dotenv import load_dotenv

# Determine the path to the .env file relative to this config file
# config.py is in src/mattermost_mcp_host/, .env is in src/
env_path = Path(__file__).parent.parent.parent / '.env'

print("ENV PATH: " + str(env_path))

# Load environment variables from .env file if it exists
load_dotenv(dotenv_path=env_path)

# Mattermost Configuration
MATTERMOST_URL = os.environ.get('MATTERMOST_URL', 'localhost')
MATTERMOST_TOKEN = os.environ.get('MATTERMOST_TOKEN', '1234')
MATTERMOST_SCHEME = os.environ.get('MATTERMOST_SCHEME', 'http')
MATTERMOST_PORT = int(os.environ.get('MATTERMOST_PORT', '8065'))
MATTERMOST_TEAM_NAME = os.environ.get('MATTERMOST_TEAM_NAME', 'test')
MATTERMOST_CHANNEL_NAME = os.environ.get('MATTERMOST_CHANNEL_NAME', 'mcp-client')
MATTERMOST_CHANNEL_ID = os.environ.get('MATTERMOST_CHANNEL_ID', '1234')  

# Command prefix for triggering the bot in mattermost
COMMAND_PREFIX = os.environ.get('COMMAND_PREFIX', '#')

# Logging Configuration
LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')

# DEFAULT LLM 
DEFAULT_PROVIDER = os.environ.get('DEFAULT_PROVIDER', 'azure') 
DEFAULT_MODEL = os.environ.get('DEFAULT_MODEL', 'gpt-4o')
AGENT_TYPE = os.environ.get('AGENT_TYPE', 'simple')  # TODO: Implement more agent types

# Provider-specific model defaults
OPENAI_MODEL = os.environ.get('OPENAI_MODEL', 'gpt-4o')

# TODO: Support more Options: openai, azure, anthropic, gemini

# LLM System Prompt Configuration
DEFAULT_SYSTEM_PROMPT = os.environ.get('DEFAULT_SYSTEM_PROMPT', 
    "You are an AI assistant integrated with Mattermost and MCP (Model Context Protocol) servers. "
    "You can call tools from connected MCP servers to help answer questions. "
    "Always be helpful, accurate, and concise. If you don't know something, say so."
    "Always search the web and respond with up to date information."
    "Call multiple tools to finalize your response."
    "If you are unsure about the response, ask for human help.")
