"""
Enhanced Tool Retriever with Neo4j Integration and Fallback

This module provides a unified interface for tool retrieval that:
- Uses the real Dynamic Tool Retriever MCP when Neo4j is available
- Falls back to dummy retriever when Neo4j connection fails
- Provides caching and error handling
- Integrates with the gateway configuration system
"""

import sys
import os
import asyncio
import logging
from typing import List, Dict, Any, Optional
from pathlib import Path

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mcp.client.session import ClientSession
from mcp.client.sse import sse_client
from gateway.config import config
from gateway.dummy_tool_retriever import server as dummy_server

logger = logging.getLogger(__name__)

class EnhancedToolRetriever:
    """
    Enhanced tool retriever with Neo4j integration and fallback capabilities.
    
    This class provides a unified interface for tool retrieval that automatically
    handles connection failures and provides intelligent fallback mechanisms.
    """
    
    def __init__(self, use_real_retriever: bool = True, fallback_to_dummy: bool = True):
        self.use_real_retriever = use_real_retriever
        self.fallback_to_dummy = fallback_to_dummy
        self.neo4j_available = None  # Cache Neo4j availability status
        self.last_neo4j_check = 0
        self.neo4j_check_interval = 300  # Check every 5 minutes
        
    async def _check_neo4j_availability(self) -> bool:
        """
        Check if Neo4j is available and the real retriever is working.
        
        Returns:
            True if Neo4j is available and working, False otherwise
        """
        import time
        
        # Use cached result if recent
        now = time.time()
        if (self.neo4j_available is not None and 
            now - self.last_neo4j_check < self.neo4j_check_interval):
            return self.neo4j_available
        
        try:
            # Try to import Neo4j dependencies
            from neo4j import GraphDatabase
            from Dynamic_tool_retriever_MCP.neo4j_retriever import retrieve_top_k_tools
            from Dynamic_tool_retriever_MCP.embedder import embed_text
            
            # Test Neo4j connection
            driver = GraphDatabase.driver(
                config.neo4j_uri,
                auth=(config.neo4j_user, config.neo4j_password)
            )
            
            with driver.session() as session:
                # Simple test query
                result = session.run("RETURN 1 as test")
                test_value = result.single()["test"]
                if test_value != 1:
                    raise Exception("Neo4j test query failed")
            
            driver.close()
            
            # Test embedding functionality
            test_embedding = embed_text("test query")
            if not test_embedding or len(test_embedding) == 0:
                raise Exception("Embedding generation failed")
            
            self.neo4j_available = True
            logger.info("Neo4j connection and retriever functionality verified")
            
        except Exception as e:
            self.neo4j_available = False
            logger.warning(f"Neo4j not available: {e}")
        
        self.last_neo4j_check = now
        return self.neo4j_available
    
    async def _retrieve_with_real_retriever(
        self, 
        task_description: str, 
        top_k: int = 3, 
        official_only: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Retrieve tools using the real Neo4j-based retriever.
        
        Args:
            task_description: Description of the task needing tools
            top_k: Number of tools to retrieve
            official_only: Whether to only return official tools
            
        Returns:
            List of tool dictionaries with MCP server configurations
            
        Raises:
            Exception: If real retriever fails
        """
        try:
            from Dynamic_tool_retriever_MCP.server import dynamic_tool_retriever
            from Dynamic_tool_retriever_MCP.server import DynamicRetrieverInput
            
            # Create input for the real retriever
            retriever_input = DynamicRetrieverInput(
                task_description=task_description,
                top_k=top_k,
                official_only=official_only
            )
            
            # Call the real retriever
            result = await dynamic_tool_retriever(retriever_input)
            
            logger.info(f"Real retriever returned {len(result)} tools for: {task_description}")
            return result
            
        except Exception as e:
            logger.error(f"Real retriever failed: {e}")
            raise
    
    async def _retrieve_with_dummy_retriever(
        self, 
        task_description: str, 
        top_k: int = 3
    ) -> List[Dict[str, Any]]:
        """
        Retrieve tools using the dummy retriever.
        
        Args:
            task_description: Description of the task needing tools
            top_k: Number of tools to retrieve
            
        Returns:
            List of mock tool dictionaries
        """
        try:
            # Use the dummy retriever function directly
            result = await dummy_server.dynamic_tool_retriever(task_description, top_k)
            
            logger.info(f"Dummy retriever returned {len(result)} tools for: {task_description}")
            return result
            
        except Exception as e:
            logger.error(f"Dummy retriever failed: {e}")
            # Return a basic fallback tool
            return [{
                "tool_name": "fallback-assistant",
                "tool_description": "Basic assistant tool (fallback)",
                "tool_parameters": {},
                "tool_required_parameters": {},
                "vendor_name": "Gateway Fallback",
                "vendor_repo": None,
                "similarity_score": 0.1,
                "mcp_server_config": {
                    "mcpServers": {
                        "sequential-thinking": {
                            "command": "npx",
                            "args": ["-y", "@modelcontextprotocol/server-sequential-thinking"],
                            "env": {}
                        }
                    }
                }
            }]
    
    async def retrieve_tools(
        self, 
        task_description: str, 
        top_k: int = 3, 
        official_only: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Retrieve tools with intelligent fallback handling.
        
        Args:
            task_description: Description of the task needing tools
            top_k: Number of tools to retrieve
            official_only: Whether to only return official tools
            
        Returns:
            List of tool dictionaries with MCP server configurations
        """
        logger.info(f"Retrieving tools for: {task_description} (top_k={top_k}, official_only={official_only})")
        
        # Try real retriever first if enabled
        if self.use_real_retriever:
            neo4j_ok = await self._check_neo4j_availability()
            
            if neo4j_ok:
                try:
                    result = await self._retrieve_with_real_retriever(
                        task_description, top_k, official_only
                    )
                    if result:  # If we got results, return them
                        logger.info("Successfully retrieved tools using real retriever")
                        return result
                except Exception as e:
                    logger.warning(f"Real retriever failed, will try fallback: {e}")
        
        # Fall back to dummy retriever if enabled
        if self.fallback_to_dummy:
            logger.info("Using dummy retriever as fallback")
            return await self._retrieve_with_dummy_retriever(task_description, top_k)
        
        # If no fallback is enabled, raise an error
        raise Exception("Tool retrieval failed and no fallback is configured")
    
    async def get_available_tools(self) -> List[Dict[str, Any]]:
        """
        Get a list of all available tools.
        
        Returns:
            List of available tool information
        """
        logger.info("Fetching available tools list")
        
        # Try real retriever first
        if self.use_real_retriever:
            neo4j_ok = await self._check_neo4j_availability()
            
            if neo4j_ok:
                try:
                    # For real retriever, we'd need to implement a method to list all tools
                    # For now, return a sample of popular tools
                    sample_tools = await self.retrieve_tools("general purpose tools", top_k=10)
                    return [
                        {
                            "name": tool.get("tool_name", "Unknown"),
                            "description": tool.get("tool_description", "No description"),
                            "vendor": tool.get("vendor_name", "Unknown")
                        }
                        for tool in sample_tools
                    ]
                except Exception as e:
                    logger.warning(f"Failed to get tools from real retriever: {e}")
        
        # Fall back to dummy retriever
        if self.fallback_to_dummy:
            try:
                result = await dummy_server.get_available_tools()
                return result
            except Exception as e:
                logger.error(f"Failed to get tools from dummy retriever: {e}")
        
        return []
    
    async def health_check(self) -> Dict[str, Any]:
        """
        Perform health check on the tool retriever.
        
        Returns:
            Health status information
        """
        health_info = {
            "status": "healthy",
            "retrievers": {},
            "timestamp": asyncio.get_event_loop().time()
        }
        
        # Check real retriever
        if self.use_real_retriever:
            neo4j_ok = await self._check_neo4j_availability()
            health_info["retrievers"]["real"] = {
                "enabled": True,
                "available": neo4j_ok,
                "last_check": self.last_neo4j_check
            }
        else:
            health_info["retrievers"]["real"] = {
                "enabled": False,
                "available": False
            }
        
        # Check dummy retriever
        if self.fallback_to_dummy:
            try:
                await dummy_server.health_check()
                health_info["retrievers"]["dummy"] = {
                    "enabled": True,
                    "available": True
                }
            except Exception as e:
                health_info["retrievers"]["dummy"] = {
                    "enabled": True,
                    "available": False,
                    "error": str(e)
                }
        else:
            health_info["retrievers"]["dummy"] = {
                "enabled": False,
                "available": False
            }
        
        # Determine overall status
        has_working_retriever = (
            (health_info["retrievers"]["real"]["available"]) or
            (health_info["retrievers"]["dummy"]["available"])
        )
        
        if not has_working_retriever:
            health_info["status"] = "unhealthy"
            health_info["message"] = "No working tool retrievers available"
        
        return health_info

# Global instance
enhanced_retriever = EnhancedToolRetriever(
    use_real_retriever=config.use_real_retriever,
    fallback_to_dummy=config.fallback_to_dummy
)