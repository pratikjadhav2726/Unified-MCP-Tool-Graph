"""
Unit tests for the unified gateway.
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from gateway.unified_gateway import WorkingUnifiedMCPGateway


@pytest.mark.asyncio
async def test_gateway_initialization():
    """Test gateway initialization."""
    gateway = WorkingUnifiedMCPGateway()
    assert gateway is not None
    assert gateway.server is not None


@pytest.mark.asyncio
async def test_neo4j_availability_check():
    """Test Neo4j availability check."""
    gateway = WorkingUnifiedMCPGateway()
    
    # Test with Neo4j unavailable
    with patch.dict('os.environ', {}, clear=True):
        available = gateway._check_neo4j_availability()
        assert isinstance(available, bool)


@pytest.mark.asyncio
async def test_fallback_config():
    """Test fallback configuration generation."""
    gateway = WorkingUnifiedMCPGateway()
    config = gateway._get_fallback_config()
    
    assert "mcpServers" in config
    assert "everything" in config["mcpServers"]
    assert "time" in config["mcpServers"]


@pytest.mark.asyncio
async def test_tool_catalog_initialization():
    """Test tool catalog is initialized."""
    gateway = WorkingUnifiedMCPGateway()
    assert isinstance(gateway.tool_catalog, dict)
    assert isinstance(gateway.server_urls, dict)

