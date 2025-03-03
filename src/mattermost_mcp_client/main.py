import sys
import asyncio
import logging
import json
import sys
from pathlib import Path
from mcp_client import MCPClient
from mattermost_client import MattermostClient
import mattermost_mcp_client.config as config

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
        
    async def handle_message(self, post):
        """Handle incoming messages from Mattermost"""
        logger.info(f"Received post: {json.dumps(post, indent=2)}")  # Better logging
        
        # Skip messages that don't start with the command prefix
        message = post.get('message', '')
        if not message.startswith(self.command_prefix):
            return
            
        # Skip messages from other channels
        if post.get('channel_id') != self.channel_id:
            logger.info(f'Received message from a different channel - {post.get('channel_id')} than configured - {self.channel_id}')
            # return
        channel_id = post.get('channel_id')
            
        logger.info(f"Processing command: {message}")
        
        try:
            command_parts = post.get('message', '').split()
            
            if len(command_parts) < 2:
                await self.send_help_message(channel_id)
                return
                
            command = command_parts[1]
            
            if command == 'help':
                await self.send_help_message(channel_id)
                return
            
            if command == 'servers':
                response = "Available MCP servers:\n"
                for name in self.mcp_clients.keys():
                    response += f"- {name}\n"
                await self.send_response(channel_id, response)
                return

            # Check if the first argument is a server name
            server_name = command
            if server_name not in self.mcp_clients:
                await self.send_response(
                    channel_id,
                    f"Unknown server '{server_name}'. Available servers: {', '.join(self.mcp_clients.keys())}"
                )
                return

            if len(command_parts) < 3:
                await self.send_response(
                    channel_id,
                    f"Invalid command. Use {self.command_prefix} {server_name} <command> [arguments]"
                )
                return

            client = self.mcp_clients[server_name]
            command = command_parts[2]

            if command == 'tools':
                tools = await client.list_tools()
                response = f"Available tools for {server_name}:\n"
                for name, tool in tools.items():
                    response += f"- {name}: {tool.description}\n"
                await self.send_response(channel_id, response)
                
            elif command == 'call':
                if len(command_parts) < 4:
                    await self.send_response(
                        channel_id,
                        f"Invalid call command. Use {self.command_prefix} {server_name} call <tool_name> [parameter_name] [value]"
                    )
                    return
                    
                tool_name = command_parts[3]
                # Handle tools with no parameters
                if len(command_parts) == 4:
                    tool_args = {}
                    logger.info(f"Calling tool {tool_name} with no parameters")
                else:
                    # Parse input as JSON if provided
                    try:
                        # Join remaining parts and parse as JSON
                        params_str = " ".join(command_parts[4:]).replace("'", '')
                        
                        tool_args = json.loads(params_str)
                        logger.info(f"Calling tool {tool_name} with JSON inputs: {tool_args}")
                    except json.JSONDecodeError:
                        # Fallback to old parameter_name value format
                        parameter_name = command_parts[4]
                        parameter_value = " ".join(command_parts[5:]) if len(command_parts) > 5 else ""
                        tool_args = {parameter_name: parameter_value}
                        logger.info(f"Calling tool {tool_name} with key-value inputs: {tool_args}")
                
                try:
                    result = await client.call_tool(tool_name, tool_args)
                    await self.send_response(channel_id, f"Tool result from {server_name}: {result}")
                    # Send the result.text as markdown
                    if hasattr(result, 'content') and result.content:
                        if hasattr(result.content[0], 'text'):
                            await self.send_response(channel_id, result.content[0].text)
                except Exception as e:
                    logger.error(f"Error calling tool {tool_name} on {server_name}: {str(e)}")
                    await self.send_response(channel_id, f"Error calling tool {tool_name} on {server_name}: {str(e)}")
                    
            elif command == 'resources':
                # Use the correct client instance
                resources = await client.list_resources()
                response = "Available MCP resources:\n"
                for resource in resources:
                    response += f"- {resource}\n"
                await self.send_response(channel_id, response)
                
            elif command == 'prompts':
                # Use the correct client instance
                prompts = await client.list_prompts()
                response = "Available MCP prompts:\n"
                for prompt in prompts:
                    response += f"- {prompt}\n"
                await self.send_response(channel_id, response)
                
            else:
                await self.send_response(
                    channel_id,
                    f"Unknown command. Available commands: tools, call, resources, prompts"
                )
        except Exception as e:
            logger.error(f"Error processing command: {str(e)}")
            await self.send_response(channel_id, f"Error processing command: {str(e)}")
                
    async def send_response(self, channel_id, message):
        """Send a response to the Mattermost channel"""
        if channel_id is None:
            logger.warning(f"Channel id is not sent, using default channel - {self.channel_id}")
            channel_id = self.channel_id
        self.mattermost_client.post_message(channel_id, message)
        
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

    async def send_help_message(self, channel_id):
        """Send a detailed help message explaining all available commands"""
        help_text = f"""
                **MCP Client Help**
                Use `{self.command_prefix} <command>` to interact with MCP servers.

                **Available Commands:**
                1. `{self.command_prefix} help` - Show this help message
                2. `{self.command_prefix} servers` - List all available MCP servers

                **Server-specific Commands:**
                Use `{self.command_prefix} <server_name> <command>` to interact with a specific server.

                **Commands for each server:**
                1. `{self.command_prefix} <server_name> tools` - List all available tools for the server
                2. `{self.command_prefix} <server_name> call <tool_name> <parameter_name> <value>` - Call a specific tool
                3. `{self.command_prefix} <server_name> resources` - List all available resources
                4. `{self.command_prefix} <server_name> prompts` - List all available prompts

                **Examples:**
                • List servers:
                `{self.command_prefix} servers`
                • List tools for a server:
                `{self.command_prefix} simple-mcp-server tools`
                • Call a tool:
                `{self.command_prefix} simple-mcp-server call echo message "Hello World"`

                **Note:**
                - Tool parameters must be provided as name-value pairs
                - For tools with multiple parameters, use JSON format:
                `{self.command_prefix} <server_name> call <tool_name> parameters '{{"param1": "value1", "param2": "value2"}}'`
                """
        await self.send_response(channel_id, help_text)

    async def send_tool_help(self, channel_id, server_name, tool_name, tool):
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

        help_text += f"\n\n**Example:**\n`{self.command_prefix} {server_name} call {tool_name} "
        if hasattr(tool, 'inputSchema') and tool.inputSchema.get('required'):
            first_required = tool.inputSchema['required'][0]
            help_text += f"{first_required} <value>`"
        else:
            help_text += "<parameter_name> <value>`"

        await self.send_response(channel_id, help_text)

                
    async def send_response(self, channel_id, message):
        """Send a response to the Mattermost channel"""
        if channel_id is None:
            logger.warning(f"Channel id is not sent, using default channel - {self.channel_id}")
            channel_id = self.channel_id
        self.mattermost_client.post_message(channel_id, message)
        
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