from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel
from embedder import embed_text
from neo4j_retriever import retrieve_top_k_tools

mcp = FastMCP("DynamicToolRetrieverMCP")

class DynamicRetrieverInput(BaseModel):
    task_description: str
    top_k: int = 3  # default

@mcp.tool()
def dynamic_tool_retriever(input: DynamicRetrieverInput) -> list:
    """Retrieve top-k relevant tools for a user task description."""
    
    # Step 1: Embed the user query
    query_embedding = embed_text(input.task_description)
    
    # Step 2: Query Neo4j for top-k tools
    retrieved_tools = retrieve_top_k_tools(query_embedding, input.top_k)
    
    # Step 3: Prepare clean response
    response = []
    for tool in retrieved_tools:
        response.append({
            "tool_name": tool.get("tool_name"),
            "tool_description": tool.get("tool_description"),
            "vendor_github": tool.get("vendor_github"),
            "required_env_keys": tool.get("required_env_keys"),
            "mcp_server_url": tool.get("vendor_mcp_url")
        })
    
    return response

if __name__ == "__main__":
    mcp.run(transport="stdio")