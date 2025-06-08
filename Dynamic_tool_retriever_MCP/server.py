"""
Implements an MCP server for dynamic tool retrieval.

The server exposes a tool that, given a task description, retrieves a list of
relevant tools from a Neo4j database using semantic similarity.
It utilizes text embeddings for the task description and pre-indexed tool descriptions
in the database.
"""

import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel

from embedder import embed_text
from neo4j_retriever import retrieve_top_k_tools
import asyncio
from Utils.get_MCP_config import extract_config_from_github_async
from Utils.get_available_env_keys import get_available_env_keys_from_dotenv  # new import

# Initialize MCP Server instance for the Dynamic Tool Retriever.
# This server will host tools that can be called remotely via MCP.
mcp = FastMCP("DynamicToolRetrieverMCP")

class DynamicRetrieverInput(BaseModel):
    """
    Input model for the dynamic_tool_retriever tool.
    
    Defines the expected structure and types for the input data.
    """
    task_description: str
    """The user's task description for which relevant tools need to be found."""
    top_k: int
    """The maximum number of relevant tools to retrieve. Defaults to 3 in the retriever if not specified otherwise by a similar parameter in the retriever function."""
    official_only: bool = False
    """Flag to restrict retrieval to official tools only. Defaults to False."""

@mcp.tool()
async def dynamic_tool_retriever(input: DynamicRetrieverInput) -> list:
    """
    Retrieves the top-k most relevant tools for a given user task description.

    The process involves:
    1. Embedding the input task description into a vector.
    2. Querying a Neo4j graph database (which contains pre-embedded tool descriptions)
       to find tools with descriptions semantically similar to the task.
    3. Formatting the retrieved tool information into a structured list.

    Args:
        input: An instance of `DynamicRetrieverInput` containing:
            - task_description (str): The description of the task.
            - top_k (int): The number of top relevant tools to retrieve.

    Returns:
        A list of dictionaries, where each dictionary represents a retrieved tool
        and contains the following keys:
        - "tool_name" (str): The name of the tool.
        - "tool_description" (str): The description of the tool.
        - "tool_parameters" (dict/str): Input parameters of the tool.
        - "tool_required_parameters" (list/str): Required parameters for the tool.
        - "vendor_name" (str): The name of the vendor providing the tool.
        - "vendor_repo" (str): The repository URL of the vendor.
        - "similarity_score" (float): The similarity score between the task
                                      description and the tool description.
    """
    print(f"[INFO] Received task description: {input.task_description}")
    # Step 1: Embed the task description
    query_embedding = embed_text(input.task_description)
    # Step 2: Query Neo4j for extended candidate set then rerank by env requirements
    initial_tools = retrieve_top_k_tools(query_embedding, input.top_k * 10, official_only=input.official_only)
    # fetch local environment keys
    available_keys = get_available_env_keys_from_dotenv()
    # fetch MCP configs for initial candidates
    async def _fetch_pair(tool):
        repo = tool.get("vendor_repository_url")
        if not repo:
            return tool, None
        try:
            cfg = await extract_config_from_github_async(repo)
            return tool, cfg
        except Exception:
            return tool, None
    pairs = await asyncio.gather(*( _fetch_pair(t) for t in initial_tools ))
    # filter to tools with config and available env keys in the MCP config
    valid_pairs = []
    for tool, cfg in pairs:
        if not cfg:
            continue
        servers = cfg.get("mcpServers", {})
        # assume single server entry
        srv_cfg = next(iter(servers.values()), {})
        required = srv_cfg.get("env", {}).keys()
        if set(required) <= set(available_keys):
            valid_pairs.append((tool, cfg))
    # select top_k by similarity score
    retrieved_tools = [tp[0] for tp in sorted(
        valid_pairs,
        key=lambda tp: -tp[0].get("score", 0)
    )][: input.top_k]
    print("Selected tools with MCP config and required env keys:", [t.get("tool_name") for t in retrieved_tools])
    # build map of repo to config for lookup
    config_map = {tool.get("vendor_repository_url"): cfg for tool, cfg in valid_pairs}

    async def get_tool_with_config(tool):
        vendor_repo = tool.get("vendor_repository_url")
        mcp_server_config = config_map.get(vendor_repo)
        return {
             "tool_name": tool.get("tool_name"),
             "tool_description": tool.get("tool_description"),
             "tool_parameters": tool.get("input_parameters"),
             "tool_required_parameters": tool.get("required_parameters"),
             "vendor_name": tool.get("vendor_name"),
             "vendor_repo": vendor_repo,
             # "required_env_keys": tool.get("vendor_required_env_keys"),
             "similarity_score": tool.get("score"),
             "mcp_server_config": mcp_server_config
         }

    tasks = [get_tool_with_config(tool) for tool in retrieved_tools]
    try:
        response = await asyncio.gather(*tasks)
    except Exception as e:
        print(f"[ERROR] Failed to build tool response with configs: {e}")
        # fallback: return tools without configs
        response = []
        for tool in retrieved_tools:
            response.append({
                "tool_name": tool.get("tool_name"),
                "tool_description": tool.get("tool_description"),
                "tool_parameters": tool.get("input_parameters"),
                "tool_required_parameters": tool.get("required_parameters"),
                "vendor_name": tool.get("vendor_name"),
                "vendor_repo": tool.get("vendor_repository_url"),
                # "required_env_keys": tool.get("vendor_required_env_keys"),
                "similarity_score": tool.get("score"),
                "mcp_server_config": None
            })
    return response

if __name__ == "__main__":
    mcp.run(transport="sse")