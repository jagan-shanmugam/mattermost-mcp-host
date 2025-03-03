import asyncio
import logging
import sys
import os
from mcp_server import main as server_main

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("ollama-mcp-server")

def main():
    """Main entry point"""
    try:
        logger.info("Starting Ollama MCP Server...")
        asyncio.run(server_main())
    except KeyboardInterrupt:
        logger.info("Shutting down Ollama MCP Server...")
    except Exception as e:
        logger.error(f"Error in server: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()