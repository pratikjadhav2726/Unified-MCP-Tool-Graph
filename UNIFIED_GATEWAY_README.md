# MCP Unified Gateway System

A comprehensive, production-ready Model Context Protocol (MCP) gateway that provides unified access to multiple MCP servers with intelligent tool routing, dynamic server management, and automatic fallback capabilities.

## 🌟 Features

### Core Capabilities
- **Unified Gateway**: Single endpoint for accessing multiple MCP servers
- **Dynamic Tool Retrieval**: Intelligent tool discovery using semantic similarity (with Neo4j)
- **Automatic Fallback**: Falls back to "everything" server when Neo4j is unavailable
- **Server Management**: Dynamic addition/removal of MCP servers
- **Tool Routing**: Intelligent routing of tool calls to appropriate servers
- **Connection Management**: Robust connection handling with retry logic

### Smart Fallback System
- **Neo4j Available**: Full dynamic tool retrieval with semantic search
- **Neo4j Unavailable**: Automatic fallback to popular MCP servers including "everything" server
- **Zero Configuration**: Works out of the box without any database setup

## 🚀 Quick Start

### 1. Installation

```bash
# Clone the repository
git clone <repository-url>
cd <project-directory>

# Install Python dependencies
pip install -r requirements.txt

# Install Node.js dependencies (for MCP servers)
npm install -g @modelcontextprotocol/server-everything
npm install -g @modelcontextprotocol/server-sequential-thinking

# Install uv for additional servers (optional)
pip install uv
```

### 2. Environment Setup (Optional)

```bash
# Copy environment template
cp .env.example .env

# Edit .env with your configuration (all settings are optional)
nano .env
```

### 3. Start the System

```bash
# Simple startup (recommended)
./start_gateway.sh

# Or directly with Python
python3 start_unified_gateway.py
```

The system will:
1. ✅ Check all dependencies
2. ✅ Validate environment configuration  
3. ✅ Start MCP server manager
4. ✅ Initialize dynamic tool retriever (or fallback)
5. ✅ Start unified gateway on port 8000

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    MCP Unified Gateway                      │
│                    (Port 8000)                             │
└─────────────────────┬───────────────────────────────────────┘
                      │
┌─────────────────────┴───────────────────────────────────────┐
│                 MCP Proxy Server                            │
│                 (Port 9000)                                │
└─┬─────────────┬─────────────┬─────────────┬─────────────────┘
  │             │             │             │
┌─▼──────────┐ ┌▼─────────────▼┐ ┌─▼─────────▼┐ ┌─▼─────────────┐
│ Dynamic    │ │ Everything   │ │Sequential  │ │ Time Server   │
│ Tool       │ │ Server       │ │ Thinking   │ │               │
│ Retriever  │ │              │ │ Server     │ │               │
└────────────┘ └──────────────┘ └────────────┘ └───────────────┘
      │
┌─────▼─────┐
│   Neo4j   │ (Optional)
│ Database  │
└───────────┘
```

## 🔧 Configuration

### Environment Variables (.env)

```bash
# Neo4j Configuration (Optional)
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=your_password

# Gateway Configuration
GATEWAY_PORT=8000
PROXY_PORT=9000
LOG_LEVEL=INFO

# API Keys (Optional - for specific servers)
TAVILY_API_KEY=your_tavily_key
OPENAI_API_KEY=your_openai_key
GROQ_API_KEY=your_groq_key
```

### Server Configuration

The system automatically configures servers based on available components:

#### With Neo4j (Full Mode)
- Dynamic Tool Retriever (semantic search)
- Sequential Thinking Server
- Time Server

#### Without Neo4j (Fallback Mode)  
- Everything Server (comprehensive toolset)
- Sequential Thinking Server
- Time Server

## 📡 API Endpoints

### Gateway Server (Port 8000)

#### Tool Management
- `POST /tools/list` - List all available tools
- `POST /tools/call` - Call a specific tool
- `POST /tools/get_server_status` - Get server status
- `POST /tools/test_server_connection` - Test server connection
- `POST /tools/get_system_info` - Get system information

#### Example Tool Call
```bash
curl -X POST http://localhost:8000/tools/call \
  -H "Content-Type: application/json" \
  -d '{
    "tool_name": "everything.web_search",
    "args": {"query": "latest AI news"}
  }'
```

### Proxy Server (Port 9000)

#### Server-Sent Events Endpoints
- `GET /servers/dynamic-tool-retriever/sse` - Dynamic tool retriever
- `GET /servers/everything/sse` - Everything server  
- `GET /servers/sequential-thinking/sse` - Sequential thinking
- `GET /servers/time/sse` - Time server

## 🛠️ Available Tools

### Dynamic Tool Retriever (Neo4j Mode)
- `dynamic_tool_retriever` - Intelligent tool discovery using semantic similarity

### Everything Server (Fallback Mode)
- `web_search` - Search the web for information
- `read_file` - Read file contents
- `write_file` - Write content to files
- `list_directory` - List directory contents
- `run_command` - Execute system commands
- And many more...

### Sequential Thinking Server
- `sequential_thinking` - Step-by-step reasoning and problem solving

### Time Server
- `get_current_time` - Get current date and time
- `get_timezone` - Get timezone information

## 🔍 System Modes

### Full Mode (Neo4j Available)
```
✅ Neo4j database connected
✅ Dynamic tool retriever enabled
✅ Semantic search capabilities
✅ Intelligent tool ranking
```

### Fallback Mode (Neo4j Unavailable)
```
⚠️  Neo4j not available
✅ Everything server enabled
✅ Comprehensive tool coverage
✅ No database dependency
```

## 🧪 Testing the System

### 1. Check System Status
```bash
curl -X POST http://localhost:8000/tools/get_system_info
```

### 2. List Available Tools
```bash
curl -X POST http://localhost:8000/tools/list
```

### 3. Test Tool Call
```bash
curl -X POST http://localhost:8000/tools/call \
  -H "Content-Type: application/json" \
  -d '{
    "tool_name": "time.get_current_time",
    "args": {}
  }'
```

### 4. Test Server Connection
```bash
curl -X POST http://localhost:8000/tools/test_server_connection \
  -H "Content-Type: application/json" \
  -d '{"server_name": "time"}'
```

## 🚨 Troubleshooting

### Common Issues

#### 1. "npx not found"
```bash
# Install Node.js and npm
curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
sudo apt-get install -y nodejs
```

#### 2. "mcp-proxy not found"
```bash
# Install mcp-proxy
pip install mcp-proxy
```

#### 3. "Neo4j connection failed"
The system automatically falls back to the everything server. This is normal if you don't have Neo4j set up.

#### 4. "Port already in use"
```bash
# Change ports in .env file
GATEWAY_PORT=8001
PROXY_PORT=9001
```

### Logs and Debugging

#### Enable Debug Logging
```bash
# In .env file
LOG_LEVEL=DEBUG
```

#### Check Server Status
```bash
curl -X POST http://localhost:8000/tools/get_server_status
```

## 🔌 Integration Examples

### Python Client
```python
import httpx
import asyncio

async def call_tool(tool_name: str, args: dict):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8000/tools/call",
            json={"tool_name": tool_name, "args": args}
        )
        return response.json()

# Example usage
result = asyncio.run(call_tool("time.get_current_time", {}))
print(result)
```

### JavaScript Client
```javascript
async function callTool(toolName, args) {
    const response = await fetch('http://localhost:8000/tools/call', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ tool_name: toolName, args })
    });
    return response.json();
}

// Example usage
callTool('everything.web_search', { query: 'AI news' })
    .then(result => console.log(result));
```

## 📈 Performance and Scaling

### System Requirements
- **Minimum**: 2GB RAM, 2 CPU cores
- **Recommended**: 4GB RAM, 4 CPU cores
- **With Neo4j**: +2GB RAM for database

### Performance Tips
1. Use SSD storage for better I/O performance
2. Increase `sse_read_timeout` for long-running tools
3. Monitor memory usage with multiple concurrent requests
4. Use load balancer for multiple gateway instances

## 🛡️ Security Considerations

### Network Security
- Gateway runs on localhost by default
- Use reverse proxy (nginx/Apache) for production
- Implement authentication/authorization as needed

### Environment Variables
- Never commit `.env` files to version control
- Use secure methods to manage API keys
- Rotate API keys regularly

## 🤝 Contributing

### Development Setup
```bash
# Install development dependencies
pip install -r requirements.txt
pip install pytest pytest-asyncio

# Run tests
python -m pytest

# Format code
black .
isort .
```

### Adding New Servers
1. Add server configuration to `start_mcp_servers()` in `unified_gateway.py`
2. Update client configuration in `mcp_client_config.json`
3. Test integration with the gateway

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🙏 Acknowledgments

- [Model Context Protocol](https://modelcontextprotocol.io/) team
- [FastMCP](https://github.com/jlowin/fastmcp) for the server framework
- [Neo4j](https://neo4j.com/) for graph database capabilities
- All MCP server contributors

---

## 📞 Support

For issues, feature requests, or questions:
1. Check the troubleshooting section above
2. Review system logs for error messages
3. Open an issue on the project repository

**Happy coding with MCP! 🚀**