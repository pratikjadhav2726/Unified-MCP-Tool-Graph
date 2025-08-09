"""
Dynamic Tool Retriever MCP Server

Implements an MCP server for intelligent tool retrieval using semantic similarity
and environment validation. The server dynamically filters tools based on:
1. Semantic similarity to user queries using local Sentence Transformers
2. Available environment configurations
3. MCP server compatibility

Key Features:
- Semantic search using local text embeddings (no API keys required)
- Environment key validation
- MCP configuration extraction from GitHub
- Intelligent tool ranking and filtering
"""

import sys
import os
import asyncio
import logging
from typing import List, Dict, Optional, Tuple, Any

# Add parent directory to path for imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field

from embedder import embed_text
from neo4j_retriever import retrieve_top_k_tools
from Utils.get_MCP_config import extract_config_from_github_async
from Utils.get_available_env_keys import get_available_env_keys_from_dotenv

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Constants
DEFAULT_TOP_K = 3
CANDIDATE_MULTIPLIER = 5  # Reduced from 10 to 5 for better performance
SERVER_NAME = "DynamicToolRetrieverMCP"
CONFIG_FETCH_TIMEOUT = 15  # Maximum time to wait for config fetching
MAX_CONCURRENT_CONFIGS = 5  # Reduced concurrent config fetches for better stability

# Initialize MCP Server
mcp = FastMCP(SERVER_NAME)

class DynamicRetrieverInput(BaseModel):
    """Input schema for dynamic tool retrieval."""
    
    task_description: str = Field(
        ..., 
        description="The user's task description for which relevant tools need to be found",
        min_length=1
    )
    
    top_k: int = Field(
        default=DEFAULT_TOP_K,
        description="Maximum number of relevant tools to retrieve",
        ge=1,
        le=50
    )
    
    official_only: bool = Field(
        default=False,
        description="Flag to restrict retrieval to official tools only"
    )

class ToolResponse(BaseModel):
    """Response schema for retrieved tools."""
    
    tool_name: str
    tool_description: str
    tool_parameters: Any
    tool_required_parameters: Any
    vendor_name: str
    vendor_repo: Optional[str]
    similarity_score: float
    mcp_server_config: Optional[Dict[str, Any]]

async def fetch_tool_config_pair(tool: Dict[str, Any]) -> Tuple[Dict[str, Any], Optional[Dict[str, Any]]]:
    """
    Fetch MCP configuration for a tool from its repository with timeout.
    
    Args:
        tool: Tool information dictionary
        
    Returns:
        Tuple of (tool, config) where config may be None if extraction fails
    """
    repo_url = tool.get("vendor_repository_url")
    if not repo_url:
        logger.debug(f"No repository URL for tool: {tool.get('tool_name', 'Unknown')}")
        return tool, None
    
    try:
        # Add timeout to config extraction
        config = await asyncio.wait_for(
            extract_config_from_github_async(repo_url),
            timeout=10.0  # 10 second timeout per config fetch
        )
        logger.debug(f"Successfully extracted config for {tool.get('tool_name')}")
        return tool, config
    except asyncio.TimeoutError:
        logger.warning(f"Timeout extracting config from {repo_url}")
        return tool, None
    except Exception as e:
        logger.warning(f"Failed to extract config from {repo_url}: {e}")
        return tool, None

def validate_environment_requirements(config: Dict[str, Any], available_keys: List[str]) -> bool:
    """
    Validate if required environment keys are available.
    
    Args:
        config: MCP server configuration
        available_keys: List of available environment variable keys
        
    Returns:
        True if all required keys are available, False otherwise
    """
    if not config:
        return False
    
    servers = config.get("mcpServers", {})
    if not servers:
        return False
    
    # Get the first server configuration (assuming single server per config)
    server_config = next(iter(servers.values()), {})
    required_keys = set(server_config.get("env", {}).keys())
    
    return required_keys <= set(available_keys)

def build_tool_response(tool: Dict[str, Any], config: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Build standardized tool response with configuration.
    
    Args:
        tool: Tool information
        config: MCP server configuration (may be None)
        
    Returns:
        Formatted tool response dictionary
    """
    # Return null for mcp_server_config if config is None or empty
    mcp_config = None if not config or not config.get("mcpServers") else config
    
    return {
        "tool_name": tool.get("tool_name", "Unknown"),
        "tool_description": tool.get("tool_description", "No description available"),
        "tool_parameters": tool.get("input_parameters"),
        "tool_required_parameters": tool.get("required_parameters"),
        "vendor_name": tool.get("vendor_name", "Unknown Vendor"),
        "vendor_repo": tool.get("vendor_repository_url"),
        "similarity_score": tool.get("score", 0.0),
        "mcp_server_config": mcp_config
    }

@mcp.tool()
async def dynamic_tool_retriever(input: DynamicRetrieverInput) -> List[Dict[str, Any]]:
    """
    Retrieve the most relevant tools for a given task description.

    This function performs intelligent tool retrieval through:
    1. Semantic embedding of the task description using local Sentence Transformers
    2. Vector similarity search in Neo4j graph database
    3. MCP configuration extraction from vendor repositories
    4. Environment validation and compatibility checking
    5. Intelligent ranking and selection of top-k tools

    Args:
        input: DynamicRetrieverInput containing task description, top_k, and filters

    Returns:
        List of tool dictionaries with complete configuration information

    Raises:
        Exception: If critical errors occur during retrieval process
    """
    logger.info(f"Processing task: '{input.task_description}' (top_k={input.top_k}, official_only={input.official_only})")
    
    try:
        # Step 1: Generate semantic embedding using local Sentence Transformers
        query_embedding = embed_text(input.task_description)
        logger.debug("Successfully generated task embedding using local model")
        
        # Step 2: Retrieve expanded candidate set from Neo4j
        candidate_count = input.top_k * CANDIDATE_MULTIPLIER
        initial_tools = retrieve_top_k_tools(
            query_embedding, 
            candidate_count, 
            official_only=input.official_only
        )
        logger.info(f"Retrieved {len(initial_tools)} initial candidate tools")
        
        # Step 3: Get available environment keys
        available_keys = get_available_env_keys_from_dotenv()
        logger.debug(f"Found {len(available_keys)} available environment keys")
        
        # Step 4: Fetch MCP configurations asynchronously with timeout and concurrency control
        semaphore = asyncio.Semaphore(MAX_CONCURRENT_CONFIGS)
        
        async def fetch_with_semaphore(tool):
            async with semaphore:
                return await fetch_tool_config_pair(tool)
        
        try:
            # Apply overall timeout to the entire config fetching process
            tool_config_pairs = await asyncio.wait_for(
                asyncio.gather(
                    *[fetch_with_semaphore(tool) for tool in initial_tools],
                    return_exceptions=True
                ),
                timeout=CONFIG_FETCH_TIMEOUT
            )
        except asyncio.TimeoutError:
            logger.warning(f"Config fetching timed out after {CONFIG_FETCH_TIMEOUT} seconds")
            # Return empty list if timeout occurs - no tools without configs
            return []
        
        # Filter out exceptions and process results - ONLY return tools with valid configs
        valid_pairs = []
        
        for result in tool_config_pairs:
            if isinstance(result, Exception):
                logger.warning(f"Config fetch failed: {result}")
                continue
            
            tool, config = result
            # Only include tools that have successfully retrieved MCP server configs
            if config and validate_environment_requirements(config, available_keys):
                valid_pairs.append((tool, config))
            else:
                logger.debug(f"Excluding tool {tool.get('tool_name', 'Unknown')} - no valid MCP config found")
        
        logger.info(f"Found {len(valid_pairs)} tools with valid MCP server configurations")
        
        # Step 5: Rank by similarity and select top-k (only from tools with valid configs)
        ranked_pairs = sorted(
            valid_pairs,
            key=lambda pair: pair[0].get("score", 0.0),  # Sort by similarity score
            reverse=True
        )
        
        selected_pairs = ranked_pairs[:input.top_k]
        selected_tool_names = [pair[0].get("tool_name", "Unknown") for pair in selected_pairs]
        logger.info(f"Selected tools with valid configs: {selected_tool_names}")
        
        # Step 6: Build final response (only tools with valid configs)
        response = [
            build_tool_response(tool, config) 
            for tool, config in selected_pairs
        ]
        
        # Return empty list if no tools found with valid configs
        if not response:
            logger.info("No tools found with valid MCP server configurations")
            return []
        
        logger.info(f"Successfully retrieved {len(response)} tools with valid MCP server configurations")
        return response
        
    except Exception as e:
        logger.error(f"Critical error in tool retrieval: {e}")
        # Return empty list rather than raising to maintain MCP compatibility
        return []


if __name__ == "__main__":
    logger.info(f"Starting {SERVER_NAME} server...")
    mcp.run(transport="stdio")