# A2A Dynamic Tool Agent

This agent demonstrates an end-to-end workflow using the A2A protocol:
- Receives a user query via A2A
- Calls the Dynamic Tool Retriever MCP to get relevant tools and their MCP server configs
- Spins up new MCP servers as needed (using `MCPServerManager`)
- Loads only the exact tools required for the query
- Executes the tools using a LangGraph agent and streams the result back via A2A

## Usage

```bash
python -m Example_Agents.A2A_DynamicToolAgent --host 0.0.0.0 --port 11000
```

You can then send tasks to the agent using the A2A protocol (see `test_a2a_client.py` for an example client).

## Key Files
- `a2a_dynamic_tool_agent_executor.py`: The A2A AgentExecutor that manages tool retrieval, MCP server orchestration, and agent execution.
- `__main__.py`: Entry point for running the agent as an A2A server.
- `mcp_server_manager.py`: Utility for managing MCP server processes.

## Requirements
- The Dynamic Tool Retriever MCP and any other MCP servers must be available to be started locally.
- Environment variables (e.g., `GROQ_API_KEY`) must be set as needed for the LLM.
