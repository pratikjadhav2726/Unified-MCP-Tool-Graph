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
from pydantic import BaseModel
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
        self.model = ChatGroq(
            temperature=0,
            groq_api_key=os.getenv("GROQ_API_KEY"),
            model_name="qwen-qwq-32b"
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
        """
        Async context manager entry: initializes MCP client and agent, keeps connection open for agent lifetime.
        """
        self.client = MultiServerMCPClient(self.config.get("mcpServers"))
        await self.client.__aenter__()
        tools = self.client.get_tools()
        print("[DEBUG] Loaded tools:", [(t.name, type(t)) for t in tools])  # Debug print
        self.agent = create_react_agent(
            self.model, tools=tools, prompt=self.SYSTEM_INSTRUCTION, # type: ignore
            checkpointer=self.memory
        )
        return self

    async def __aexit__(self, exc_type, exc, tb):
        """
        Async context manager exit: closes MCP client connection.
        """
        if self.client:
            await self.client.__aexit__(exc_type, exc, tb)
        self.client = None
        self.agent = None

    # Deprecated: keep for backward compatibility, but warn users
    async def initialize_client(self):
        print("[WARNING] initialize_client is deprecated. Use 'async with ReactAgent(...) as agent:' instead.")
        await self.__aenter__()

    def invoke(self, query: str, sessionId: str) -> dict:
        """
        Invokes the LangGraph agent with a user query in a synchronous manner.

        Args:
            query: The user's query string.
            sessionId: A unique identifier for the current session/thread.

        Returns:
            A dictionary containing the agent's final response, formatted by
            `get_agent_response`.
        """
        config = {"configurable": {"thread_id": sessionId}}
        try:
            self.agent.invoke({"messages": [("user", query)]}, config)
            return self.get_agent_response(config)
        except Exception as e:
            print(f"[ERROR] Agent invocation failed: {e}")
            return {"is_task_complete": False, "require_user_input": True, "content": str(e)}

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
        async for item in self.agent.astream(inputs, config=config):
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

        Args:
            config: The configuration dictionary, typically containing the thread_id,
                    used to fetch the agent's state.

        Returns:
            A dictionary with the agent's response:
            - "is_task_complete" (bool): True if a message is found, False otherwise.
            - "require_user_input" (bool): False if a message is found, True otherwise.
            - "content" (str): The content of the last message, or an error message.
        """
        state = self.agent.get_state(config)
        # Try to extract a structured/tool response if present
        structured_response = state.values.get('structured_response')
        if structured_response:
            if hasattr(structured_response, 'dict'):
                structured_response = structured_response.dict()
            status = structured_response.get('status', 'completed')
            message = structured_response.get('message', '')
            return {
                'is_task_complete': status == 'completed',
                'require_user_input': status == 'input_required',
                'content': message,
            }
        # Fallback: extract last message content
        messages = state.values.get("messages", [])
        if messages:
            last_msg = messages[-1]
            return {
                "is_task_complete": True,
                "require_user_input": False,
                "content": getattr(last_msg, "content", str(last_msg))
            }
        return {
            "is_task_complete": False,
            "require_user_input": True,
            "content": "Unable to process your request at the moment."
        }
