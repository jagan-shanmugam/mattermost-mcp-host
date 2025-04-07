from mattermost_mcp_host.mcp_client import MCPClient
from mattermost_mcp_host.mattermost_client import MattermostClient
import mattermost_mcp_host.config as config
from mattermost_mcp_host.agent import LangGraphAgent

import sys
import asyncio
import logging
import json
from pathlib import Path

# Add these imports
from typing import Dict, List, Any
import traceback

from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, ToolMessage

PYTHON_EXECUTABLE = sys.executable

import nest_asyncio
nest_asyncio.apply()

# Configure logging
logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def load_server_configs():
    """Load MCP server configurations from mcp-servers.json"""
    try:
        config_path = Path(__file__).parent / "mcp-servers.json"
        with open(config_path) as f:
            config = json.load(f)
            return config.get("mcpServers", {})
    except Exception as e:
        logger.error(f"Error loading server configurations: {str(e)}")
        return {}

class MattermostMCPIntegration:
    def __init__(self):
        """Initialize the integration"""
        self.mcp_clients = {}  # Dictionary to store multiple MCP clients
        self.mattermost_client = None
        self.channel_id = config.MATTERMOST_CHANNEL_ID
        self.command_prefix = config.COMMAND_PREFIX
        
    async def initialize(self):
        """Initialize the mattermost client and connect to it via Websocket"""
        
        try:
            # Load server configurations
            server_configs = load_server_configs()
            logger.info(f"Found {len(server_configs)} MCP servers in config")
            
            all_langchain_tools = []
            # Initialize each MCP client
            for server_name, server_config in server_configs.items():
                try:
                    client = MCPClient(server_config=server_config)

                    await client.connect()
                    self.mcp_clients[server_name] = client
                    lanchain_tools = await client.convert_mcp_tools_to_langchain()
                    all_langchain_tools.extend(lanchain_tools)
                    logger.info(f"Connected to MCP server '{server_name}' via stdio")
                except Exception as e:
                    logger.error(f"Failed to connect to MCP server '{server_name}': {str(e)}")
                    # Continue with other servers even if one fails
                    continue
            
            if not self.mcp_clients:
                raise ValueError("No MCP servers could be connected")

        except Exception as e:
            logger.error(f"Failed to initialize MCP servers: {str(e)}")
            raise
        
        # Set up agent tools
        logger.info(f"Setting up agent with {all_langchain_tools} tools")
        logger.info(f"Number of tools : {len(all_langchain_tools)}")

        # Initialize agent based on configuration
        if config.AGENT_TYPE.lower() == 'simple':
            system_prompt = config.DEFAULT_SYSTEM_PROMPT
            name = 'simple'
            
        elif config.AGENT_TYPE.lower() == 'github':
            name = 'github'
            system_prompt = config.GITHUB_AGENT_SYSTEM_PROMPT

        self.agent = LangGraphAgent(name=name, 
                                    provider=config.DEFAULT_PROVIDER, 
                                    model=config.DEFAULT_MODEL, 
                                    tools=all_langchain_tools, 
                                    system_prompt=system_prompt)
        
        # Initialize Mattermost client
        try:
            self.mattermost_client = MattermostClient(
                url=config.MATTERMOST_URL,
                token=config.MATTERMOST_TOKEN,
                scheme=config.MATTERMOST_SCHEME,
                port=config.MATTERMOST_PORT
            )
            self.mattermost_client.connect()
            logger.info("Connected to Mattermost server")
        except Exception as e:
            logger.error(f"Failed to connect to Mattermost server: {str(e)}")
            raise
        
        # Always try to get channel ID to verify it exists
        try:
            teams = self.mattermost_client.get_teams()
            logger.info(f"Available teams: {teams}")
            if teams:  # Only try to get channel if teams exist
                team_id = next(team['id'] for team in teams if team['name'] == config.MATTERMOST_TEAM_NAME)
                channel = self.mattermost_client.get_channel_by_name(team_id, config.MATTERMOST_CHANNEL_NAME)
                if not self.channel_id:
                    self.channel_id = channel['id']
                logger.info(f"Using channel ID: {self.channel_id}")
        except Exception as e:
            logger.warning(f"Channel verification failed: {str(e)}. Using configured channel ID: {self.channel_id}")
            # Don't raise the exception, continue with the configured channel ID
        
        if not self.channel_id:
            raise ValueError("No channel ID available. Please configure MATTERMOST_CHANNEL_ID or ensure team/channel exist")
        
        # Set up message handler
        self.mattermost_client.add_message_handler(self.handle_message)
        await self.mattermost_client.start_websocket()
        logger.info(f"Listening for {self.command_prefix} commands in channel {self.channel_id}")
        
    async def get_thread_history(self, root_id=None, channel_id=None) -> List[Dict[str, Any]]:
        """
        Fetch conversation history from a Mattermost thread
        
        Args:
            root_id: ID of the root post in the thread
            channel_id: Channel ID where the thread exists
            
        Returns:
            List of messages formatted for the LLM
        """
        if not root_id or not channel_id:
            # If there's no thread, return an empty history
            return []
            
        try:
            # Fetch posts in the thread
            posts_response = self.mattermost_client.driver.posts.get_thread(root_id)
            if not posts_response or 'posts' not in posts_response:
                return []
                
            # Sort posts by create_at to maintain chronological order
            posts = posts_response['posts']
            ordered_posts = sorted(posts.values(), key=lambda x: x['create_at'])
            
            # Convert to LLM message format
            messages = []
            bot_user_id = self.mattermost_client.driver.client.userid
            
            for post in ordered_posts:
                # Skip the system messages
                if post.get('type') == 'system_join_channel':
                    continue
                    
                content = post.get('message', '')
                user_id = post.get('user_id')
                
                # Skip empty messages
                if not content:
                    continue
                    
                # Determine role based on sender
                role = "assistant" if user_id == bot_user_id else "user"
                
                # Add to messages in LLM format
                messages.append({
                    "role": role,
                    "content": content
                })
                
            return messages
            
        except Exception as e:
            logger.error(f"Error fetching thread history: {str(e)}")
            logger.error(traceback.format_exc())
            return []

    async def handle_llm_request(self, channel_id: str, message: str, user_id: str, post_id: str = None, root_id: str = None):
        """
        Handle a request to the LLM
        
        Args:
            channel_id: Channel ID
            message: User's message text
            user_id: User ID for tracking conversation history
            post_id: Post ID for threading
        """
        try:
            # Fetch thread history - if post_id exists, it's the root of a new thread
            root_id = post_id if root_id is None or root_id == "" else root_id
            logger.info(f"Fetching thread history for root_id: {root_id}")
            
            # Send a typing indicator
            # await self.send_response(channel_id, "Processing your request...", root_id)
            
            # Collect available tools from all connected MCP servers
            all_tools = {}
            for server_name, client in self.mcp_clients.items():
                try:
                    server_tools = await client.list_tools()
                    # Add server name prefix to tool names to avoid conflicts
                    prefixed_tools = {
                        f"{server_name}.{name}": tool 
                        for name, tool in server_tools.items()
                    }
                    all_tools.update(prefixed_tools)
                except Exception as e:
                    logger.error(f"Error getting tools from {server_name}: {str(e)}")
            
            # Get thread history (will be empty for a new conversation)
            thread_history = await self.get_thread_history(root_id, channel_id)
            
            # Format the message for the agent
            # The agent expects a query, history, and user_id
            logger.info(f"Running agent with message: {message}")
            
            # Run the agent with the user's message, thread history, and user ID
            # Pass the thread history and user ID to the agent for proper memory management
            result = await self.agent.run(
                query=message,
                history=thread_history,
                user_id=user_id,
                metadata={
                    "channel_id": channel_id,
                    "team_name": config.MATTERMOST_TEAM_NAME.lower().replace(" ", "-"),
                    "channel_name": config.MATTERMOST_CHANNEL_NAME.lower().replace(" ", "-"),
                    "github_username": config.GITHUB_USERNAME,
                    "github_repo": config.GITHUB_REPO_NAME,
                }
            )
            
            # Extract the final response from the agent's messages
            responses = self.agent.extract_response(result["messages"])
            logger.info(f"Agent response: {responses}")
            previous_agent_responses = [msg["content"] for msg in thread_history if msg["role"] == "assistant"]
            
            # Filter out previous agent responses to avoid duplicates
            for response in responses:
                if response not in previous_agent_responses:
                    await self.send_response(channel_id, response or "No response generated", root_id)
                
        except Exception as e:
            logger.error(f"Error handling LLM request: {str(e)}")
            logger.error(traceback.format_exc())
            await self.send_response(channel_id, f"Error processing your request: {str(e)}", root_id)

    async def handle_message(self, post):
        """Handle incoming messages from Mattermost"""
        try:
            logger.info(f"Received post: {json.dumps(post, indent=2)}")  # Better logging
            
            # Skip messages from the bot itself
            if post.get('user_id') == self.mattermost_client.driver.client.userid:
                return
            
            # Extract message data
            channel_id = post.get('channel_id')
            message = post.get('message', '')
            user_id = post.get('user_id')
            post_id = post.get('id') 
            root_id = post.get('root_id')  # Get the root post ID for threading
            
            # Skip messages from other channels if a specific channel is configured
            if self.channel_id and channel_id != self.channel_id:
                logger.info(f'Received message from a different channel - {channel_id} than configured - {self.channel_id}')
                # Only process direct messages to the bot and messages in the configured channel
                # if not any(team_member.get('mention_keys', []) in message for team_member in self.mattermost_client.driver.users.get_user_teams(user_id)):
                #     return
            
            # Check if the message starts with the command prefix
            if message.startswith(self.command_prefix):
                # Handle MCP command
                # Remove the command prefix before processing
                message = message[len(self.command_prefix):].strip()
                await self.handle_command(channel_id, message, user_id, post_id, root_id)
            else:
                # Direct message to LLM
                await self.handle_llm_request(channel_id, message, user_id, post_id, root_id)
                
        except Exception as e:
            logger.error(f"Error handling message: {str(e)}")
            logger.error(traceback.format_exc())

    async def handle_command(self, channel_id, message_text, user_id, post_id=None, root_id=None):
        """Handle command messages from Mattermost"""
        try:
            root_id = post_id if root_id is None or root_id == "" else root_id

            # Split the command text
            command_parts = message_text.split()
            
            if len(command_parts) < 1:
                await self.send_help_message(channel_id, root_id)
                return
            
            command = command_parts[0]
            
            if command == 'help':
                await self.send_help_message(channel_id, root_id)
                return
            
            if command == 'servers':
                response = "Available MCP servers:\n"
                for name in self.mcp_clients.keys():
                    response += f"- {name}\n"
                await self.send_response(channel_id, response, root_id)
                return
            
            # Check if the first argument is a server name
            server_name = command
            if server_name not in self.mcp_clients:
                await self.send_response(
                    channel_id,
                    f"Unknown server '{server_name}'. Available servers: {', '.join(self.mcp_clients.keys())}",
                    root_id
                )
                return
            
            if len(command_parts) < 2:
                await self.send_response(
                    channel_id,
                    f"Invalid command. Use {self.command_prefix}{server_name} <command> [arguments]",
                    root_id
                )
                return
            
            client = self.mcp_clients[server_name]
            subcommand = command_parts[1]
            
            # Process the subcommand
            if subcommand == 'tools':
                tools = await client.list_tools()
                response = f"Available tools for {server_name}:\n"
                for name, tool in tools.items():
                    response += f"- {name}: {tool.description}\n"
                await self.send_response(channel_id, response, root_id)
                
            elif subcommand == 'call':
                if len(command_parts) < 4:
                    await self.send_response(
                        channel_id,
                        f"Invalid call command. Use {self.command_prefix}{server_name} call <tool_name> [parameter_name] [value]",
                        root_id
                    )
                    return
                    
                tool_name = command_parts[2]
                # Handle tools with no parameters
                if len(command_parts) == 4:
                    tool_args = {}
                    logger.info(f"Calling tool {tool_name} with no parameters")
                else:
                    # Parse input as JSON if provided
                    try:
                        # Join remaining parts and parse as JSON
                        params_str = " ".join(command_parts[3:]).replace("'", '')
                        
                        tool_args = json.loads(params_str)
                        logger.info(f"Calling tool {tool_name} with JSON inputs: {tool_args}")
                    except json.JSONDecodeError:
                        # Fallback to old parameter_name value format
                        parameter_name = command_parts[3]
                        parameter_value = " ".join(command_parts[4:]) if len(command_parts) > 4 else ""
                        tool_args = {parameter_name: parameter_value}
                        logger.info(f"Calling tool {tool_name} with key-value inputs: {tool_args}")
                
                try:
                    result = await client.call_tool(tool_name, tool_args)
                    await self.send_response(channel_id, f"Tool result from {server_name}: {result}", root_id)
                    # Send the result.text as markdown
                    if hasattr(result, 'content') and result.content:
                        if hasattr(result.content[0], 'text'):
                            await self.send_response(channel_id, result.content[0].text, root_id)
                except Exception as e:
                    logger.error(f"Error calling tool {tool_name} on {server_name}: {str(e)}")
                    await self.send_response(channel_id, f"Error calling tool {tool_name} on {server_name}: {str(e)}", root_id)
                    
            elif subcommand == 'resources':
                # Use the correct client instance
                resources = await client.list_resources()
                response = "Available MCP resources:\n"
                for resource in resources:
                    response += f"- {resource}\n"
                await self.send_response(channel_id, response, root_id)
                
            elif subcommand == 'prompts':
                # Use the correct client instance
                prompts = await client.list_prompts()
                response = "Available MCP prompts:\n"
                for prompt in prompts:
                    response += f"- {prompt}\n"
                await self.send_response(channel_id, response, root_id)
                
            else:
                # Try to use LLM as a fallback
                await self.handle_llm_request(channel_id, message_text, user_id, root_id)
                
        except Exception as e:
            logger.error(f"Error processing command: {str(e)}")
            await self.send_response(channel_id, f"Error processing command: {str(e)}", root_id)

    async def send_help_message(self, channel_id, post_id=None):
        """Send a detailed help message explaining all available commands"""
        help_text = f"""
                **MCP Client Help**
                Use `{self.command_prefix}<command>` to interact with MCP servers.

                **Available Commands:**
                1. `{self.command_prefix}help` - Show this help message
                2. `{self.command_prefix}servers` - List all available MCP servers

                **Server-specific Commands:**
                Use `{self.command_prefix}<server_name> <command>` to interact with a specific server.

                **Commands for each server:**
                1. `{self.command_prefix}<server_name> tools` - List all available tools for the server
                2. `{self.command_prefix}<server_name> call <tool_name> <parameter_name> <value>` - Call a specific tool
                3. `{self.command_prefix}<server_name> resources` - List all available resources
                4. `{self.command_prefix}<server_name> prompts` - List all available prompts

                **Examples:**
                • List servers:
                `{self.command_prefix}servers`
                • List tools for a server:
                `{self.command_prefix}simple-mcp-server tools`
                • Call a tool:
                `{self.command_prefix}simple-mcp-server call echo message "Hello World"`

                **Note:**
                - Tool parameters must be provided as name-value pairs
                - For tools with multiple parameters, use JSON format:
                `{self.command_prefix}<server_name> call <tool_name> parameters '{{"param1": "value1", "param2": "value2"}}'`
                
                **Direct Interaction:**
                You can also directly chat with the AI assistant which will use tools as needed.
                """
        await self.send_response(channel_id, help_text, post_id)
    
    async def send_tool_help(self, channel_id, server_name, tool_name, tool, post_id=None):
        """Send help message for a specific tool"""
        help_text = f"""
                    **Tool Help: {tool_name}**
                    Description: {tool.description}

                    **Parameters:**
                    """
        if hasattr(tool, 'inputSchema') and tool.inputSchema:
            required = tool.inputSchema.get('required', [])
            properties = tool.inputSchema.get('properties', {})
            for param_name, param_info in properties.items():
                req_mark = "*" if param_name in required else ""
                param_type = param_info.get('type', 'any')
                param_desc = param_info.get('description', '')
                help_text += f"- {param_name}{req_mark}: {param_type}"
                if param_desc:
                    help_text += f" - {param_desc}"
                help_text += "\n"
            help_text += "\n* = required parameter"
        else:
            help_text += "No parameters required"

        help_text += f"\n\n**Example:**\n`{self.command_prefix}{server_name} call {tool_name} "
        if hasattr(tool, 'inputSchema') and tool.inputSchema.get('required'):
            first_required = tool.inputSchema['required'][0]
            help_text += f"{first_required} <value>`"
        else:
            help_text += "<parameter_name> <value>`"

        await self.send_response(channel_id, help_text, post_id)
                
    async def send_response(self, channel_id, message, root_id=None):
        """Send a response to the Mattermost channel"""
        if channel_id is None:
            logger.warning(f"Channel id is not sent, using default channel - {self.channel_id}")
            channel_id = self.channel_id
        self.mattermost_client.post_message(channel_id, message, root_id)
        
    async def run(self):
        """Run the integration"""
        try:
            await self.initialize()
            
            # Keep the application running
            while True:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            logger.info("Shutting down...")
        except Exception as e:
            logger.error(f"Error in main loop: {str(e)}")
        finally:
            # Close clients in reverse order of initialization
            if self.mattermost_client:
                self.mattermost_client.close()
            for client in self.mcp_clients.values():
                await client.close()

async def start():
    integration = MattermostMCPIntegration()
    await integration.run()

def main():
    asyncio.run(start())

if __name__ == "__main__":
    main()
