"""
SaaS MCP Server - Multi-Tenant MCP Server Implementation

This module implements a SaaS-hosted MCP server that can:
1. Accept connections from multiple tenants
2. Route tool calls to underlying MCP servers
3. Aggregate tools from multiple servers
4. Enforce tenant isolation and rate limits
"""

import os
import asyncio
import logging
import json
from typing import Dict, Any, List, Optional
from datetime import datetime
from uuid import uuid4

from mcp.server.fastmcp import FastMCP
from mcp.client.session import ClientSession
from mcp.client.sse import sse_client
from pydantic import BaseModel, Field

# Import existing components
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from MCP_Server_Manager.mcp_server_manager import MCPServerManager
from gateway.authentication import AuthenticationMiddleware, AuthenticationError

logger = logging.getLogger("SaaSMCPServer")


class TenantContext(BaseModel):
    """Tenant context for multi-tenancy."""
    tenant_id: str
    api_key: Optional[str] = None
    enabled_servers: List[str] = []
    rate_limit_per_minute: int = 60
    rate_limit_per_hour: int = 1000
    custom_tools: List[Dict[str, Any]] = []


class SaaSMCPServer:
    """
    Multi-tenant SaaS MCP Server.
    
    This server acts as a gateway that:
    - Accepts MCP client connections
    - Identifies tenants from connection context
    - Routes tool calls to underlying MCP servers
    - Aggregates tools from multiple servers
    - Enforces tenant isolation and rate limits
    """
    
    def __init__(self, enable_auth: bool = True):
        self.server = FastMCP("SaaS-MCP-Gateway")
        self.tenant_contexts: Dict[str, TenantContext] = {}
        self.connection_tenant_map: Dict[str, str] = {}  # connection_id -> tenant_id
        self.underlying_servers: Dict[str, Dict[str, Any]] = {}  # tenant_id -> {server_name: config}
        self.server_manager = MCPServerManager()
        self.tool_catalog: Dict[str, Dict[str, Any]] = {}  # tool_name -> {tenant_id, server_name, tool_info}
        
        # Authentication middleware
        self.enable_auth = enable_auth
        if enable_auth:
            self.auth_middleware = AuthenticationMiddleware()
        else:
            self.auth_middleware = None
        
        # Register meta-tools
        self._register_tools()
    
    def _register_tools(self):
        """Register SaaS MCP server tools."""
        
        @self.server.tool()
        async def list_tools() -> List[Dict[str, Any]]:
            """
            List all available tools for the current tenant.
            
            Aggregates tools from all enabled MCP servers for the tenant.
            """
            tenant_id = self._get_current_tenant()
            if not tenant_id:
                return []
            
            tenant = self.tenant_contexts.get(tenant_id)
            if not tenant:
                return []
            
            # Aggregate tools from all enabled servers
            all_tools = []
            for server_name in tenant.enabled_servers:
                server_tools = await self._get_tools_from_server(tenant_id, server_name)
                all_tools.extend(server_tools)
            
            # Add custom tenant tools
            all_tools.extend(tenant.custom_tools)
            
            logger.info(f"Listed {len(all_tools)} tools for tenant {tenant_id}")
            return all_tools
        
        @self.server.tool()
        async def call_tool(tool_name: str, args: dict) -> Any:
            """
            Call a tool, routing to the appropriate underlying MCP server.
            
            Args:
                tool_name: Name of the tool to call (format: server.tool_name)
                args: Arguments for the tool
                
            Returns:
                Tool execution result
            """
            tenant_id = self._get_current_tenant()
            if not tenant_id:
                raise ValueError("No tenant context available")
            
            tenant = self.tenant_contexts.get(tenant_id)
            if not tenant:
                raise ValueError(f"Tenant {tenant_id} not found")
            
            # Check rate limits
            if not await self._check_rate_limit(tenant_id):
                raise RuntimeError("Rate limit exceeded")
            
            # Parse tool name (format: server.tool_name or just tool_name)
            if "." in tool_name:
                server_name, actual_tool_name = tool_name.split(".", 1)
            else:
                # Find server that has this tool
                server_name = self._find_server_for_tool(tenant_id, tool_name)
                actual_tool_name = tool_name
            
            if not server_name:
                raise ValueError(f"Tool {tool_name} not found for tenant {tenant_id}")
            
            # Route to underlying server
            result = await self._call_underlying_server(
                tenant_id,
                server_name,
                actual_tool_name,
                args
            )
            
            # Log usage
            await self._log_tool_usage(tenant_id, tool_name, success=result is not None)
            
            return result
        
        @self.server.tool()
        async def get_tenant_info() -> Dict[str, Any]:
            """Get information about the current tenant."""
            tenant_id = self._get_current_tenant()
            if not tenant_id:
                return {"error": "No tenant context"}
            
            tenant = self.tenant_contexts.get(tenant_id)
            if not tenant:
                return {"error": "Tenant not found"}
            
            return {
                "tenant_id": tenant.tenant_id,
                "enabled_servers": tenant.enabled_servers,
                "rate_limits": {
                    "per_minute": tenant.rate_limit_per_minute,
                    "per_hour": tenant.rate_limit_per_hour
                },
                "custom_tools_count": len(tenant.custom_tools)
            }
    
    def _get_current_tenant(self) -> Optional[str]:
        """
        Get current tenant ID from connection context.
        
        In a real implementation, this would extract tenant from:
        - Connection headers (JWT token)
        - URL path (/tenants/{tenant_id}/sse)
        - Connection metadata
        """
        # If authentication is enabled, get from auth middleware
        if self.enable_auth and self.auth_middleware:
            connection_id = self._get_connection_id()
            tenant_info = self.auth_middleware.get_tenant_context(connection_id)
            if tenant_info:
                return tenant_info.get("tenant_id")
        
        # Fallback: return first tenant (single-tenant mode)
        if self.tenant_contexts:
            return list(self.tenant_contexts.keys())[0]
        return None
    
    def _get_connection_id(self) -> str:
        """Get current connection ID."""
        # TODO: Implement proper connection ID extraction from FastMCP context
        # This is a placeholder
        return "default"
    
    def register_tenant(
        self,
        tenant_id: str,
        enabled_servers: List[str],
        api_key: Optional[str] = None,
        rate_limit_per_minute: int = 60,
        rate_limit_per_hour: int = 1000
    ):
        """Register a tenant with their configuration."""
        tenant = TenantContext(
            tenant_id=tenant_id,
            api_key=api_key,
            enabled_servers=enabled_servers,
            rate_limit_per_minute=rate_limit_per_minute,
            rate_limit_per_hour=rate_limit_per_hour
        )
        self.tenant_contexts[tenant_id] = tenant
        
        # Initialize underlying servers for this tenant
        asyncio.create_task(self._initialize_tenant_servers(tenant_id))
        
        logger.info(f"Registered tenant {tenant_id} with {len(enabled_servers)} servers")
    
    async def _initialize_tenant_servers(self, tenant_id: str):
        """Initialize underlying MCP servers for a tenant."""
        tenant = self.tenant_contexts.get(tenant_id)
        if not tenant:
            return
        
        self.underlying_servers[tenant_id] = {}
        
        for server_name in tenant.enabled_servers:
            try:
                # Get server config from server manager
                server_config = await self.server_manager.get_server_config(server_name)
                if server_config:
                    self.underlying_servers[tenant_id][server_name] = server_config
                    # Discover tools from this server
                    await self._discover_tools_from_server(tenant_id, server_name)
            except Exception as e:
                logger.error(f"Failed to initialize server {server_name} for tenant {tenant_id}: {e}")
    
    async def _discover_tools_from_server(self, tenant_id: str, server_name: str):
        """Discover tools from an underlying MCP server."""
        server_config = self.underlying_servers.get(tenant_id, {}).get(server_name)
        if not server_config:
            return
        
        try:
            url = server_config.get("url")
            if not url:
                return
            
            async with sse_client(url=url, timeout=15.0) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    tools_response = await session.list_tools()
                    tools = getattr(tools_response, "tools", [])
                    
                    for tool in tools:
                        tool_key = f"{server_name}.{tool.name}"
                        self.tool_catalog[tool_key] = {
                            "tenant_id": tenant_id,
                            "server_name": server_name,
                            "tool_name": tool.name,
                            "description": getattr(tool, "description", ""),
                            "inputSchema": getattr(tool, "inputSchema", None)
                        }
                    
                    logger.info(f"Discovered {len(tools)} tools from {server_name} for tenant {tenant_id}")
        except Exception as e:
            logger.error(f"Failed to discover tools from {server_name}: {e}")
    
    async def _get_tools_from_server(self, tenant_id: str, server_name: str) -> List[Dict[str, Any]]:
        """Get tools from a specific server for a tenant."""
        tools = []
        for tool_key, tool_info in self.tool_catalog.items():
            if (tool_info["tenant_id"] == tenant_id and 
                tool_info["server_name"] == server_name):
                tools.append({
                    "name": tool_key,
                    "description": tool_info["description"],
                    "inputSchema": tool_info.get("inputSchema")
                })
        return tools
    
    def _find_server_for_tool(self, tenant_id: str, tool_name: str) -> Optional[str]:
        """Find which server has a specific tool for a tenant."""
        for tool_key, tool_info in self.tool_catalog.items():
            if (tool_info["tenant_id"] == tenant_id and 
                tool_key.endswith(f".{tool_name}") or tool_key == tool_name):
                return tool_info["server_name"]
        return None
    
    async def _call_underlying_server(
        self,
        tenant_id: str,
        server_name: str,
        tool_name: str,
        args: dict
    ) -> Any:
        """Call a tool on an underlying MCP server."""
        server_config = self.underlying_servers.get(tenant_id, {}).get(server_name)
        if not server_config:
            raise ValueError(f"Server {server_name} not configured for tenant {tenant_id}")
        
        url = server_config.get("url")
        if not url:
            raise ValueError(f"No URL configured for server {server_name}")
        
        try:
            async with sse_client(url=url, timeout=30.0) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    result = await session.call_tool(tool_name, args)
                    
                    # Extract content from result
                    if hasattr(result, 'content') and result.content:
                        content_item = result.content[0]
                        if hasattr(content_item, 'text'):
                            return content_item.text
                        return str(content_item)
                    
                    return result
        except Exception as e:
            logger.error(f"Error calling tool {tool_name} on {server_name}: {e}")
            raise
    
    async def _check_rate_limit(self, tenant_id: str) -> bool:
        """Check if tenant has exceeded rate limits."""
        # TODO: Implement Redis-based rate limiting
        # For now, always return True
        return True
    
    async def _log_tool_usage(self, tenant_id: str, tool_name: str, success: bool):
        """Log tool usage for analytics."""
        # TODO: Implement usage logging to database
        logger.info(f"Tool usage: tenant={tenant_id}, tool={tool_name}, success={success}")
    
    def run(self, transport: str = "stdio"):
        """Run the SaaS MCP server."""
        logger.info("Starting SaaS MCP Server...")
        self.server.run(transport=transport)


async def main():
    """Main entry point for SaaS MCP Server."""
    server = SaaSMCPServer()
    
    # Example: Register a tenant
    # In production, this would come from database
    server.register_tenant(
        tenant_id="tenant-123",
        enabled_servers=["time", "everything"],
        rate_limit_per_minute=60,
        rate_limit_per_hour=1000
    )
    
    # Run server
    server.run(transport="stdio")


if __name__ == "__main__":
    asyncio.run(main())

