import asyncio

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

import os
import sys
import logging
import shutil  # Add this import at the top with other imports

PYTHON_EXECUTABLE = sys.executable

class MCPClient:
    def __init__(self, mcp_command="python", mcp_args=None, env=None, log_level="INFO"):
        """
        Initialize MCP client to connect to any MCP server
        
        Args:
            mcp_command: Command to execute MCP server (e.g., "python")
            mcp_args: Arguments for the MCP server command
            env: Environment variables for the MCP server
            log_level: Logging level
        """
        self.mcp_command = mcp_command
        self.mcp_args = mcp_args or []
        self.env = env
        self.session = None
        self.read = None
        self.write = None
        self.stdio_context = None  # Store the context manager
        
        # Configure logging
        logging.basicConfig(
            level=getattr(logging, log_level),
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)

    async def connect(self):
        """Establish connection with the MCP server"""
        self.logger.info(f"Using MCP Server Command - {self.mcp_command}, Arguments: {self.mcp_args}")
        
        # Detect Docker path if needed
        command = self.mcp_command
        if command == "docker":
            docker_path = shutil.which("docker")
            if not docker_path:
                raise RuntimeError("Docker executable not found. Please ensure Docker is installed and in PATH")
            command = docker_path
            self.logger.info(f"Using Docker path: {docker_path}")
        elif command == "python":
            command = PYTHON_EXECUTABLE
        else:
            self.logger.warning(f"Unknown MCP command: {self.mcp_command}. Assuming it's a command to execute.")
        
        server_params = StdioServerParameters(
            command=command,
            args=self.mcp_args,
            env=self.env
        )
        
        self.stdio_context = stdio_client(server_params)
        self.read, self.write = await self.stdio_context.__aenter__()
        self.session = ClientSession(self.read, self.write)
        await self.session.__aenter__()
        await self.session.initialize()
        
        # server_info = await self.session.get_server_info()
        # self.logger.info(f"Connected to MCP Server: {server_info.name} (version {server_info.version})")
        
        return self.session

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
            if self.stdio_context:
                await self.stdio_context.__aexit__(None, None, None)
            self.session = None
            self.read = None
            self.write = None
            self.stdio_context = None
            self.logger.info("Connection closed")
