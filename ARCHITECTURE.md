# Unified MCP Tool Graph - Architecture Documentation

## Overview

The Unified MCP Tool Graph is a SaaS-ready platform that aggregates and orchestrates Model Context Protocol (MCP) servers, providing a unified interface for AI agents to discover and use tools dynamically.

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Client Layer                             │
│  (AI Agents, LLMs, Applications, IDEs)                         │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            │ HTTPS/REST/SSE
                            │
┌───────────────────────────▼─────────────────────────────────────┐
│                    API Gateway Layer                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐         │
│  │ Auth Service │  │ Rate Limiter │  │ Load Balancer│         │
│  └──────────────┘  └──────────────┘  └──────────────┘         │
└───────────────────────────┬─────────────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────────────┐
│                  Unified Gateway Service                         │
│  ┌──────────────────────────────────────────────────────┐      │
│  │  FastAPI Application (Port 8000)                      │      │
│  │  - Tool Discovery & Routing                           │      │
│  │  - Request Orchestration                              │      │
│  │  - Multi-tenant Support                               │      │
│  └──────────────────────────────────────────────────────┘      │
└───────────────────────────┬─────────────────────────────────────┘
                            │
        ┌───────────────────┼───────────────────┐
        │                   │                   │
┌───────▼────────┐  ┌───────▼────────┐  ┌───────▼────────┐
│ Tool Retriever │  │ Server Manager │  │  Proxy Manager  │
│   (Neo4j)      │  │                │  │  (mcp-proxy)    │
└───────┬────────┘  └───────┬────────┘  └───────┬────────┘
        │                   │                   │
        │                   │                   │
┌───────▼───────────────────▼───────────────────▼────────┐
│              MCP Proxy Server (Port 9000)               │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐            │
│  │ Server 1 │  │ Server 2 │  │ Server N │            │
│  └──────────┘  └──────────┘  └──────────┘            │
└────────────────────────────────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────────────┐
│                    Data Layer                                    │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐       │
│  │  Neo4j   │  │PostgreSQL│  │  Redis   │  │  S3/S3   │       │
│  │  (Graph) │  │  (Users) │  │  (Cache) │  │ (Storage)│       │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘       │
└─────────────────────────────────────────────────────────────────┘
```

## Component Details

### 1. API Gateway Layer

**Purpose**: Entry point for all client requests with security, rate limiting, and routing.

**Components**:
- **Authentication Service**: JWT-based auth, API key validation
- **Rate Limiter**: Per-tenant/API key rate limiting
- **Load Balancer**: Distribute requests across gateway instances

**Technologies**: FastAPI, Redis, JWT

### 2. Unified Gateway Service

**Purpose**: Core orchestration service that routes tool requests to appropriate MCP servers.

**Key Features**:
- Dynamic tool discovery via Neo4j graph
- Request routing and aggregation
- Multi-tenant isolation
- Tool caching and optimization
- Health monitoring

**Endpoints**:
- `POST /v1/tools/list` - List all available tools
- `POST /v1/tools/call` - Execute a tool
- `POST /v1/tools/discover` - Discover tools by query
- `GET /v1/health` - Health check
- `GET /v1/metrics` - Prometheus metrics

### 3. Tool Retriever Service

**Purpose**: Intelligent tool discovery using Neo4j graph database.

**Capabilities**:
- Semantic search for tools
- Relationship mapping (overlaps_with, extends, preferred_for)
- Vendor categorization
- Tool recommendation based on context

**Graph Schema**:
```
(Vendor)-[:PROVIDES]->(Tool)
(Tool)-[:OVERLAPS_WITH]->(Tool)
(Tool)-[:EXTENDS]->(Tool)
(Tool)-[:PREFERRED_FOR]->(UseCase)
(Vendor)-[:IN_CATEGORY]->(Category)
```

### 4. MCP Server Manager

**Purpose**: Lifecycle management of MCP server instances.

**Features**:
- Dynamic server spin-up on demand
- Server pooling and keep-alive
- Health monitoring
- Automatic failover
- Resource limits per tenant

**Server States**:
- `idle` - Available but not in use
- `active` - Currently handling requests
- `warm` - Pre-warmed for fast startup
- `stopped` - Not running

### 5. MCP Proxy Server

**Purpose**: Bridge between stdio MCP servers and HTTP clients.

**Features**:
- Expose stdio servers as HTTP/SSE endpoints
- Connection pooling
- Request queuing
- Timeout management

## SaaS Architecture

### Multi-Tenancy Model

**Tenant Isolation**:
- Database-level isolation (separate schemas/rows)
- Resource quotas per tenant
- Custom MCP server configurations per tenant
- Usage analytics per tenant

**Tenant Management**:
```python
class Tenant:
    id: str
    name: str
    api_key: str
    quota: ResourceQuota
    enabled_servers: List[str]
    custom_config: Dict[str, Any]
```

### Authentication & Authorization

**Authentication Methods**:
1. **API Key**: Simple key-based auth for programmatic access
2. **JWT Tokens**: Token-based auth for web applications
3. **OAuth 2.0**: For third-party integrations

**Authorization Levels**:
- `admin`: Full access, manage tenants
- `user`: Standard tool access
- `readonly`: Query tools only, no execution

### Rate Limiting

**Strategies**:
- Per API key: X requests/minute
- Per tenant: Y requests/hour
- Per tool: Z calls/minute (to prevent abuse)

**Implementation**: Redis-based sliding window

### Data Storage

**Neo4j** (Graph Database):
- Tool metadata and relationships
- Vendor information
- Usage patterns and analytics

**PostgreSQL** (Relational Database):
- User/tenant management
- API keys and tokens
- Billing and usage records
- Audit logs

**Redis** (Cache):
- Tool metadata cache
- Rate limiting counters
- Session storage
- Real-time metrics

**Object Storage** (S3/MinIO):
- Tool execution logs
- Large response payloads
- Backup data

### Monitoring & Observability

**Metrics** (Prometheus):
- Request rate and latency
- Tool execution success/failure rates
- Server health and availability
- Resource usage per tenant

**Logging** (Structured JSON):
- Request/response logs
- Error traces
- Audit logs for compliance

**Tracing** (OpenTelemetry):
- Distributed request tracing
- Tool execution flow
- Performance bottlenecks

### Scalability

**Horizontal Scaling**:
- Stateless gateway instances
- Load-balanced across multiple nodes
- Shared Redis/PostgreSQL/Neo4j

**Vertical Scaling**:
- Resource limits per component
- Auto-scaling based on metrics

**Caching Strategy**:
- Tool metadata: Redis (TTL: 1 hour)
- Tool results: Redis (TTL: 5 minutes)
- Server health: In-memory (TTL: 30 seconds)

## Deployment Architecture

### Development
```
Single container with all services
- Gateway + Proxy
- Neo4j (optional)
- Local file storage
```

### Production (SaaS)
```
┌─────────────────────────────────────────┐
│         Load Balancer (Nginx/HAProxy)    │
└─────────────────┬───────────────────────┘
                  │
    ┌─────────────┼─────────────┐
    │             │             │
┌───▼───┐    ┌───▼───┐    ┌───▼───┐
│Gateway│    │Gateway│    │Gateway│
│  Pod  │    │  Pod  │    │  Pod  │
└───┬───┘    └───┬───┘    └───┬───┘
    │            │            │
    └────────────┼────────────┘
                 │
    ┌────────────┼────────────┐
    │            │            │
┌───▼───┐   ┌───▼───┐   ┌───▼───┐
│Neo4j  │   │Postgres│  │ Redis │
│Cluster│   │Cluster │  │Cluster│
└───────┘   └────────┘  └───────┘
```

### Kubernetes Deployment

**Services**:
- `gateway-service`: Stateless, auto-scaling
- `proxy-service`: Stateful, connection pooling
- `neo4j-service`: StatefulSet with persistence
- `postgres-service`: StatefulSet with replication
- `redis-service`: StatefulSet or Redis Cluster

**ConfigMaps**:
- Environment configuration
- MCP server definitions
- Feature flags

**Secrets**:
- Database credentials
- API keys
- JWT secrets

## Security Architecture

### Network Security
- TLS/HTTPS for all external communication
- VPC isolation for internal services
- Network policies in Kubernetes

### Data Security
- Encryption at rest (database encryption)
- Encryption in transit (TLS)
- Secrets management (Vault/AWS Secrets Manager)

### Access Control
- API key rotation
- JWT token expiration
- IP whitelisting (optional)
- Audit logging

## API Design

### RESTful Endpoints

**Base URL**: `https://api.mcpgateway.com/v1`

**Authentication**: 
```
Authorization: Bearer <api_key>
# or
Authorization: Bearer <jwt_token>
```

**Endpoints**:

1. **Tool Discovery**
   ```
   POST /v1/tools/discover
   Body: { "query": "schedule LinkedIn post", "limit": 5 }
   Response: { "tools": [...], "configs": {...} }
   ```

2. **List Tools**
   ```
   POST /v1/tools/list
   Body: { "server": "optional_server_name" }
   Response: { "tools": [...] }
   ```

3. **Execute Tool**
   ```
   POST /v1/tools/call
   Body: { "tool": "server.tool_name", "args": {...} }
   Response: { "result": {...}, "metadata": {...} }
   ```

4. **Health Check**
   ```
   GET /v1/health
   Response: { "status": "healthy", "services": {...} }
   ```

5. **Metrics**
   ```
   GET /v1/metrics
   Response: Prometheus format
   ```

## Migration Path to SaaS

### Phase 1: Foundation (Current)
- ✅ Basic gateway functionality
- ✅ MCP server management
- ✅ Neo4j integration
- ⏳ Multi-tenancy support
- ⏳ Authentication system

### Phase 2: SaaS Core
- ⏳ User/tenant management
- ⏳ API key generation
- ⏳ Rate limiting
- ⏳ Usage tracking
- ⏳ Billing integration

### Phase 3: Enterprise Features
- ⏳ SSO/SAML support
- ⏳ Advanced analytics
- ⏳ Custom MCP server onboarding
- ⏳ SLA guarantees
- ⏳ Dedicated infrastructure

## Performance Targets

- **Latency**: < 100ms for tool discovery, < 500ms for tool execution
- **Throughput**: 1000+ requests/second per gateway instance
- **Availability**: 99.9% uptime SLA
- **Scalability**: Auto-scale from 1 to 100+ instances

## Future Enhancements

1. **GraphQL API**: More flexible querying
2. **WebSocket Support**: Real-time tool execution
3. **Tool Marketplace**: Community-contributed tools
4. **Workflow Builder**: Visual tool orchestration
5. **AI-Powered Routing**: ML-based tool selection
6. **Edge Deployment**: Regional gateways for low latency

