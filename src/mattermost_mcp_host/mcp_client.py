import os
import sys
import logging
import shutil

from mcp import ClientSession, StdioServerParameters
from mcp.types import (
            CallToolResult,
            EmbeddedResource,
            ImageContent,
            TextContent,
        )

NonTextContent = ImageContent | EmbeddedResource
from mcp.client.stdio import stdio_client
from mcp.client.sse import sse_client  # noqa
from langchain_core.tools import BaseTool, StructuredTool, ToolException

PYTHON_EXECUTABLE = sys.executable

class MCPClient:
    def __init__(self, server_config, log_level="INFO"):
        """
        Initialize MCP client to connect to an MCP server based on config.

        Args:
            server_config (dict): Configuration for the MCP server, including
                                  'command', 'args', 'env', 'type', 'url'.
            log_level (str): Logging level.
        """
        self.config = server_config
        # Default to stdio server type

        self.server_type = server_config.get('type', 'stdio').lower()
        self.mcp_command = server_config.get('command')
        self.mcp_args = server_config.get('args', [])
        self.env = server_config.get('env', os.environ.copy()) # Default to current environment
        self.url = server_config.get('url') # For http/sse

        self.session = None
        self.read = None
        self.write = None
        self.client_context = None  # Store the context manager (stdio or http)

        # Configure logging
        logging.basicConfig(
            level=getattr(logging, log_level),
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)

    async def connect(self):
        """Establish connection with the MCP server based on type."""
        if self.server_type == 'stdio':
            await self._connect_stdio()
        elif self.server_type in ['http', 'sse']:
            await self._connect_http()
        else:
            raise ValueError(f"Unsupported MCP server type: {self.server_type}")

        await self.session.initialize()
        # server_info = await self.session.get_server_info() # Optional: Log server info
        # self.logger.info(f"Connected to MCP Server: {server_info.name} (version {server_info.version})")
        return self.session

    async def _connect_stdio(self):
        """Establish connection via STDIO."""
        self.logger.info(f"Connecting via STDIO. Command: {self.mcp_command}, Args: {self.mcp_args}")

        command_path = self._find_executable(self.mcp_command)
        if not command_path:
             raise RuntimeError(f"Executable not found for command: {self.mcp_command}")
        self.logger.info(f"Using executable path: {command_path}")
        
        server_params = StdioServerParameters(
            command=command_path,
            args=self.mcp_args,
            env=self.env
        )

        self.client_context = stdio_client(server_params)
        self.read, self.write = await self.client_context.__aenter__()
        self.session = ClientSession(self.read, self.write)
        await self.session.__aenter__()
        self.logger.info("STDIO connection established.")

    async def _connect_http(self):
        """Establish connection via HTTP/SSE."""
        if not self.url:
            raise ValueError("URL is required for HTTP/SSE connection.")
        self.logger.info(f"Connecting via HTTP/SSE to URL: {self.url}")

        raise NotImplementedError("HTTP/SSE connection is not implemented yet.")
        # TODO: Implement HTTP/SSE connection
        # Assuming HttpClientParameters and http_client exist in the SDK
        # The http_client might handle both regular HTTP and SSE automatically
        # based on server capabilities or configuration.
        # client_params = HttpClientParameters(
        #     base_url=self.url,
        #     # Add any necessary headers or auth parameters here if needed
        #     # headers=self.config.get('headers'),
        # )

        # self.client_context = sse_client(client_params) # Assuming http_client exists
        # self.read, self.write = await self.client_context.__aenter__()
        # self.session = ClientSession(self.read, self.write)
        # await self.session.__aenter__()
        # self.logger.info("HTTP/SSE connection established.")

    def _find_executable(self, command):
        """Find the full path for an executable command."""
        if not command:
            return None
        # Handle absolute paths or commands already in PATH
        if os.path.isabs(command) or shutil.which(command):
            return command

        # Specific handling for common package managers/interpreters
        common_commands = {
            "python": PYTHON_EXECUTABLE,
            "node": shutil.which("node"),
            "docker": shutil.which("docker"),
            "npx": shutil.which("npx"),
            "uvx": shutil.which("uvx"), # Assuming uvx is in PATH
            # Add others if needed
        }

        if command in common_commands:
            return common_commands[command]

        # Fallback: try finding it in PATH again (might have been missed)
        found_path = shutil.which(command)
        if found_path:
             return found_path

        self.logger.warning(f"Could not find executable for command '{command}'. Assuming it's directly executable.")
        return command # Return original command as last resort

    async def list_tools(self):
        """List all available tools from the MCP server"""
        if not self.session:
            raise ConnectionError("MCP client not connected")
        
        response = await self.session.list_tools()
        tools = response.tools
        self.logger.info(f"Found {len(tools)} tools")
        return {tool.name: tool for tool in tools}

    async def call_tool(self, tool_name, inputs=None):
        """
        Call a specific MCP tool
        
        Args:
            tool_name: Name of the tool to call
            inputs: Dictionary of inputs for the tool (or None for tools without inputs)
        
        Returns:
            Result from the tool
        """
        if not self.session:
            raise ConnectionError("MCP client not connected")
        
        # TODO: Send this as response to user in Mattermost
        self.logger.info(f"Calling tool: {tool_name} with inputs: {inputs}")
        result = await self.session.call_tool(tool_name, arguments=inputs or {})
        return result

    async def list_resources(self):
        """List all available resources from the MCP server"""
        if not self.session:
            raise ConnectionError("MCP client not connected")
        
        response = await self.session.list_resources()
        resources = response.resources
        self.logger.info(f"Found {len(resources)} resources")
        return resources

    async def read_resource(self, uri):
        """
        Read a specific resource by URI
        
        Args:
            uri: URI of the resource to read
            
        Returns:
            Content of the resource
        """
        if not self.session:
            raise ConnectionError("MCP client not connected")
            
        result = await self.session.read_resource(uri)
        return result

    async def list_prompts(self):
        """List all available prompts from the MCP server"""
        if not self.session:
            raise ConnectionError("MCP client not connected")
        
        response = await self.session.list_prompts()
        prompts = response.prompts
        self.logger.info(f"Found {len(prompts)} prompts")
        return prompts

    async def get_prompt(self, name, arguments=None):
        """
        Get a specific prompt
        
        Args:
            name: Name of the prompt
            arguments: Dictionary of arguments for the prompt
            
        Returns:
            Prompt content
        """
        if not self.session:
            raise ConnectionError("MCP client not connected")
            
        result = await self.session.get_prompt(name, arguments or {})
        return result

    async def close(self):
        """Close the connection to the MCP server"""
        if self.session:
            await self.session.__aexit__(None, None, None)
            if self.client_context:
                await self.client_context.__aexit__(None, None, None)
            self.session = None
            self.read = None
            self.write = None
            self.client_context = None
            self.logger.info("Connection closed")

    async def convert_mcp_tools_to_langchain(self) -> list[BaseTool]:
        """
        Convert MCP tools to LangChain tools

        Returns:
            List of LangChain tools
        """
        
        # Define helper function for converting call tool results
        async def _convert_call_tool_result(
            call_tool_result: CallToolResult,
        ) -> tuple[str | list[str], list[NonTextContent] | None]:
            text_contents: list[TextContent] = []
            non_text_contents: list[NonTextContent] = []
            for content in call_tool_result.content:
                if isinstance(content, TextContent):
                    text_contents.append(content)
                else:
                    non_text_contents.append(content)

            tool_content: str | list[str] = [content.text for content in text_contents]
            if len(text_contents) == 1:
                tool_content = tool_content[0]

            if call_tool_result.isError:
                raise ToolException(tool_content)
            self.logger.info(f"tool_content: {tool_content}")
            # TODO: Handle non-text contents in a more appropriate way, e.g., by returning them as a list of EmbeddedResource or ImageContent or some other representation
            self.logger.info(f"non_text_contents: {non_text_contents}")
            return tool_content, non_text_contents or None
        
        # Get all MCP tools
        mcp_tools = await self.list_tools()
        langchain_tools = []
        
        # Convert each MCP tool to a LangChain tool
        for tool_name, tool_info in mcp_tools.items():
            # Create a function that will call the MCP tool
            async def _call_tool(tool_name=tool_name, **arguments):
                call_tool_result = await self.call_tool(tool_name, inputs=arguments)
                return await _convert_call_tool_result(call_tool_result)
            
            # Create a LangChain StructuredTool
            langchain_tool = StructuredTool(
                name=tool_name,
                description=tool_info.description or "",
                args_schema=tool_info.inputSchema,
                coroutine=_call_tool,
                response_format="content_and_artifact",
            )
            langchain_tools.append(langchain_tool)

        return langchain_tools
