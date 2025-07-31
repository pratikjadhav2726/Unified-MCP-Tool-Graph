#!/usr/bin/env python3
"""
Python Client Example for Unified MCP Gateway

This example demonstrates how to interact with the Unified MCP Gateway
using Python. It shows various usage patterns including:

- Authentication
- Tool discovery
- Tool invocation
- Error handling
- Health monitoring
- Dynamic tool retrieval
"""

import asyncio
import aiohttp
import json
import time
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class GatewayConfig:
    """Configuration for the gateway client."""
    base_url: str = "http://localhost:8000"
    api_key: Optional[str] = None
    timeout: int = 30

class UnifiedMCPClient:
    """
    Python client for the Unified MCP Gateway.
    
    This client provides a convenient interface for interacting with
    the gateway API, including authentication, error handling, and
    response processing.
    """
    
    def __init__(self, config: GatewayConfig):
        self.config = config
        self.session: Optional[aiohttp.ClientSession] = None
        
    async def __aenter__(self):
        """Async context manager entry."""
        await self.connect()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.disconnect()
    
    async def connect(self):
        """Initialize the HTTP session."""
        headers = {}
        if self.config.api_key:
            headers["Authorization"] = f"Bearer {self.config.api_key}"
        
        timeout = aiohttp.ClientTimeout(total=self.config.timeout)
        self.session = aiohttp.ClientSession(
            base_url=self.config.base_url,
            headers=headers,
            timeout=timeout
        )
        
        logger.info(f"Connected to gateway at {self.config.base_url}")
    
    async def disconnect(self):
        """Close the HTTP session."""
        if self.session:
            await self.session.close()
            self.session = None
            logger.info("Disconnected from gateway")
    
    async def _request(self, method: str, path: str, **kwargs) -> Dict[str, Any]:
        """Make an HTTP request with error handling."""
        if not self.session:
            raise RuntimeError("Client not connected. Use async context manager or call connect()")
        
        try:
            async with self.session.request(method, path, **kwargs) as response:
                # Handle rate limiting
                if response.status == 429:
                    retry_after = int(response.headers.get("Retry-After", "60"))
                    logger.warning(f"Rate limited. Retry after {retry_after} seconds")
                    raise Exception(f"Rate limited. Retry after {retry_after} seconds")
                
                # Parse response
                if response.content_type == "application/json":
                    data = await response.json()
                else:
                    data = {"text": await response.text()}
                
                # Handle HTTP errors
                if response.status >= 400:
                    error_msg = data.get("error", f"HTTP {response.status}")
                    logger.error(f"Request failed: {error_msg}")
                    raise Exception(f"Request failed: {error_msg}")
                
                return data
        
        except aiohttp.ClientError as e:
            logger.error(f"Network error: {e}")
            raise Exception(f"Network error: {e}")
    
    async def get_info(self) -> Dict[str, Any]:
        """Get basic gateway information."""
        return await self._request("GET", "/")
    
    async def health_check(self) -> Dict[str, Any]:
        """Get comprehensive health status."""
        return await self._request("GET", "/health")
    
    async def list_tools(self) -> List[Dict[str, Any]]:
        """List all available tools."""
        response = await self._request("GET", "/tools")
        return response.get("tools", [])
    
    async def list_servers(self) -> Dict[str, Any]:
        """List all configured servers."""
        response = await self._request("GET", "/servers")
        return response.get("servers", {})
    
    async def call_tool(self, tool_name: str, arguments: Dict[str, Any] = None) -> Any:
        """Call a specific tool."""
        if arguments is None:
            arguments = {}
        
        payload = {
            "tool": tool_name,
            "arguments": arguments
        }
        
        response = await self._request("POST", "/call", json=payload)
        return response.get("result")
    
    async def retrieve_tools(
        self, 
        task_description: str, 
        top_k: int = 3, 
        official_only: bool = False
    ) -> List[Dict[str, Any]]:
        """Retrieve relevant tools for a task."""
        payload = {
            "task_description": task_description,
            "top_k": top_k,
            "official_only": official_only
        }
        
        response = await self._request("POST", "/retrieve-tools", json=payload)
        return response.get("tools", [])
    
    async def wait_for_healthy(self, max_wait: int = 60, check_interval: int = 5) -> bool:
        """Wait for the gateway to become healthy."""
        start_time = time.time()
        
        while time.time() - start_time < max_wait:
            try:
                health = await self.health_check()
                if health.get("status") == "healthy":
                    logger.info("Gateway is healthy")
                    return True
                else:
                    logger.info(f"Gateway status: {health.get('status')}")
            except Exception as e:
                logger.warning(f"Health check failed: {e}")
            
            await asyncio.sleep(check_interval)
        
        logger.error(f"Gateway did not become healthy within {max_wait} seconds")
        return False

async def demo_basic_usage():
    """Demonstrate basic gateway usage."""
    print("=== Basic Usage Demo ===")
    
    config = GatewayConfig(
        base_url="http://localhost:8000",
        # api_key="your-api-key-here"  # Uncomment if authentication is enabled
    )
    
    async with UnifiedMCPClient(config) as client:
        # Get gateway info
        info = await client.get_info()
        print(f"Gateway: {info['name']} v{info['version']}")
        
        # Check health
        health = await client.health_check()
        print(f"Health Status: {health['status']}")
        print(f"Total Tools: {health['metrics']['total_tools']}")
        print(f"Healthy Servers: {health['metrics']['healthy_servers']}/{health['metrics']['total_servers']}")
        
        # List available tools
        tools = await client.list_tools()
        print(f"\nAvailable Tools ({len(tools)}):")
        for tool in tools[:5]:  # Show first 5 tools
            print(f"  - {tool['name']}: {tool['description'][:60]}...")
        
        if len(tools) > 5:
            print(f"  ... and {len(tools) - 5} more tools")

async def demo_tool_invocation():
    """Demonstrate tool invocation."""
    print("\n=== Tool Invocation Demo ===")
    
    config = GatewayConfig()
    
    async with UnifiedMCPClient(config) as client:
        # Find a time tool
        tools = await client.list_tools()
        time_tool = None
        
        for tool in tools:
            if "time" in tool["name"].lower():
                time_tool = tool["name"]
                break
        
        if time_tool:
            print(f"Calling tool: {time_tool}")
            try:
                result = await client.call_tool(time_tool, {"timezone": "UTC"})
                print(f"Result: {result}")
            except Exception as e:
                print(f"Tool call failed: {e}")
        else:
            print("No time tool found")
        
        # Try calling a non-existent tool
        print("\nTrying to call non-existent tool...")
        try:
            await client.call_tool("non.existent.tool")
        except Exception as e:
            print(f"Expected error: {e}")

async def demo_tool_retrieval():
    """Demonstrate dynamic tool retrieval."""
    print("\n=== Tool Retrieval Demo ===")
    
    config = GatewayConfig()
    
    async with UnifiedMCPClient(config) as client:
        # Retrieve tools for web search
        print("Retrieving tools for: 'search the web for AI news'")
        tools = await client.retrieve_tools(
            "search the web for AI news",
            top_k=3,
            official_only=False
        )
        
        print(f"Found {len(tools)} relevant tools:")
        for tool in tools:
            print(f"  - {tool.get('tool_name', 'Unknown')}: {tool.get('tool_description', 'No description')[:60]}...")
        
        # Retrieve tools for file operations
        print("\nRetrieving tools for: 'read and process files'")
        tools = await client.retrieve_tools("read and process files", top_k=2)
        
        print(f"Found {len(tools)} relevant tools:")
        for tool in tools:
            print(f"  - {tool.get('tool_name', 'Unknown')}: {tool.get('tool_description', 'No description')[:60]}...")

async def demo_error_handling():
    """Demonstrate error handling."""
    print("\n=== Error Handling Demo ===")
    
    config = GatewayConfig()
    
    async with UnifiedMCPClient(config) as client:
        # Test various error conditions
        error_tests = [
            ("Invalid tool call", lambda: client.call_tool("invalid.tool")),
            ("Empty task description", lambda: client.retrieve_tools("")),
            ("Malformed request", lambda: client._request("POST", "/call", json={"invalid": "data"})),
        ]
        
        for test_name, test_func in error_tests:
            print(f"\nTesting: {test_name}")
            try:
                await test_func()
                print("  ✗ Expected error but got success")
            except Exception as e:
                print(f"  ✓ Caught expected error: {e}")

async def demo_monitoring():
    """Demonstrate monitoring capabilities."""
    print("\n=== Monitoring Demo ===")
    
    config = GatewayConfig()
    
    async with UnifiedMCPClient(config) as client:
        # Get detailed health information
        health = await client.health_check()
        
        print("System Health:")
        print(f"  Overall Status: {health['status']}")
        print(f"  Timestamp: {health['timestamp']}")
        
        # System component health
        system = health['components']['system']
        print(f"  System Status: {system['overall_status']}")
        print(f"  Orphaned Processes: {system['orphaned_processes']}")
        
        # Tool retriever health
        retriever = health['components']['tool_retriever']
        print(f"  Tool Retriever Status: {retriever['status']}")
        
        real_retriever = retriever['retrievers']['real']
        dummy_retriever = retriever['retrievers']['dummy']
        print(f"    Real Retriever: {'✓' if real_retriever['available'] else '✗'} ({'enabled' if real_retriever['enabled'] else 'disabled'})")
        print(f"    Dummy Retriever: {'✓' if dummy_retriever['available'] else '✗'} ({'enabled' if dummy_retriever['enabled'] else 'disabled'})")
        
        # Server health
        servers = health['components']['servers']
        print(f"  Server Health:")
        for server_name, server_info in servers.items():
            status_icon = "✓" if server_info['status'] == 'healthy' else '✗'
            print(f"    {server_name}: {status_icon} {server_info['status']}")

async def demo_complete_workflow():
    """Demonstrate a complete workflow."""
    print("\n=== Complete Workflow Demo ===")
    
    config = GatewayConfig()
    
    async with UnifiedMCPClient(config) as client:
        # Wait for gateway to be ready
        print("Waiting for gateway to be healthy...")
        if not await client.wait_for_healthy(max_wait=30):
            print("Gateway is not healthy, continuing anyway...")
        
        # Step 1: Discover available capabilities
        print("\n1. Discovering available tools...")
        tools = await client.list_tools()
        servers = await client.list_servers()
        
        print(f"   Found {len(tools)} tools across {len(servers)} servers")
        
        # Step 2: Find relevant tools for a task
        print("\n2. Finding tools for task: 'get current time information'")
        relevant_tools = await client.retrieve_tools(
            "get current time information",
            top_k=3
        )
        
        print(f"   Found {len(relevant_tools)} relevant tools")
        
        # Step 3: Execute a tool
        print("\n3. Executing a tool...")
        
        # Find a time-related tool from discovered tools
        time_tool = None
        for tool in tools:
            if "time" in tool["name"].lower():
                time_tool = tool["name"]
                break
        
        if time_tool:
            try:
                result = await client.call_tool(time_tool, {"timezone": "UTC"})
                print(f"   Tool '{time_tool}' result: {result}")
            except Exception as e:
                print(f"   Tool execution failed: {e}")
        else:
            print("   No time tool available for execution")
        
        # Step 4: Monitor system health
        print("\n4. Checking system health...")
        health = await client.health_check()
        
        healthy_servers = health['metrics']['healthy_servers']
        total_servers = health['metrics']['total_servers']
        total_tools = health['metrics']['total_tools']
        
        print(f"   System Status: {health['status']}")
        print(f"   Servers: {healthy_servers}/{total_servers} healthy")
        print(f"   Tools: {total_tools} available")
        
        print("\n✓ Workflow completed successfully!")

async def main():
    """Run all demonstrations."""
    print("Unified MCP Gateway - Python Client Demo")
    print("=" * 50)
    
    try:
        await demo_basic_usage()
        await demo_tool_invocation()
        await demo_tool_retrieval()
        await demo_error_handling()
        await demo_monitoring()
        await demo_complete_workflow()
        
        print("\n" + "=" * 50)
        print("All demos completed successfully!")
        
    except Exception as e:
        print(f"\nDemo failed with error: {e}")
        logger.exception("Demo error details:")

if __name__ == "__main__":
    # Run the demo
    asyncio.run(main())