from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

import logging
import asyncio

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Create server parameters for stdio connection
server_params = StdioServerParameters(
    command="python", # Executable
    args=["simple-mcp-server/server.py"], # Update to use an actual server path
    env=None # Optional environment variables
)

async def run():
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            # Initialize the connection
            await session.initialize()

            # List available prompts
            prompts = await session.list_prompts()
            logger.info(f"Available prompts: {prompts}")

            # List available resources
            resources = await session.list_resources()
            logger.info(f"Available resources: {resources}")

            # List available tools
            tools = await session.list_tools()
            logger.info(f"Available tools: {tools}")

            # Call a tool
            result = await session.call_tool("echo", arguments={"message": "Hello World"})
            logger.info(f"Tool result: {result}")

if __name__ == "__main__":
    asyncio.run(run())