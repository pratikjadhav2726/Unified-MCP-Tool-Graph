import os
import time
import requests
from mcp_server_manager import MCPServerManager
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.prebuilt import create_react_agent
from langchain_groq import ChatGroq
from langgraph.checkpoint.memory import InMemorySaver
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue

# --- CONFIGURE YOUR POPULAR MCP SERVERS HERE ---
POPULAR_MCP_SERVERS = {
    "dynamic_tool_retriever": {
        "command": "python",
        "args": ["Dynamic_tool_retriever_MCP/server.py"],
        "endpoint": "http://localhost:8001"
    },
    # Add more if you want them always running
}

def call_dynamic_tool_retriever_mcp(task_description, top_k=3):
    url = POPULAR_MCP_SERVERS['dynamic_tool_retriever']['endpoint'] + "/dynamic_tool_retriever"
    payload = {"task_description": task_description, "top_k": top_k}
    try:
        resp = requests.post(url, json=payload, timeout=10)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print(f"[ERROR] Failed to call dynamic tool retriever MCP: {e}")
        return []

class A2ADynamicToolAgentExecutor(AgentExecutor):
    def __init__(self):
        self.mcp_manager = MCPServerManager(POPULAR_MCP_SERVERS)
        self.mcp_manager.start_popular_servers()
        # Optionally: asyncio.create_task(self.mcp_manager.cleanup_loop())

    async def execute(self, context: RequestContext, event_queue: EventQueue):
        user_query = context.task.input.text if context.task.input else ""
        session_id = f"session-{int(time.time())}"

        # 1. Get required tools from dynamic tool retriever
        tool_infos = call_dynamic_tool_retriever_mcp(user_query, top_k=3)

        # 2. Ensure all required MCP servers are running
        for tool in tool_infos:
            mcp_cfg = tool.get('mcp_server_config')
            tool_name = tool.get('tool_name')
            if mcp_cfg and tool_name:
                self.mcp_manager.ensure_server(tool_name, mcp_cfg)

        # 3. Build MCP server config for only the 5 popular and new required
        mcp_servers_config = {}
        for name, cfg in POPULAR_MCP_SERVERS.items():
            mcp_servers_config[name] = {"url": cfg["endpoint"], "transport": "sse"}
        for tool in tool_infos:
            mcp_cfg = tool.get('mcp_server_config')
            tool_name = tool.get('tool_name')
            if mcp_cfg and tool_name and tool_name not in mcp_servers_config:
                mcp_servers_config[tool_name] = {"url": mcp_cfg["endpoint"], "transport": "sse"}

        # 4. Only load the exact tools retrieved
        client = MultiServerMCPClient(mcp_servers_config)
        await client.__aenter__()
        all_tools = client.get_tools()
        required_tool_names = {tool['tool_name'] for tool in tool_infos}
        filtered_tools = [tool for tool in all_tools if getattr(tool, 'name', None) in required_tool_names]

        # 5. Build the LangGraph agent
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

        # 6. Run the agent and stream results to A2A
        inputs = {'messages': [('user', user_query)]}
        config = {'configurable': {'thread_id': session_id}}
        async for result in agent.astream(inputs, config=config):
            await event_queue.put({
                'is_task_complete': True,
                'require_user_input': False,
                'content': result["messages"][-1].content if "messages" in result and result["messages"] else "",
            })

    async def cancel(self, request: RequestContext, event_queue: EventQueue) -> None:
        """Cancel a running task. (Not implemented)"""
        # You can implement actual cancellation logic here if needed.
        # For now, raise unsupported operation to match Langgraph pattern.
        from a2a.types import UnsupportedOperationError
        from a2a.utils.errors import ServerError
        raise ServerError(error=UnsupportedOperationError())
