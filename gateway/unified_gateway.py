#!/usr/bin/env python3
"""
Working Unified MCP Gateway

A robust implementation that properly manages MCP server connections
using the official MCP Python SDK patterns, with dynamic tool retrieval
and automatic fallback to popular servers when Neo4j is unavailable.
"""

import sys
import os
import asyncio
import logging
import json
from typing import Dict, Any, List, Optional

# Add parent directory to Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mcp.server.fastmcp import FastMCP
from mcp.client.session import ClientSession
from mcp.client.sse import sse_client
from MCP_Server_Manager.mcp_server_manager import MCPServerManager

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("WorkingUnifiedMCPGateway")

class WorkingUnifiedMCPGateway:
    """A working unified MCP gateway that properly manages connections with dynamic tool retrieval."""
    
    def __init__(self):
        self.server = FastMCP("WorkingUnifiedMCPGateway")
        self.tool_catalog: Dict[str, Dict[str, Any]] = {}  # tool_name -> {server_name, tool_info, url}
        self.server_urls: Dict[str, str] = {}  # server_name -> url
        self.neo4j_available = self._check_neo4j_availability()
        self.register_meta_tools()
    
    def _check_neo4j_availability(self) -> bool:
        """Check if Neo4j is available for the dynamic tool retriever."""
        try:
            from dotenv import load_dotenv
            load_dotenv()
            
            neo4j_uri = os.getenv("NEO4J_URI")
            neo4j_user = os.getenv("NEO4J_USER")
            neo4j_password = os.getenv("NEO4J_PASSWORD")
            
            if not (neo4j_uri and neo4j_user and neo4j_password):
                logger.warning("Neo4j environment variables not set")
                return False
                
            # Try to import and test Neo4j connection
            from neo4j import GraphDatabase
            driver = GraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_password))
            with driver.session() as session:
                session.run("RETURN 1")
            driver.close()
            logger.info("Neo4j connection verified")
            return True
        except Exception as e:
            logger.warning(f"Neo4j not available: {e}")
            return False
    
    def _get_fallback_config(self) -> Dict[str, Any]:
        """Get fallback server configuration when Neo4j is not available."""
        return {
            "mcpServers": {
                "everything": {
                    "command": "npx",
                    "args": ["-y", "@modelcontextprotocol/server-everything"]
                },
                "sequential-thinking": {
                    "command": "npx",
                    "args": ["-y", "@modelcontextprotocol/server-sequential-thinking"]
                },
                "time": {
                    "command": "uvx",
                    "args": ["mcp-server-time"]
                }
            }
        }
    
    async def initialize_from_config(self, config_file: str = "mcp_client_config.json"):
        """Initialize the gateway from MCP client configuration with fallback support."""
        try:
            with open(config_file, 'r') as f:
                config = json.load(f)
        except FileNotFoundError:
            logger.warning(f"Configuration file {config_file} not found, using fallback")
            if not self.neo4j_available:
                # Use fallback configuration
                fallback_config = self._get_fallback_config()
                # Convert to client format
                config = {"mcpServers": {}}
                for server_name in fallback_config["mcpServers"]:
                    config["mcpServers"][server_name] = {
                        "type": "sse",
                        "url": f"http://localhost:9000/servers/{server_name}/sse",
                        "timeout": 5,
                        "sse_read_timeout": 300
                    }
            else:
                logger.error(f"Configuration file {config_file} not found and no fallback available")
                return
        
        servers_config = config.get("mcpServers", {})
        logger.info(f"Loading {len(servers_config)} servers from configuration")
        
        # Store server URLs
        for server_name, server_config in servers_config.items():
            if server_config.get("type") == "sse":
                self.server_urls[server_name] = server_config["url"]
        
        # Discover tools from each server
        await self._discover_tools()
        
        logger.info(f"Gateway initialized with {len(self.tool_catalog)} tools from {len(self.server_urls)} servers")
    
    async def _discover_tools(self):
        """Discover tools from all configured servers."""
        for server_name, url in self.server_urls.items():
            try:
                await self._discover_tools_from_server(server_name, url)
            except Exception as e:
                logger.warning(f"Failed to discover tools from {server_name}: {e}")
    
    async def _discover_tools_from_server(self, server_name: str, url: str):
        """Discover tools from a single server."""
        logger.info(f"Discovering tools from {server_name} at {url}")
        
        try:
            # Create a temporary connection to discover tools
            async with sse_client(url=url, timeout=10.0, sse_read_timeout=30.0) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    
                    # Get tools
                    tools_response = await session.list_tools()
                    tools = getattr(tools_response, "tools", [])
                    
                    for tool in tools:
                        tool_key = f"{server_name}.{tool.name}"
                        self.tool_catalog[tool_key] = {
                            "server_name": server_name,
                            "tool_name": tool.name,
                            "tool_info": tool,
                            "url": url,
                            "description": getattr(tool, "description", "")
                        }
                        logger.debug(f"Registered tool: {tool_key}")
                    
                    logger.info(f"✓ Discovered {len(tools)} tools from {server_name}")
                    
        except Exception as e:
            logger.error(f"✗ Failed to discover tools from {server_name}: {e}")
            raise
    
    async def call_tool_on_server(self, server_name: str, tool_name: str, arguments: dict) -> Any:
        """Call a tool on a specific server using a fresh connection."""
        url = self.server_urls.get(server_name)
        if not url:
            raise ValueError(f"Server {server_name} not configured")
        
        logger.info(f"Calling tool {tool_name} on {server_name} with args: {arguments}")
        
        try:
            # Create a fresh connection for this tool call
            async with sse_client(url=url, timeout=10.0, sse_read_timeout=300.0) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    
                    # Call the tool
                    result = await session.call_tool(tool_name, arguments)
                    logger.info(f"Tool call successful: {tool_name}")
                    return result
                    
        except Exception as e:
            logger.error(f"Error calling tool {tool_name} on {server_name}: {e}")
            raise
    
    async def route_tool_call(self, tool_name: str, args: dict) -> Any:
        """Route a tool call to the appropriate server."""
        logger.info(f"Routing tool call: {tool_name}")
        
        if tool_name not in self.tool_catalog:
            available_tools = list(self.tool_catalog.keys())
            logger.error(f"Tool '{tool_name}' not found. Available: {available_tools}")
            return {
                "error": f"Tool '{tool_name}' not found",
                "available_tools": available_tools
            }
        
        tool_info = self.tool_catalog[tool_name]
        server_name = tool_info["server_name"]
        actual_tool_name = tool_info["tool_name"]
        
        try:
            result = await self.call_tool_on_server(server_name, actual_tool_name, args)
            
            # Handle CallToolResult objects by extracting their content
            if hasattr(result, 'content'):
                if hasattr(result, 'isError') and result.isError:
                    return {"error": str(result.content)}
                else:
                    # Extract the actual content from the result
                    if result.content and len(result.content) > 0:
                        # Handle TextContent objects
                        content_item = result.content[0]
                        if hasattr(content_item, 'text'):
                            text_content = content_item.text
                            # Try to parse as JSON if it looks like JSON
                            if text_content.strip().startswith(('[', '{')):
                                try:
                                    import json
                                    return json.loads(text_content)
                                except (json.JSONDecodeError, ValueError):
                                    return text_content
                            return text_content
                        else:
                            return str(content_item)
                    return {"content": str(result.content)}
            
            return result
        except Exception as e:
            return {"error": str(e)}
    
    async def test_server_connection(self, server_name: str) -> Dict[str, Any]:
        """Test connection to a specific server (instance method)."""
        if server_name not in self.server_urls:
            return {"error": f"Server {server_name} not configured"}
        
        url = self.server_urls[server_name]
        try:
            async with sse_client(url=url, timeout=5.0) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    return {"status": "connected", "server": server_name, "url": url}
        except Exception as e:
            return {"status": "failed", "server": server_name, "error": str(e)}
    
    def register_meta_tools(self):
        """Register meta-tools for the gateway."""
        
        @self.server.tool()
        async def list_tools() -> List[Dict[str, Any]]:
            """List all available tools across all connected servers."""
            logger.info("list_tools called")
            tools = []
            for tool_key, tool_info in self.tool_catalog.items():
                tools.append({
                    "name": tool_key,
                    "description": tool_info["description"],
                    "server": tool_info["server_name"],
                    "actual_name": tool_info["tool_name"]
                })
            return tools
        
        @self.server.tool()
        async def call_tool(tool_name: str, args: dict) -> Any:
            """Call a specific tool by name."""
            logger.info(f"call_tool meta-tool called for: {tool_name}")
            return await self.route_tool_call(tool_name, args)
        
        @self.server.tool()
        async def get_server_status() -> Dict[str, Any]:
            """Get the status of all configured servers."""
            status = {}
            for server_name, url in self.server_urls.items():
                tools_count = len([t for t in self.tool_catalog.values() if t["server_name"] == server_name])
                status[server_name] = {
                    "url": url,
                    "tools_count": tools_count,
                    "configured": True,
                    "neo4j_available": self.neo4j_available
                }
            return status
        
        @self.server.tool()
        async def test_server_connection(server_name: str) -> Dict[str, Any]:
            """Test connection to a specific server."""
            if server_name not in self.server_urls:
                return {"error": f"Server {server_name} not configured"}
            
            url = self.server_urls[server_name]
            try:
                async with sse_client(url=url, timeout=5.0) as (read, write):
                    async with ClientSession(read, write) as session:
                        await session.initialize()
                        return {"status": "connected", "server": server_name, "url": url}
            except Exception as e:
                return {"status": "failed", "server": server_name, "error": str(e)}
        
        @self.server.tool()
        async def get_system_info() -> Dict[str, Any]:
            """Get information about the gateway system configuration."""
            return {
                "neo4j_available": self.neo4j_available,
                "total_servers": len(self.server_urls),
                "total_tools": len(self.tool_catalog),
                "servers": list(self.server_urls.keys()),
                "fallback_mode": not self.neo4j_available
            }

def start_mcp_servers():
    """Start the MCP server manager with popular servers and dynamic tool retriever."""
    PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    # Check Neo4j availability for dynamic configuration
    neo4j_available = False
    try:
        from dotenv import load_dotenv
        load_dotenv()
        neo4j_uri = os.getenv("NEO4J_URI")
        neo4j_user = os.getenv("NEO4J_USER")
        neo4j_password = os.getenv("NEO4J_PASSWORD")
        neo4j_available = bool(neo4j_uri and neo4j_user and neo4j_password)
    except:
        pass
    
    POPULAR_SERVERS = {}
    
    if neo4j_available:
        # Include dynamic tool retriever when Neo4j is available
        POPULAR_SERVERS.update({
            "dynamic-tool-retriever": {
                "command": "python",
                "args": [os.path.join(PROJECT_ROOT, "Dynamic_tool_retriever_MCP", "server.py")]
            },
            "sequential-thinking": {
                "command": "npx",
                "args": ["-y", "@modelcontextprotocol/server-sequential-thinking"]
            },
            "time": {
                "command": "uvx",
                "args": ["mcp-server-time"]
            }
        })
    else:
        # Fallback configuration without Neo4j dependency
        POPULAR_SERVERS.update({
            "everything": {
                "command": "npx",
                "args": ["-y", "@modelcontextprotocol/server-everything"]
            },
            "sequential-thinking": {
                "command": "npx",
                "args": ["-y", "@modelcontextprotocol/server-sequential-thinking"]
            },
            "time": {
                "command": "uvx",
                "args": ["mcp-server-time"]
            }
        })
    
    # Initialize and start server manager
    manager = MCPServerManager(popular_servers=POPULAR_SERVERS, proxy_port=9000)
    
    try:
        manager.start()
        logger.info("MCP Server Manager started successfully")
        if neo4j_available:
            logger.info("Running with Neo4j-enabled dynamic tool retriever")
        else:
            logger.info("Running in fallback mode with everything server")
        return manager
    except Exception as e:
        logger.error(f"Failed to start MCP Server Manager: {e}")
        return None

async def main():
    """Main function to run the working gateway."""
    logger.info("Starting Working Unified MCP Gateway...")
    
    # Start MCP servers
    manager = start_mcp_servers()
    if not manager:
        logger.error("Failed to start MCP servers")
        return
    
    # Wait for servers to start
    logger.info("Waiting for servers to start...")
    await asyncio.sleep(5)
    
    # Initialize gateway
    gateway = WorkingUnifiedMCPGateway()
    
    try:
        # Initialize from configuration
        await gateway.initialize_from_config("mcp_client_config.json")
        
        logger.info("=== Working Unified MCP Gateway Ready ===")
        logger.info(f"Available tools: {list(gateway.tool_catalog.keys())}")
        logger.info(f"Neo4j available: {gateway.neo4j_available}")
        logger.info("Starting FastMCP server on port 8000...")
        
        # Start the FastMCP server using async method to avoid event loop conflict
        import uvicorn
        config = uvicorn.Config(
            app=gateway.server.streamable_http_app,
            host="0.0.0.0",
            port=8000,
            log_level="info"
        )
        server = uvicorn.Server(config)
        await server.serve()
        
    except KeyboardInterrupt:
        logger.info("Received shutdown signal")
    except Exception as e:
        logger.error(f"Gateway error: {e}")
    finally:
        if manager:
            manager.stop()
        logger.info("Gateway shutdown complete")

if __name__ == "__main__":
    # Run the gateway
    asyncio.run(main())