# 🚀 Getting Started with Unified MCP Tool Graph

This guide will help you set up and run the Unified MCP Tool Graph system in minutes using `uv`, the modern Python package manager.

## 📋 Prerequisites

Before you begin, ensure you have:

- **Python 3.12+** installed
- **uv** installed ([Installation Guide](https://docs.astral.sh/uv/getting-started/installation/))
- **Node.js 16+** (optional, for Node.js-based MCP servers)
- **Internet connection** (for downloading dependencies and MCP servers)

### Installing uv

**Windows (PowerShell):**
```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

**macOS/Linux:**
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**Or using pip:**
```bash
pip install uv
```

Verify installation:
```bash
uv --version
```

## ⚡ Quick Start (5 minutes)

### 1. Clone the Repository

```bash
git clone https://github.com/your-username/unified-mcp-tool-graph.git
cd unified-mcp-tool-graph
```

### 2. Install Dependencies with uv

The project uses `uv` for dependency management. All dependencies are defined in `pyproject.toml`.

```bash
# Install all project dependencies
uv sync
```

This will:
- Create a virtual environment automatically
- Install all Python dependencies from `pyproject.toml`
- Install development dependencies if needed

### 3. Install MCP Proxy (Required)

The system uses `mcp-proxy` to expose MCP servers as HTTP endpoints:

```bash
# Using uv
uv pip install mcp-proxy

# Or using pip
pip install mcp-proxy
```

### 4. Start the Unified Gateway

```bash
# Using uv (recommended)
uv run python start_unified_gateway.py
```

The gateway will:
- ✅ Check all dependencies
- ✅ Validate environment configuration
- ✅ Start MCP Server Manager (port 9000)
- ✅ Start Unified Gateway (port 8000)

You should see output like:
```
🚀 MCP Unified Gateway System Startup
============================================================
📦 Checking Python dependencies...
✓ All dependencies available
📦 Checking Node.js dependencies...
✓ npx is available (or warnings if not installed)
📦 Checking mcp-proxy...
✓ mcp-proxy is available
🔧 Validating environment configuration...
✅ All checks passed! Starting gateway system...
```

## 🧪 Verify Installation

### Test the Gateway

Open a new terminal and test the gateway:

```bash
# Check system info
curl -X POST http://localhost:8000/tools/get_system_info
```

Expected response:
```json
{
  "neo4j_available": false,
  "total_servers": 3,
  "total_tools": 25,
  "servers": ["everything", "sequential-thinking", "time"],
  "fallback_mode": true
}
```

### Test a Tool Call

```bash
# Get current time
curl -X POST http://localhost:8000/tools/call \
  -H "Content-Type: application/json" \
  -d '{"tool_name": "time.get_current_time", "args": {}}'
```

### List All Available Tools

```bash
# List all tools from all servers
curl -X POST http://localhost:8000/tools/list
```

## 🔧 Configuration

### Environment Variables (Optional)

Create a `.env` file in the project root for optional configuration:

```bash
# Neo4j Configuration (Optional - for dynamic tool retrieval)
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=your_password

# Gateway Configuration (Optional)
GATEWAY_PORT=8000
PROXY_PORT=9000
LOG_LEVEL=INFO
```

**Note:** The gateway works without Neo4j! It will automatically fall back to popular MCP servers.

### Optional: Enable Neo4j for Dynamic Tool Retrieval

If you want the full dynamic tool retrieval capabilities:

1. **Install Neo4j** (using Docker):
```bash
docker run -d \
  --name neo4j \
  -p 7474:7474 -p 7687:7687 \
  -e NEO4J_AUTH=neo4j/your_password \
  neo4j:latest
```

2. **Configure `.env`** with Neo4j credentials (see above)

3. **Restart the gateway** - it will automatically detect Neo4j and enable dynamic tool retrieval

## 🏗️ Project Structure

```
unified-mcp-tool-graph/
├── gateway/                 # Unified gateway implementation
├── MCP_Server_Manager/      # MCP server management
├── Dynamic_tool_retriever_MCP/  # Dynamic tool retrieval
├── Example_Agents/          # Example agent implementations
├── Ingestion_pipeline/      # Tool ingestion scripts
├── Utils/                   # Utility functions
├── pyproject.toml          # Project dependencies (uv)
├── uv.lock                 # Locked dependencies
└── start_unified_gateway.py # Main startup script
```

## 🎯 Common Workflows

### Running with uv

```bash
# Run any Python script
uv run python script.py

# Run with specific Python version
uv run --python 3.12 python script.py

# Install additional dependencies
uv add package-name

# Update dependencies
uv sync --upgrade
```

### Connecting to the Unified Gateway

The gateway exposes all tools from all MCP servers through a single endpoint:

**Endpoint:** `http://localhost:8000`

**Example Python client:**
```python
import asyncio
from mcp.client.sse import sse_client
from mcp.client.session import ClientSession

async def main():
    url = "http://localhost:8000"
    
    async with sse_client(url=url, timeout=15.0) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            
            # List all tools
            tools = await session.list_tools()
            print(f"Available tools: {len(tools.tools)}")
            
            # Call a tool
            result = await session.call_tool("time.get_current_time", {})
            print(result)

asyncio.run(main())
```

## 🆘 Troubleshooting

### Issue: "uv: command not found"

**Solution:** Install uv using the instructions above, or add it to your PATH.

### Issue: "npx not found" warning

**Solution:** This is optional! The gateway works without Node.js. If you need Node.js-based MCP servers:
- Install Node.js from [nodejs.org](https://nodejs.org/)
- The warning will disappear after installation

### Issue: "Port already in use"

**Solution:** Change the ports in your `.env` file:
```bash
GATEWAY_PORT=8001
PROXY_PORT=9001
```

### Issue: "mcp-proxy not found"

**Solution:** Install mcp-proxy:
```bash
uv pip install mcp-proxy
# or
pip install mcp-proxy
```

### Issue: PyTorch/DLL errors on Windows

**Solution:** The system automatically skips optional dependencies that require Visual C++ Redistributable. The gateway will work in fallback mode without these dependencies.

### Issue: Tools not appearing

**Solution:** 
1. Check server status: `curl -X POST http://localhost:8000/tools/get_server_status`
2. Wait a few seconds after startup for servers to initialize
3. Check logs for connection errors

## 📚 Next Steps

1. **Explore Example Agents**: Check out `Example_Agents/` for LangGraph and A2A implementations
2. **Add Custom MCP Servers**: Use the MCP Server Manager to add your own servers
3. **Integrate with Your App**: Use the unified gateway API to integrate with your application
4. **Enable Neo4j**: Set up Neo4j for full dynamic tool retrieval capabilities

## 🔗 Additional Resources

- **uv Documentation**: https://docs.astral.sh/uv/
- **MCP Protocol**: https://modelcontextprotocol.io/
- **Project README**: See `README.md` for project overview
- **Example Agents**: See `Example_Agents/` for integration examples

## 💡 Tips

- Use `uv run` for all Python commands to ensure you're using the correct environment
- The gateway automatically manages MCP server lifecycle (starts/stops as needed)
- All tools are namespaced: `{server_name}.{tool_name}` (e.g., `time.get_current_time`)
- The gateway works without Neo4j - it falls back to popular servers automatically

---

**Happy building! 🎉**

For issues or questions, please open an issue on GitHub.
