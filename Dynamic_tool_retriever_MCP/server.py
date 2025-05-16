from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel
from embedder import embed_text
from neo4j_retriever import retrieve_top_k_tools

# Initialize MCP Server
mcp = FastMCP("DynamicToolRetrieverMCP")

class DynamicRetrieverInput(BaseModel):
    task_description: str
    top_k: int # default top k tools to retrieve

@mcp.tool()
def dynamic_tool_retriever(input: DynamicRetrieverInput) -> list:
    """Retrieve top-k relevant tools info for a user task description."""
    
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
    mcp.run(transport="stdio")