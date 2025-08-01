# 🚀 MCP Unified Gateway System

A comprehensive, production-ready **Model Context Protocol (MCP) Gateway** that provides unified access to multiple MCP servers with intelligent tool routing, dynamic server management, and automatic fallback capabilities.

## ✨ Key Features

- 🔄 **Unified Gateway**: Single endpoint for accessing multiple MCP servers
- 🧠 **Dynamic Tool Retrieval**: Intelligent tool discovery using semantic similarity (with Neo4j)
- 🛡️ **Automatic Fallback**: Falls back to "everything" server when Neo4j is unavailable
- ⚡ **Zero Configuration**: Works out of the box without any database setup
- 🔧 **Server Management**: Dynamic addition/removal of MCP servers
- 🎯 **Smart Routing**: Intelligent routing of tool calls to appropriate servers
- 📊 **Connection Management**: Robust connection handling with retry logic

## 🚀 Quick Start

### 1. Install Dependencies
```bash
# Install Python dependencies
pip install --break-system-packages -r requirements.txt

# Install essential MCP servers
npm install -g @modelcontextprotocol/server-everything
npm install -g @modelcontextprotocol/server-sequential-thinking
```

### 2. Start the System
```bash
# Make startup script executable
chmod +x start_gateway.sh

# Start the unified gateway
./start_gateway.sh
```

**That's it!** 🎉 The gateway starts on `http://localhost:8000`

### 3. Test Your Setup
```bash
# Check system status
curl -X POST http://localhost:8000/tools/get_system_info

# List available tools
curl -X POST http://localhost:8000/tools/list

# Call a tool
curl -X POST http://localhost:8000/tools/call \
  -H "Content-Type: application/json" \
  -d '{"tool_name": "time.get_current_time", "args": {}}'
```

## 🏗️ System Architecture

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

## 🔧 Configuration Modes

### 🌟 Full Mode (Neo4j Available)
- ✅ Neo4j database connected
- ✅ Dynamic tool retriever enabled  
- ✅ Semantic search capabilities
- ✅ Intelligent tool ranking

### 🔄 Fallback Mode (Neo4j Unavailable)
- ⚠️ Neo4j not available
- ✅ Everything server enabled
- ✅ Comprehensive tool coverage
- ✅ No database dependency

## 📁 Project Structure

```
├── gateway/                     # Unified gateway implementation
│   ├── unified_gateway.py      # Main gateway server
│   └── dummy_tool_retriever.py # Fallback tool retriever
├── MCP_Server_Manager/         # Server management system
│   ├── mcp_server_manager.py   # Dynamic server manager
│   └── mcp_client_config.json  # Client configuration
├── Dynamic_tool_retriever_MCP/ # Neo4j-based tool retrieval
│   ├── server.py               # Dynamic tool retriever server
│   ├── neo4j_retriever.py      # Neo4j integration with fallback
│   └── embedder.py             # Text embedding utilities
├── mcp-chat-agent/            # Next.js chat interface (optional)
├── start_unified_gateway.py   # Main startup script
├── start_gateway.sh           # Shell startup wrapper
├── .env.example               # Environment configuration template
├── UNIFIED_GATEWAY_README.md  # Comprehensive documentation
└── GETTING_STARTED.md         # Quick start guide
```

## 📚 Documentation

- **[🚀 Getting Started](GETTING_STARTED.md)** - Quick 5-minute setup guide
- **[📖 Complete Documentation](UNIFIED_GATEWAY_README.md)** - Comprehensive system documentation
- **[⚙️ Environment Setup](.env.example)** - Configuration options

## 🛠️ Available Tools

### Dynamic Mode (with Neo4j)
- `dynamic_tool_retriever` - Intelligent tool discovery using semantic similarity

### Fallback Mode (without Neo4j)
- `web_search` - Search the web for information
- `read_file` - Read file contents
- `write_file` - Write content to files
- `list_directory` - List directory contents
- `run_command` - Execute system commands
- And many more via the everything server...

### Always Available
- `sequential_thinking` - Step-by-step reasoning and problem solving
- `get_current_time` - Get current date and time
- `get_timezone` - Get timezone information

## 🔌 API Endpoints

- `POST /tools/list` - List all available tools
- `POST /tools/call` - Call a specific tool
- `POST /tools/get_server_status` - Get server status
- `POST /tools/test_server_connection` - Test server connection
- `POST /tools/get_system_info` - Get system information

## 🎯 Use Cases

- **AI Agent Development**: Provide tools for AI agents to interact with the world
- **Workflow Automation**: Chain multiple tools together for complex workflows
- **API Gateway**: Unified interface for accessing diverse MCP servers
- **Development Platform**: Build applications that need access to various tools

## 🔧 Optional: Enable Neo4j

For full dynamic tool retrieval capabilities:

```bash
# Using Docker (easiest)
docker run -d \
  --name neo4j \
  -p 7474:7474 -p 7687:7687 \
  -e NEO4J_AUTH=neo4j/your_password \
  neo4j:latest

# Configure environment
cp .env.example .env
# Edit .env with your Neo4j credentials

# Restart gateway
./start_gateway.sh
```

## 🚨 Troubleshooting

### Common Issues
- **"npx not found"**: Install Node.js from [nodejs.org](https://nodejs.org)
- **"mcp-proxy not found"**: Run `pip install --break-system-packages mcp-proxy`
- **"Port already in use"**: Change ports in `.env` file
- **Neo4j connection failed**: System automatically falls back to everything server

### Get Help
- Check [troubleshooting section](UNIFIED_GATEWAY_README.md#-troubleshooting) in full documentation
- Review system logs for error messages
- Open an issue if you need assistance

## 🤝 Contributing

We welcome contributions! Please see our [development setup guide](UNIFIED_GATEWAY_README.md#-contributing) for details on:
- Setting up the development environment
- Running tests
- Adding new servers
- Code formatting guidelines

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- [Model Context Protocol](https://modelcontextprotocol.io/) team for the foundational framework
- [FastMCP](https://github.com/jlowin/fastmcp) for the server implementation
- [Neo4j](https://neo4j.com/) for graph database capabilities
- All MCP server contributors in the community

---

**Ready to build with MCP? Start with our [🚀 Getting Started Guide](GETTING_STARTED.md)!**


