# Dynamic Tool Retriever MCP Directory

This directory contains the core components for the Dynamic Tool Retriever based on the Model Context Protocol (MCP).

## Files

- **`embedder.py`**: This script is responsible for generating embeddings for tool descriptions. These embeddings are used for semantic search and retrieval of tools.
- **`neo4j_retriever.py`**: This script handles the interaction with the Neo4j graph database. It provides functionalities to query the graph and retrieve tools based on various criteria.
- **`server.py`**: This script likely implements the MCP server functionality, allowing agents to connect and dynamically retrieve tools.
