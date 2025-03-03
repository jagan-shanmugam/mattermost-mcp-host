# Ollama MCP Server

A MCP server implementation that integrates with Ollama to provide AI model capabilities through the MCP protocol.

## Features

- Seamless integration with Ollama's AI models
- Support for multiple model types and configurations
- Real-time inference and response generation
- Configurable model parameters and settings

## Prerequisites

- Python 3.13.1+
- Ollama installed and running locally
- Required Python packages (see requirements.txt)

## Installation

1. **Clone the repository**

```bash
git clone <repository-url>
cd ollama-mcp-server
```

2. **Create and activate a virtual environment**

```bash
uv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. **Install dependencies**

```bash
pip install -r requirements.txt
```

## Configuration

1. **Copy the example environment file**

```bash
cp .env.example .env
```

2. **Configure your environment variables**

Copy `.env.example` to `.env` and edit

## Usage

### Starting the Server

```bash
python src/ollama_mcp_server/main.py
```

### Available Tools

1. **generate**: Generate text using the configured model
   ```json
   {
     "prompt": "Write a short story about a robot",
     "model": "llama3.2:latest",  // optional
     "max_tokens": 500   // optional
   }
   ```

2. **chat**: Have a conversation with the model
   ```json
   {
     "messages": [
       {"role": "user", "content": "Hello, how are you?"}
     ],
     "model": "llama2"  // optional
   }
   ```
3. **list-models**: List available models
   ```json
   {}
   ```

## Troubleshooting

1. **Connection Issues**
   - Ensure Ollama is running (`ollama serve`)
   - Verify OLLAMA_HOST in .env is correct
   - Check network connectivity

2. **Model Issues**
   - Ensure the requested model is pulled (`ollama pull modelname`)
   - Check model compatibility
   - Verify memory requirements

3. **Performance Issues**
   - Monitor system resources
   - Adjust batch sizes and concurrent requests
   - Consider GPU availability
