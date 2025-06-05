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
        print(f"[ERROR] Failed to call dynamic tool retriever MCP: {e}")
        return []

class A2ADynamicToolAgentExecutor(AgentExecutor):
    def __init__(self):
        self.mcp_manager = MCPServerManager(POPULAR_MCP_SERVERS)
        self.mcp_manager.start_popular_servers()
        # Optionally: asyncio.create_task(self.mcp_manager.cleanup_loop())

    async def execute(self, context: RequestContext, event_queue: EventQueue):
        task = context.current_task
        if not task:
            # This part might need adjustment based on how A2A framework expects tasks to be created/retrieved.
            # If context.task is guaranteed to exist, this might not be needed.
            # For now, let's assume context.task might be sufficient.
            task = new_task(context.message) # Or handle if task is always present
            # If new_task is used, ensure event_queue.enqueue_event(task) is called appropriately if not handled by A2A framework
        updater = TaskUpdater(event_queue, task.id, task.contextId)

        user_query = task.input.text if task.input else ""
        session_id = f"session-{int(time.time())}"

        # 1. Get required tools from dynamic tool retriever
        tool_infos = call_dynamic_tool_retriever_mcp(user_query, top_k=3)

        # 2. Ensure all required MCP servers are running
        valid_tool_infos = [] # Keep track of tools with valid configs
        for tool_info in tool_infos: # Renamed to avoid confusion with loop var 'tool' later
            mcp_cfg = tool_info.get('mcp_server_config')
            tool_name = tool_info.get('tool_name')

            if not tool_name:
                logger.warning(f"Tool information missing 'tool_name'. Skipping: {tool_info}")
                continue

            if mcp_cfg and isinstance(mcp_cfg, dict) and mcp_cfg.get("endpoint"): # Basic check for a valid-looking config
                self.mcp_manager.ensure_server(tool_name, mcp_cfg)
                valid_tool_infos.append(tool_info) # Add to list of tools to be used
            else:
                logger.warning(f"MCP server config missing or invalid for tool '{tool_name}'. Tool will not be available. Config: {mcp_cfg}")
                # Optionally, decide if this tool should still be considered for 'required_tool_names'
                # or if it should be excluded if its server cannot be started.
                # For now, we will exclude it from being actively managed by mcp_manager if config is bad,
                # and it might subsequently be filtered out if its server isn't in POPULAR_MCP_SERVERS.

        # 3. Build MCP server config for only the 5 popular and new required
        # This part should now primarily use POPULAR_MCP_SERVERS and then add
        # valid dynamic tools that were successfully ensured.
        mcp_servers_config = {}
        for name, cfg in POPULAR_MCP_SERVERS.items():
            mcp_servers_config[name] = {"url": cfg["endpoint"], "transport": "sse"} # Assuming sse, or make it configurable

        for tool_info in valid_tool_infos: # Iterate over tools that had valid configs
            mcp_cfg = tool_info['mcp_server_config'] # We know this is valid from check above
            tool_name = tool_info['tool_name']
            # Add to mcp_servers_config if not already there from popular servers
            if tool_name not in mcp_servers_config:
                 # Ensure mcp_cfg has 'url' and 'transport' or adapt as needed.
                 # The dynamic_tool_retriever returns a full mcp_server_config structure.
                if "url" in mcp_cfg and "transport" in mcp_cfg:
                    mcp_servers_config[tool_name] = {
                        "url": mcp_cfg["url"],
                        "transport": mcp_cfg["transport"]
                    }
                elif "endpoint" in mcp_cfg: # If only endpoint is there, assume sse or default
                     mcp_servers_config[tool_name] = {
                        "url": mcp_cfg["endpoint"],
                        "transport": mcp_cfg.get("transport", "sse") # Default to sse if not specified
                    }
                else:
                    logger.warning(f"Cannot form client config for tool '{tool_name}' due to missing 'url' or 'endpoint' in mcp_cfg: {mcp_cfg}")


        # 4. Only load the exact tools retrieved
        # The 'required_tool_names' should now be based on 'valid_tool_infos'
        # or tools whose servers are confirmed to be running.
        async with MultiServerMCPClient(mcp_servers_config) as client:
            all_tools = client.get_tools()
            # Update required_tool_names to only include tools that are expected to be available
            required_tool_names = {ti['tool_name'] for ti in valid_tool_infos if ti.get('tool_name')}
            # Also add tools from POPULAR_MCP_SERVERS if they were requested by the retriever,
            # assuming the retriever might return names of popular tools as well.
            # For simplicity, we'll rely on the retriever's output for required_tool_names.
            # If a tool from tool_infos (even if popular) had bad config, it won't be in valid_tool_infos.

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
                # Default values
                is_task_complete = False
                require_user_input = False
                content = ""

                # Check for structured response from ReactAgent's stream method
                if isinstance(item, dict):
                    is_task_complete = item.get('is_task_complete', False)
                    require_user_input = item.get('require_user_input', False)
                    content = item.get('content', '')
                else: # Fallback for direct content or other structures from agent.astream
                    agent_state = item.get('agent') if isinstance(item, dict) else None # Langgraph specific
                    if agent_state and isinstance(agent_state, dict) and 'messages' in agent_state:
                        messages = agent_state['messages']
                        content = getattr(messages[-1], 'content', str(messages[-1])) if messages else ''
                    elif 'messages' in item and item['messages']: # General structure from create_react_agent
                        messages = item['messages']
                        content = getattr(messages[-1], 'content', str(messages[-1]))
                    elif hasattr(item, 'content'): # Simpler direct content
                         content = item.content
                    else: # Catch all for unexpected item structure
                        content = str(item)

                if not is_task_complete and not require_user_input:
                    updater.update_status(
                        TaskState.working,
                        new_agent_text_message(
                            content,
                            task.contextId,
                            task.id,
                        ),
                    )
                elif require_user_input:
                    updater.update_status(
                        TaskState.input_required,
                        new_agent_text_message(
                            content,
                            task.contextId,
                            task.id,
                        ),
                        final=True, # Mark as final if input is required
                    )
                    break # Exit loop as we are waiting for user input
                else: # Task is complete
                    updater.add_artifact(
                        [Part(root=TextPart(text=content if content else "Task completed successfully."))], # Ensure content is not empty
                        name='tool_result', # Or a more appropriate name
                    )
                    updater.complete()
                    break # Exit loop as task is complete
        except Exception as e:
            # Handle exceptions during agent execution
            error_message = f"Error during agent execution: {str(e)}"
            print(f"[ERROR] {error_message}")
            # Ensure updater is defined in this scope, or handle error reporting differently if client setup fails
            if 'updater' in locals():
                updater.update_status(
                    TaskState.error,
                    new_agent_text_message(
                        error_message,
                        task.contextId,
                        task.id,
                    ),
                    final=True,
                )
            # else: # Basic error logging if updater isn't available
                # print(f"[CRITICAL ERROR] Agent execution failed before updater initialization: {error_message}")


    async def cancel(self, request: RequestContext, event_queue: EventQueue) -> None:
        """Cancel a running task. (Not implemented)"""
        # You can implement actual cancellation logic here if needed.
        # For now, raise unsupported operation to match Langgraph pattern.
        from a2a.types import UnsupportedOperationError
        from a2a.utils.errors import ServerError
        raise ServerError(error=UnsupportedOperationError())
