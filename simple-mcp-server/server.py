import asyncio
import logging

from mcp.server.fastmcp import FastMCP

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import custom tools

# Create an MCP server
mcp = FastMCP("Test")


@mcp.tool()
def echo(message: str) -> str:
    """Echo a message"""
    return message

@mcp.tool()
def reverse(message: str) -> str:
    """Reverse a message"""
    return message[::-1]


# Add a dynamic greeting resource
@mcp.resource("greeting://{name}")
def get_greeting(name: str) -> str:
    """Get a personalized greeting"""
    return f"Hello, {name}!"

if __name__ == "__main__":
    mcp.run()