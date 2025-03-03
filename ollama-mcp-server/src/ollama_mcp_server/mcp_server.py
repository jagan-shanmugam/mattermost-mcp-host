import asyncio
import os
import logging
import json
from datetime import datetime
from typing import Dict, List, Optional, Any

import aiohttp
from mcp.server.models import InitializationOptions
import mcp.types as types
from mcp.server import NotificationOptions, Server
from pydantic import AnyUrl
import mcp.server.stdio

# Ollama Configuration
OLLAMA_BASE_URL = os.environ.get('OLLAMA_BASE_URL', 'http://localhost:11434')
DEFAULT_MODEL = os.environ.get('DEFAULT_MODEL', 'llama2')

class config:
    LOG_LEVEL = "DEBUG"
    MODEL_NAME = DEFAULT_MODEL
    MCP_SERVER_NAME = "ollama-mcp-server"
    MCP_SERVER_VERSION = "0.1.0"

# Configure logging
logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

server = Server("ollama-mcp-server")

# Ollama API helper functions
async def call_ollama_api(endpoint: str, method: str = "GET", json_data: Optional[Dict] = None) -> Dict:
    """Call Ollama API with the given endpoint and method"""
    url = f"{OLLAMA_BASE_URL}/api/{endpoint}"
    
    async with aiohttp.ClientSession() as session:
        if method == "GET":
            async with session.get(url) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    error = await response.text()
                    raise ValueError(f"Failed to call Ollama API. Status: {response.status}, Error: {error}")
        elif method == "POST":
            async with session.post(url, json=json_data) as response:
                if response.status == 200:
                    # Handle streaming responses (for generate and chat endpoints)
                    if endpoint in ["generate", "chat"]:
                        final_response = {"response": "", "model": "", "message": {}}
                        async for line in response.content.iter_any():
                            if not line:
                                continue
                            try:
                                data = json.loads(line)
                                logger.debug(f"Data response: {data}")
                                # For generate endpoint
                                if "response" in data:
                                    final_response["response"] += data.get("response", "")
                                    final_response["model"] = data.get("model", "")
                                # For chat endpoint
                                elif "message" in data:
                                    if not final_response["message"]:
                                        final_response["message"] = data.get("message", {})
                                    else:
                                        final_response["message"]["content"] = final_response["message"].get("content", "") + data.get("message", {}).get("content", "")
                                    final_response["model"] = data.get("model", "")
                                if data.get("done", False):
                                    break
                            except json.JSONDecodeError as e:
                                logger.error(f"Error parsing streaming response: {e}")
                                continue
                        logger.debug(f"Ollama API streaming response: {final_response}")
                        return final_response
                    else:
                        # For non-streaming endpoints (like tags)
                        return await response.json()
                else:
                    error = await response.text()
                    raise ValueError(f"Failed to call Ollama API. Status: {response.status}, Error: {error}")
        else:
            raise ValueError(f"Unsupported HTTP method: {method}")

async def list_models() -> List[Dict]:
    """List all available models from Ollama"""
    try:
        response = await call_ollama_api("tags")
        # The Ollama API returns models directly in the response
        return response.get("models", []) if isinstance(response, dict) else []
    except Exception as e:
        logger.error(f"Error listing models: {str(e)}")
        return []

async def generate_text(prompt: str, model: Optional[str] = None, system_prompt: Optional[str] = None, **options) -> Dict:
    """Generate text using Ollama"""
    model = model or config.MODEL_NAME
    
    request_data = {
        "model": model,
        "prompt": prompt,
        "options": options
    }
    
    if system_prompt:
        request_data["system"] = system_prompt
    
    return await call_ollama_api("generate", method="POST", json_data=request_data)

async def chat_completion(messages: List[Dict], model: Optional[str] = None, **options) -> Dict:
    """Chat with Ollama model"""
    model = model or config.MODEL_NAME
    
    request_data = {
        "model": model,
        "messages": messages,
        "options": options
    }
    
    return await call_ollama_api("chat", method="POST", json_data=request_data)

@server.list_resources()
async def handle_list_resources() -> list[types.Resource]:
    """
    List available Ollama resources.
    """
    resources = [
        types.Resource(
            uri=AnyUrl("ollama://config"),
            name="Ollama Configuration",
            description="Ollama server configuration",
            mimeType="application/json",
        ),
        types.Resource(
            uri=AnyUrl("ollama://models"),
            name="Ollama Models",
            description="List of available models in Ollama",
            mimeType="application/json",
        )
    ]
    
    # Add resources for each model
    try:
        models = await list_models()
        for model in models:
            model_name = model.get("name")
            resources.append(
                types.Resource(
                    uri=AnyUrl(f"ollama://model/{model_name}"),
                    name=f"Model: {model_name}",
                    description=f"Ollama model: {model_name}",
                    mimeType="application/json",
                )
            )
    except Exception as e:
        logger.error(f"Error fetching models: {str(e)}")
    
    return resources

@server.read_resource()
async def handle_read_resource(uri: AnyUrl) -> str:
    """
    Read a specific Ollama resource by its URI.
    """
    if uri.scheme != "ollama":
        raise ValueError(f"Unsupported URI scheme: {uri.scheme}")

    path = uri.path
    if path.startswith("/"):
        path = path[1:]
    
    parts = path.split("/") if "/" in path else [path]
    
    if parts[0] == "config":
        return json.dumps({
            "base_url": OLLAMA_BASE_URL,
            "default_model": config.MODEL_NAME
        }, indent=2)
    
    elif parts[0] == "models":
        try:
            models = await list_models()
            return json.dumps(models, indent=2)
        except Exception as e:
            raise ValueError(f"Failed to list models: {str(e)}")
    
    elif parts[0] == "model" and len(parts) > 1:
        model_name = parts[1]
        try:
            # Get model info by listing models and filtering
            models = await list_models()
            for model in models:
                if model.get("name") == model_name:
                    return json.dumps(model, indent=2)
            
            raise ValueError(f"Model not found: {model_name}")
        except Exception as e:
            raise ValueError(f"Failed to get model info: {str(e)}")
    
    raise ValueError(f"Unsupported resource: {path}")

@server.list_prompts()
async def handle_list_prompts() -> list[types.Prompt]:
    """
    List available Ollama-related prompts.
    """
    return [
        types.Prompt(
            name="default-prompt",
            description="Default prompt template for generating text",
            arguments=[
                types.PromptArgument(
                    name="instruction",
                    description="The instruction or task for the AI",
                    required=True,
                ),
                types.PromptArgument(
                    name="model",
                    description="The model to use",
                    required=False,
                )
            ],
        ),
        types.Prompt(
            name="system-prompt",
            description="System prompt template for chat",
            arguments=[
                types.PromptArgument(
                    name="system_message",
                    description="The system message that defines AI behavior",
                    required=True,
                ),
                types.PromptArgument(
                    name="user_message",
                    description="The user's initial message",
                    required=True,
                )
            ],
        )
    ]

@server.get_prompt()
async def handle_get_prompt(
    name: str, arguments: dict[str, str] | None
) -> types.GetPromptResult:
    """
    Generate Ollama-related prompts.
    """
    if not arguments:
        raise ValueError("Missing required arguments")
    
    if name == "default-prompt":
        instruction = arguments.get("instruction")
        if not instruction:
            raise ValueError("Missing required argument: instruction")
            
        model = arguments.get("model", config.MODEL_NAME)
            
        return types.GetPromptResult(
            description=f"Default prompt for {model}",
            messages=[
                types.PromptMessage(
                    role="user",
                    content=types.TextContent(
                        type="text",
                        text=instruction,
                    ),
                )
            ],
        )
    
    elif name == "system-prompt":
        system_message = arguments.get("system_message")
        user_message = arguments.get("user_message")
        
        if not system_message or not user_message:
            raise ValueError("Missing required arguments: system_message and user_message")
            
        return types.GetPromptResult(
            description="Chat with system prompt",
            messages=[
                types.PromptMessage(
                    role="system",
                    content=types.TextContent(
                        type="text",
                        text=system_message,
                    ),
                ),
                types.PromptMessage(
                    role="user",
                    content=types.TextContent(
                        type="text",
                        text=user_message,
                    ),
                )
            ],
        )
        
    raise ValueError(f"Unknown prompt: {name}")

@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    """
    List available Ollama tools.
    """
    return [
        types.Tool(
            name="generate",
            description="Generate text using Ollama",
            inputSchema={
                "type": "object",
                "properties": {
                    "prompt": {
                        "type": "string",
                        "description": "The prompt to generate text from"
                    },
                    "system_prompt": {
                        "type": "string",
                        "description": "Optional system prompt"
                    },
                    "model": {
                        "type": "string",
                        "description": "Optional model name to use"
                    },
                    "temperature": {
                        "type": "number",
                        "description": "Sampling temperature between 0 and 1"
                    },
                    "max_tokens": {
                        "type": "integer",
                        "description": "Maximum number of tokens to generate"
                    }
                },
                "required": ["prompt"]
            },
        ),
        types.Tool(
            name="chat",
            description="Chat with Ollama model",
            inputSchema={
                "type": "object",
                "properties": {
                    "messages": {
                        "type": "array",
                        "description": "Array of message objects with role and content",
                        "items": {
                            "type": "object",
                            "properties": {
                                "role": {
                                    "type": "string",
                                    "description": "Role of the message sender (system, user, assistant)"
                                },
                                "content": {
                                    "type": "string",
                                    "description": "Content of the message"
                                }
                            },
                            "required": ["role", "content"]
                        }
                    },
                    "model": {
                        "type": "string",
                        "description": "Optional model name to use"
                    },
                    "temperature": {
                        "type": "number",
                        "description": "Sampling temperature between 0 and 1"
                    },
                    "max_tokens": {
                        "type": "integer",
                        "description": "Maximum number of tokens to generate"
                    }
                },
                "required": ["messages"]
            },
        ),
        types.Tool(
            name="list_models",
            description="List all available models from Ollama",
            inputSchema={
                "type": "object",
                "properties": {}
            },
        )
    ]

@server.call_tool()
async def handle_call_tool(
    name: str, arguments: dict | None
) -> list[types.TextContent | types.ImageContent | types.EmbeddedResource]:
    """
    Handle Ollama tool execution requests.
    """
    if not arguments:
        arguments = {}
        
    if name == "generate":
        # Extract arguments
        prompt = arguments.get("prompt")
        if not prompt:
            return [
                types.TextContent(
                    type="text",
                    text="Error: Missing required argument 'prompt'"
                )
            ]
        
        system_prompt = arguments.get("system_prompt")
        model = arguments.get("model")
        
        # Build options
        options = {}
        if "temperature" in arguments:
            options["temperature"] = float(arguments["temperature"])
        if "max_tokens" in arguments:
            options["num_predict"] = int(arguments["max_tokens"])
        
        try:
            # Call Ollama API
            response = await generate_text(
                prompt=prompt,
                model=model,
                system_prompt=system_prompt,
                **options
            )
            
            logger.debug(f"Ollama API response: {response}")    
            generated_text = response.get("response", "")
            model_used = response.get("model", "")
            
            return [
                types.TextContent(
                    type="text",
                    text=f"Generated with model: {model_used}\n\n{generated_text}"
                )
            ]
        except Exception as e:
            return [
                types.TextContent(
                    type="text",
                    text=f"Error generating text: {str(e)}"
                )
            ]
    
    elif name == "chat":
        # Extract arguments
        messages = arguments.get("messages", [])
        if not messages:
            return [
                types.TextContent(
                    type="text",
                    text="Error: Missing required argument 'messages'"
                )
            ]
        
        model = arguments.get("model")
        
        # Build options
        options = {}
        if "temperature" in arguments:
            options["temperature"] = float(arguments["temperature"])
        if "max_tokens" in arguments:
            options["num_predict"] = int(arguments["max_tokens"])
        
        try:
            # Call Ollama API
            response = await chat_completion(
                messages=messages,
                model=model,
                **options
            )
            
            assistant_message = response.get("message", {})
            assistant_content = assistant_message.get("content", "")
            model_used = response.get("model", "")
            
            return [
                types.TextContent(
                    type="text",
                    text=f"Response from model: {model_used}\n\n{assistant_content}"
                )
            ]
        except Exception as e:
            return [
                types.TextContent(
                    type="text",
                    text=f"Error in chat completion: {str(e)}"
                )
            ]
    
    elif name == "list_models":
        try:
            models = await list_models()
            
            # Format model information
            model_info = []
            for model in models:
                model_name = model.get("name", "Unknown")
                model_size = model.get("size", 0)
                model_size_formatted = f"{model_size / 1_000_000_000:.2f} GB" if model_size else "Unknown size"
                model_modified = model.get("modified_at", "Unknown date")
                
                model_info.append(f"- {model_name} ({model_size_formatted}), modified: {model_modified}")
            
            return [
                types.TextContent(
                    type="text",
                    text=f"Available models:\n\n" + "\n".join(model_info)
                )
            ]
        except Exception as e:
            return [
                types.TextContent(
                    type="text",
                    text=f"Error listing models: {str(e)}"
                )
            ]
    
    return [
        types.TextContent(
            type="text",
            text=f"Unknown tool: {name}"
        )
    ]

async def main():
    """Main entry point to run the server"""
    # Run the server using stdin/stdout streams
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="ollama-mcp-server",
                server_version="0.1.0",
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )

if __name__ == "__main__":
    asyncio.run(main())