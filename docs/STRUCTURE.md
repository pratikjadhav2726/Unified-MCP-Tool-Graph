# Project Structure

This document describes the organization of the Unified MCP Tool Graph codebase.

## Directory Structure

```
unified-mcp-tool-graph/
├── .github/                    # GitHub workflows and templates
│   ├── workflows/              # CI/CD pipelines
│   └── ISSUE_TEMPLATE/         # Issue templates
│
├── config/                     # Configuration files and templates
│   ├── mcp_client_config.json.example
│   ├── mcp_proxy_servers.json.example
│   ├── prometheus.yml
│   └── grafana/                # Grafana dashboards and datasources
│
├── Data/                       # Data files (gitignored if large)
│   └── ...
│
├── docs/                       # Documentation
│   ├── STRUCTURE.md           # This file
│   ├── API.md                 # API documentation
│   ├── DEPLOYMENT.md          # Deployment guides
│   └── DEVELOPMENT.md         # Development guide
│
├── Dynamic_tool_retriever_MCP/ # Dynamic tool retrieval service
│   ├── embedder.py            # Text embedding for semantic search
│   ├── neo4j_retriever.py     # Neo4j graph queries
│   ├── server.py              # MCP server implementation
│   └── README.md
│
├── Example_Agents/             # Example agent implementations
│   ├── A2A_DynamicToolAgent/  # A2A agent example
│   └── Langgraph/             # LangGraph agent example
│
├── experimental/               # Experimental features (use with caution)
│   └── ...
│
├── gateway/                    # Unified gateway implementation
│   ├── unified_gateway.py     # Main gateway service
│   ├── dummy_tool_retriever.py # Fallback tool retriever
│   └── test_working_gateway.py # Gateway tests
│
├── Ingestion_pipeline/         # Tool ingestion and graph building
│   ├── Ingestion_Neo4j.py     # Neo4j ingestion script
│   ├── Preprocess_parse_and_embed.py # Data preprocessing
│   ├── cluster_vendors_ingestion.py # Vendor clustering
│   └── README.md
│
├── MCP_Server_Manager/         # MCP server lifecycle management
│   ├── mcp_server_manager.py  # Server manager implementation
│   ├── test_mcp_multi_server_client.py
│   └── test_mcp_streamable_http_client.py
│
├── scripts/                    # Utility scripts
│   ├── init_db.sql            # Database initialization
│   ├── setup.sh               # Setup script
│   └── migrate.py             # Database migrations
│
├── tests/                      # Test suite
│   ├── unit/                  # Unit tests
│   ├── integration/           # Integration tests
│   └── e2e/                   # End-to-end tests
│
├── Utils/                      # Utility functions and helpers
│   └── ...
│
├── .env.example               # Environment variables template
├── .gitignore                 # Git ignore rules
├── ARCHITECTURE.md            # Architecture documentation
├── CODE_OF_CONDUCT.md         # Code of conduct
├── CONTRIBUTING.md            # Contribution guidelines
├── docker-compose.yml         # Docker Compose configuration
├── Dockerfile                 # Docker image definition
├── GETTING_STARTED.md         # Quick start guide
├── LICENSE                    # License file
├── package.json               # Node.js dependencies
├── pyproject.toml             # Python project configuration
├── README.md                  # Main project README
├── start_unified_gateway.py   # Main entry point
└── uv.lock                    # Dependency lock file
```

## Key Components

### Gateway (`gateway/`)

The unified gateway is the main entry point for all tool requests. It:
- Routes requests to appropriate MCP servers
- Manages tool discovery via Neo4j
- Handles authentication and rate limiting
- Provides a unified API interface

**Main Files**:
- `unified_gateway.py`: FastAPI application with all endpoints
- `dummy_tool_retriever.py`: Fallback when Neo4j is unavailable

### MCP Server Manager (`MCP_Server_Manager/`)

Manages the lifecycle of MCP server instances:
- Starts/stops servers on demand
- Maintains server pools
- Monitors server health
- Handles failover

**Main Files**:
- `mcp_server_manager.py`: Core server management logic

### Dynamic Tool Retriever (`Dynamic_tool_retriever_MCP/`)

Intelligent tool discovery service:
- Queries Neo4j graph for relevant tools
- Performs semantic search using embeddings
- Returns tool metadata and MCP server configs

**Main Files**:
- `server.py`: MCP server implementation
- `neo4j_retriever.py`: Graph query logic
- `embedder.py`: Text embedding generation

### Ingestion Pipeline (`Ingestion_pipeline/`)

Processes and ingests tool data into Neo4j:
- Parses MCP server tool definitions
- Generates embeddings for semantic search
- Builds graph relationships
- Categorizes vendors and tools

**Main Files**:
- `Ingestion_Neo4j.py`: Main ingestion script
- `Preprocess_parse_and_embed.py`: Data preprocessing
- `cluster_vendors_ingestion.py`: Vendor clustering

## Configuration Files

### Environment Variables (`.env`)

All configuration is done via environment variables. See `.env.example` for:
- Database connections (Neo4j, PostgreSQL, Redis)
- Service ports and hosts
- Security settings (JWT, API keys)
- Feature flags
- SaaS-specific settings

### MCP Configuration

- `config/mcp_client_config.json`: Client-side MCP server configuration
- `config/mcp_proxy_servers.json`: Proxy server definitions

**Note**: These files are gitignored. Use `.example` files as templates.

## Data Flow

```
1. Client Request
   ↓
2. API Gateway (Auth, Rate Limiting)
   ↓
3. Unified Gateway (Routing)
   ↓
4. Tool Retriever (Neo4j Query)
   ↓
5. Server Manager (Start/Route to MCP Server)
   ↓
6. MCP Proxy (HTTP → stdio)
   ↓
7. MCP Server (Tool Execution)
   ↓
8. Response back through chain
```

## Development Guidelines

### Adding New Features

1. **New MCP Server**: Add to `config/mcp_proxy_servers.json.example`
2. **New API Endpoint**: Add to `gateway/unified_gateway.py`
3. **New Tool Type**: Update ingestion pipeline in `Ingestion_pipeline/`
4. **New Graph Relationship**: Update Neo4j schema in `Dynamic_tool_retriever_MCP/`

### Code Organization

- **Services**: Business logic in dedicated modules
- **Utils**: Shared utilities and helpers
- **Tests**: Mirror directory structure
- **Docs**: Keep documentation up to date

### Naming Conventions

- **Files**: `snake_case.py`
- **Classes**: `PascalCase`
- **Functions**: `snake_case`
- **Constants**: `UPPER_SNAKE_CASE`
- **Private**: Prefix with `_`

## Testing Structure

```
tests/
├── unit/                      # Unit tests for individual components
│   ├── test_gateway.py
│   ├── test_server_manager.py
│   └── test_tool_retriever.py
│
├── integration/               # Integration tests
│   ├── test_gateway_integration.py
│   └── test_mcp_servers.py
│
└── e2e/                       # End-to-end tests
    └── test_full_workflow.py
```

## Deployment Structure

### Docker

- `Dockerfile`: Single-stage build for production
- `docker-compose.yml`: Full stack with all services

### Kubernetes (Future)

```
k8s/
├── deployments/              # Deployment manifests
├── services/                 # Service definitions
├── configmaps/               # Configuration
└── secrets/                  # Secrets (gitignored)
```

## Dependencies

### Python (`pyproject.toml`)

Core dependencies:
- `fastapi`: Web framework
- `mcp`: MCP protocol SDK
- `neo4j`: Graph database driver
- `pydantic`: Data validation
- `aiohttp`, `httpx`: HTTP clients

### Node.js (`package.json`)

- `@modelcontextprotocol/sdk`: MCP SDK for Node.js servers

## Migration Notes

### From Local to SaaS

1. **Multi-tenancy**: Add tenant context to all requests
2. **Authentication**: Implement API key/JWT validation
3. **Database**: Separate tenant data in PostgreSQL
4. **Caching**: Use Redis for multi-instance caching
5. **Monitoring**: Add Prometheus metrics and logging

### Breaking Changes

- Configuration moved to environment variables
- API versioning (`/v1/` prefix)
- Authentication required for all endpoints (SaaS mode)

