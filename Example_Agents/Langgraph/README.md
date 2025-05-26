# LangGraph Example Agent Directory

This directory contains an example agent implementation using LangGraph, a library for building stateful, multi-actor applications with LLMs. This agent demonstrates how to integrate the Unified MCP Tool Graph with LangGraph for dynamic tool retrieval.

## Files

- **`Agent.py`**: Defines the core LangGraph agent logic, including graph definition, state management, and node functionalities.
- **`__main__.py`**: The main entry point for running the LangGraph agent. It likely handles setup, configuration, and task execution.
- **`mcp_server_config.json`**: A JSON configuration file for the MCP server that this LangGraph agent interacts with. It might specify the server address, port, and other connection details.
- **`task_manager.py`**: Contains logic for managing tasks that the LangGraph agent will process. This could include task creation, tracking, and state updates.
