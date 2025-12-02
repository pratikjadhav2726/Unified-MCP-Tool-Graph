# Authentication for SaaS MCP Server

## Overview

This document describes authentication strategies for a multi-tenant SaaS MCP server. Since MCP supports multiple transports (SSE, WebSocket, stdio), authentication must work across all of them.

## Authentication Flow

```
┌─────────────────────────────────────────────────────────┐
│  MCP Client (IDE/Agent)                                 │
│  ┌──────────────────────────────────────────────────┐  │
│  │  1. Obtains Auth Token (JWT/API Key)             │  │
│  │  2. Connects to SaaS MCP Server                  │  │
│  │  3. Includes Token in Connection                 │  │
│  └──────────────────────────────────────────────────┘  │
└───────────────────────┬─────────────────────────────────┘
                        │
                        │ MCP Protocol + Auth Token
                        │
┌───────────────────────▼─────────────────────────────────┐
│  SaaS MCP Server                                        │
│  ┌──────────────────────────────────────────────────┐  │
│  │  1. Extract Token from Connection               │  │
│  │  2. Validate Token (JWT/API Key)                │  │
│  │  3. Extract Tenant/User Info                    │  │
│  │  4. Create Tenant Context                       │  │
│  │  5. Initialize Tenant's MCP Servers             │  │
│  └──────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

## Authentication Methods

### Method 1: JWT Token in Connection Headers (Recommended)

**How it works:**
- Client obtains JWT token from auth service
- Token included in connection headers
- Server validates token and extracts tenant/user info

**Implementation:**

#### Client Side

```python
from mcp.client.sse import sse_client
from mcp.client.session import ClientSession
import jwt

async def connect_with_jwt(tenant_id: str, user_id: str):
    # Get JWT token (from auth service or local generation)
    token = generate_jwt_token(tenant_id, user_id)
    
    # Connect with token in headers
    url = "https://saas-mcp.example.com/sse"
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Tenant-ID": tenant_id  # Optional, for additional validation
    }
    
    async with sse_client(url=url, headers=headers) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            # Now authenticated and tenant context is set
            tools = await session.list_tools()
            return tools
```

#### Server Side

```python
from mcp.server.fastmcp import FastMCP
from mcp.server.models import InitializationOptions
import jwt
from typing import Optional

class AuthenticatedSaaSMCPServer:
    def __init__(self):
        self.server = FastMCP("SaaS-MCP")
        self.jwt_secret = os.getenv("JWT_SECRET")
        self.tenant_contexts = {}
        self._setup_auth_middleware()
    
    def _setup_auth_middleware(self):
        """Setup authentication middleware."""
        
        @self.server.on_initialize
        async def on_initialize(params: InitializationOptions) -> dict:
            """Validate authentication on connection initialization."""
            # Extract token from connection context
            token = self._extract_token_from_context()
            
            if not token:
                raise ValueError("Authentication required")
            
            # Validate token
            tenant_info = self._validate_jwt_token(token)
            if not tenant_info:
                raise ValueError("Invalid authentication token")
            
            # Store tenant context
            connection_id = self._get_connection_id()
            self.tenant_contexts[connection_id] = tenant_info
            
            return {
                "serverInfo": {
                    "name": "SaaS-MCP",
                    "version": "1.0.0"
                },
                "capabilities": {}
            }
    
    def _extract_token_from_context(self) -> Optional[str]:
        """Extract JWT token from connection context."""
        # This depends on the transport:
        # - SSE: From HTTP headers
        # - WebSocket: From connection headers
        # - stdio: From environment or initial message
        
        # For SSE/WebSocket, extract from headers
        # Implementation depends on FastMCP's context access
        # This is a placeholder - actual implementation varies
        return None  # TODO: Implement based on transport
    
    def _validate_jwt_token(self, token: str) -> Optional[dict]:
        """Validate JWT token and extract tenant info."""
        try:
            payload = jwt.decode(
                token,
                self.jwt_secret,
                algorithms=["HS256"]
            )
            return {
                "tenant_id": payload["tenant_id"],
                "user_id": payload.get("user_id"),
                "permissions": payload.get("permissions", [])
            }
        except jwt.ExpiredSignatureError:
            logger.error("JWT token expired")
            return None
        except jwt.InvalidTokenError:
            logger.error("Invalid JWT token")
            return None
```

### Method 2: API Key Authentication

**How it works:**
- Client uses API key instead of JWT
- Key validated against database
- Simpler but less flexible than JWT

**Implementation:**

#### Client Side

```python
async def connect_with_api_key(api_key: str):
    url = "https://saas-mcp.example.com/sse"
    headers = {
        "X-API-Key": api_key
    }
    
    async with sse_client(url=url, headers=headers) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            return session
```

#### Server Side

```python
import hashlib
from database import get_tenant_by_api_key

class APIKeyAuthenticator:
    def __init__(self):
        self.api_keys = {}  # In production, use database
    
    async def validate_api_key(self, api_key: str) -> Optional[dict]:
        """Validate API key and return tenant info."""
        # Hash the provided key
        key_hash = hashlib.sha256(api_key.encode()).hexdigest()
        
        # Look up in database
        tenant = await get_tenant_by_api_key(key_hash)
        if not tenant:
            return None
        
        # Check if key is active
        if not tenant.get("is_active"):
            return None
        
        return {
            "tenant_id": tenant["tenant_id"],
            "api_key_id": tenant["api_key_id"],
            "permissions": tenant.get("permissions", [])
        }
```

### Method 3: Path-Based Tenant Identification

**How it works:**
- Tenant ID in URL path
- Additional authentication via headers
- Good for multi-tenant routing

**Implementation:**

```python
# Client connects to tenant-specific endpoint
url = "https://saas-mcp.example.com/tenants/{tenant_id}/sse"
headers = {
    "Authorization": "Bearer {token}"  # Still need auth
}

# Server extracts tenant from path
def extract_tenant_from_path(url: str) -> str:
    # /tenants/{tenant_id}/sse
    parts = url.split("/")
    tenant_index = parts.index("tenants")
    return parts[tenant_index + 1]
```

### Method 4: Query Parameter Authentication

**How it works:**
- Token passed as query parameter
- Less secure (appears in logs)
- Useful for testing

**Implementation:**

```python
# Client
url = f"https://saas-mcp.example.com/sse?token={api_key}"

# Server
def extract_token_from_query(request) -> str:
    return request.query_params.get("token")
```

## Transport-Specific Authentication

### SSE (Server-Sent Events)

**HTTP Headers:**
```python
# Client
headers = {
    "Authorization": "Bearer {jwt_token}",
    "X-API-Key": "{api_key}",  # Alternative
    "X-Tenant-ID": "{tenant_id}"  # Optional validation
}

# Server - Extract from HTTP request
def extract_auth_from_sse(request):
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        return auth_header[7:]  # Remove "Bearer " prefix
    return None
```

### WebSocket

**Connection Headers:**
```python
# Client
headers = {
    "Authorization": "Bearer {jwt_token}"
}

# Server - Extract from WebSocket handshake
def extract_auth_from_websocket(websocket):
    headers = websocket.headers
    auth_header = headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        return auth_header[7:]
    return None
```

### stdio (For Local/Development)

**Environment Variables:**
```python
# Client sets environment variable
os.environ["MCP_API_KEY"] = api_key

# Server reads from environment
def extract_auth_from_stdio():
    return os.getenv("MCP_API_KEY")
```

**Initial Message:**
```python
# Client sends auth as first message
{"type": "auth", "token": "{jwt_token}"}

# Server processes before initialization
async def handle_stdio_auth(read, write):
    auth_message = await read()
    if auth_message.get("type") == "auth":
        token = auth_message.get("token")
        return validate_token(token)
```

## Complete Authentication Implementation

### Authentication Middleware

```python
from functools import wraps
from typing import Callable, Optional

class AuthenticationMiddleware:
    """Middleware for handling authentication in MCP server."""
    
    def __init__(self, jwt_secret: str):
        self.jwt_secret = jwt_secret
        self.tenant_contexts = {}  # connection_id -> tenant_info
    
    def extract_token(self, connection_context: dict) -> Optional[str]:
        """Extract token from connection context."""
        # Try Authorization header first
        headers = connection_context.get("headers", {})
        auth_header = headers.get("Authorization") or headers.get("authorization")
        
        if auth_header and auth_header.startswith("Bearer "):
            return auth_header[7:]
        
        # Try API key header
        api_key = headers.get("X-API-Key") or headers.get("x-api-key")
        if api_key:
            return api_key
        
        # Try query parameter
        query = connection_context.get("query", {})
        token = query.get("token")
        if token:
            return token
        
        return None
    
    def validate_token(self, token: str) -> Optional[dict]:
        """Validate token and return tenant info."""
        # Try JWT first
        try:
            payload = jwt.decode(token, self.jwt_secret, algorithms=["HS256"])
            return {
                "tenant_id": payload["tenant_id"],
                "user_id": payload.get("user_id"),
                "auth_method": "jwt"
            }
        except jwt.InvalidTokenError:
            pass
        
        # Try API key
        tenant_info = self.validate_api_key(token)
        if tenant_info:
            tenant_info["auth_method"] = "api_key"
            return tenant_info
        
        return None
    
    async def validate_api_key(self, api_key: str) -> Optional[dict]:
        """Validate API key."""
        # Hash and lookup in database
        key_hash = hashlib.sha256(api_key.encode()).hexdigest()
        tenant = await self.get_tenant_by_key_hash(key_hash)
        return tenant
    
    def require_auth(self, func: Callable) -> Callable:
        """Decorator to require authentication for tool calls."""
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Get connection context
            connection_id = self.get_connection_id()
            tenant_info = self.tenant_contexts.get(connection_id)
            
            if not tenant_info:
                raise PermissionError("Authentication required")
            
            # Add tenant context to function
            kwargs["tenant_id"] = tenant_info["tenant_id"]
            kwargs["user_id"] = tenant_info.get("user_id")
            
            return await func(*args, **kwargs)
        
        return wrapper
```

### Integration with SaaS MCP Server

```python
from gateway.saas_mcp_server import SaaSMCPServer
from authentication import AuthenticationMiddleware

class AuthenticatedSaaSMCPServer(SaaSMCPServer):
    """SaaS MCP Server with authentication."""
    
    def __init__(self):
        super().__init__()
        self.auth_middleware = AuthenticationMiddleware(
            jwt_secret=os.getenv("JWT_SECRET")
        )
        self._setup_authentication()
    
    def _setup_authentication(self):
        """Setup authentication hooks."""
        
        @self.server.on_initialize
        async def on_initialize(params):
            """Authenticate on connection initialization."""
            # Get connection context (implementation depends on FastMCP)
            connection_context = self._get_connection_context()
            
            # Extract and validate token
            token = self.auth_middleware.extract_token(connection_context)
            if not token:
                raise ValueError("Authentication required")
            
            tenant_info = self.auth_middleware.validate_token(token)
            if not tenant_info:
                raise ValueError("Invalid authentication")
            
            # Store tenant context
            connection_id = self._get_connection_id()
            self.auth_middleware.tenant_contexts[connection_id] = tenant_info
            
            # Initialize tenant's servers
            await self._initialize_tenant(tenant_info["tenant_id"])
            
            return {
                "serverInfo": {
                    "name": "SaaS-MCP",
                    "version": "1.0.0"
                },
                "capabilities": {}
            }
        
        # Protect tools with authentication
        original_list_tools = self.server._tools.get("list_tools")
        if original_list_tools:
            @self.server.tool()
            @self.auth_middleware.require_auth
            async def list_tools(tenant_id: str = None):
                return await original_list_tools()
        
        original_call_tool = self.server._tools.get("call_tool")
        if original_call_tool:
            @self.server.tool()
            @self.auth_middleware.require_auth
            async def call_tool(tool_name: str, args: dict, tenant_id: str = None):
                return await original_call_tool(tool_name, args)
```

## Token Generation

### JWT Token Generation

```python
import jwt
from datetime import datetime, timedelta

def generate_jwt_token(
    tenant_id: str,
    user_id: Optional[str] = None,
    expires_hours: int = 24
) -> str:
    """Generate JWT token for tenant/user."""
    payload = {
        "tenant_id": tenant_id,
        "user_id": user_id,
        "iat": datetime.utcnow(),
        "exp": datetime.utcnow() + timedelta(hours=expires_hours)
    }
    
    token = jwt.encode(
        payload,
        os.getenv("JWT_SECRET"),
        algorithm="HS256"
    )
    
    return token
```

### API Key Generation

```python
import secrets
import hashlib

def generate_api_key(tenant_id: str) -> tuple[str, str]:
    """Generate API key for tenant.
    
    Returns:
        (api_key, key_hash) - Store key_hash in database, return api_key to user
    """
    # Generate random key
    api_key = f"mcp_{secrets.token_urlsafe(32)}"
    
    # Hash for storage
    key_hash = hashlib.sha256(api_key.encode()).hexdigest()
    
    # Store in database
    store_api_key(tenant_id, key_hash)
    
    return api_key, key_hash
```

## Database Schema for Authentication

```sql
-- API Keys table
CREATE TABLE api_keys (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    key_hash VARCHAR(255) NOT NULL UNIQUE,
    name VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP,
    last_used_at TIMESTAMP,
    is_active BOOLEAN DEFAULT true
);

-- JWT token blacklist (for revocation)
CREATE TABLE jwt_blacklist (
    token_hash VARCHAR(255) PRIMARY KEY,
    tenant_id UUID,
    expires_at TIMESTAMP,
    blacklisted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Authentication logs
CREATE TABLE auth_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID,
    user_id UUID,
    auth_method VARCHAR(50),  -- 'jwt', 'api_key'
    ip_address INET,
    success BOOLEAN,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

## Security Best Practices

### 1. Token Storage

**Client Side:**
- Store tokens securely (keychain, secure storage)
- Never commit tokens to version control
- Use environment variables for API keys

**Server Side:**
- Hash API keys before storage
- Use strong JWT secrets
- Rotate secrets regularly

### 2. Token Validation

```python
def validate_token_comprehensive(token: str) -> Optional[dict]:
    """Comprehensive token validation."""
    # 1. Check format
    if not token or len(token) < 10:
        return None
    
    # 2. Validate JWT
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None
    
    # 3. Check blacklist
    if is_token_blacklisted(token):
        return None
    
    # 4. Check tenant is active
    tenant = get_tenant(payload["tenant_id"])
    if not tenant or not tenant.is_active:
        return None
    
    return payload
```

### 3. Rate Limiting by Authentication

```python
async def check_auth_rate_limit(tenant_id: str, auth_method: str) -> bool:
    """Rate limit authentication attempts."""
    key = f"auth_rate_limit:{tenant_id}:{auth_method}"
    attempts = await redis.incr(key)
    
    if attempts == 1:
        await redis.expire(key, 300)  # 5 minute window
    
    max_attempts = 10  # Max 10 attempts per 5 minutes
    return attempts <= max_attempts
```

### 4. Audit Logging

```python
async def log_authentication(
    tenant_id: str,
    user_id: Optional[str],
    auth_method: str,
    success: bool,
    ip_address: str
):
    """Log authentication attempts."""
    await db.execute("""
        INSERT INTO auth_logs 
        (tenant_id, user_id, auth_method, success, ip_address)
        VALUES ($1, $2, $3, $4, $5)
    """, tenant_id, user_id, auth_method, success, ip_address)
```

## Example: Complete Authentication Flow

```python
# 1. Client obtains token
token = await get_auth_token(tenant_id, user_id)

# 2. Client connects with token
async with sse_client(
    url="https://saas-mcp.example.com/sse",
    headers={"Authorization": f"Bearer {token}"}
) as (read, write):
    async with ClientSession(read, write) as session:
        # 3. Server validates during initialize
        await session.initialize()
        
        # 4. All subsequent calls are authenticated
        tools = await session.list_tools()
        result = await session.call_tool("tool_name", {})
```

## Troubleshooting

### Common Issues

1. **Token not found in headers**
   - Check client is sending Authorization header
   - Verify header format: "Bearer {token}"

2. **Token validation fails**
   - Check JWT secret matches
   - Verify token hasn't expired
   - Check token format

3. **Tenant context not available**
   - Ensure authentication happens before tool calls
   - Verify tenant_id is in token payload

## Next Steps

1. Implement token extraction for your transport (SSE/WebSocket)
2. Add token validation logic
3. Create API key management system
4. Add audit logging
5. Implement token revocation
6. Add rate limiting for auth attempts

