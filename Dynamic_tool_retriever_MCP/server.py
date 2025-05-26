"""
Implements an MCP server for dynamic tool retrieval.

The server exposes a tool that, given a task description, retrieves a list of
relevant tools from a Neo4j database using semantic similarity.
It utilizes text embeddings for the task description and pre-indexed tool descriptions
in the database.
"""

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel
from embedder import embed_text
from neo4j_retriever import retrieve_top_k_tools

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

@mcp.tool()
def dynamic_tool_retriever(input: DynamicRetrieverInput) -> list:
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
    
    # Step 1: Embed the task description
    query_embedding = embed_text(input.task_description)
    
    # Step 2: Query Neo4j to retrieve top-k similar tools
    retrieved_tools = retrieve_top_k_tools(query_embedding, input.top_k)
    
    # Step 3: Prepare the cleaned, final response
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
            "similarity_score": tool.get("score")  # optional but useful
        })
    
    return response

if __name__ == "__main__":
    mcp.run(transport="sse")