# Unified MCP Tool Graph - API Documentation

## Base URL

**Development**: `http://localhost:8000`  
**Production**: `https://api.mcpgateway.com/v1`

## Authentication

All API requests require authentication via one of the following methods:

### API Key Authentication

```http
Authorization: Bearer YOUR_API_KEY
```

### JWT Token Authentication

```http
Authorization: Bearer YOUR_JWT_TOKEN
```

## API Endpoints

### 1. Health Check

Check the health status of the gateway and its dependencies.

**Endpoint**: `GET /health`

**Response**:
```json
{
  "status": "healthy",
  "timestamp": "2024-01-15T10:30:00Z",
  "services": {
    "gateway": "healthy",
    "neo4j": "healthy",
    "proxy": "healthy",
    "postgres": "healthy",
    "redis": "healthy"
  },
  "version": "1.0.0"
}
```

### 2. List All Tools

Retrieve a list of all available tools from all MCP servers.

**Endpoint**: `POST /v1/tools/list`

**Request Body**:
```json
{
  "server": "optional_server_name",
  "include_metadata": true
}
```

**Response**:
```json
{
  "tools": [
    {
      "name": "time.get_current_time",
      "server": "time",
      "description": "Get the current time",
      "parameters": {
        "type": "object",
        "properties": {}
      }
    }
  ],
  "total": 100,
  "servers": ["time", "everything", "sequential-thinking"]
}
```

### 3. Discover Tools

Intelligently discover tools based on a natural language query.

**Endpoint**: `POST /v1/tools/discover`

**Request Body**:
```json
{
  "query": "I want to schedule a LinkedIn post",
  "limit": 5,
  "include_config": true
}
```

**Response**:
```json
{
  "tools": [
    {
      "name": "linkedin.create_post",
      "server": "linkedin",
      "description": "Create a new LinkedIn post",
      "relevance_score": 0.95,
      "mcp_config": {
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-linkedin"]
      }
    }
  ],
  "query": "I want to schedule a LinkedIn post",
  "total_found": 3
}
```

### 4. Execute Tool

Execute a specific tool with provided arguments.

**Endpoint**: `POST /v1/tools/call`

**Request Body**:
```json
{
  "tool": "time.get_current_time",
  "args": {},
  "timeout": 30
}
```

**Response**:
```json
{
  "result": {
    "time": "2024-01-15T10:30:00Z",
    "timezone": "UTC"
  },
  "metadata": {
    "execution_time_ms": 45,
    "server": "time",
    "timestamp": "2024-01-15T10:30:00Z"
  }
}
```

**Error Response**:
```json
{
  "error": {
    "code": "TOOL_EXECUTION_ERROR",
    "message": "Tool execution failed",
    "details": "..."
  }
}
```

### 5. Get Server Status

Get the status of all MCP servers.

**Endpoint**: `GET /v1/servers/status`

**Response**:
```json
{
  "servers": [
    {
      "name": "time",
      "status": "active",
      "tools_count": 5,
      "uptime_seconds": 3600,
      "last_used": "2024-01-15T10:25:00Z"
    }
  ],
  "total_servers": 10,
  "active_servers": 8
}
```

### 6. Get System Info

Get system-wide information and statistics.

**Endpoint**: `GET /v1/system/info`

**Response**:
```json
{
  "neo4j_available": true,
  "total_servers": 10,
  "total_tools": 11066,
  "servers": ["time", "everything", "linkedin", ...],
  "version": "1.0.0",
  "uptime_seconds": 86400
}
```

### 7. Metrics (Prometheus)

Get Prometheus-formatted metrics.

**Endpoint**: `GET /metrics`

**Response**: Prometheus metrics format

## Error Handling

All errors follow a consistent format:

```json
{
  "error": {
    "code": "ERROR_CODE",
    "message": "Human-readable error message",
    "details": "Additional error details",
    "timestamp": "2024-01-15T10:30:00Z"
  }
}
```

### Error Codes

- `AUTHENTICATION_REQUIRED`: Missing or invalid authentication
- `RATE_LIMIT_EXCEEDED`: Too many requests
- `TOOL_NOT_FOUND`: Requested tool doesn't exist
- `TOOL_EXECUTION_ERROR`: Tool execution failed
- `SERVER_UNAVAILABLE`: MCP server is not available
- `INVALID_REQUEST`: Request validation failed
- `INTERNAL_ERROR`: Internal server error

## Rate Limiting

Rate limits are applied per API key:

- **Default**: 60 requests/minute, 1000 requests/hour
- **Headers**: Rate limit info is included in response headers:
  ```
  X-RateLimit-Limit: 60
  X-RateLimit-Remaining: 45
  X-RateLimit-Reset: 1642248000
  ```

## Pagination

List endpoints support pagination:

**Request**:
```json
{
  "page": 1,
  "page_size": 20
}
```

**Response**:
```json
{
  "data": [...],
  "pagination": {
    "page": 1,
    "page_size": 20,
    "total": 100,
    "total_pages": 5
  }
}
```

## WebSocket Support (Future)

Real-time tool execution via WebSocket:

**Endpoint**: `WS /v1/tools/stream`

**Message Format**:
```json
{
  "action": "call_tool",
  "tool": "time.get_current_time",
  "args": {}
}
```

## SDK Examples

### Python

```python
from mcp_gateway_client import MCPGatewayClient

client = MCPGatewayClient(
    api_key="your_api_key",
    base_url="https://api.mcpgateway.com/v1"
)

# Discover tools
tools = await client.discover_tools("schedule LinkedIn post", limit=5)

# Execute tool
result = await client.call_tool("time.get_current_time", {})
```

### JavaScript/TypeScript

```typescript
import { MCPGatewayClient } from '@mcpgateway/client';

const client = new MCPGatewayClient({
  apiKey: 'your_api_key',
  baseUrl: 'https://api.mcpgateway.com/v1'
});

// Discover tools
const tools = await client.discoverTools('schedule LinkedIn post', { limit: 5 });

// Execute tool
const result = await client.callTool('time.get_current_time', {});
```

## Versioning

API versioning is done via URL path:
- `/v1/` - Current stable version
- `/v2/` - Future version (when available)

Breaking changes will result in a new version number.

## Changelog

### v1.0.0 (Current)
- Initial API release
- Tool discovery and execution
- Multi-server support
- Basic authentication

