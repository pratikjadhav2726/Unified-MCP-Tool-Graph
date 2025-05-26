"""
Provides a resolver for fetching Agent Cards from A2A (Agent-to-Agent) servers.

The Agent Card contains metadata about an agent, such as its capabilities,
supported modalities, and available skills. This module allows clients to
discover this information from a standardized endpoint.
"""
import json

import httpx

from common.types import (
    A2AClientJSONError,
    AgentCard,
)


class A2ACardResolver:
    """
    Resolves and retrieves an AgentCard from a remote A2A server.

    The AgentCard provides metadata about an agent, such as its name,
    description, capabilities, and available skills. This resolver fetches
    this information from a well-known URI on the agent server.
    """
    def __init__(self, base_url: str, agent_card_path: str = '/.well-known/agent.json'):
        """
        Initializes the A2ACardResolver.

        Args:
            base_url: The base URL of the A2A server (e.g., "http://localhost:10000").
            agent_card_path: The path to the agent card JSON file on the server.
                             Defaults to "/.well-known/agent.json".
        """
        self.base_url = base_url.rstrip('/')
        self.agent_card_path = agent_card_path.lstrip('/')

    def get_agent_card(self) -> AgentCard:
        """
        Fetches and parses the AgentCard from the configured A2A server endpoint.

        The method constructs the full URL from `base_url` and `agent_card_path`,
        makes an HTTP GET request, and then parses the JSON response into an
        `AgentCard` Pydantic model.

        Returns:
            An `AgentCard` instance populated with the metadata from the server.

        Raises:
            httpx.HTTPStatusError: If the server returns an HTTP error status
                                   (e.g., 404 Not Found, 500 Internal Server Error).
            A2AClientJSONError: If the response content is not valid JSON or
                                cannot be parsed into an `AgentCard` model.
                                This typically wraps `json.JSONDecodeError`
                                or Pydantic's `ValidationError`.
        """
        with httpx.Client() as client:
            full_url = f"{self.base_url}/{self.agent_card_path}"
            response = client.get(full_url)
            response.raise_for_status()  # Raises HTTPStatusError for 4xx/5xx responses
            try:
                # Assuming AgentCard is a Pydantic model
                return AgentCard(**response.json())
            except json.JSONDecodeError as e:
                raise A2AClientJSONError(f"Failed to decode JSON from {full_url}: {e}") from e
            # Pydantic's ValidationError can also occur if JSON structure doesn't match AgentCard
            # This will be caught by a broader exception handler if not specified,
            # or could be explicitly caught if A2AClientJSONError is designed to wrap it.
            # For now, relying on A2AClientJSONError for JSON issues.
