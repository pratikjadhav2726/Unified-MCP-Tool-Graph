"""
Production Configuration Management for Unified MCP Gateway

This module provides a comprehensive configuration system that:
- Uses environment variables for all sensitive data
- Supports different environments (dev, staging, prod)
- Provides sensible defaults
- Validates configuration on startup
"""

import os
import json
import logging
from typing import Dict, Any, List, Optional
from pathlib import Path
from pydantic import BaseModel, Field, validator
from dotenv import load_dotenv

# Load environment variables from .env file if it exists
load_dotenv()

logger = logging.getLogger(__name__)

class ServerConfig(BaseModel):
    """Configuration for a single MCP server."""
    command: str
    args: List[str] = Field(default_factory=list)
    env: Dict[str, str] = Field(default_factory=dict)
    cwd: Optional[str] = None
    enabled: bool = True
    timeout: int = 30
    
class GatewayConfig(BaseModel):
    """Main configuration for the Unified MCP Gateway."""
    
    # Server settings
    host: str = Field(default="0.0.0.0", description="Gateway host address")
    port: int = Field(default=8000, description="Gateway port")
    proxy_port: int = Field(default=9000, description="MCP proxy port")
    
    # Security settings
    api_key: Optional[str] = Field(default=None, description="API key for authentication")
    cors_origins: List[str] = Field(default=["*"], description="CORS allowed origins")
    rate_limit: int = Field(default=100, description="Rate limit per minute")
    
    # Database settings
    neo4j_uri: str = Field(default="bolt://localhost:7687", description="Neo4j connection URI")
    neo4j_user: str = Field(default="neo4j", description="Neo4j username")
    neo4j_password: str = Field(default="password", description="Neo4j password")
    
    # Tool retriever settings
    use_real_retriever: bool = Field(default=True, description="Use real Neo4j retriever or fallback to dummy")
    fallback_to_dummy: bool = Field(default=True, description="Fallback to dummy retriever on Neo4j failure")
    
    # Server management
    server_idle_timeout: int = Field(default=600, description="Idle timeout for dynamic servers (seconds)")
    max_dynamic_servers: int = Field(default=20, description="Maximum number of dynamic servers")
    
    # Monitoring
    health_check_interval: int = Field(default=60, description="Health check interval (seconds)")
    enable_metrics: bool = Field(default=True, description="Enable metrics collection")
    
    # Logging
    log_level: str = Field(default="INFO", description="Logging level")
    log_format: str = Field(default="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    
    # Popular servers configuration
    popular_servers: Dict[str, ServerConfig] = Field(default_factory=dict)
    
    @validator('log_level')
    def validate_log_level(cls, v):
        valid_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
        if v.upper() not in valid_levels:
            raise ValueError(f'log_level must be one of {valid_levels}')
        return v.upper()
    
    @validator('port', 'proxy_port')
    def validate_ports(cls, v):
        if not (1024 <= v <= 65535):
            raise ValueError('Port must be between 1024 and 65535')
        return v

def load_config() -> GatewayConfig:
    """Load configuration from environment variables and defaults."""
    
    # Build popular servers configuration from environment
    popular_servers = {
        "tavily-mcp": ServerConfig(
            command="npx",
            args=["-y", "tavily-mcp@latest"],
            env={"TAVILY_API_KEY": os.getenv("TAVILY_API_KEY", "")},
            enabled=bool(os.getenv("TAVILY_API_KEY"))
        ),
        "sequential-thinking": ServerConfig(
            command="npx",
            args=["-y", "@modelcontextprotocol/server-sequential-thinking"],
            enabled=True
        ),
        "time": ServerConfig(
            command="uvx",
            args=["mcp-server-time"],
            enabled=True
        ),
        "server-everything": ServerConfig(
            command="uvx",
            args=["mcp-server-everything-search"],
            env={"EVERYTHING_SDK_PATH": os.getenv("EVERYTHING_SDK_PATH", "")},
            enabled=bool(os.getenv("EVERYTHING_SDK_PATH", True))  # Enable by default for dummy
        ),
        "dynamic-tool-retriever": ServerConfig(
            command="python",
            args=[str(Path(__file__).parent.parent / "Dynamic_tool_retriever_MCP" / "server.py")],
            enabled=True
        )
    }
    
    config = GatewayConfig(
        host=os.getenv("GATEWAY_HOST", "0.0.0.0"),
        port=int(os.getenv("GATEWAY_PORT", "8000")),
        proxy_port=int(os.getenv("PROXY_PORT", "9000")),
        api_key=os.getenv("GATEWAY_API_KEY"),
        cors_origins=os.getenv("CORS_ORIGINS", "*").split(","),
        rate_limit=int(os.getenv("RATE_LIMIT", "100")),
        neo4j_uri=os.getenv("NEO4J_URI", "bolt://localhost:7687"),
        neo4j_user=os.getenv("NEO4J_USER", "neo4j"),
        neo4j_password=os.getenv("NEO4J_PASSWORD", "password"),
        use_real_retriever=os.getenv("USE_REAL_RETRIEVER", "true").lower() == "true",
        fallback_to_dummy=os.getenv("FALLBACK_TO_DUMMY", "true").lower() == "true",
        server_idle_timeout=int(os.getenv("SERVER_IDLE_TIMEOUT", "600")),
        max_dynamic_servers=int(os.getenv("MAX_DYNAMIC_SERVERS", "20")),
        health_check_interval=int(os.getenv("HEALTH_CHECK_INTERVAL", "60")),
        enable_metrics=os.getenv("ENABLE_METRICS", "true").lower() == "true",
        log_level=os.getenv("LOG_LEVEL", "INFO"),
        popular_servers=popular_servers
    )
    
    # Validate configuration
    _validate_config(config)
    
    return config

def _validate_config(config: GatewayConfig):
    """Validate configuration and log warnings for missing optional settings."""
    
    # Check for required API keys if servers are enabled
    if config.popular_servers["tavily-mcp"].enabled and not config.popular_servers["tavily-mcp"].env.get("TAVILY_API_KEY"):
        logger.warning("TAVILY_API_KEY not set - Tavily server will be disabled")
        config.popular_servers["tavily-mcp"].enabled = False
    
    # Check Neo4j connection if using real retriever
    if config.use_real_retriever:
        if not all([config.neo4j_uri, config.neo4j_user, config.neo4j_password]):
            logger.warning("Neo4j credentials incomplete - will fallback to dummy retriever")
            if not config.fallback_to_dummy:
                raise ValueError("Neo4j credentials required when fallback_to_dummy is False")
    
    # Log configuration summary
    enabled_servers = [name for name, server in config.popular_servers.items() if server.enabled]
    logger.info(f"Configuration loaded - Enabled servers: {enabled_servers}")
    logger.info(f"Gateway will run on {config.host}:{config.port}")
    logger.info(f"Proxy will run on port {config.proxy_port}")

def create_env_template():
    """Create a .env template file with all available configuration options."""
    template = """# Unified MCP Gateway Configuration Template
# Copy this file to .env and fill in your values

# === Server Configuration ===
GATEWAY_HOST=0.0.0.0
GATEWAY_PORT=8000
PROXY_PORT=9000

# === Security ===
# GATEWAY_API_KEY=your-secret-api-key-here
CORS_ORIGINS=*
RATE_LIMIT=100

# === Database (Neo4j) ===
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=password

# === Tool Retriever Settings ===
USE_REAL_RETRIEVER=true
FALLBACK_TO_DUMMY=true

# === Server Management ===
SERVER_IDLE_TIMEOUT=600
MAX_DYNAMIC_SERVERS=20

# === Monitoring ===
HEALTH_CHECK_INTERVAL=60
ENABLE_METRICS=true

# === Logging ===
LOG_LEVEL=INFO

# === External API Keys ===
# Required for Tavily search functionality
# TAVILY_API_KEY=your-tavily-api-key-here

# Required for Everything search functionality (optional)
# EVERYTHING_SDK_PATH=/path/to/everything/sdk
"""
    
    env_path = Path(".env.template")
    with open(env_path, "w") as f:
        f.write(template)
    
    logger.info(f"Environment template created at {env_path}")
    return env_path

# Global config instance
config = load_config()