# 🚀 Getting Started with MCP Unified Gateway

This guide will get you up and running with the MCP Unified Gateway in just a few minutes!

## ⚡ Quick Setup (5 minutes)

### 1. Prerequisites Check
Make sure you have:
- ✅ Python 3.8+ installed
- ✅ Node.js 16+ installed  
- ✅ [uv](https://docs.astral.sh/uv/) installed (recommended)
- ✅ Internet connection (for downloading MCP servers)

### 2. Install Dependencies

#### Option A: Using uv (Recommended)
```bash
# Install uv if not already installed
curl -LsSf https://astral.sh/uv/install.sh | sh

# Initialize project and install dependencies
uv init --no-readme
uv add python-dotenv aiohttp requests neo4j sentence-transformers langchain-mcp-adapters pydantic a2a-sdk langchain-groq langgraph langchain langchain-community mcp fastapi uvicorn httpx pytest pytest-asyncio mcp-proxy

# Install essential MCP servers
npm install -g @modelcontextprotocol/server-everything
npm install -g @modelcontextprotocol/server-sequential-thinking
```

#### Option B: Using pip (Alternative)
```bash
# Install Python packages
pip install -r requirements.txt

# Install essential MCP servers
npm install -g @modelcontextprotocol/server-everything
npm install -g @modelcontextprotocol/server-sequential-thinking
```

### 3. Start the Gateway

#### With uv (Recommended)
```bash
uv run python start_unified_gateway.py
```

#### With pip
```bash
# Make startup script executable (Linux/Mac)
chmod +x start_gateway.sh

# Start the system
./start_gateway.sh
```

**That's it!** 🎉 The gateway will start on `http://localhost:8000`

## 🧪 Test Your Setup

### Quick Test
```bash
# Check if the gateway is running
curl -X POST http://localhost:8000/tools/get_system_info
```

You should see output like:
```json
{
  "neo4j_available": false,
  "total_servers": 3,
  "total_tools": 25,
  "servers": ["everything", "sequential-thinking", "time"],
  "fallback_mode": true
}
```

### Try a Tool
```bash
# Get current time
curl -X POST http://localhost:8000/tools/call \
  -H "Content-Type: application/json" \
  -d '{"tool_name": "time.get_current_time", "args": {}}'
```

### Search the Web
```bash
# Search for AI news
curl -X POST http://localhost:8000/tools/call \
  -H "Content-Type: application/json" \
  -d '{"tool_name": "everything.web_search", "args": {"query": "latest AI news"}}'
```

## 🔧 Optional: Enable Neo4j (Advanced)

If you want the full dynamic tool retrieval capabilities:

### 1. Install Neo4j
```bash
# Using Docker (easiest)
docker run -d \
  --name neo4j \
  -p 7474:7474 -p 7687:7687 \
  -e NEO4J_AUTH=neo4j/your_password \
  neo4j:latest
```

### 2. Configure Environment
```bash
# Copy environment template
cp .env.example .env

# Edit .env file
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=your_password
```

### 3. Restart Gateway
```bash
./start_gateway.sh
```

Now you'll have full dynamic tool retrieval! 🚀

## 🎯 What's Next?

1. **Read the Full Documentation**: Check out `UNIFIED_GATEWAY_README.md` for complete details
2. **Integrate with Your App**: Use the API endpoints to integrate with your application
3. **Add More Servers**: Explore additional MCP servers for specific capabilities
4. **Customize Configuration**: Adjust settings in `.env` for your needs

## 🆘 Need Help?

### Common Issues
- **"npx not found"**: Install Node.js from [nodejs.org](https://nodejs.org)
- **"Port already in use"**: Change ports in `.env` file
- **Tools not working**: Check server status with `/tools/get_server_status`

### Support
- Check the troubleshooting section in `UNIFIED_GATEWAY_README.md`
- Review system logs for error messages
- Open an issue if you need help

**Happy building! 🎉**