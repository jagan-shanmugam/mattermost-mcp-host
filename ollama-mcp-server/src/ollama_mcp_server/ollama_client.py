import httpx
import logging
import json
from typing import Dict, List, Optional, Any, AsyncGenerator
from config import settings

logger = logging.getLogger(__name__)


class OllamaClient:
    """Client for interacting with Ollama API"""
    
    def __init__(self, base_url: str = None, model_name: str = None):
        self.base_url = base_url or settings.ollama_base_url
        self.model_name = model_name or settings.model_name
        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=httpx.Timeout(60.0)
        )
        
    async def __aenter__(self):
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.client.aclose()
    
    async def list_models(self) -> List[Dict[str, Any]]:
        """List all available models from Ollama"""
        try:
            response = await self.client.get("/api/tags")
            return response.json().get("models", [])
        except Exception as e:
            logger.error(f"Error listing models: {e}")
            raise
    
    async def generate(self, 
                       prompt: str, 
                       system_prompt: Optional[str] = None,
                       model: Optional[str] = None,
                       stream: bool = False,
                       **kwargs) -> Union[Dict[str, Any], AsyncGenerator[Dict[str, Any], None]]:
        """Generate completions from Ollama"""
        try:
            model = model or self.model_name
            
            request_data = {
                "model": model,
                "prompt": prompt,
                "stream": stream,
                "options": kwargs
            }
            
            if system_prompt:
                request_data["system"] = system_prompt
                
            if stream:
                return self._stream_generate(request_data)
            else:
                response = await self.client.post("/api/generate", json=request_data)
                return response.json()
        except Exception as e:
            logger.error(f"Error generating with Ollama: {e}")
            raise
    
    async def _stream_generate(self, request_data: Dict[str, Any]) -> AsyncGenerator[Dict[str, Any], None]:
        """Stream completions from Ollama"""
        try:
            async with self.client.stream("POST", "/api/generate", json=request_data) as response:
                async for line in response.aiter_lines():
                    if not line:
                        continue
                    
                    try:
                        data = json.loads(line)
                        yield data
                        
                        if data.get("done", False):
                            break
                    except json.JSONDecodeError:
                        logger.error(f"Error parsing chunk: {line}")
                        continue
        except Exception as e:
            logger.error(f"Error streaming from Ollama: {e}")
            raise
            
    async def chat(self, 
                  messages: List[Dict[str, str]], 
                  model: Optional[str] = None,
                  stream: bool = False,
                  **kwargs) -> Union[Dict[str, Any], AsyncGenerator[Dict[str, Any], None]]:
        """Chat with Ollama using the chat endpoint"""
        try:
            model = model or self.model_name
            
            request_data = {
                "model": model,
                "messages": messages,
                "stream": stream,
                "options": kwargs
            }
                
            if stream:
                return self._stream_chat(request_data)
            else:
                response = await self.client.post("/api/chat", json=request_data)
                return response.json()
        except Exception as e:
            logger.error(f"Error chatting with Ollama: {e}")
            raise
    
    async def _stream_chat(self, request_data: Dict[str, Any]) -> AsyncGenerator[Dict[str, Any], None]:
        """Stream chat completions from Ollama"""
        try:
            async with self.client.stream("POST", "/api/chat", json=request_data) as response:
                async for line in response.aiter_lines():
                    if not line:
                        continue
                    
                    try:
                        data = json.loads(line)
                        yield data
                        
                        if data.get("done", False):
                            break
                    except json.JSONDecodeError:
                        logger.error(f"Error parsing chunk: {line}")
                        continue
        except Exception as e:
            logger.error(f"Error streaming chat from Ollama: {e}")
            raise