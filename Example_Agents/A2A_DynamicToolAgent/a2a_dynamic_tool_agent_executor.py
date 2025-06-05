import os
import time
import requests
import logging
from mcp_server_manager import MCPServerManager
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.prebuilt import create_react_agent
from langchain_groq import ChatGroq
from langgraph.checkpoint.memory import InMemorySaver
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.server.tasks import TaskUpdater
from a2a.types import TaskState, Part, TextPart
from a2a.utils import new_agent_text_message, new_task

logger = logging.getLogger(__name__)

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
        # Using logger instead of print for consistency
        logger.error(f"[ERROR] Failed to call dynamic tool retriever MCP: {e}", exc_info=True)
        return []

class A2ADynamicToolAgentExecutor(AgentExecutor):
    def __init__(self):
        self.mcp_manager = MCPServerManager(POPULAR_MCP_SERVERS)
        self.mcp_manager.start_popular_servers()
        # Optionally: asyncio.create_task(self.mcp_manager.cleanup_loop())

    async def execute(self, context: RequestContext, event_queue: EventQueue):
        task = context.current_task
        if not task:
            task = new_task(context.message)
        updater = TaskUpdater(event_queue, task.id, task.contextId)

        user_query = context.get_user_input()
        if user_query is None:
            user_query = "" # Ensure user_query is a string
            logger.warning("User query from context.get_user_input() was None. Defaulting to empty string.")
        session_id = f"session-{int(time.time())}"

        # 1. Get required tools from dynamic tool retriever
        tool_infos = call_dynamic_tool_retriever_mcp(user_query, top_k=3)

        # 2. Ensure all required MCP servers are running
        valid_tool_infos = []
        for tool_info in tool_infos:
            mcp_cfg = tool_info.get('mcp_server_config')
            tool_name = tool_info.get('tool_name')

            if not tool_name:
                logger.warning(f"Tool information missing 'tool_name'. Skipping: {tool_info}")
                continue

            if mcp_cfg and isinstance(mcp_cfg, dict) and mcp_cfg.get("endpoint"):
                self.mcp_manager.ensure_server(tool_name, mcp_cfg)
                valid_tool_infos.append(tool_info)
            else:
                logger.warning(f"MCP server config missing or invalid for tool '{tool_name}'. Tool will not be available. Config: {mcp_cfg}")

        # 3. Build MCP server config
        mcp_servers_config = {}
        for name, cfg in POPULAR_MCP_SERVERS.items():
            mcp_servers_config[name] = {"url": cfg["endpoint"], "transport": "sse"}

        for tool_info in valid_tool_infos:
            mcp_cfg = tool_info['mcp_server_config']
            tool_name = tool_info['tool_name']
            if tool_name not in mcp_servers_config:
                if "url" in mcp_cfg and "transport" in mcp_cfg:
                    mcp_servers_config[tool_name] = {
                        "url": mcp_cfg["url"],
                        "transport": mcp_cfg["transport"]
                    }
                elif "endpoint" in mcp_cfg:
                     mcp_servers_config[tool_name] = {
                        "url": mcp_cfg["endpoint"],
                        "transport": mcp_cfg.get("transport", "sse")
                    }
                else:
                    logger.warning(f"Cannot form client config for tool '{tool_name}' due to missing 'url' or 'endpoint' in mcp_cfg: {mcp_cfg}")

        # 4. Only load the exact tools retrieved and run agent
        async with MultiServerMCPClient(mcp_servers_config) as client:
            all_tools = client.get_tools()
            required_tool_names = {ti['tool_name'] for ti in valid_tool_infos if ti.get('tool_name')}

            filtered_tools = [tool for tool in all_tools if getattr(tool, 'name', None) in required_tool_names]
            if not filtered_tools and required_tool_names:
                logger.warning(f"No tools were loaded for required tool names: {required_tool_names}. Check MCP server availability and configurations.")

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
            try:
                async for item in agent.astream(inputs, config=config):
                    is_task_complete = False
                    require_user_input = False
                    content = ""

                    if isinstance(item, dict):
                        is_task_complete = item.get('is_task_complete', False)
                        require_user_input = item.get('require_user_input', False)
                        content = item.get('content', '')
                    else:
                        agent_state = item.get('agent') if isinstance(item, dict) else None
                        if agent_state and isinstance(agent_state, dict) and 'messages' in agent_state:
                            messages = agent_state['messages']
                            content = getattr(messages[-1], 'content', str(messages[-1])) if messages else ''
                        elif 'messages' in item and item['messages']:
                            messages = item['messages']
                            content = getattr(messages[-1], 'content', str(messages[-1]))
                        elif hasattr(item, 'content'):
                             content = item.content
                        else:
                            content = str(item)

                    if not is_task_complete and not require_user_input:
                        updater.update_status(
                            TaskState.working,
                            new_agent_text_message(content, task.contextId, task.id),
                        )
                    elif require_user_input:
                        updater.update_status(
                            TaskState.input_required,
                            new_agent_text_message(content, task.contextId, task.id),
                            final=True,
                        )
                        break
                    else: # Task is complete
                        updater.add_artifact(
                            [Part(root=TextPart(text=content if content else "Task completed successfully."))],
                            name='tool_result',
                        )
                        updater.complete()
                        break
            except Exception as e:
                error_message = f"Error during agent execution: {str(e)}"
                logger.error(f"Agent execution failed: {error_message}", exc_info=True)
                if 'updater' in locals():
                    updater.update_status(
                        TaskState.error,
                        new_agent_text_message(error_message, task.contextId, task.id),
                        final=True,
                    )
        # Note: The 'async def cancel' method is correctly outside the 'async with' block.

    async def cancel(self, request: RequestContext, event_queue: EventQueue) -> None:
        """Cancel a running task. (Not implemented)"""
        from a2a.types import UnsupportedOperationError
        from a2a.utils.errors import ServerError
        raise ServerError(error=UnsupportedOperationError())
