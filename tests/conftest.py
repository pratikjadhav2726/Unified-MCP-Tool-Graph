"""
Pytest configuration and fixtures for Unified MCP Tool Graph tests.
"""

import pytest
import asyncio
import os
from typing import AsyncGenerator
from unittest.mock import Mock, AsyncMock

# Set test environment variables
os.environ.setdefault("GATEWAY_PORT", "8000")
os.environ.setdefault("PROXY_PORT", "9000")
os.environ.setdefault("LOG_LEVEL", "DEBUG")
os.environ.setdefault("MOCK_MCP_SERVERS", "true")


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_neo4j_driver():
    """Mock Neo4j driver for testing."""
    driver = Mock()
    session = Mock()
    session.run = Mock(return_value=Mock(data=lambda: []))
    driver.session = Mock(return_value=session)
    return driver


@pytest.fixture
def mock_mcp_server():
    """Mock MCP server for testing."""
    server = AsyncMock()
    server.list_tools = AsyncMock(return_value=Mock(tools=[]))
    server.call_tool = AsyncMock(return_value=Mock(content=[{"text": "result"}]))
    return server


@pytest.fixture
def sample_tool_config():
    """Sample tool configuration for testing."""
    return {
        "name": "test_tool",
        "server": "test_server",
        "description": "A test tool",
        "parameters": {
            "type": "object",
            "properties": {}
        }
    }


@pytest.fixture
def sample_mcp_config():
    """Sample MCP server configuration for testing."""
    return {
        "mcpServers": {
            "test_server": {
                "type": "sse",
                "url": "http://localhost:9000/servers/test_server/sse",
                "timeout": 5
            }
        }
    }

