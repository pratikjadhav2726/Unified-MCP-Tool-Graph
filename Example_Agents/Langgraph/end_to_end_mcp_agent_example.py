"""
End-to-end example: User query -> Dynamic Tool Retriever MCP -> Start/ensure MCP servers -> LangGraph agent executes tools -> Returns answer
"""
import asyncio
import requests
import time
from mcp_server_manager import MCPServerManager
from agent import ReactAgent
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.prebuilt import create_react_agent
from langchain_groq import ChatGroq
from langgraph.checkpoint.memory import InMemorySaver

# --- CONFIGURE YOUR POPULAR MCP SERVERS HERE ---
POPULAR_MCP_SERVERS = {
    "dynamic_tool_retriever": {
        "command": "python",
        "args": ["Dynamic_tool_retriever_MCP/server.py"],
        "endpoint": "http://localhost:8001"
    },
    # Add more if you want them always running
}

# --- DYNAMIC TOOL RETRIEVER CALL ---
def call_dynamic_tool_retriever_mcp(task_description, top_k=3):
    """
    Calls the dynamic tool retriever MCP server to get relevant tools and their MCP server configs.
    Assumes the server is running at POPULAR_MCP_SERVERS['dynamic_tool_retriever']['endpoint'].
    """
    url = POPULAR_MCP_SERVERS['dynamic_tool_retriever']['endpoint'] + "/dynamic_tool_retriever"
    payload = {"task_description": task_description, "top_k": top_k}
    try:
        resp = requests.post(url, json=payload, timeout=10)
        resp.raise_for_status()
        return resp.json()  # Should be a list of tool dicts, each with mcp server config
    except Exception as e:
        print(f"[ERROR] Failed to call dynamic tool retriever MCP: {e}")
        return []

async def main():
    # 1. Start MCP server manager and popular servers
    mcp_manager = MCPServerManager(POPULAR_MCP_SERVERS)
    mcp_manager.start_popular_servers()
    asyncio.create_task(mcp_manager.cleanup_loop())

    # 2. Get user query
    user_query = input("Enter your query: ")
    session_id = f"session-{int(time.time())}"

    # 3. Call dynamic tool retriever MCP to get required tools and their MCP server configs
    tool_infos = call_dynamic_tool_retriever_mcp(user_query, top_k=3)
    # tool_infos should be a list of dicts, each with at least 'tool_name', 'mcp_server_config' (with command, args, endpoint)

    # 4. Ensure all required MCP servers are running
    for tool in tool_infos:
        mcp_cfg = tool.get('mcp_server_config')
        tool_name = tool.get('tool_name')
        if mcp_cfg and tool_name:
            mcp_manager.ensure_server(tool_name, mcp_cfg)


    # 5. Build a minimal MCP server config with only the 5 popular and the new required ones
    #    Only include the MCP servers that are actually needed for the tools
    #    (not all active servers)
    mcp_servers_config = {}
    # Always include the 5 popular
    for name, cfg in POPULAR_MCP_SERVERS.items():
        mcp_servers_config[name] = {"url": cfg["endpoint"], "transport": "sse"}
    # Add new required ones (from tool_infos)
    for tool in tool_infos:
        mcp_cfg = tool.get('mcp_server_config')
        tool_name = tool.get('tool_name')
        if mcp_cfg and tool_name and tool_name not in mcp_servers_config:
            mcp_servers_config[tool_name] = {"url": mcp_cfg["endpoint"], "transport": "sse"}

    # 6. Only load the exact tools retrieved from the tool retriever MCP
    #    (not all tools from the MCP servers)
    #    We'll use the MultiServerMCPClient directly for this
    client = MultiServerMCPClient(mcp_servers_config)
    await client.__aenter__()
    # Get all tools from the selected servers
    all_tools = client.get_tools()
    # Filter to only the tools returned by the tool retriever
    required_tool_names = {tool['tool_name'] for tool in tool_infos}
    filtered_tools = [tool for tool in all_tools if getattr(tool, 'name', None) in required_tool_names]

    # 7. Build the LangGraph agent with only the filtered tools
    model = ChatGroq(
        temperature=0,
        groq_api_key=os.getenv("GROQ_API_KEY"),
        model_name="qwen-qwq-32b"
    )
    memory = InMemorySaver()
    SYSTEM_INSTRUCTION = (
        "You are an agent that decomposes the user's task into sub-tasks and retrieves the best tools to solve it. "
        "Give just the tools summary and workflow."
    )
    agent = create_react_agent(
        model, tools=filtered_tools, prompt=SYSTEM_INSTRUCTION, checkpointer=memory
    )

    # 8. Run the agent and print the result
    print("\n--- Agent Response ---")
    inputs = {'messages': [('user', user_query)]}
    config = {'configurable': {'thread_id': session_id}}
    async for result in agent.astream(inputs, config=config):
        print({
            'is_task_complete': True,
            'require_user_input': False,
            'content': result["messages"][-1].content if "messages" in result and result["messages"] else "",
        })

if __name__ == "__main__":
    asyncio.run(main())
