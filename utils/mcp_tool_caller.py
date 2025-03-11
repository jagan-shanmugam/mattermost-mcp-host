import asyncio
import argparse
import json
from mattermost_mcp_host.mcp_client import MCPClient
import os
from pathlib import Path
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def load_server_configs():
    """Load MCP server configurations from mcp-servers.json"""
    try:
        # Get the path to mcp-servers.json relative to the package
        config_path = Path(__file__).parent.parent / "src" / "mattermost_mcp_host" / "mcp-servers.json"
        
        with open(config_path) as f:
            config = json.load(f)
            return config.get("mcpServers", {})
    except Exception as e:
        logger.error(f"Error loading server configurations: {str(e)}")
        return {}

async def call_server_tool(server_command, server_args, tool_name, tool_args_json=None):
    """
    Connect to a specific MCP server and call a tool
    
    Args:
        server_command: Command to run the server (e.g., 'python')
        server_args: Arguments to pass to the server command
        tool_name: Name of the tool to call
        tool_args_json: JSON string containing tool arguments
    """
    # Parse tool arguments if provided
    tool_args = {}
    if tool_args_json:
        try:
            tool_args = json.loads(tool_args_json)
        except json.JSONDecodeError as e:
            print(f"Error parsing tool arguments: {str(e)}")
            return
    
    logger.info("Connecting to the MCP server...")
    logger.info(f"Server command: {server_command}")
    logger.info(f"Server arguments: {server_args.split() if isinstance(server_args, str) else server_args}")
    # Create and connect to the MCP server
    client = MCPClient(
        mcp_command=server_command,
        mcp_args=server_args.split() if isinstance(server_args, str) else server_args,
        log_level="INFO"
    )
    
    try:
        # Connect to the server
        await client.connect()
        
        # List available tools
        tools = await client.list_tools()
        print(f"Available tools: {', '.join(tools.keys())}")
        
        # Check if the requested tool exists
        if tool_name not in tools:
            print(f"Error: Tool '{tool_name}' not found. Available tools: {', '.join(tools.keys())}")
            return
        
        # Get tool details to check required arguments
        tool = tools[tool_name]
        print(f"Calling tool: {tool_name}")
        
        # Call the tool
        result = await client.call_tool(tool_name, tool_args)
        
        # Process and display the result
        print("Tool result:")
        if isinstance(result, list):
            for item in result:
                if hasattr(item, 'text'):
                    print(item.text)
                else:
                    print(item)
        else:
            print(result)
        
    except Exception as e:
        print(f"Error: {str(e)}")
    finally:
        # Close the connection
        await client.close()

async def list_server_capabilities(server_command, server_args):
    """
    Connect to an MCP server and list all its capabilities
    
    Args:
        server_command: Command to run the server
        server_args: Arguments to pass to the server command
    """
    logger.info("Connecting to the MCP server...")
    logger.info(f"Server command: {server_command}")
    logger.info(f"Server arguments: {server_args}")

    # Create and connect to the MCP server
    client = MCPClient(
        mcp_command=server_command,
        mcp_args=server_args.split() if isinstance(server_args, str) else server_args,
        log_level="INFO"
    )
    
    try:
        # Connect to the server
        await client.connect()
        
        # List available tools
        tools = await client.list_tools()
        print("\nAvailable Tools:")
        for name, tool in tools.items():
            print(f"  - {name}: {tool.description}")
            if hasattr(tool, 'inputSchema') and tool.inputSchema:
                required = tool.inputSchema.get('required', [])
                properties = tool.inputSchema.get('properties', {})
                if properties:
                    print("    Parameters:")
                    for param_name, param_info in properties.items():
                        req_mark = "*" if param_name in required else ""
                        param_type = param_info.get('type', 'any')
                        print(f"      - {param_name}{req_mark}: {param_type}")
        
        # List available resources
        resources = await client.list_resources()
        print("\nAvailable Resources:")
        for resource in resources:
            print(f"  - {resource.name}: {resource.uri}")
            if hasattr(resource, 'description') and resource.description:
                print(f"    {resource.description}")
        
        # List available prompts
        prompts = await client.list_prompts()
        print("\nAvailable Prompts:")
        for prompt in prompts:
            print(f"  - {prompt.name}: {prompt.description}")
            if hasattr(prompt, 'arguments') and prompt.arguments:
                print("    Arguments:")
                for arg in prompt.arguments:
                    req_mark = "*" if arg.required else ""
                    print(f"      - {arg.name}{req_mark}: {arg.description}")
        
    except Exception as e:
        print(f"Error: {str(e)}")
    finally:
        # Close the connection
        await client.close()

def main():
    parser = argparse.ArgumentParser(description="MCP Tool Caller")
    subparsers = parser.add_subparsers(dest="command", help="Command")
    
    # Load server configurations
    server_configs = load_server_configs()
    available_servers = list(server_configs.keys())
    
    # Call tool command
    call_parser = subparsers.add_parser("call", help="Call an MCP tool")
    call_parser.add_argument("--server-name", required=True, choices=available_servers,
                           help=f"Server name from config. Available: {', '.join(available_servers)}")
    call_parser.add_argument("--tool", required=True, help="Tool name to call")
    call_parser.add_argument("--tool-args", help="JSON string of tool arguments (e.g., '{\"message\": \"Hello\"}')")
    
    # List capabilities command
    list_parser = subparsers.add_parser("list", help="List server capabilities")
    list_parser.add_argument("--server-name", required=True, choices=available_servers,
                           help=f"Server name from config. Available: {', '.join(available_servers)}")
    
    args = parser.parse_args()
    
    if not available_servers:
        print("Error: No MCP servers configured in mcp-servers.json")
        return
    
    if args.command == "call":
        server_config = server_configs[args.server_name]
        asyncio.run(call_server_tool(
            server_config["command"],
            server_config["args"],
            args.tool,
            args.tool_args
        ))
    elif args.command == "list":
        server_config = server_configs[args.server_name]
        asyncio.run(list_server_capabilities(
            server_config["command"],
            server_config["args"]
        ))
    else:
        parser.print_help()

if __name__ == "__main__":
    main()