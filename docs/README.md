# Unified MCP Gateway - Production Ready

A robust, production-ready gateway for Model Context Protocol (MCP) servers that provides unified access to multiple MCP tools through a single API endpoint.

## 🚀 Features

- **Unified API**: Single endpoint to access tools from multiple MCP servers
- **Dynamic Tool Discovery**: Automatically discovers and catalogs tools from connected servers
- **Intelligent Tool Retrieval**: Uses Neo4j knowledge graph with fallback to dummy retriever
- **Production Ready**: Authentication, rate limiting, health checks, monitoring
- **Error Handling**: Comprehensive error handling with circuit breakers and recovery
- **Process Management**: Automatic server lifecycle management and orphan cleanup
- **Scalable Architecture**: Supports popular servers (always-on) and dynamic servers (on-demand)

## 📋 Prerequisites

- Python 3.8+
- Node.js 18+ (for NPM-based MCP servers)
- UV package manager (`pip install uv`)
- Neo4j database (optional, will fallback to dummy retriever)

## 🛠️ Installation

1. **Clone the repository:**
```bash
git clone <repository-url>
cd unified-mcp-gateway
```

2. **Install dependencies:**
```bash
pip install -r requirements.txt
```

3. **Install MCP proxy:**
```bash
npm install -g mcp-proxy
```

4. **Configure environment:**
```bash
cp .env.template .env
# Edit .env with your configuration
```

## ⚙️ Configuration

The gateway uses environment variables for configuration. Copy `.env.template` to `.env` and configure:

### Essential Settings
```bash
# Server Configuration
GATEWAY_HOST=0.0.0.0
GATEWAY_PORT=8000
PROXY_PORT=9000

# Security (optional but recommended for production)
GATEWAY_API_KEY=your-secret-api-key-here
CORS_ORIGINS=*
RATE_LIMIT=100

# Neo4j Database (for real tool retriever)
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=password

# Tool Retriever Settings
USE_REAL_RETRIEVER=true
FALLBACK_TO_DUMMY=true

# External API Keys
TAVILY_API_KEY=your-tavily-api-key-here
```

### Server Management
```bash
SERVER_IDLE_TIMEOUT=600        # Idle timeout for dynamic servers (seconds)
MAX_DYNAMIC_SERVERS=20         # Maximum number of dynamic servers
HEALTH_CHECK_INTERVAL=60       # Health check interval (seconds)
```

## 🚦 Quick Start

1. **Start the gateway:**
```bash
python gateway/unified_gateway_v2.py
```

2. **Check health:**
```bash
curl http://localhost:8000/health
```

3. **List available tools:**
```bash
curl http://localhost:8000/tools
```

4. **Call a tool:**
```bash
curl -X POST http://localhost:8000/call \
  -H "Content-Type: application/json" \
  -d '{"tool": "time.get_current_time", "arguments": {"timezone": "UTC"}}'
```

## 📚 API Reference

### Authentication

If `GATEWAY_API_KEY` is set, all endpoints (except `/health` and `/`) require authentication:

```bash
curl -H "Authorization: Bearer your-api-key" http://localhost:8000/tools
```

### Endpoints

#### `GET /`
Basic gateway information and available endpoints.

#### `GET /health`
Comprehensive health check including:
- System health status
- Server connectivity
- Tool retriever status  
- Process monitoring
- Performance metrics

#### `GET /tools`
List all discovered tools across all servers.

**Response:**
```json
{
  "tools": [
    {
      "name": "time.get_current_time",
      "description": "Get the current time",
      "server": "time",
      "actual_name": "get_current_time"
    }
  ],
  "total": 5,
  "servers": ["time", "tavily-mcp", "sequential-thinking"]
}
```

#### `GET /servers`
List all configured servers and their status.

#### `POST /call`
Call a specific tool.

**Request:**
```json
{
  "tool": "time.get_current_time",
  "arguments": {
    "timezone": "UTC"
  }
}
```

**Response:**
```json
{
  "tool": "time.get_current_time",
  "arguments": {"timezone": "UTC"},
  "result": "2024-01-15T10:30:00Z",
  "status": "success"
}
```

#### `POST /retrieve-tools`
Retrieve relevant tools for a task description using intelligent matching.

**Request:**
```json
{
  "task_description": "search the web for AI news",
  "top_k": 3,
  "official_only": false
}
```

**Response:**
```json
{
  "task_description": "search the web for AI news",
  "tools": [
    {
      "tool_name": "tavily-search",
      "tool_description": "Search the web using Tavily",
      "similarity_score": 0.95,
      "mcp_server_config": {...}
    }
  ],
  "count": 3
}
```

## 🔧 Supported MCP Servers

### Popular Servers (Always Running)
- **tavily-mcp**: Web search using Tavily API
- **sequential-thinking**: Structured reasoning and planning
- **time**: Time and date utilities
- **server-everything**: File system operations (dummy fallback)
- **dynamic-tool-retriever**: Intelligent tool discovery

### Dynamic Servers (On-Demand)
The gateway can dynamically start additional MCP servers based on tool retrieval results.

## 📊 Monitoring & Observability

### Health Checks
The `/health` endpoint provides comprehensive system status:

```json
{
  "status": "healthy",
  "timestamp": 1642248600,
  "components": {
    "system": {
      "overall_status": "healthy",
      "servers": {...},
      "orphaned_processes": 0
    },
    "tool_retriever": {
      "status": "healthy",
      "retrievers": {
        "real": {"enabled": true, "available": true},
        "dummy": {"enabled": true, "available": true}
      }
    },
    "servers": {
      "time": {"status": "healthy", "url": "..."},
      "tavily-mcp": {"status": "healthy", "url": "..."}
    }
  },
  "metrics": {
    "total_servers": 4,
    "healthy_servers": 4,
    "total_tools": 15
  }
}
```

### Process Management
- Automatic detection and cleanup of orphaned MCP server processes
- Circuit breaker pattern for failing servers
- Graceful degradation when servers are unavailable
- Automatic server restart on failure

### Error Handling
- Comprehensive error tracking and reporting
- Graceful fallback mechanisms
- Request/response logging with timing
- Rate limiting and security headers

## 🛡️ Security Features

### Authentication & Authorization
- API key-based authentication
- User permission management
- Admin-only endpoints for server management

### Rate Limiting
- Configurable rate limits per client
- IP-based and API key-based limiting
- Graceful handling of rate limit exceeded

### Security Headers
- CORS configuration
- Security headers (CSP, XSS protection, etc.)
- Request validation and sanitization

## 🔄 Development & Testing

### Running Tests
```bash
# Install test dependencies
pip install pytest pytest-asyncio httpx

# Run unit tests
pytest tests/

# Run integration tests
pytest tests/test_integration.py --integration -v
```

### Development Mode
```bash
# Run with debug logging
LOG_LEVEL=DEBUG python gateway/unified_gateway_v2.py

# Run without authentication
unset GATEWAY_API_KEY
python gateway/unified_gateway_v2.py
```

## 🚀 Production Deployment

### Docker Deployment
```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

# Install Node.js for MCP servers
RUN apt-get update && apt-get install -y nodejs npm
RUN npm install -g mcp-proxy

EXPOSE 8000
CMD ["python", "gateway/unified_gateway_v2.py"]
```

### Environment Variables for Production
```bash
# Security
GATEWAY_API_KEY=<strong-random-key>
CORS_ORIGINS=https://yourdomain.com,https://api.yourdomain.com

# Database
NEO4J_URI=bolt://neo4j-server:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=<secure-password>

# External APIs
TAVILY_API_KEY=<your-tavily-key>

# Performance
RATE_LIMIT=1000
MAX_DYNAMIC_SERVERS=50
SERVER_IDLE_TIMEOUT=300
```

### Health Check Endpoint for Load Balancers
Configure your load balancer to use `/health` for health checks:
- Returns 200 when healthy
- Returns 503 when degraded but operational
- Returns 500 when critical errors occur

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Run the test suite
5. Submit a pull request

## 📄 License

MIT License - see LICENSE file for details.

## 🆘 Troubleshooting

### Common Issues

**Gateway fails to start:**
- Check that ports 8000 and 9000 are available
- Verify all dependencies are installed
- Check environment variable configuration

**No tools discovered:**
- Verify MCP servers are starting correctly
- Check server logs for connection issues
- Ensure required API keys are configured

**Neo4j connection failed:**
- Verify Neo4j is running and accessible
- Check NEO4J_URI, NEO4J_USER, and NEO4J_PASSWORD
- Gateway will fallback to dummy retriever automatically

**Rate limiting issues:**
- Adjust RATE_LIMIT environment variable
- Check client IP and authentication status
- Monitor rate limit headers in responses

### Debug Mode
Enable debug logging to troubleshoot issues:
```bash
LOG_LEVEL=DEBUG python gateway/unified_gateway_v2.py
```

### Support
For support and questions:
1. Check the troubleshooting section
2. Review server logs and health endpoint
3. Open an issue with detailed error information