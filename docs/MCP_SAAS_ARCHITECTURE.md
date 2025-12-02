# MCP Server as SaaS - Architecture

## Overview

This document describes how to transform the Unified MCP Tool Graph into a **SaaS-hosted MCP server** that can host and orchestrate multiple underlying MCP servers, all while staying within the MCP protocol (no REST API needed).

## Core Concept

**A single MCP server instance acts as a SaaS platform**, where:
- Clients connect via MCP protocol (stdio, SSE, or WebSocket)
- Each client connection represents a tenant/user
- The SaaS MCP server routes tool calls to underlying MCP servers
- Multi-tenancy is handled at the connection/session level

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    MCP Client (IDE/Agent)                    │
│              Connects via MCP Protocol (SSE/WS)              │
└───────────────────────────┬─────────────────────────────────┘
                            │
                            │ MCP Protocol
                            │ (tenant context in connection)
                            │
┌───────────────────────────▼─────────────────────────────────┐
│              SaaS MCP Server (Hosted)                        │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  Connection Manager (Multi-Tenant)                    │  │
│  │  - Tenant identification from connection             │  │
│  │  - Session isolation                                 │  │
│  │  - Resource quotas per tenant                        │  │
│  └──────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  Tool Router & Orchestrator                          │  │
│  │  - Routes tool calls to underlying MCP servers       │  │
│  │  - Aggregates tools from multiple servers            │  │
│  │  - Tenant-specific tool filtering                    │  │
│  └──────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  Underlying MCP Server Manager                         │  │
│  │  - Manages lifecycle of tenant MCP servers             │  │
│  │  - Connection pooling                                 │  │
│  │  - Health monitoring                                  │  │
│  └──────────────────────────────────────────────────────┘  │
└───────────────────────────┬─────────────────────────────────┘
                            │
        ┌───────────────────┼───────────────────┐
        │                   │                   │
┌───────▼────────┐  ┌───────▼────────┐  ┌───────▼────────┐
│  MCP Server 1  │  │  MCP Server 2  │  │  MCP Server N  │
│  (LinkedIn)    │  │  (GitHub)      │  │  (Custom)      │
└────────────────┘  └────────────────┘  └────────────────┘
```

## Multi-Tenancy Strategies

### Strategy 1: Connection-Based Isolation (Recommended)

Each tenant gets a unique connection endpoint:

```
wss://saas-mcp.example.com/tenants/{tenant_id}/sse
```

**Implementation**:
- Tenant ID extracted from URL path
- Each connection maintains tenant context
- Tools filtered per tenant configuration
- Resource quotas enforced per connection

**Pros**:
- Clean isolation
- Easy to scale
- Clear tenant boundaries

**Cons**:
- Requires URL routing
- More complex connection management

### Strategy 2: Session-Based Isolation

Single endpoint, tenant identified via authentication:

```
wss://saas-mcp.example.com/sse
Authorization: Bearer {jwt_token_with_tenant_id}
```

**Implementation**:
- Tenant extracted from JWT token
- Session context stores tenant info
- Tools filtered dynamically per session

**Pros**:
- Single endpoint
- Standard authentication flow
- Easier client setup

**Cons**:
- Requires token validation
- More complex session management

### Strategy 3: Tool-Level Tenant Context

Tenant passed as parameter in tool calls:

```python
@server.tool()
async def call_tool(
    tool_name: str,
    args: dict,
    tenant_id: str  # Extracted from connection metadata
):
    # Route based on tenant_id
```

**Implementation**:
- Tenant context in every tool call
- Most flexible
- Works with any MCP transport

## Connection Flow

### 1. Client Connection

```
Client → SaaS MCP Server (SSE/WebSocket)
  ├─ Authentication (JWT/API Key)
  ├─ Tenant Identification
  └─ Session Creation
```

### 2. Tool Discovery

```
Client → list_tools()
  ├─ SaaS MCP Server aggregates tools from:
  │   ├─ Tenant's enabled MCP servers
  │   ├─ Shared/public tools
  │   └─ Tenant-specific custom tools
  └─ Returns unified tool list
```

### 3. Tool Execution

```
Client → call_tool("linkedin.create_post", {...})
  ├─ SaaS MCP Server:
  │   ├─ Validates tenant permissions
  │   ├─ Checks rate limits
  │   ├─ Routes to underlying MCP server
  │   └─ Returns result
  └─ Client receives response
```

## Implementation Components

### 1. Multi-Tenant MCP Server

```python
from mcp.server.fastmcp import FastMCP
from mcp.server.models import InitializationOptions

class SaaSMCPServer:
    def __init__(self):
        self.server = FastMCP("SaaS-MCP-Gateway")
        self.tenant_sessions = {}  # connection_id -> tenant_id
        self.tenant_servers = {}   # tenant_id -> [server_configs]
        
    async def handle_connection(self, connection_id: str, tenant_id: str):
        """Handle new client connection with tenant context."""
        self.tenant_sessions[connection_id] = tenant_id
        # Initialize tenant's MCP servers
        await self.initialize_tenant_servers(tenant_id)
```

### 2. Tenant-Aware Tool Registration

```python
@server.tool()
async def list_tools(tenant_id: str = None) -> List[Dict]:
    """List tools available to the tenant."""
    # Get tenant from connection context
    tenant_id = self.get_tenant_from_connection()
    
    # Get tenant's enabled servers
    servers = self.tenant_servers.get(tenant_id, [])
    
    # Aggregate tools from all servers
    all_tools = []
    for server_config in servers:
        tools = await self.get_tools_from_server(server_config)
        all_tools.extend(tools)
    
    return all_tools
```

### 3. Tool Routing with Tenant Context

```python
@server.tool()
async def call_tool(
    tool_name: str,
    args: dict
) -> Any:
    """Route tool call to appropriate server with tenant context."""
    tenant_id = self.get_tenant_from_connection()
    
    # Validate tenant permissions
    if not self.can_tenant_use_tool(tenant_id, tool_name):
        raise PermissionError("Tool not available for tenant")
    
    # Check rate limits
    if not self.check_rate_limit(tenant_id):
        raise RateLimitError("Rate limit exceeded")
    
    # Find which server has this tool
    server_config = self.find_server_for_tool(tool_name, tenant_id)
    
    # Route to underlying MCP server
    result = await self.call_underlying_server(
        server_config,
        tool_name,
        args
    )
    
    # Log usage
    await self.log_tool_usage(tenant_id, tool_name)
    
    return result
```

### 4. Underlying Server Manager

```python
class UnderlyingServerManager:
    """Manages connections to underlying MCP servers."""
    
    def __init__(self):
        self.server_connections = {}  # server_id -> ClientSession
        self.tenant_server_mapping = {}  # tenant_id -> [server_ids]
    
    async def get_or_create_connection(
        self,
        tenant_id: str,
        server_config: dict
    ) -> ClientSession:
        """Get or create connection to underlying MCP server."""
        server_id = server_config["id"]
        
        # Check if connection exists
        if server_id in self.server_connections:
            return self.server_connections[server_id]
        
        # Create new connection
        url = server_config["url"]
        async with sse_client(url=url) as (read, write):
            session = ClientSession(read, write)
            await session.initialize()
            self.server_connections[server_id] = session
            return session
```

## Transport Options for SaaS

### 1. SSE (Server-Sent Events) - Recommended

**Endpoint**: `https://saas-mcp.example.com/tenants/{tenant_id}/sse`

**Pros**:
- HTTP-based, easy to deploy
- Works through firewalls/proxies
- Standard MCP transport

**Cons**:
- One-way communication (client → server via HTTP POST)
- Less efficient for high-frequency calls

### 2. WebSocket

**Endpoint**: `wss://saas-mcp.example.com/tenants/{tenant_id}/ws`

**Pros**:
- Full bidirectional communication
- Lower latency
- Better for real-time updates

**Cons**:
- More complex to implement
- Requires WebSocket support in MCP SDK

### 3. HTTP with Polling

**Endpoint**: `https://saas-mcp.example.com/tenants/{tenant_id}/poll`

**Pros**:
- Simplest to implement
- Works everywhere

**Cons**:
- Higher latency
- Less efficient

## Authentication & Authorization

**See [docs/MCP_SAAS_AUTHENTICATION.md](MCP_SAAS_AUTHENTICATION.md) for comprehensive authentication guide.**

### Quick Overview

1. **JWT Token in Headers** (Recommended)
   - Client includes `Authorization: Bearer {jwt_token}` in connection headers
   - Server validates token and extracts tenant/user info
   - Supports expiration and revocation

2. **API Key Authentication**
   - Client includes `X-API-Key: {api_key}` in headers
   - Server validates against database
   - Simpler but less flexible than JWT

3. **Path-Based Tenant ID**
   - Tenant ID in URL: `/tenants/{tenant_id}/sse`
   - Still requires authentication token
   - Good for routing and logging

### Implementation

The authentication is handled by `AuthenticationMiddleware` which:
- Extracts tokens from connection headers
- Validates JWT tokens or API keys
- Maintains tenant context per connection
- Provides decorators for protecting tools

## Tenant Configuration

### Database Schema

```sql
-- Tenant configuration
CREATE TABLE tenant_mcp_configs (
    tenant_id UUID PRIMARY KEY,
    enabled_servers JSONB,  -- List of server IDs
    custom_tools JSONB,     -- Tenant-specific tools
    rate_limits JSONB,       -- Per-tenant limits
    created_at TIMESTAMP
);

-- Server definitions
CREATE TABLE mcp_servers (
    server_id UUID PRIMARY KEY,
    name VARCHAR(255),
    url VARCHAR(500),
    config JSONB,
    is_public BOOLEAN,  -- Available to all tenants
    created_at TIMESTAMP
);
```

### Configuration Loading

```python
async def load_tenant_config(tenant_id: str) -> dict:
    """Load tenant's MCP server configuration."""
    config = await db.get_tenant_config(tenant_id)
    return {
        "enabled_servers": config["enabled_servers"],
        "rate_limits": config["rate_limits"],
        "custom_tools": config["custom_tools"]
    }
```

## Rate Limiting & Quotas

### Per-Tenant Rate Limits

```python
class TenantRateLimiter:
    def __init__(self):
        self.redis = Redis()
    
    async def check_rate_limit(
        self,
        tenant_id: str,
        tool_name: str
    ) -> bool:
        key = f"rate_limit:{tenant_id}:{tool_name}"
        current = await self.redis.incr(key)
        
        if current == 1:
            await self.redis.expire(key, 60)  # 1 minute window
        
        limit = await self.get_tenant_limit(tenant_id)
        return current <= limit
```

## Monitoring & Observability

### Metrics per Tenant

- Tool calls per tenant
- Response times per tenant
- Error rates per tenant
- Active connections per tenant

### Logging

```python
logger.info("tool_call", extra={
    "tenant_id": tenant_id,
    "tool_name": tool_name,
    "duration_ms": duration,
    "success": success
})
```

## Deployment Architecture

### Single Instance (Development)

```
┌─────────────────────────────┐
│   SaaS MCP Server           │
│   (Single Process)          │
│   - All tenants             │
│   - All servers             │
└─────────────────────────────┘
```

### Multi-Instance (Production)

```
┌─────────────────────────────┐
│   Load Balancer             │
│   (Routes by tenant_id)     │
└──────────────┬──────────────┘
               │
    ┌──────────┼──────────┐
    │          │          │
┌───▼───┐  ┌───▼───┐  ┌───▼───┐
│SaaS MCP│  │SaaS MCP│  │SaaS MCP│
│Server 1│  │Server 2│  │Server 3│
└────────┘  └────────┘  └────────┘
    │          │          │
    └──────────┼──────────┘
               │
    ┌──────────▼──────────┐
    │  Shared Services     │
    │  - PostgreSQL        │
    │  - Redis             │
    │  - Neo4j             │
    └───────────────────────┘
```

## Client Connection Example

### Python Client

```python
from mcp.client.sse import sse_client
from mcp.client.session import ClientSession

async def connect_to_saas_mcp(tenant_id: str, api_key: str):
    url = f"https://saas-mcp.example.com/tenants/{tenant_id}/sse"
    headers = {"Authorization": f"Bearer {api_key}"}
    
    async with sse_client(url=url, headers=headers) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            
            # List all tools (aggregated from underlying servers)
            tools = await session.list_tools()
            
            # Call a tool (routed automatically)
            result = await session.call_tool(
                "linkedin.create_post",
                {"content": "Hello World"}
            )
            
            return result
```

### JavaScript/TypeScript Client

```typescript
import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { SSEClientTransport } from "@modelcontextprotocol/sdk/client/sse.js";

async function connectToSaaSMCP(tenantId: string, apiKey: string) {
  const url = `https://saas-mcp.example.com/tenants/${tenantId}/sse`;
  const transport = new SSEClientTransport(
    new URL(url),
    { headers: { Authorization: `Bearer ${apiKey}` } }
  );
  
  const client = new Client({
    name: "my-client",
    version: "1.0.0"
  }, {
    capabilities: {}
  });
  
  await client.connect(transport);
  
  // List tools
  const tools = await client.listTools();
  
  // Call tool
  const result = await client.callTool({
    name: "linkedin.create_post",
    arguments: { content: "Hello World" }
  });
  
  return result;
}
```

## Advantages of MCP-as-SaaS

1. **Protocol Native**: Stays within MCP, no REST layer needed
2. **IDE Integration**: Works directly with MCP-compatible IDEs
3. **Agent Compatibility**: Works with any MCP-compatible agent
4. **Unified Interface**: Single connection for all tools
5. **Dynamic Routing**: Automatic routing to underlying servers
6. **Tool Aggregation**: All tools appear as one unified server

## Migration Path

### Phase 1: Single-Tenant SaaS MCP Server
- Basic MCP server with tool routing
- Single tenant support
- Connection to underlying servers

### Phase 2: Multi-Tenant Support
- Tenant identification
- Per-tenant server configuration
- Resource isolation

### Phase 3: Enterprise Features
- Advanced rate limiting
- Usage analytics
- Custom tool registration
- SSO integration

## Next Steps

1. Implement tenant-aware connection handler
2. Add authentication middleware
3. Create tenant configuration system
4. Implement tool routing with tenant context
5. Add rate limiting per tenant
6. Set up monitoring and logging

