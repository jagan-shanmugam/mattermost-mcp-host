from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
import mcp.types as types

import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Create server parameters for stdio connection
server_params = StdioServerParameters(
    command="python", # Executable
    args=["mcp-server/server.py"], # Optional command line arguments
    env=None # Optional environment variables
)

# Optional: create a sampling callback
async def handle_sampling_message(message: types.CreateMessageRequestParams) -> types.CreateMessageResult:
    return types.CreateMessageResult(
        role="assistant",
        content=types.TextContent(
            type="text",
            text="Hello, world! from model",
        ),
        model="gpt-3.5-turbo",
        stopReason="endTurn",
    )

async def run():
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write, sampling_callback=handle_sampling_message) as session:
            # Initialize the connection
            await session.initialize()

            # List available prompts
            prompts = await session.list_prompts()
            logger.info(f"Available prompts: {prompts}")
            # Get a prompt
            # prompt = await session.get_prompt("example-prompt", arguments={"arg1": "value"})

            # List available resources
            resources = await session.list_resources()
            logger.info(f"Available resources: {resources}")

            # List available tools
            tools = await session.list_tools()
            logger.info(f"Available tools: {tools}")
            # Read a resource
            # content, mime_type = await session.read_resource("file://some/path")

            # Call a tool
            result = await session.call_tool("echo", arguments={"message": "value"})

if __name__ == "__main__":
    import asyncio
    asyncio.run(run())