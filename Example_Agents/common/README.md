# Common Utilities Directory

This directory contains common modules, utilities, and base classes shared across different example agent implementations.

## Subdirectories

- **`client/`**: Contains client-side components for interacting with MCP (Model Context Protocol) servers.
  - `__init__.py`: Initializes the client module.
  - `card_resolver.py`: Likely handles resolving or managing agent cards or capabilities.
  - `client.py`: Provides the main client logic for MCP communication, including connecting to servers, sending requests, and handling responses.
- **`server/`**: Contains server-side components and base classes for building agent servers.
  - `__init__.py`: Initializes the server module.
  - `server.py`: Provides a base or generic A2A (Agent-to-Agent) server implementation.
  - `task_manager.py`: Offers base classes or utilities for managing agent tasks.
  - `utils.py`: Contains miscellaneous utility functions for server-side operations.
- **`utils/`**: Contains general utility modules that can be used by both client and server components.
  - `in_memory_cache.py`: Implements an in-memory caching mechanism.
  - `push_notification_auth.py`: Handles authentication for push notifications.

## Files

- **`__init__.py`**: Initializes the common module.
- **`types.py`**: Defines common data types, Pydantic models, or enums used throughout the example agents and their interactions.
