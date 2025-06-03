# Dynamic Tool Retriever MCP Directory

This directory contains the core components for the Dynamic Tool Retriever based on the Model Context Protocol (MCP).

## Files

- **`embedder.py`**: This script is responsible for generating embeddings for tool descriptions. These embeddings are used for semantic search and retrieval of tools.
- **`neo4j_retriever.py`**: This script handles the interaction with the Neo4j graph database. It provides functionalities to query the graph and retrieve tools based on various criteria.
- **`server.py`**: This script likely implements the MCP server functionality, allowing agents to connect and dynamically retrieve tools.

## Example MCP Server Config

```json
{
  "mcpServers": [
    {
      "name": "Dynamic Tool Retriever MCP",
      "description": "Retrieves the most relevant tools for a user query using semantic search over a Neo4j graph.",
      "command": "python",
      "args": ["Dynamic_tool_retriever_MCP/server.py"],
      "endpoint": "http://localhost:8001",
      "env": {
        "NEO4J_URI": "bolt://localhost:7687",
        "NEO4J_USER": "neo4j",
        "NEO4J_PASSWORD": "your_password"
      }
    }
  ]
}
```

- Adjust the `endpoint` and `env` values as needed for your deployment.
- This config can be used by agent managers to spin up or connect to the Dynamic Tool Retriever MCP server.
