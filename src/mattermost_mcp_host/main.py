import sys
import asyncio
import logging
import json
from pathlib import Path
from mattermost_mcp_host.mcp_client import MCPClient
from mattermost_mcp_host.mattermost_client import MattermostClient
import mattermost_mcp_host.config as config
from mattermost_mcp_host.llm_clients import LLMClient

# Add these imports
from typing import Dict, List, Any, Optional
import traceback

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
        self.llm_client = LLMClient(config.DEFAULT_PROVIDER, config.DEFAULT_MODEL)
        
    async def initialize(self):
        """Initialize both clients and connect them"""
        # Initialize MCP clients based on configuration
        try:
            # Load server configurations
            server_configs = load_server_configs()
            logger.info(f"Found {len(server_configs)} MCP servers in config")
            
            # Initialize each MCP client
            for server_name, server_config in server_configs.items():
                if server_config.get('type') == 'stdio':
                    try:
                        client = MCPClient(
                            mcp_command=server_config["command"],
                            mcp_args=server_config["args"],
                            env=config.MCP_ENV
                        )
                        await client.connect()
                        self.mcp_clients[server_name] = client
                        logger.info(f"Connected to MCP server '{server_name}' via stdio")
                    except Exception as e:
                        logger.error(f"Failed to connect to MCP server '{server_name}': {str(e)}")
                        # Continue with other servers even if one fails
                        continue
                else:
                    logger.warning(f"Unknown server type '{server_config.get('type')}' for server '{server_name}'. Skipping.")

            if not self.mcp_clients:
                raise ValueError("No MCP servers could be connected")

        except Exception as e:
            logger.error(f"Failed to initialize MCP servers: {str(e)}")
            raise

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
        
    async def get_thread_history(self, root_id=None, channel_id=None):
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

    async def handle_llm_request(self, channel_id: str, message: str, user_id: str, post_id: str = None):
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
            root_id = post_id
            
            # Send a typing indicator
            await self.send_response(channel_id, "Processing your request...", root_id)
            
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
            
            # Convert MCP tools to OpenAI tools format
            openai_tools = self.llm_client.convert_mcp_tools_to_openai_tools(all_tools)
            
            # Get thread history (will be empty for a new conversation)
            thread_messages = await self.get_thread_history(root_id, channel_id)
            
            # Add current message if not already in thread history
            if not thread_messages or thread_messages[-1]["content"] != message:
                thread_messages.append({
                    "role": "user",
                    "content": message
                })
            
            # Call the LLM with thread history
            response = await self.llm_client.generate_response(
                prompt=message,
                tools=openai_tools,
                messages=thread_messages
            )
            
            # Process the response
            response_message = response.choices[0].message
            
            # Check if the model wants to use tools
            if hasattr(response_message, "tool_calls") and response_message.tool_calls:
                await self.handle_tool_calls(channel_id, response_message.tool_calls, all_tools, root_id, post_id)
            else:
                # Just return the text response
                await self.send_response(channel_id, response_message.content or "No response generated", post_id)
                
        except Exception as e:
            logger.error(f"Error handling LLM request: {str(e)}")
            logger.error(traceback.format_exc())
            await self.send_response(channel_id, f"Error processing your request: {str(e)}", post_id)
    
    async def handle_tool_calls(self, channel_id, tool_calls, all_tools, root_id=None, post_id=None):
        """
        Handle tool calls from the LLM
        
        Args:
            channel_id: Channel ID
            tool_calls: List of tool calls from the LLM
            all_tools: Dictionary of available tools
            root_id: Root post ID for the thread
            post_id: Current post ID
        """
        thread_id = root_id or post_id
        
        # Extract and process each tool call
        tool_results = []
        for tool_call in tool_calls:
            try:
                function = tool_call.function
                tool_name = function.name
                
                # Parse the function arguments
                function_args = {}
                if function.arguments:
                    try:
                        function_args = json.loads(function.arguments)
                    except json.JSONDecodeError:
                        logger.error(f"Failed to parse tool arguments: {function.arguments}")
                        function_args = {"text": function.arguments}
                
                # Find the corresponding MCP tool
                if tool_name in all_tools:
                    # Direct match
                    mcp_tool = all_tools[tool_name]
                    server_name, tool_short_name = tool_name.split('.', 1)
                else:
                    # Try to find by short name (without server prefix)
                    matching_tools = [
                        (s_name, t_name, tool)
                        for full_name, tool in all_tools.items()
                        for s_name, t_name in [full_name.split('.', 1)]
                        if t_name == tool_name
                    ]
                    
                    if not matching_tools:
                        await self.send_response(
                            channel_id, 
                            f"⚠️ Tool '{tool_name}' not found in any MCP server.", 
                            thread_id
                        )
                        tool_results.append({
                            "tool_call_id": tool_call.id,
                            "role": "tool",
                            "name": tool_name,
                            "content": f"Tool '{tool_name}' not found in any MCP server."
                        })
                        continue
                    
                    # Use the first matching tool if multiple matches found
                    server_name, tool_short_name, mcp_tool = matching_tools[0]
                
                # Call the tool via the MCP client
                client = self.mcp_clients.get(server_name)
                if not client:
                    error_msg = f"Server '{server_name}' not found or not connected."
                    await self.send_response(channel_id, f"⚠️ {error_msg}", thread_id)
                    tool_results.append({
                        "tool_call_id": tool_call.id,
                        "role": "tool",
                        "name": tool_name,
                        "content": error_msg
                    })
                    continue
                
                # Log tool execution for debugging
                logger.info(f"Calling tool '{tool_short_name}' on server '{server_name}' with args: {function_args}")
                
                # Execute the tool
                await self.send_response(
                    channel_id, 
                    f"🔧 Executing tool: `{tool_short_name}` on server `{server_name}`...", 
                    thread_id
                )
                result = await client.call_tool(tool_short_name, function_args)
                
                # Format and process tool result
                result_str = str(result)
                if isinstance(result, dict):
                    # Try to format dict results nicely
                    try:
                        result_str = json.dumps(result, indent=2)
                    except:
                        result_str = str(result)
                
                await self.send_response(
                    channel_id, 
                    f"📊 Tool `{tool_short_name}` result:\n```\n{result_str}\n```", 
                    thread_id
                )
                
                # Add to tool results for LLM
                tool_results.append({
                    "tool_call_id": tool_call.id,
                    "role": "tool",
                    "name": tool_name,
                    "content": result_str
                })
                
            except Exception as e:
                error_msg = f"Error executing tool '{tool_call.function.name}': {str(e)}"
                logger.error(error_msg)
                logger.error(traceback.format_exc())
                
                await self.send_response(channel_id, f"⚠️ {error_msg}", thread_id)
                
                # Add error to tool results
                tool_results.append({
                    "tool_call_id": tool_call.id,
                    "role": "tool",
                    "name": tool_call.function.name,
                    "content": error_msg
                })
        
        # Get updated thread history
        thread_messages = await self.get_thread_history(thread_id, channel_id)
        
        # Add tool results to messages for follow-up LLM call
        thread_messages.extend(tool_results)
        
        # Call LLM again with tool results for final response
        await self.send_response(channel_id, "🧠 Processing tool results...", thread_id)
        
        # Get tools again for the follow-up response
        openai_tools = self.llm_client.convert_mcp_tools_to_openai_tools(all_tools)
        
        # Generate follow-up response
        response = await self.llm_client.generate_response(
            prompt="Please analyze the tool results and provide a final response.",
            tools=openai_tools,  # Keep tools available for follow-up
            messages=thread_messages
        )
        
        # Process the follow-up response
        final_message = response.choices[0].message
        
        # Send the final response
        await self.send_response(channel_id, final_message.content or "No response generated", thread_id)
        
        # Check if we need to handle more tool calls (recursive)
        if hasattr(final_message, "tool_calls") and final_message.tool_calls:
            await self.handle_tool_calls(channel_id, final_message.tool_calls, all_tools, thread_id)

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
            post_id = post.get('id')  # Get the post ID for threading
            
            # Skip messages from other channels if a specific channel is configured
            if self.channel_id and channel_id != self.channel_id:
                logger.info(f'Received message from a different channel - {channel_id} than configured - {self.channel_id}')
                # Only process direct messages to the bot and messages in the configured channel
                if not any(team_member.get('mention_keys', []) in message for team_member in self.mattermost_client.driver.users.get_user_teams(user_id)):
                    return
            
            # Check if the message starts with the command prefix
            if message.startswith(self.command_prefix):
                # Handle MCP command
                await self.handle_command(channel_id, message, user_id, post_id)
            elif message.startswith('!') or message.startswith('/'):
                # Skip other commands
                return
            else:
                # Direct message to LLM
                await self.handle_llm_request(channel_id, message, user_id, post_id)
                
        except Exception as e:
            logger.error(f"Error handling message: {str(e)}")
            logger.error(traceback.format_exc())

    async def handle_command(self, channel_id, message_text, user_id, post_id=None):
        """Handle command messages from Mattermost"""
        try:
            # Split the command text
            command_parts = message_text.split()
            
            if len(command_parts) < 1:
                await self.send_help_message(channel_id, post_id)
                return
            
            command = command_parts[0]
            
            if command == 'help':
                await self.send_help_message(channel_id, post_id)
                return
            
            if command == 'servers':
                response = "Available MCP servers:\n"
                for name in self.mcp_clients.keys():
                    response += f"- {name}\n"
                await self.send_response(channel_id, response, post_id)
                return
            
            # Check if the first argument is a server name
            server_name = command
            if server_name not in self.mcp_clients:
                await self.send_response(
                    channel_id,
                    f"Unknown server '{server_name}'. Available servers: {', '.join(self.mcp_clients.keys())}",
                    post_id
                )
                return
            
            if len(command_parts) < 2:
                await self.send_response(
                    channel_id,
                    f"Invalid command. Use {self.command_prefix}{server_name} <command> [arguments]",
                    post_id
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
                await self.send_response(channel_id, response, post_id)
                
            elif subcommand == 'call':
                if len(command_parts) < 4:
                    await self.send_response(
                        channel_id,
                        f"Invalid call command. Use {self.command_prefix}{server_name} call <tool_name> [parameter_name] [value]",
                        post_id
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
                    await self.send_response(channel_id, f"Tool result from {server_name}: {result}", post_id)
                    # Send the result.text as markdown
                    if hasattr(result, 'content') and result.content:
                        if hasattr(result.content[0], 'text'):
                            await self.send_response(channel_id, result.content[0].text, post_id)
                except Exception as e:
                    logger.error(f"Error calling tool {tool_name} on {server_name}: {str(e)}")
                    await self.send_response(channel_id, f"Error calling tool {tool_name} on {server_name}: {str(e)}", post_id)
                    
            elif subcommand == 'resources':
                # Use the correct client instance
                resources = await client.list_resources()
                response = "Available MCP resources:\n"
                for resource in resources:
                    response += f"- {resource}\n"
                await self.send_response(channel_id, response, post_id)
                
            elif subcommand == 'prompts':
                # Use the correct client instance
                prompts = await client.list_prompts()
                response = "Available MCP prompts:\n"
                for prompt in prompts:
                    response += f"- {prompt}\n"
                await self.send_response(channel_id, response, post_id)
                
            else:
                # Try to use LLM as a fallback
                await self.handle_llm_request(channel_id, message_text, user_id, post_id)
                
        except Exception as e:
            logger.error(f"Error processing command: {str(e)}")
            await self.send_response(channel_id, f"Error processing command: {str(e)}", post_id)

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

if __name__ == "__main__":
    asyncio.run(start())