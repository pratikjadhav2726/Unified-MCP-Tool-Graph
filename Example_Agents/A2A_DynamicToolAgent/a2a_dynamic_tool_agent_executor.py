import os
import time
import requests
import json
import logging
from mcp_server_manager import MCPServerManager
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.prebuilt import create_react_agent
from langchain_groq import ChatGroq
from langgraph.checkpoint.memory import InMemorySaver
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue

logger = logging.getLogger(__name__)
# --- CONFIGURE YOUR POPULAR MCP SERVERS HERE ---
POPULAR_MCP_SERVERS = {
    "dynamic_tool_retriever": {
        "command": "python",
        "args": ["Dynamic_tool_retriever_MCP/server.py"],
        "url": "http://localhost:8000/sse",
        "transport": "sse",
    },
    # Add more if you want them always running
}

async def call_dynamic_tool_retriever_via_mcpclient(
    user_query: str,
    top_k: int,
    retriever_server_config: dict,
    retriever_tool_name: str = "dynamic_tool_retriever" # Allow overriding tool name if needed
) -> list:
    """
    Calls the specified dynamic_tool_retriever tool via MCP client.

    Args:
        user_query: The user's task description.
        top_k: The maximum number of relevant tools to retrieve.
        retriever_server_config: MCP client configuration for the retriever server.
                                 Example: {"dynamic_tool_retriever_server_key": {"url": "...", "transport": "..."}}
        retriever_tool_name: The name of the retriever tool on its MCP server.

    Returns:
        A list of tool information dictionaries, or an empty list if an error occurs.
    """
    tool_infos = []
    if not retriever_server_config:
        logger.error("Retriever server configuration is empty. Cannot call retriever tool.")
        return tool_infos

    logger.info(f"Attempting to call tool '{retriever_tool_name}' via MCP using config: {retriever_server_config}")

    try:
        client = MultiServerMCPClient(retriever_server_config)
        # async with MultiServerMCPClient(retriever_server_config) as client:
        tools = await client.get_tools()
        dtr_tool = next((t for t in tools if getattr(t, 'name', None) == retriever_tool_name), None)

        if not dtr_tool:
            logger.error(f"Tool '{retriever_tool_name}' not found in MCP client with config {retriever_server_config}.")
            return tool_infos

        logger.info(f"Found '{retriever_tool_name}' tool via MCP. Invoking with query: '{user_query[:100]}...'")
        tool_input = {"input": {
            "task_description": user_query,
            "top_k": top_k,
        }}
        # Assuming dtr_tool is a LangChain BaseTool or compatible
        response = await dtr_tool.arun(tool_input)

        if isinstance(response, list):
            tool_infos = response
            logger.info(f"Successfully retrieved {len(tool_infos)} tool(s) using '{retriever_tool_name}' via MCP.")

    except Exception as e:
        logger.error(f"Failed to call '{retriever_tool_name}' via MCP. Error: {e}", exc_info=True)
        # tool_infos remains empty

    return tool_infos
    

class A2ADynamicToolAgentExecutor(AgentExecutor):
    def __init__(self):
        self.mcp_manager = MCPServerManager(POPULAR_MCP_SERVERS)
        self.mcp_manager.start_popular_servers()
        # Optionally: asyncio.create_task(self.mcp_manager.cleanup_loop())

    async def execute(self, context: RequestContext, event_queue: EventQueue):
        user_query = context.get_user_input()
        session_id = f"session-{int(time.time())}"


        cfg = POPULAR_MCP_SERVERS["dynamic_tool_retriever"]
        ret_url, ret_transport = cfg.get("url"), cfg.get("transport")
        if ret_url and ret_transport:
            retriever_mcp_config = { "dynamic_tool_retriever": { "url": ret_url, "transport": ret_transport } }

        # 1. Get required tools from dynamic tool retriever
        tool_infos = await call_dynamic_tool_retriever_via_mcpclient(
                user_query=user_query, top_k=3, retriever_server_config=retriever_mcp_config
            )
        print(f"[Debug] Retrieved tool infos: {tool_infos}")
        tool_infos=[json.loads(item) for item in tool_infos]
        # 2. Ensure all required MCP servers are running
        for tool in tool_infos:
            mcp_cfg = tool.get('mcp_server_config')
            cfg = next(iter(mcp_cfg.values()))
            tool_name = tool.get('tool_name')
            if mcp_cfg and tool_name:
                self.mcp_manager.ensure_server(tool_name, cfg)

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
