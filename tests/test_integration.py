"""
Comprehensive Integration Tests for Unified MCP Gateway

These tests validate the complete end-to-end workflow including:
- Server startup and discovery
- Tool discovery and cataloging
- Tool invocation and result processing
- Error handling and recovery
- Health monitoring
- Authentication and rate limiting
"""

import pytest
import asyncio
import httpx
import json
import time
from typing import Dict, Any
from pathlib import Path
import subprocess
import signal
import os
import sys

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from gateway.unified_gateway_v2 import UnifiedMCPGateway
from gateway.config import config
from gateway.auth import SecurityMiddleware

class TestIntegration:
    """Integration tests for the Unified MCP Gateway."""
    
    @pytest.fixture(scope="class")
    async def gateway(self):
        """Start the gateway for testing."""
        gateway = UnifiedMCPGateway()
        
        # Initialize the gateway
        await gateway.initialize()
        
        # Wait for everything to be ready
        await asyncio.sleep(10)
        
        yield gateway
        
        # Cleanup
        await gateway.shutdown()
    
    @pytest.fixture(scope="class")
    def client(self, gateway):
        """HTTP client for testing the gateway API."""
        base_url = f"http://{config.host}:{config.port}"
        return httpx.AsyncClient(base_url=base_url)
    
    @pytest.fixture
    def auth_headers(self):
        """Authentication headers for API requests."""
        if config.api_key:
            # Generate a test API key
            security = SecurityMiddleware(config.api_key, config.rate_limit)
            test_key = security.api_key_manager.generate_api_key("test_user", ["read", "write"])
            return {"Authorization": f"Bearer {test_key}"}
        return {}

class TestBasicFunctionality(TestIntegration):
    """Test basic gateway functionality."""
    
    @pytest.mark.asyncio
    async def test_root_endpoint(self, client):
        """Test the root endpoint returns basic information."""
        response = await client.get("/")
        assert response.status_code == 200
        
        data = response.json()
        assert data["name"] == "Unified MCP Gateway"
        assert data["version"] == "2.0.0"
        assert data["status"] == "operational"
        assert "endpoints" in data
    
    @pytest.mark.asyncio
    async def test_health_endpoint(self, client):
        """Test the health check endpoint."""
        response = await client.get("/health")
        assert response.status_code in [200, 503]  # Healthy or degraded
        
        data = response.json()
        assert "status" in data
        assert "timestamp" in data
        assert "components" in data
        assert "metrics" in data
        
        # Check component structure
        components = data["components"]
        assert "system" in components
        assert "tool_retriever" in components
        assert "servers" in components

class TestAuthentication(TestIntegration):
    """Test authentication and authorization."""
    
    @pytest.mark.asyncio
    async def test_unauthenticated_request(self, client):
        """Test that protected endpoints require authentication."""
        if not config.api_key:
            pytest.skip("Authentication not enabled in config")
        
        response = await client.get("/tools")
        assert response.status_code == 401
    
    @pytest.mark.asyncio
    async def test_authenticated_request(self, client, auth_headers):
        """Test that authenticated requests work."""
        response = await client.get("/tools", headers=auth_headers)
        assert response.status_code == 200
    
    @pytest.mark.asyncio
    async def test_rate_limiting(self, client, auth_headers):
        """Test rate limiting functionality."""
        # Make many requests quickly
        responses = []
        for _ in range(config.rate_limit + 5):
            response = await client.get("/", headers=auth_headers)
            responses.append(response)
        
        # Should eventually get rate limited
        rate_limited = any(r.status_code == 429 for r in responses)
        if config.rate_limit > 0:
            assert rate_limited, "Rate limiting should have been triggered"

class TestToolDiscovery(TestIntegration):
    """Test tool discovery functionality."""
    
    @pytest.mark.asyncio
    async def test_list_tools(self, client, auth_headers):
        """Test listing all available tools."""
        response = await client.get("/tools", headers=auth_headers)
        assert response.status_code == 200
        
        data = response.json()
        assert "tools" in data
        assert "total" in data
        assert "servers" in data
        
        # Should have some tools
        assert data["total"] > 0
        assert len(data["tools"]) > 0
        
        # Check tool structure
        for tool in data["tools"]:
            assert "name" in tool
            assert "description" in tool
            assert "server" in tool
            assert "actual_name" in tool
    
    @pytest.mark.asyncio
    async def test_list_servers(self, client, auth_headers):
        """Test listing all configured servers."""
        response = await client.get("/servers", headers=auth_headers)
        assert response.status_code == 200
        
        data = response.json()
        assert "servers" in data
        assert "total" in data
        
        # Should have some servers
        assert data["total"] > 0
        
        # Check server structure
        for server_name, server_info in data["servers"].items():
            assert "url" in server_info
            assert "tools_count" in server_info
            assert "status" in server_info

class TestToolInvocation(TestIntegration):
    """Test tool invocation functionality."""
    
    @pytest.mark.asyncio
    async def test_call_time_tool(self, client, auth_headers):
        """Test calling the time tool."""
        # First get available tools to find the time tool
        tools_response = await client.get("/tools", headers=auth_headers)
        tools_data = tools_response.json()
        
        # Find a time-related tool
        time_tool = None
        for tool in tools_data["tools"]:
            if "time" in tool["name"].lower():
                time_tool = tool["name"]
                break
        
        if not time_tool:
            pytest.skip("No time tool available")
        
        # Call the tool
        call_data = {
            "tool": time_tool,
            "arguments": {"timezone": "UTC"}
        }
        
        response = await client.post("/call", json=call_data, headers=auth_headers)
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "success"
        assert data["tool"] == time_tool
        assert "result" in data
    
    @pytest.mark.asyncio
    async def test_call_nonexistent_tool(self, client, auth_headers):
        """Test calling a tool that doesn't exist."""
        call_data = {
            "tool": "nonexistent.tool",
            "arguments": {}
        }
        
        response = await client.post("/call", json=call_data, headers=auth_headers)
        assert response.status_code == 404
        
        data = response.json()
        assert "error" in data
        assert "not found" in data["error"].lower()
    
    @pytest.mark.asyncio
    async def test_call_tool_with_invalid_arguments(self, client, auth_headers):
        """Test calling a tool with invalid arguments."""
        # Get a tool first
        tools_response = await client.get("/tools", headers=auth_headers)
        tools_data = tools_response.json()
        
        if not tools_data["tools"]:
            pytest.skip("No tools available")
        
        tool_name = tools_data["tools"][0]["name"]
        
        # Call with invalid arguments
        call_data = {
            "tool": tool_name,
            "arguments": {"invalid_param": "invalid_value"}
        }
        
        response = await client.post("/call", json=call_data, headers=auth_headers)
        # May succeed or fail depending on the tool, but should not crash
        assert response.status_code in [200, 400, 500]

class TestToolRetrieval(TestIntegration):
    """Test dynamic tool retrieval functionality."""
    
    @pytest.mark.asyncio
    async def test_retrieve_tools_for_web_search(self, client, auth_headers):
        """Test retrieving tools for web search task."""
        request_data = {
            "task_description": "search the web for information about AI",
            "top_k": 3,
            "official_only": False
        }
        
        response = await client.post("/retrieve-tools", json=request_data, headers=auth_headers)
        assert response.status_code == 200
        
        data = response.json()
        assert data["task_description"] == request_data["task_description"]
        assert "tools" in data
        assert "count" in data
        
        # Should return some tools
        assert data["count"] > 0
        assert len(data["tools"]) > 0
        
        # Check tool structure
        for tool in data["tools"]:
            assert "tool_name" in tool
            assert "tool_description" in tool
    
    @pytest.mark.asyncio
    async def test_retrieve_tools_for_file_operations(self, client, auth_headers):
        """Test retrieving tools for file operations."""
        request_data = {
            "task_description": "read and process files",
            "top_k": 2
        }
        
        response = await client.post("/retrieve-tools", json=request_data, headers=auth_headers)
        assert response.status_code == 200
        
        data = response.json()
        assert data["count"] > 0
    
    @pytest.mark.asyncio
    async def test_retrieve_tools_empty_description(self, client, auth_headers):
        """Test retrieving tools with empty description."""
        request_data = {
            "task_description": "",
            "top_k": 1
        }
        
        response = await client.post("/retrieve-tools", json=request_data, headers=auth_headers)
        assert response.status_code == 400

class TestErrorHandling(TestIntegration):
    """Test error handling and recovery."""
    
    @pytest.mark.asyncio
    async def test_malformed_request(self, client, auth_headers):
        """Test handling of malformed requests."""
        # Send invalid JSON
        response = await client.post(
            "/call", 
            content="invalid json", 
            headers={**auth_headers, "Content-Type": "application/json"}
        )
        assert response.status_code == 422  # Unprocessable Entity
    
    @pytest.mark.asyncio
    async def test_missing_required_fields(self, client, auth_headers):
        """Test handling of missing required fields."""
        # Call tool without tool name
        response = await client.post("/call", json={"arguments": {}}, headers=auth_headers)
        assert response.status_code == 400
        
        data = response.json()
        assert "error" in data
    
    @pytest.mark.asyncio
    async def test_system_health_under_load(self, client, auth_headers):
        """Test system health under load."""
        # Make multiple concurrent requests
        tasks = []
        for _ in range(10):
            task = client.get("/health")
            tasks.append(task)
        
        responses = await asyncio.gather(*tasks)
        
        # All health checks should complete
        for response in responses:
            assert response.status_code in [200, 503]

class TestMonitoring(TestIntegration):
    """Test monitoring and observability features."""
    
    @pytest.mark.asyncio
    async def test_health_check_components(self, client):
        """Test detailed health check components."""
        response = await client.get("/health")
        data = response.json()
        
        components = data["components"]
        
        # System health
        system = components["system"]
        assert "overall_status" in system
        assert "servers" in system
        
        # Tool retriever health
        retriever = components["tool_retriever"]
        assert "status" in retriever
        assert "retrievers" in retriever
        
        # Server status
        servers = components["servers"]
        for server_name, server_info in servers.items():
            assert "status" in server_info
            assert "url" in server_info
    
    @pytest.mark.asyncio
    async def test_metrics_collection(self, client):
        """Test metrics collection in health endpoint."""
        response = await client.get("/health")
        data = response.json()
        
        metrics = data["metrics"]
        assert "total_servers" in metrics
        assert "healthy_servers" in metrics
        assert "total_tools" in metrics
        
        # Metrics should be reasonable
        assert metrics["total_servers"] >= 0
        assert metrics["healthy_servers"] >= 0
        assert metrics["total_tools"] >= 0
        assert metrics["healthy_servers"] <= metrics["total_servers"]

class TestEndToEndWorkflow(TestIntegration):
    """Test complete end-to-end workflows."""
    
    @pytest.mark.asyncio
    async def test_complete_tool_workflow(self, client, auth_headers):
        """Test a complete workflow: discover -> retrieve -> call."""
        # Step 1: List available tools
        tools_response = await client.get("/tools", headers=auth_headers)
        assert tools_response.status_code == 200
        tools_data = tools_response.json()
        
        # Step 2: Retrieve tools for a specific task
        retrieve_response = await client.post(
            "/retrieve-tools",
            json={"task_description": "get current time", "top_k": 3},
            headers=auth_headers
        )
        assert retrieve_response.status_code == 200
        retrieve_data = retrieve_response.json()
        
        # Step 3: Find a tool to call
        available_tools = [tool["name"] for tool in tools_data["tools"]]
        if available_tools:
            tool_to_call = available_tools[0]
            
            # Step 4: Call the tool
            call_response = await client.post(
                "/call",
                json={"tool": tool_to_call, "arguments": {}},
                headers=auth_headers
            )
            # Should succeed or fail gracefully
            assert call_response.status_code in [200, 400, 404, 500]
    
    @pytest.mark.asyncio
    async def test_error_recovery_workflow(self, client, auth_headers):
        """Test error recovery in workflows."""
        # Try to call a non-existent tool
        error_response = await client.post(
            "/call",
            json={"tool": "non.existent.tool", "arguments": {}},
            headers=auth_headers
        )
        assert error_response.status_code == 404
        
        # System should still be healthy after error
        health_response = await client.get("/health")
        health_data = health_response.json()
        
        # System should recover and remain operational
        assert health_data["status"] in ["healthy", "degraded"]

# Test configuration and utilities
@pytest.fixture(scope="session")
def event_loop():
    """Create an event loop for the test session."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()

def pytest_configure():
    """Configure pytest with custom markers."""
    pytest.main.add_option(
        "--integration", 
        action="store_true", 
        help="Run integration tests"
    )

def pytest_collection_modifyitems(config, items):
    """Modify test collection based on options."""
    if not config.getoption("--integration"):
        # Skip integration tests if not explicitly requested
        skip_integration = pytest.mark.skip(reason="Integration tests not requested")
        for item in items:
            if "integration" in item.nodeid:
                item.add_marker(skip_integration)

if __name__ == "__main__":
    # Run tests directly
    pytest.main([__file__, "-v", "--integration"])