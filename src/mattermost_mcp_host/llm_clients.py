import os
import json
import logging
import asyncio
import traceback
from typing import List, Dict, Any, Optional, Union
from openai import OpenAI, AzureOpenAI
from openai.types.chat import ChatCompletionMessageParam, ChatCompletionToolParam

# Handle optional dependencies
try:
    from anthropic import Anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False

try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False

import mattermost_mcp_host.config as config

logger = logging.getLogger(__name__)

class LLMClient:
    def __init__(self, provider: str, model: str, system_prompt: Optional[str] = None):
        """
        Initialize LLM client for different providers
        
        Args:
            provider: The LLM provider (openai, azure, anthropic, gemini)
            model: The model to use
            system_prompt: Optional system prompt to use for the model
        """
        self.provider = provider
        self.model = model
        
        # Set the system prompt or use default
        self.system_prompt = system_prompt or config.DEFAULT_SYSTEM_PROMPT
        
        if self.provider == 'openai':
            self.client = OpenAI(
                api_key=os.environ.get('OPENAI_API_KEY'),
                base_url=os.environ.get('OPENAI_BASE_URL'),
                api_version=os.environ.get('OPENAI_API_VERSION'),
                organization=os.environ.get('OPENAI_ORGANIZATION'),
                project=os.environ.get('OPENAI_PROJECT'),
            )
        elif self.provider == 'azure':
            self.client = AzureOpenAI(
                api_key=os.environ.get('AZURE_OPENAI_API_KEY'),
                api_version=os.environ.get('AZURE_OPENAI_API_VERSION', '2024-02-15-preview'),
                azure_endpoint=os.environ.get('AZURE_OPENAI_ENDPOINT'),
                azure_deployment=os.environ.get('AZURE_OPENAI_DEPLOYMENT')
            )
            # For Azure, the model is specified in the deployment
            self.model = os.environ.get('AZURE_OPENAI_DEPLOYMENT')
        elif self.provider == 'anthropic':
            if not ANTHROPIC_AVAILABLE:
                raise ImportError(
                    "Anthropic package is not installed. Please install it with: "
                    "pip install mattermost-mcp-host[anthropic] or "
                    "pip install anthropic"
                )
            self.api_key = os.environ.get("ANTHROPIC_API_KEY")
            self.model = model or os.environ.get("ANTHROPIC_MODEL", "claude-3-opus-20240229")
            
            self.client = Anthropic(
                api_key=self.api_key,
            )
        elif self.provider == 'gemini':
            if not GEMINI_AVAILABLE:
                raise ImportError(
                    "Google Generative AI package is not installed. Please install it with: "
                    "pip install mattermost-mcp-host[gemini] or "
                    "pip install google-generativeai"
                )
            self.api_key = os.environ.get("GOOGLE_API_KEY")
            self.model = model or os.environ.get("GEMINI_MODEL", "gemini-1.5-pro")
            
            # Configure the Gemini API
            genai.configure(api_key=self.api_key)
        else:
            raise ValueError(f"Invalid provider: {self.provider}")
        
        logger.info(f"Initialized LLM client with provider: {provider}, model: {model}")
        logger.debug(f"Using system prompt: {self.system_prompt[:50]}...")

    async def generate_response(self, 
                               prompt: str, 
                               img_url: Optional[str] = None, 
                               img_type: Optional[str] = None, 
                               img_b64_str: Optional[str] = None, 
                               tools: Optional[List[ChatCompletionToolParam]] = None,
                               messages: Optional[List[Dict[str, Any]]] = None,
                               system_prompt: Optional[str] = None) -> Any:
        """
        Generate a response from the LLM
        
        Args:
            prompt: The text prompt
            img_url: Optional URL to an image
            img_type: Optional MIME type of an image
            img_b64_str: Optional base64-encoded image
            tools: Optional list of tools to use
            messages: Optional list of messages for chat history
            system_prompt: Optional system prompt that overrides the default one
        
        Returns:
            The response from the LLM
        """
        try:
            # Use provided system prompt or fall back to the default
            effective_system_prompt = system_prompt or self.system_prompt
            
            # Prepare the content list
            content = [{"type": "text", "text": prompt}]
            
            # Add image if provided
            if img_url:
                content.append({
                    "type": "image_url",
                    "image_url": {"url": img_url}
                })
            elif img_b64_str and img_type:
                content.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:{img_type};base64,{img_b64_str}"}
                })
            
            # Create system message
            system_message = {"role": "system", "content": effective_system_prompt}
            
            # Use provided messages or create a new list with system message
            if messages:
                # Check if the first message is already a system message
                if not messages or messages[0].get("role") != "system":
                    messages.insert(0, system_message)
                elif messages[0].get("role") == "system" and system_prompt:
                    # Replace existing system message if a new one is provided
                    messages[0]["content"] = effective_system_prompt
                
                # Add the current prompt as the latest user message
                messages.append({
                    "role": "user",
                    "content": content
                })
                chat_messages = messages
            else:
                chat_messages = [
                    system_message,
                    {"role": "user", "content": content}
                ]
            
            # Prepare the API call parameters
            params = {
                "model": self.model,
                "messages": chat_messages,
            }
            
            # Add tools if provided
            if tools:
                params["tools"] = tools
                params["tool_choice"] = "auto"
            
            logger.debug(f"Calling LLM with parameters: {json.dumps(params, default=str)}")
            
            if self.provider == 'openai' or self.provider == 'azure':
                # Make the API call for OpenAI/Azure
                response = self.client.chat.completions.create(**params)
                logger.debug(f"LLM response: {response}")
                return response
            elif self.provider == 'anthropic':
                # Convert parameters to Anthropic format
                # Anthropic has a different format for system prompt
                if chat_messages[0]["role"] == "system":
                    system = chat_messages[0]["content"]
                    chat_messages = chat_messages[1:]  # Remove system message from messages list
                else:
                    system = effective_system_prompt
                
                response = self.client.messages.create(
                    model=self.model,
                    system=system,
                    messages=chat_messages,
                    # Other parameters as needed
                )
                return response
            elif self.provider == 'gemini':
                # Gemini implementation with system prompt
                model = genai.GenerativeModel(self.model)
                
                # Gemini has a different format, we need to convert the messages
                generation_config = {
                    "system_instruction": effective_system_prompt,
                }
                
                response = model.generate_content(
                    contents=[msg for msg in chat_messages if msg["role"] != "system"],
                    generation_config=generation_config
                )
                return response
            
        except Exception as e:
            logger.error(f"Error generating LLM response: {str(e)}")
            logger.error(traceback.format_exc())
            raise
            
    def convert_mcp_tools_to_openai_tools(self, mcp_tools: Dict[str, Any]) -> List[ChatCompletionToolParam]:
        """
        Convert MCP tools to OpenAI tool format
        
        Args:
            mcp_tools: Dictionary of MCP tools
            
        Returns:
            List of OpenAI tools
        """
        openai_tools = []
        
        for name, tool in mcp_tools.items():
            try:
                # Extract tool schema from MCP tool
                if hasattr(tool, 'inputSchema') and tool.inputSchema:
                    # Build OpenAI tool format
                    openai_tool = {
                        "type": "function",
                        "function": {
                            "name": name,
                            "description": tool.description,
                            "parameters": tool.inputSchema
                        }
                    }
                    openai_tools.append(openai_tool)
                else:
                    # Simple tool with no parameters
                    openai_tool = {
                        "type": "function",
                        "function": {
                            "name": name,
                            "description": tool.description,
                            "parameters": {
                                "type": "object",
                                "properties": {},
                                "required": []
                            }
                        }
                    }
                    openai_tools.append(openai_tool)
            except Exception as e:
                logger.error(f"Error converting MCP tool {name} to OpenAI format: {str(e)}")
                
        return openai_tools