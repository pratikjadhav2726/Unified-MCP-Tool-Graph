"""
Defines a LangGraph-based ReAct agent that interacts with MCP (Model Context Protocol)
servers to dynamically utilize tools.

This module contains:
- ResponseFormat: A Pydantic model for standardizing response structures.
- ReactAgent: The core class implementing the LangGraph agent logic, including
  state management, MCP client interaction, and message processing.
"""
import asyncio
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_mcp_adapters.tools import load_mcp_tools
from langgraph.prebuilt import create_react_agent
from langchain_groq import ChatGroq
from langgraph.checkpoint.memory import InMemorySaver
import os
import json
from pydantic import BaseModel, SecretStr
from typing import Any, AsyncIterable, Literal

class ResponseFormat(BaseModel):
    """
    Defines the standardized response format for agent interactions.
    """
    status: Literal['input_required', 'completed', 'error'] = 'input_required'
    """The status of the agent's processing.
    - 'input_required': Agent needs more input.
    - 'completed': Agent has completed the task.
    - 'error': An error occurred.
    """
    message: str
    """A descriptive message accompanying the status."""

class ReactAgent:
    """
    A ReAct (Reasoning and Acting) agent implemented using LangGraph.

    This agent connects to MCP servers defined in a configuration file,
    loads tools from these servers, and uses a language model (ChatGroq)
    to process user queries by reasoning and selecting appropriate tools.
    It maintains conversation state using an in-memory checkpointer.
    """
    SYSTEM_INSTRUCTION = (
        "You are an agent that decomposes the user's task into sub-tasks and retrieves the best tools to solve it. "
        "Give just the tools summary and workflow."
         'Set response status to input_required if the user needs to provide more information.'
        'Set response status to error if there is an error while processing the request.'
        'Set response status to completed if the request is complete.'
    )
    """Default system instruction provided to the language model."""

    SUPPORTED_CONTENT_TYPES = ['text', 'text/plain']
    """List of supported content types for user input."""

    def __init__(self, config_path: str):
        """
        Initializes the ReactAgent.

        Args:
            config_path: Path to the JSON configuration file. This file should
                         contain details for connecting to MCP servers, typically
                         under an "mcpServers" key.
        """
        self.config = self.load_config(config_path)
        self.memory = InMemorySaver()
        """In-memory checkpointer for saving and loading LangGraph state."""
        api_key = os.getenv("GROQ_API_KEY")
        if api_key is not None:
            api_key = SecretStr(api_key)
        self.model = ChatGroq(
            temperature=0,
            api_key=api_key,
            model="deepseek-r1-distill-llama-70b"
        )
        """The language model used by the agent (ChatGroq)."""
        self.client: MultiServerMCPClient | None = None
        """Client for interacting with MCP servers. Initialized by `initialize_client`."""
        self.agent = None
        """The LangGraph agent instance. Initialized by `initialize_client`."""

    def load_config(self, config_path: str) -> dict:
        """
        Loads agent configuration from a JSON file with error handling.

        Args:
            config_path: Path to the configuration file.

        Returns:
            A dictionary containing the loaded configuration.
        Raises:
            FileNotFoundError: If the config file does not exist.
            json.JSONDecodeError: If the config file is not valid JSON.
        """
        print(f"Loading config from {config_path}")
        try:
            with open(config_path, "r") as config_file:
                return json.load(config_file)
        except FileNotFoundError as e:
            print(f"[ERROR] Config file not found: {e}")
            raise
        except json.JSONDecodeError as e:
            print(f"[ERROR] Failed to decode config JSON: {e}")
            raise

    async def __aenter__(self):
        self.client = MultiServerMCPClient(self.config.get("mcpServers"))
        tools = await self.client.get_tools()
        print("[DEBUG] Loaded tools:", [(t.name, type(t)) for t in tools])
        self.agent = create_react_agent(
            self.model, tools=tools, prompt=self.SYSTEM_INSTRUCTION, checkpointer=self.memory
        )
        return self

    async def __aexit__(self, exc_type, exc, tb):
        self.client = None
        self.agent = None

    # Deprecated: keep for backward compatibility, but warn users
    async def initialize_client(self):
        print("[WARNING] initialize_client is deprecated. Use 'async with ReactAgent(...) as agent:' instead.")
        await self.__aenter__()

    def invoke(self, query: str, sessionId: str) -> dict:
        """
        Invokes the LangGraph agent with a user query in a synchronous manner.
        (Disabled for standalone test runner; use async streaming instead.)
        """
        raise NotImplementedError("Synchronous invoke is not supported in standalone mode. Use async streaming.")

    async def stream(self, query: str, sessionId: str) -> AsyncIterable[dict[str, Any]]:
        """
        Streams responses from the LangGraph agent for a user query.

        This method allows for receiving intermediate steps and the final response
        as the agent processes the query.

        Args:
            query: The user's query string.
            sessionId: A unique identifier for the current session/thread.

        Yields:
            Dictionaries representing events or messages from the agent's stream.
            Each dictionary includes:
            - 'is_task_complete' (bool): Indicates if the task is considered complete.
            - 'require_user_input' (bool): Indicates if user input is required.
            - 'content' (str): The content of the latest message in the stream.
        """
        inputs = {'messages': [('user', query)]}
        config = {'configurable': {'thread_id': sessionId}}
        if not self.agent:
            raise RuntimeError("Agent is not initialized. Use 'async with ReactAgent' context.")
        # Type ignore to satisfy linter for RunnableConfig
        async for item in self.agent.astream(inputs, config=config):  # type: ignore
            print("[DEBUG] LangGraph agent stream item:", item)  # Debug print

            # Check for structured/tool response
            agent_state = item.get('agent') if isinstance(item, dict) else None
            # Fix: agent_state.values is a method, not a dict. Use agent_state.values if it's a dict, else getattr
            structured_response = None
            if agent_state:
                values = getattr(agent_state, 'values', None)
                if isinstance(values, dict):
                    structured_response = values.get('structured_response')
            if structured_response:
                if hasattr(structured_response, 'dict'):
                    structured_response = structured_response.dict()
                status = structured_response.get('status', 'completed')
                message = structured_response.get('message', '')
                yield {
                    'is_task_complete': status == 'completed',
                    'require_user_input': status == 'input_required',
                    'content': message,
                }
                if status == 'completed':
                    break
                continue

            # Fallback: extract last message content
            if agent_state and isinstance(agent_state, dict) and 'messages' in agent_state:
                messages = agent_state['messages']
                content = getattr(messages[-1], 'content', str(messages[-1])) if messages else ''
            elif 'messages' in item and item['messages']:
                messages = item['messages']
                content = getattr(messages[-1], 'content', str(messages[-1]))
            elif 'content' in item:
                content = item['content']
            else:
                content = ''
            yield {
                'is_task_complete': False,
                'require_user_input': False,
                'content': content,
            }

    def get_agent_response(self, config: dict) -> dict:
        """
        Retrieves the current state of the agent for a given configuration
        and formats the last message as the response.
        (Disabled for standalone test runner; use async streaming instead.)
        """
        raise NotImplementedError("get_agent_response is not supported in standalone mode. Use async streaming.")

# --- Add a minimal test runner at the bottom ---
if __name__ == "__main__":
    import asyncio
    import sys

    async def test_agent():
        config_path = sys.argv[1] if len(sys.argv) > 1 else "mcp_server_config.json"
        async with ReactAgent(config_path) as agent:
            user_query = input("Enter your query: ")
            session_id = "test-session"
            async for result in agent.stream(user_query, session_id):
                print(result)

    asyncio.run(test_agent())
