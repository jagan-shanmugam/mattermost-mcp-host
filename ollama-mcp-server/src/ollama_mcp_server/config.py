from pydantic_settings import BaseSettings
from typing import Dict, Any


class Settings(BaseSettings):
    # Ollama Configuration
    ollama_base_url: str = "http://localhost:11434"
    model_name: str = "llama3.2:latest"
    
    # Server Configuration
    host: str = "127.0.0.1"
    port: int = 8000
    
    # MCP Server Information
    mcp_server_name: str = "ollama-mcp-server"
    mcp_server_version: str = "0.1.0"
    
    class Config:
        env_file = ".env"


settings = Settings()