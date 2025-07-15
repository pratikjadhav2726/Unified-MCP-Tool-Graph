# LangGraph A2A Agent Example

This directory contains a robust, SOLID-compliant example of integrating a LangGraph agent with the [Agent2Agent (A2A) Protocol](https://github.com/a2aproject/a2a-python) and [Model Context Protocol (MCP)](https://github.com/modelcontextprotocol/python-sdk). The agent dynamically loads tools from MCP servers and exposes them via an A2A-compatible API.

---

## Features
- **LangGraph agent** with dynamic MCP tool loading
- **A2A server** for agent-to-agent interoperability
- **SOLID principles**: extensible, testable, and maintainable
- **Async context management** for resource safety
- **Tested A2A client** for end-to-end validation

---

## 1. Installation

**Python 3.10+ required.**

Install dependencies:
```bash
pip install -r requirements.txt
pip install a2a-sdk langchain-mcp-adapters httpx uvicorn
```

---

## 2. Configuration

Edit `mcp_server_config.json` to point to your running MCP server:
```json
{
  "mcpServers": {
    "UnifiedMCP": {
      "url": "http://localhost:8000/mcp/",
      "transport": "streamable_http"
    }
  }
}
```
- Make sure your MCP server is running and reachable at the specified URL.

---

## 3. Running the LangGraph A2A Server

From the project root, start the server:
```bash
python -m Example_Agents.Langgraph --host localhost --port 10020 --config Example_Agents/Langgraph/mcp_server_config.json
```
- The server will be available at `http://localhost:10020` by default.

---

## 4. Testing with the A2A Client

A ready-to-use test client is provided:
```bash
python Example_Agents/Langgraph/test_a2a_client.py
```
- This script will:
  - Discover the agent via its A2A metadata endpoint
  - Send a sample message ("I want to post on linkedin using google search")
  - Print the agent's response

---

## 5. Code Structure

- `agent.py` — LangGraph agent that loads tools from MCP and supports async context
- `generic_langgraph_executor.py` — Generic, SOLID-compliant executor for any LangGraph agent
- `langgraph_server_utils.py` — Utilities for creating A2A-compatible servers
- `__main__.py` — Entrypoint for running the A2A server
- `test_a2a_client.py` — Example/test A2A client
- `mcp_server_config.json` — MCP server configuration

---

## 6. Extending the Agent
- To add new skills or change the agent, edit `agent.py` and update the skills in `__main__.py`.
- The executor and server utilities are open for extension and closed for modification (SOLID).

---

## 7. Troubleshooting
- **ModuleNotFoundError**: Use relative imports (with a dot) for all local modules.
- **Agent is not initialized**: The executor now always uses async context management for the agent.
- **Session terminated**: Ensure your MCP server is running and the config is correct.

---

## 8. References
- [LangGraph](https://github.com/langchain-ai/langgraph)
- [A2A Python SDK](https://github.com/a2aproject/a2a-python)
- [Model Context Protocol Python SDK](https://github.com/modelcontextprotocol/python-sdk)
- [LangChain MCP Adapters](https://github.com/langchain-ai/langchain-mcp-adapters)

---

## 9. License
MIT License
