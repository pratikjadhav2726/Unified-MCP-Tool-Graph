#!/usr/bin/env python3
"""
Dummy Tool Retriever MCP Server

A simple mock implementation that returns dummy tool suggestions
without requiring Neo4j or external dependencies.
"""

import asyncio
import logging
from mcp.server.fastmcp import FastMCP

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("DummyToolRetriever")

# Create the MCP server
server = FastMCP("dummy-tool-retriever")

@server.tool()
async def dynamic_tool_retriever(task_description: str, top_k: int = 3) -> list:
    """
    Mock dynamic tool retriever that returns dummy tool suggestions.
    
    Args:
        task_description: Description of the task needing tools
        top_k: Number of tools to return (default: 3)
    
    Returns:
        List of mock tool configurations
    """
    logger.info(f"Mock tool retrieval for: {task_description} (top_k={top_k})")
    
    # Mock tool suggestions based on task description keywords
    mock_tools = []
    
    if "web" in task_description.lower() or "search" in task_description.lower():
        mock_tools.append({
            "tool_name": "web-search",
            "description": "Search the web for information",
            "relevance_score": 0.95,
            "mcp_server_config": {
                "mcpServers": {
                    "web-search-server": {
                        "command": "npx",
                        "args": ["-y", "@modelcontextprotocol/server-web-search"],
                        "env": {}
                    }
                }
            }
        })
    
    if "file" in task_description.lower() or "read" in task_description.lower():
        mock_tools.append({
            "tool_name": "file-reader",
            "description": "Read and process files",
            "relevance_score": 0.88,
            "mcp_server_config": {
                "mcpServers": {
                    "file-reader-server": {
                        "command": "uvx",
                        "args": ["mcp-server-filesystem"],
                        "env": {}
                    }
                }
            }
        })
    
    if "database" in task_description.lower() or "sql" in task_description.lower():
        mock_tools.append({
            "tool_name": "database-query",
            "description": "Query databases with SQL",
            "relevance_score": 0.82,
            "mcp_server_config": {
                "mcpServers": {
                    "database-server": {
                        "command": "uvx",
                        "args": ["mcp-server-sqlite"],
                        "env": {}
                    }
                }
            }
        })
    
    # Default tools if no specific matches
    if not mock_tools:
        mock_tools = [
            {
                "tool_name": "general-assistant",
                "description": "General purpose assistant tool",
                "relevance_score": 0.5,
                "mcp_server_config": {
                    "mcpServers": {
                        "assistant-server": {
                            "command": "npx",
                            "args": ["-y", "@modelcontextprotocol/server-sequential-thinking"],
                            "env": {}
                        }
                    }
                }
            }
        ]
    
    # Return top_k results
    result = mock_tools[:top_k]
    logger.info(f"Returning {len(result)} mock tool suggestions")
    return result

@server.tool()
async def get_available_tools() -> list:
    """
    Get a list of all available tools in the mock knowledge graph.
    
    Returns:
        List of available tool names and descriptions
    """
    logger.info("Fetching available tools list")
    
    available_tools = [
        {"name": "web-search", "description": "Search the web for information"},
        {"name": "file-reader", "description": "Read and process files"},
        {"name": "database-query", "description": "Query databases with SQL"},
        {"name": "general-assistant", "description": "General purpose assistant tool"},
        {"name": "code-analyzer", "description": "Analyze and understand code"},
        {"name": "data-processor", "description": "Process and transform data"},
    ]
    
    return available_tools

@server.tool()
async def health_check() -> dict:
    """
    Health check endpoint for the dummy tool retriever.
    
    Returns:
        Health status information
    """
    return {
        "status": "healthy",
        "service": "dummy-tool-retriever",
        "version": "1.0.0",
        "description": "Mock tool retriever for testing MCP unified gateway"
    }

if __name__ == "__main__":
    logger.info("Starting Dummy Tool Retriever MCP Server...")
    server.run()