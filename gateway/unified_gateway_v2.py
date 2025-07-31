#!/usr/bin/env python3
"""
Unified MCP Gateway - Production Ready Implementation

This is the canonical entrypoint for the Unified MCP Gateway system.
It provides a robust, production-ready implementation with:

- Configuration management via environment variables
- Authentication and rate limiting
- Comprehensive error handling and process monitoring
- Health checks and monitoring endpoints
- Integration with real and dummy tool retrievers
- Graceful degradation and recovery
- Process cleanup and orphan detection

Author: AI Assistant
Version: 2.0.0
"""

import sys
import os
import asyncio
import logging
import signal
from typing import Dict, Any, List, Optional
from pathlib import Path
from contextlib import asynccontextmanager

# Add parent directory to Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# FastAPI and MCP imports
from fastapi import FastAPI, HTTPException, Depends, Request, BackgroundTasks
from fastapi.responses import JSONResponse
from fastapi.middleware.base import BaseHTTPMiddleware
import uvicorn

# MCP SDK imports
from mcp.server.fastmcp import FastMCP
from mcp.client.session import ClientSession
from mcp.client.sse import sse_client

# Local imports
from gateway.config import config, create_env_template
from gateway.auth import SecurityMiddleware, setup_cors_middleware, create_security_headers_middleware
from gateway.error_handling import error_handler
from gateway.enhanced_tool_retriever import enhanced_retriever
from MCP_Server_Manager.mcp_server_manager import MCPServerManager

# Set up logging
logging.basicConfig(
    level=getattr(logging, config.log_level),
    format=config.log_format
)
logger = logging.getLogger("UnifiedMCPGateway")

class UnifiedMCPGateway:
    """
    Production-ready Unified MCP Gateway.
    
    This class provides a comprehensive gateway implementation that manages
    multiple MCP servers, handles authentication, provides error recovery,
    and offers monitoring capabilities.
    """
    
    def __init__(self):
        self.app = FastAPI(
            title="Unified MCP Gateway",
            description="Production-ready gateway for Model Context Protocol servers",
            version="2.0.0",
            docs_url="/docs" if not config.api_key else None,  # Disable docs in production
            redoc_url="/redoc" if not config.api_key else None
        )
        
        # Initialize components
        self.security = SecurityMiddleware(config.api_key, config.rate_limit)
        self.server_manager: Optional[MCPServerManager] = None
        self.tool_catalog: Dict[str, Dict[str, Any]] = {}
        self.server_urls: Dict[str, str] = {}
        self.background_tasks = set()
        
        # Setup middleware and routes
        self._setup_middleware()
        self._setup_routes()
        self._setup_error_handlers()
        
        logger.info("Unified MCP Gateway initialized")
    
    def _setup_middleware(self):
        """Setup all middleware components."""
        # CORS middleware
        setup_cors_middleware(self.app, config.cors_origins)
        
        # Security headers
        self.app.add_middleware(BaseHTTPMiddleware, dispatch=create_security_headers_middleware())
        
        # Request logging middleware
        @self.app.middleware("http")
        async def log_requests(request: Request, call_next):
            start_time = asyncio.get_event_loop().time()
            
            # Log request
            logger.info(f"Request: {request.method} {request.url.path}")
            
            response = await call_next(request)
            
            # Log response
            process_time = asyncio.get_event_loop().time() - start_time
            logger.info(f"Response: {response.status_code} ({process_time:.3f}s)")
            
            # Add timing header
            response.headers["X-Process-Time"] = str(process_time)
            
            return response
    
    def _setup_routes(self):
        """Setup all API routes."""
        auth_dependency = self.security.create_auth_dependency()
        
        @self.app.get("/")
        async def root():
            """Root endpoint with basic information."""
            return {
                "name": "Unified MCP Gateway",
                "version": "2.0.0",
                "status": "operational",
                "endpoints": {
                    "health": "/health",
                    "tools": "/tools",
                    "servers": "/servers",
                    "call": "/call"
                }
            }
        
        @self.app.get("/health")
        async def health_check():
            """Comprehensive health check endpoint."""
            try:
                # Get system health from error handler
                system_health = await error_handler.get_system_health()
                
                # Get tool retriever health
                retriever_health = await enhanced_retriever.health_check()
                
                # Get server manager status
                server_status = {}
                if self.server_manager:
                    endpoints = self.server_manager.get_client_endpoints()
                    for name, url in endpoints.items():
                        try:
                            # Quick connection test
                            async with sse_client(url=url, timeout=2.0) as (read, write):
                                async with ClientSession(read, write) as session:
                                    await session.initialize()
                                    server_status[name] = {"status": "healthy", "url": url}
                        except Exception as e:
                            server_status[name] = {"status": "unhealthy", "error": str(e), "url": url}
                
                health_data = {
                    "status": "healthy" if system_health["overall_status"] == "healthy" else "degraded",
                    "timestamp": system_health["timestamp"],
                    "components": {
                        "system": system_health,
                        "tool_retriever": retriever_health,
                        "servers": server_status
                    },
                    "metrics": {
                        "total_servers": len(server_status),
                        "healthy_servers": len([s for s in server_status.values() if s["status"] == "healthy"]),
                        "total_tools": len(self.tool_catalog)
                    }
                }
                
                status_code = 200 if health_data["status"] == "healthy" else 503
                return JSONResponse(content=health_data, status_code=status_code)
                
            except Exception as e:
                logger.error(f"Health check failed: {e}")
                return JSONResponse(
                    content={"status": "error", "message": str(e)},
                    status_code=500
                )
        
        @self.app.get("/tools")
        async def list_tools(auth: dict = Depends(auth_dependency)):
            """List all available tools across all servers."""
            try:
                tools = []
                for tool_key, tool_info in self.tool_catalog.items():
                    tools.append({
                        "name": tool_key,
                        "description": tool_info.get("description", ""),
                        "server": tool_info.get("server_name", ""),
                        "actual_name": tool_info.get("tool_name", "")
                    })
                
                return {
                    "tools": tools,
                    "total": len(tools),
                    "servers": list(set(tool["server"] for tool in tools))
                }
            except Exception as e:
                logger.error(f"Failed to list tools: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.get("/servers")
        async def list_servers(auth: dict = Depends(auth_dependency)):
            """List all configured servers and their status."""
            try:
                servers = {}
                if self.server_manager:
                    endpoints = self.server_manager.get_client_endpoints()
                    for name, url in endpoints.items():
                        tools_count = len([t for t in self.tool_catalog.values() 
                                         if t.get("server_name") == name])
                        servers[name] = {
                            "url": url,
                            "tools_count": tools_count,
                            "status": "configured"
                        }
                
                return {"servers": servers, "total": len(servers)}
            except Exception as e:
                logger.error(f"Failed to list servers: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.post("/call")
        async def call_tool(
            request: dict,
            auth: dict = Depends(auth_dependency)
        ):
            """Call a specific tool."""
            try:
                tool_name = request.get("tool")
                arguments = request.get("arguments", {})
                
                if not tool_name:
                    raise HTTPException(status_code=400, detail="Tool name is required")
                
                # Route the tool call
                result = await self.route_tool_call(tool_name, arguments)
                
                return {
                    "tool": tool_name,
                    "arguments": arguments,
                    "result": result,
                    "status": "success"
                }
                
            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"Tool call failed: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.post("/retrieve-tools")
        async def retrieve_tools(
            request: dict,
            auth: dict = Depends(auth_dependency)
        ):
            """Retrieve relevant tools for a task description."""
            try:
                task_description = request.get("task_description")
                top_k = request.get("top_k", 3)
                official_only = request.get("official_only", False)
                
                if not task_description:
                    raise HTTPException(status_code=400, detail="Task description is required")
                
                # Use enhanced retriever
                tools = await enhanced_retriever.retrieve_tools(
                    task_description, top_k, official_only
                )
                
                return {
                    "task_description": task_description,
                    "tools": tools,
                    "count": len(tools)
                }
                
            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"Tool retrieval failed: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.post("/admin/restart-server")
        async def restart_server(
            request: dict,
            auth: dict = Depends(auth_dependency)
        ):
            """Restart a specific server (admin only)."""
            # Check admin permissions
            user = auth.get("user", {})
            if "admin" not in user.get("permissions", []):
                raise HTTPException(status_code=403, detail="Admin access required")
            
            server_name = request.get("server_name")
            if not server_name:
                raise HTTPException(status_code=400, detail="Server name is required")
            
            try:
                # Attempt to restart the server
                success = await self._restart_server(server_name)
                
                return {
                    "server_name": server_name,
                    "restart_success": success,
                    "message": "Server restart initiated" if success else "Server restart failed"
                }
                
            except Exception as e:
                logger.error(f"Server restart failed: {e}")
                raise HTTPException(status_code=500, detail=str(e))
    
    def _setup_error_handlers(self):
        """Setup global error handlers."""
        
        @self.app.exception_handler(HTTPException)
        async def http_exception_handler(request: Request, exc: HTTPException):
            return JSONResponse(
                status_code=exc.status_code,
                content={"error": exc.detail, "status_code": exc.status_code}
            )
        
        @self.app.exception_handler(Exception)
        async def general_exception_handler(request: Request, exc: Exception):
            logger.error(f"Unhandled exception: {exc}", exc_info=True)
            return JSONResponse(
                status_code=500,
                content={"error": "Internal server error", "status_code": 500}
            )
    
    async def initialize(self):
        """Initialize the gateway and all its components."""
        logger.info("Initializing Unified MCP Gateway...")
        
        try:
            # Start MCP server manager
            await self._start_server_manager()
            
            # Wait for servers to start
            await asyncio.sleep(5)
            
            # Discover tools from all servers
            await self._discover_tools()
            
            # Start background monitoring
            await self._start_background_tasks()
            
            logger.info(f"Gateway initialized with {len(self.tool_catalog)} tools from {len(self.server_urls)} servers")
            
        except Exception as e:
            logger.error(f"Gateway initialization failed: {e}")
            raise
    
    async def _start_server_manager(self):
        """Start the MCP server manager with configured servers."""
        # Convert config servers to manager format
        popular_servers = {}
        for name, server_config in config.popular_servers.items():
            if server_config.enabled:
                popular_servers[name] = {
                    "command": server_config.command,
                    "args": server_config.args,
                    "env": server_config.env,
                    "cwd": server_config.cwd
                }
        
        # Initialize server manager
        self.server_manager = MCPServerManager(
            popular_servers=popular_servers,
            proxy_port=config.proxy_port
        )
        
        # Register error recovery strategies
        for server_name in popular_servers.keys():
            error_handler.register_recovery_strategy(
                server_name,
                lambda: self._restart_server(server_name)
            )
        
        # Start the manager
        self.server_manager.start()
        
        # Store server URLs for tool discovery
        self.server_urls = self.server_manager.get_client_endpoints()
        
        logger.info(f"Started MCP server manager with {len(popular_servers)} servers")
    
    async def _discover_tools(self):
        """Discover tools from all configured servers."""
        discovery_tasks = []
        for server_name, url in self.server_urls.items():
            discovery_tasks.append(self._discover_tools_from_server(server_name, url))
        
        # Run discovery in parallel
        results = await asyncio.gather(*discovery_tasks, return_exceptions=True)
        
        successful_discoveries = 0
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                server_name = list(self.server_urls.keys())[i]
                logger.warning(f"Failed to discover tools from {server_name}: {result}")
            else:
                successful_discoveries += 1
        
        logger.info(f"Tool discovery completed: {successful_discoveries}/{len(self.server_urls)} servers successful")
    
    async def _discover_tools_from_server(self, server_name: str, url: str):
        """Discover tools from a single server."""
        async with error_handler.error_context(server_name, "tool_discovery"):
            logger.info(f"Discovering tools from {server_name} at {url}")
            
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
                    
                    logger.info(f"✓ Discovered {len(tools)} tools from {server_name}")
    
    async def route_tool_call(self, tool_name: str, arguments: dict) -> Any:
        """Route a tool call to the appropriate server."""
        if tool_name not in self.tool_catalog:
            # Try to find similar tool names
            available_tools = list(self.tool_catalog.keys())
            similar_tools = [t for t in available_tools if tool_name.lower() in t.lower()]
            
            error_msg = f"Tool '{tool_name}' not found"
            if similar_tools:
                error_msg += f". Similar tools: {similar_tools[:3]}"
            
            raise HTTPException(status_code=404, detail=error_msg)
        
        tool_info = self.tool_catalog[tool_name]
        server_name = tool_info["server_name"]
        actual_tool_name = tool_info["tool_name"]
        url = tool_info["url"]
        
        async with error_handler.error_context(server_name, f"tool_call:{actual_tool_name}"):
            logger.info(f"Calling tool {actual_tool_name} on {server_name}")
            
            async with sse_client(url=url, timeout=10.0, sse_read_timeout=300.0) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    
                    # Call the tool
                    result = await session.call_tool(actual_tool_name, arguments)
                    
                    # Process the result
                    return self._process_tool_result(result)
    
    def _process_tool_result(self, result: Any) -> Any:
        """Process and normalize tool call results."""
        if hasattr(result, 'content'):
            if hasattr(result, 'isError') and result.isError:
                raise HTTPException(status_code=500, detail=str(result.content))
            
            # Extract content from MCP result objects
            if result.content and len(result.content) > 0:
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
    
    async def _restart_server(self, server_name: str) -> bool:
        """Restart a specific server."""
        if not self.server_manager:
            return False
        
        try:
            logger.info(f"Restarting server: {server_name}")
            
            # Remove and re-add the server (this restarts it)
            server_config = None
            for name, cfg in config.popular_servers.items():
                if name == server_name and cfg.enabled:
                    server_config = {
                        "command": cfg.command,
                        "args": cfg.args,
                        "env": cfg.env,
                        "cwd": cfg.cwd
                    }
                    break
            
            if server_config:
                self.server_manager.remove_server(server_name)
                await asyncio.sleep(2)
                self.server_manager.add_server(server_name, server_config)
                
                # Update URLs and rediscover tools
                self.server_urls = self.server_manager.get_client_endpoints()
                await asyncio.sleep(3)
                
                if server_name in self.server_urls:
                    await self._discover_tools_from_server(server_name, self.server_urls[server_name])
                
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Failed to restart server {server_name}: {e}")
            return False
    
    async def _start_background_tasks(self):
        """Start background monitoring and maintenance tasks."""
        # Health monitoring task
        health_task = asyncio.create_task(
            error_handler.start_health_monitoring(config.health_check_interval)
        )
        self.background_tasks.add(health_task)
        health_task.add_done_callback(self.background_tasks.discard)
        
        # Server cleanup task
        cleanup_task = asyncio.create_task(self._periodic_cleanup())
        self.background_tasks.add(cleanup_task)
        cleanup_task.add_done_callback(self.background_tasks.discard)
        
        logger.info("Background monitoring tasks started")
    
    async def _periodic_cleanup(self):
        """Periodic cleanup of idle servers and orphaned processes."""
        while True:
            try:
                await asyncio.sleep(config.server_idle_timeout)
                
                if self.server_manager:
                    # Clean up idle dynamic servers
                    self.server_manager.cleanup_idle(ttl=config.server_idle_timeout)
                
                # Clean up orphaned processes
                await error_handler.process_monitor.cleanup_orphaned_processes()
                
            except Exception as e:
                logger.error(f"Periodic cleanup error: {e}")
    
    async def shutdown(self):
        """Graceful shutdown of the gateway."""
        logger.info("Starting graceful shutdown...")
        
        try:
            # Cancel background tasks
            for task in self.background_tasks:
                task.cancel()
            
            # Wait for tasks to complete
            if self.background_tasks:
                await asyncio.gather(*self.background_tasks, return_exceptions=True)
            
            # Stop server manager
            if self.server_manager:
                self.server_manager.stop()
            
            logger.info("Graceful shutdown completed")
            
        except Exception as e:
            logger.error(f"Error during shutdown: {e}")

# Global gateway instance
gateway = UnifiedMCPGateway()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan management."""
    # Startup
    await gateway.initialize()
    
    yield
    
    # Shutdown
    await gateway.shutdown()

# Update the app with lifespan
gateway.app.router.lifespan_context = lifespan

async def main():
    """Main function to run the gateway."""
    logger.info("Starting Unified MCP Gateway v2.0...")
    
    # Create environment template if it doesn't exist
    if not Path(".env").exists():
        create_env_template()
        logger.info("Created .env.template - please copy to .env and configure")
    
    # Setup signal handlers for graceful shutdown
    def signal_handler(signum, frame):
        logger.info(f"Received signal {signum}, initiating shutdown...")
        asyncio.create_task(gateway.shutdown())
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Configure uvicorn
    uvicorn_config = uvicorn.Config(
        app=gateway.app,
        host=config.host,
        port=config.port,
        log_level=config.log_level.lower(),
        access_log=True,
        lifespan="on"
    )
    
    # Start the server
    server = uvicorn.Server(uvicorn_config)
    
    try:
        await server.serve()
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt")
    finally:
        await gateway.shutdown()

if __name__ == "__main__":
    asyncio.run(main())