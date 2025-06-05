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
        "url": "http://localhost:8001/sse",  # Explicit MCP endpoint URL
        "transport": "sse"                   # Explicit transport type
    },
    # Add more if you want them always running, following the same structure
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
        async with MultiServerMCPClient(retriever_server_config) as client:
            tools = client.get_tools()
            dtr_tool = next((t for t in tools if getattr(t, 'name', None) == retriever_tool_name), None)

            if not dtr_tool:
                logger.error(f"Tool '{retriever_tool_name}' not found in MCP client with config {retriever_server_config}.")
                return tool_infos

            logger.info(f"Found '{retriever_tool_name}' tool via MCP. Invoking with query: '{user_query[:100]}...'")
            tool_input = {
                'task_description': user_query,
                'top_k': top_k,
                'official_only': False # Or make this a parameter if needed
            }
            # Assuming dtr_tool is a LangChain BaseTool or compatible
            response = await dtr_tool.ainvoke(tool_input)

            if isinstance(response, list):
                tool_infos = response
                logger.info(f"Successfully retrieved {len(tool_infos)} tool(s) using '{retriever_tool_name}' via MCP.")
            else:
                logger.error(f"'{retriever_tool_name}' tool via MCP returned an unexpected response type: {type(response)}. Expected list. Response: {response}")
                # tool_infos remains empty

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
        if user_query is None:
            user_query = ""
            logger.warning("User query from context.get_user_input() was None. Defaulting to empty string.")

        session_id = f"session-{int(time.time())}"

        task = context.current_task
        if not task:
            logger.error("No current_task in context. Cannot proceed.")
            await event_queue.put({
                'is_task_complete': True,
                'require_user_input': False,
                'content': "Error: Agent failed to initialize due to missing task context."
            }) # Fallback direct event
            return

        updater = TaskUpdater(event_queue, task.id, task.contextId)

        # 1. Prepare retriever_mcp_config
        retriever_server_key_in_popular = "dynamic_tool_retriever"
        retriever_mcp_config = {}
        if retriever_server_key_in_popular in POPULAR_MCP_SERVERS:
            cfg = POPULAR_MCP_SERVERS[retriever_server_key_in_popular]
            ret_url, ret_transport = cfg.get("url"), cfg.get("transport")
            if ret_url and ret_transport:
                retriever_mcp_config = { retriever_server_key_in_popular: { "url": ret_url, "transport": ret_transport } }
            else:
                logger.error(f"'{retriever_server_key_in_popular}' config in POPULAR_MCP_SERVERS missing 'url' or 'transport'.")
        else:
            logger.error(f"'{retriever_server_key_in_popular}' not found in POPULAR_MCP_SERVERS.")

        # 2. Call retriever via helper
        tool_infos = []
        if retriever_mcp_config: # Proceed only if retriever config was successfully prepared
            tool_infos = await call_dynamic_tool_retriever_via_mcpclient(
                user_query=user_query, top_k=3, retriever_server_config=retriever_mcp_config
            )

        # 3. Filter tools and handle no tools case
        tool_infos_with_config = [ti for ti in tool_infos if ti.get('mcp_server_config')]
        if not tool_infos_with_config:
            msg = "No tools with valid configurations found for your query." if tool_infos else "Failed to retrieve tools or no tools found for your query."
            logger.warning(f"{msg} Query: '{user_query[:100]}...'")
            updater.update_status(TaskState.completed, new_agent_text_message(msg, task.contextId, task.id), final=True)
            return

        # 4. Ensure servers for valid tools are running
        valid_tool_infos_for_agent = []
        for tool_info in tool_infos_with_config:
            mcp_cfg = tool_info['mcp_server_config']
            tool_name = tool_info['tool_name']
            if mcp_cfg and isinstance(mcp_cfg, dict) and mcp_cfg.get("url"):
                # Assuming mcp_manager.ensure_server can correctly identify/manage the server process
                # based on tool_name and its specific mcp_cfg.
                self.mcp_manager.ensure_server(tool_name, mcp_cfg)
                valid_tool_infos_for_agent.append(tool_info)
            else:
                logger.warning(f"MCP server config invalid for tool '{tool_name}'. Skipping. Config: {mcp_cfg}")

        if not valid_tool_infos_for_agent:
             logger.warning("No tools remained after mcp_manager.ensure_server validation.")
             updater.update_status(TaskState.completed, new_agent_text_message("Found tools, but none had server configurations that could be started by the manager.", task.contextId, task.id), final=True)
             return

        # 5. Build main agent's MCP client config
        mcp_servers_config_for_agent = {}
        for name, cfg in POPULAR_MCP_SERVERS.items():
            pop_url, pop_transport = cfg.get("url"), cfg.get("transport")
            if pop_url and pop_transport: mcp_servers_config_for_agent[name] = {"url": pop_url, "transport": pop_transport}
            else: logger.warning(f"Popular server '{name}' missing 'url'/'transport' in POPULAR_MCP_SERVERS. Skipping.")

        for tool_info in valid_tool_infos_for_agent:
            server_cfg = tool_info['mcp_server_config']
            server_key = server_cfg.get('url') or server_cfg.get('endpoint') # Use URL as unique key
            if not server_key:
                logger.warning(f"Tool '{tool_info['tool_name']}' mcp_server_config missing 'url'/'endpoint'. Skipping: {server_cfg}")
                continue
            if server_key not in mcp_servers_config_for_agent: # Add only if server not already listed
                srv_url = server_cfg.get('url', server_cfg.get('endpoint')) # Prefer 'url'
                srv_transport = server_cfg.get('transport', 'sse') # Default to 'sse' if not specified
                mcp_servers_config_for_agent[server_key] = {"url": srv_url, "transport": srv_transport}

        logger.info(f"Final MCP client config for agent: {mcp_servers_config_for_agent}")

        # 6. Agent Execution and Streaming with TaskUpdater
        try:
            async with MultiServerMCPClient(mcp_servers_config_for_agent) as client:
                all_tools = client.get_tools()
                required_tool_names = {ti['tool_name'] for ti in valid_tool_infos_for_agent}
                filtered_tools = [t for t in all_tools if getattr(t, 'name', None) in required_tool_names]

                if not filtered_tools and required_tool_names:
                    logger.warning(f"No tools loaded for required names: {required_tool_names}. Check server statuses.")
                    updater.update_status(TaskState.completed, new_agent_text_message(f"Could not load required tools: {', '.join(required_tool_names)}. Please check server status.", task.contextId, task.id), final=True)
                    return

                model = ChatGroq(temperature=0, groq_api_key=os.getenv("GROQ_API_KEY"), model_name="qwen-qwq-32b")
                memory = InMemorySaver()
                SYSTEM_INSTRUCTION = "You are an agent that decomposes the user's task into sub-tasks and retrieves the best tools to solve it. Give just the tools summary and workflow."
                agent = create_react_agent(model, tools=filtered_tools, prompt=SYSTEM_INSTRUCTION, checkpointer=memory)

                inputs = {'messages': [('user', user_query)]}
                config = {'configurable': {'thread_id': session_id}}

                last_streamed_content = ""
                stream_had_content = False
                final_message_content = "Agent processing complete." # Default final message

                async for chunk in agent.astream(inputs, config=config):
                    current_chunk_content = None
                    # Simplified parsing: look for content in messages list from the chunk
                    if "messages" in chunk and isinstance(chunk["messages"], list) and chunk["messages"]:
                        last_msg_in_chunk = chunk["messages"][-1]
                        if hasattr(last_msg_in_chunk, 'content'):
                            current_chunk_content = last_msg_in_chunk.content

                    # Fallback for other structures if necessary (more complex parsing can be added here)
                    # For now, we primarily rely on the 'messages' structure from create_react_agent stream.

                    if current_chunk_content and current_chunk_content != last_streamed_content:
                        updater.update_status(TaskState.working, new_agent_text_message(current_chunk_content, task.contextId, task.id))
                        last_streamed_content = current_chunk_content
                        stream_had_content = True

                # After the loop, complete the task
                # The `last_streamed_content` is considered the final result if any content was generated and streamed.
                if hasattr(updater, 'is_done') and updater.is_done(): # Hypothetical check, adapt if TaskUpdater has such a method
                    pass # Already in a final state
                elif stream_had_content:
                    updater.add_artifact([Part(root=TextPart(text=last_streamed_content))], name='final_result')
                    updater.complete()
                else: # No content was streamed, or agent finished silently
                    updater.update_status(TaskState.completed, new_agent_text_message(final_message_content, task.contextId, task.id), final=True)

        except Exception as e:
            logger.error(f"Exception during agent execution or streaming: {e}", exc_info=True)
            try:
                # Hypothetical check, adapt if TaskUpdater has such a method
                # if not (hasattr(updater, 'is_done') and updater.is_done()):
                updater.update_status(TaskState.error, new_agent_text_message(f"An error occurred: {str(e)}", task.contextId, task.id), final=True)
            except Exception as ue: # If updater itself fails
                 logger.error(f"Failed to update task status to error: {ue}", exc_info=True)

    async def cancel(self, request: RequestContext, event_queue: EventQueue) -> None:
        """Cancel a running task. (Not implemented)"""
        from a2a.types import UnsupportedOperationError
        from a2a.utils.errors import ServerError
        raise ServerError(error=UnsupportedOperationError())
