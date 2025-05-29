"""
Example: Using MCPServerManager with the LangGraph agent
"""
import asyncio
from mcp_server_manager import MCPServerManager
from agent import ReactAgent

# Define your 5 popular MCP servers (update paths/commands as needed)
POPULAR_MCP_SERVERS = {
    "dynamic_tool_retriever": {
        "command": "python",
        "args": ["Dynamic_tool_retriever_MCP/server.py"],
        "endpoint": "http://localhost:8001"
    },
    # Add 4 more popular MCP servers here, e.g.:
    # "github": {"command": "python", "args": ["path/to/github_mcp.py"], "endpoint": "http://localhost:8002"},
    # ...
}

async def main():
    # 1. Start the MCP server manager and popular servers
    mcp_manager = MCPServerManager(POPULAR_MCP_SERVERS)
    mcp_manager.start_popular_servers()
    asyncio.create_task(mcp_manager.cleanup_loop())

    # 2. Initialize the LangGraph agent (using the config file as before)
    agent = ReactAgent("mcp_server_config.json")
    await agent.initialize_client()

    # 3. Example: handle a user query
    user_query = "Find the best tool for data extraction."
    session_id = "example-session-1"
    # (Optionally, ensure additional MCP servers for new tools here)
    # Example: mcp_manager.ensure_server(tool_name, tool_cfg)

    # 4. Run the agent and print the result
    async for result in agent.stream(user_query, session_id):
        print(result)

if __name__ == "__main__":
    asyncio.run(main())
