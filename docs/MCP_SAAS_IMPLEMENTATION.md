# MCP Server as SaaS - Implementation Guide

## Overview

This guide provides step-by-step instructions for implementing a SaaS-hosted MCP server that can host and orchestrate multiple underlying MCP servers.

## Key Concepts

1. **Single MCP Server Instance**: One MCP server acts as the SaaS platform
2. **Multi-Tenant Support**: Each connection represents a tenant
3. **Tool Aggregation**: Tools from multiple servers appear as one unified server
4. **Automatic Routing**: Tool calls automatically route to underlying servers

## Implementation Steps

### Step 1: Create Tenant-Aware MCP Server

The core server needs to:
- Accept connections with tenant context
- Maintain tenant-specific configurations
- Route tools to appropriate underlying servers

### Step 2: Implement Connection Handler

Handle tenant identification from:
- URL path: `/tenants/{tenant_id}/sse`
- Headers: `Authorization: Bearer {jwt_with_tenant}`
- Connection metadata

### Step 3: Tool Discovery & Aggregation

For each tenant:
1. Load tenant's enabled MCP servers
2. Connect to each underlying server
3. Discover tools from each server
4. Aggregate into unified tool list
5. Return to client

### Step 4: Tool Execution Routing

When a tool is called:
1. Identify tenant from connection
2. Find which underlying server has the tool
3. Route call to that server
4. Return result to client

### Step 5: Add Multi-Tenancy Features

- Rate limiting per tenant
- Resource quotas
- Usage tracking
- Tenant isolation

## Connection Patterns

### Pattern 1: Path-Based Tenant Identification

```
Client connects to: wss://saas-mcp.example.com/tenants/{tenant_id}/sse

Server extracts tenant_id from URL path
```

### Pattern 2: Token-Based Tenant Identification

```
Client connects to: wss://saas-mcp.example.com/sse
Headers: Authorization: Bearer {jwt_token}

Server extracts tenant_id from JWT payload
```

### Pattern 3: Query Parameter

```
Client connects to: wss://saas-mcp.example.com/sse?tenant={tenant_id}

Server extracts tenant_id from query parameter
```

## Example: Complete SaaS MCP Server

```python
from mcp.server.fastmcp import FastMCP
from mcp.client.sse import sse_client
from mcp.client.session import ClientSession
import jwt

class SaaSMCPServer:
    def __init__(self):
        self.server = FastMCP("SaaS-MCP")
        self.tenants = {}
        self.tenant_servers = {}
        self._register_tools()
    
    def _register_tools(self):
        @self.server.tool()
        async def list_tools() -> List[Dict]:
            tenant_id = self._get_tenant_from_context()
            return await self._aggregate_tools(tenant_id)
        
        @self.server.tool()
        async def call_tool(tool_name: str, args: dict) -> Any:
            tenant_id = self._get_tenant_from_context()
            return await self._route_tool_call(tenant_id, tool_name, args)
    
    def _get_tenant_from_context(self) -> str:
        # Extract from connection context
        # Implementation depends on transport
        pass
    
    async def _aggregate_tools(self, tenant_id: str) -> List[Dict]:
        all_tools = []
        servers = self.tenant_servers.get(tenant_id, [])
        
        for server_config in servers:
            tools = await self._get_tools_from_server(server_config)
            all_tools.extend(tools)
        
        return all_tools
    
    async def _route_tool_call(
        self,
        tenant_id: str,
        tool_name: str,
        args: dict
    ) -> Any:
        # Find server
        server_config = self._find_server_for_tool(tenant_id, tool_name)
        
        # Route call
        return await self._call_server_tool(server_config, tool_name, args)
```

## Deployment Options

### Option 1: Single Instance (Development)

```bash
# Run single SaaS MCP server
python gateway/saas_mcp_server.py
```

### Option 2: Multiple Instances with Load Balancer

```yaml
# docker-compose.yml
services:
  saas-mcp-1:
    build: .
    ports:
      - "8001:8000"
  
  saas-mcp-2:
    build: .
    ports:
      - "8002:8000"
  
  nginx:
    image: nginx
    ports:
      - "8000:80"
    # Routes /tenants/{id} to appropriate instance
```

### Option 3: Kubernetes Deployment

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: saas-mcp
spec:
  replicas: 3
  template:
    spec:
      containers:
      - name: saas-mcp
        image: saas-mcp:latest
        ports:
        - containerPort: 8000
```

## Client Integration

### Python Client Example

```python
from mcp.client.sse import sse_client
from mcp.client.session import ClientSession

async def connect_saas_mcp(tenant_id: str, api_key: str):
    url = f"https://saas-mcp.example.com/tenants/{tenant_id}/sse"
    headers = {"Authorization": f"Bearer {api_key}"}
    
    async with sse_client(url=url, headers=headers) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            
            # All tools from all underlying servers
            tools = await session.list_tools()
            
            # Call any tool (automatically routed)
            result = await session.call_tool(
                "linkedin.create_post",
                {"content": "Hello"}
            )
```

## Advantages

1. **Protocol Native**: Stays within MCP protocol
2. **IDE Compatible**: Works with any MCP-compatible IDE
3. **Agent Compatible**: Works with any MCP-compatible agent
4. **Unified Interface**: Single connection for all tools
5. **Automatic Routing**: No need to know which server has which tool
6. **Scalable**: Can scale horizontally

## Next Steps

1. Implement tenant identification from connection
2. Add authentication/authorization
3. Implement rate limiting
4. Add usage tracking
5. Create admin interface for tenant management

