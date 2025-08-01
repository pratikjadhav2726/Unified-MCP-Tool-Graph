#!/usr/bin/env python3
"""
Unified MCP Gateway Startup Script

This script starts the complete MCP unified gateway system including:
1. Environment validation
2. Dependency checking
3. MCP server manager initialization
4. Dynamic tool retriever (with Neo4j fallback)
5. Unified gateway server

The system automatically falls back to the "everything" server configuration
when Neo4j is not available, ensuring the gateway always works.
"""

import sys
import os
import asyncio
import logging
import subprocess
import time
from pathlib import Path
from typing import Optional

# Add local bin to PATH for installed packages
local_bin = os.path.expanduser("~/.local/bin")
if local_bin not in os.environ.get("PATH", ""):
    os.environ["PATH"] = f"{local_bin}:{os.environ.get('PATH', '')}"

# Add project directories to Python path
PROJECT_ROOT = Path(__file__).parent.absolute()
sys.path.append(str(PROJECT_ROOT))
sys.path.append(str(PROJECT_ROOT / "gateway"))
sys.path.append(str(PROJECT_ROOT / "MCP_Server_Manager"))
sys.path.append(str(PROJECT_ROOT / "Dynamic_tool_retriever_MCP"))

def setup_logging():
    """Setup logging configuration."""
    from dotenv import load_dotenv
    load_dotenv()
    
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    logging.basicConfig(
        level=getattr(logging, log_level, logging.INFO),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    return logging.getLogger("UnifiedGatewayStartup")

def check_dependencies():
    """Check if required dependencies are installed."""
    logger = logging.getLogger("UnifiedGatewayStartup")
    
    required_packages = [
        "mcp",
        "fastapi", 
        "uvicorn",
        "python-dotenv",
        "aiohttp",
        "httpx",
        "pydantic"
    ]
    
    optional_packages = [
        ("neo4j", "Neo4j database connectivity"),
        ("sentence_transformers", "Local text embeddings for dynamic tool retrieval")
    ]
    
    missing_required = []
    missing_optional = []
    
    for package in required_packages:
        try:
            __import__(package.replace("-", "_"))
        except ImportError:
            missing_required.append(package)
    
    for package, description in optional_packages:
        try:
            __import__(package.replace("-", "_"))
        except ImportError:
            missing_optional.append((package, description))
    
    if missing_required:
        logger.error(f"Missing required packages: {missing_required}")
        logger.error("Install with: pip install --break-system-packages " + " ".join(missing_required))
        return False
    
    if missing_optional:
        logger.warning("Missing optional packages:")
        for package, description in missing_optional:
            logger.warning(f"  - {package}: {description}")
        logger.warning("System will run in fallback mode without these packages")
    
    return True

def check_node_dependencies():
    """Check if required Node.js packages are available."""
    logger = logging.getLogger("UnifiedGatewayStartup")
    
    # Check if npx is available
    try:
        subprocess.run(["npx", "--version"], check=True, capture_output=True)
        logger.info("✓ npx is available")
    except (subprocess.CalledProcessError, FileNotFoundError):
        logger.error("✗ npx not found. Please install Node.js and npm")
        return False
    
    # Check if uvx is available (optional)
    try:
        subprocess.run(["uvx", "--version"], check=True, capture_output=True)
        logger.info("✓ uvx is available")
    except (subprocess.CalledProcessError, FileNotFoundError):
        logger.warning("✗ uvx not found. Some servers may not be available")
        logger.warning("Install with: pip install --break-system-packages uv")
    
    return True

def validate_environment():
    """Validate environment configuration."""
    logger = logging.getLogger("UnifiedGatewayStartup")
    
    from dotenv import load_dotenv
    load_dotenv()
    
    # Check Neo4j configuration (optional)
    neo4j_uri = os.getenv("NEO4J_URI")
    neo4j_user = os.getenv("NEO4J_USER") 
    neo4j_password = os.getenv("NEO4J_PASSWORD")
    
    neo4j_configured = bool(neo4j_uri and neo4j_user and neo4j_password)
    
    if neo4j_configured:
        logger.info("✓ Neo4j configuration found - dynamic tool retriever will be enabled")
        try:
            from neo4j import GraphDatabase
            driver = GraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_password))
            with driver.session() as session:
                session.run("RETURN 1")
            driver.close()
            logger.info("✓ Neo4j connection verified")
        except Exception as e:
            logger.warning(f"✗ Neo4j connection failed: {e}")
            logger.warning("System will fallback to everything server")
            neo4j_configured = False
    else:
        logger.info("ℹ Neo4j not configured - using fallback mode with everything server")
    
    # Validate ports
    gateway_port = int(os.getenv("GATEWAY_PORT", 8000))
    proxy_port = int(os.getenv("PROXY_PORT", 9000))
    
    logger.info(f"Gateway will run on port {gateway_port}")
    logger.info(f"Proxy will run on port {proxy_port}")
    
    return {
        "neo4j_available": neo4j_configured,
        "gateway_port": gateway_port,
        "proxy_port": proxy_port
    }

def install_mcp_proxy():
    """Install mcp-proxy if not available."""
    logger = logging.getLogger("UnifiedGatewayStartup")
    
    try:
        # Check if mcp-proxy is already installed
        subprocess.run(["mcp-proxy", "--version"], check=True, capture_output=True)
        logger.info("✓ mcp-proxy is already available")
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        logger.info("Installing mcp-proxy...")
        try:
            subprocess.run(["pip", "install", "--break-system-packages", "mcp-proxy"], check=True)
            logger.info("✓ mcp-proxy installed successfully")
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"✗ Failed to install mcp-proxy: {e}")
            return False

async def start_gateway_system():
    """Start the complete gateway system."""
    logger = logging.getLogger("UnifiedGatewayStartup")
    
    try:
        # Import after path setup
        from gateway.unified_gateway import main as gateway_main
        
        logger.info("🚀 Starting Unified MCP Gateway System...")
        await gateway_main()
        
    except KeyboardInterrupt:
        logger.info("🛑 System shutdown requested")
    except Exception as e:
        logger.error(f"💥 System error: {e}")
        raise

def main():
    """Main startup function."""
    logger = setup_logging()
    logger.info("=" * 60)
    logger.info("🚀 MCP Unified Gateway System Startup")
    logger.info("=" * 60)
    
    # Step 1: Check dependencies
    logger.info("📦 Checking Python dependencies...")
    if not check_dependencies():
        logger.error("❌ Dependency check failed")
        sys.exit(1)
    
    # Step 2: Check Node.js dependencies
    logger.info("📦 Checking Node.js dependencies...")
    if not check_node_dependencies():
        logger.error("❌ Node.js dependency check failed")
        sys.exit(1)
    
    # Step 3: Install mcp-proxy if needed
    logger.info("📦 Checking mcp-proxy...")
    if not install_mcp_proxy():
        logger.error("❌ mcp-proxy installation failed")
        sys.exit(1)
    
    # Step 4: Validate environment
    logger.info("🔧 Validating environment configuration...")
    env_config = validate_environment()
    
    # Step 5: Show system configuration
    logger.info("⚙️  System Configuration:")
    logger.info(f"   • Neo4j Available: {env_config['neo4j_available']}")
    logger.info(f"   • Gateway Port: {env_config['gateway_port']}")
    logger.info(f"   • Proxy Port: {env_config['proxy_port']}")
    
    if env_config['neo4j_available']:
        logger.info("   • Mode: Full (with dynamic tool retriever)")
    else:
        logger.info("   • Mode: Fallback (using everything server)")
    
    logger.info("=" * 60)
    logger.info("✅ All checks passed! Starting gateway system...")
    logger.info("=" * 60)
    
    # Step 6: Start the system
    try:
        asyncio.run(start_gateway_system())
    except KeyboardInterrupt:
        logger.info("👋 Goodbye!")
    except Exception as e:
        logger.error(f"💥 Fatal error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()