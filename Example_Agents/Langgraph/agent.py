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
        Loads agent configuration from a JSON file.

        Args:
            config_path: Path to the configuration file.

        Returns:
            A dictionary containing the loaded configuration.
        """
        print(f"Loading config from {config_path}")
        with open(config_path, "r") as config_file:
            return json.load(config_file)

    def sync_initialize_client(self):
        """
        Synchronous wrapper for `initialize_client`.
        Useful for scenarios where async operations need to be run from sync code.
        """
        asyncio.run(self.initialize_client())

    async def initialize_client(self):
        """
        Asynchronously initializes the MCP client and the LangGraph agent.

        This method:
        1. Creates a `MultiServerMCPClient` instance using server configurations
           from the loaded config.
        2. Asynchronously enters the client's context (e.g., establishing connections).
        3. Retrieves available tools from the MCP client.
        4. Creates the ReAct agent using `create_react_agent` from LangGraph,
           configuring it with the model, retrieved tools, system instruction,
           and memory checkpointer.
        """
        self.client = MultiServerMCPClient(self.config.get("mcpServers"))
        await self.client.__aenter__()
        tools = self.client.get_tools()
        self.agent = create_react_agent(
            self.model, tools=tools, prompt=self.SYSTEM_INSTRUCTION, # type: ignore
            checkpointer=self.memory
        )

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
        # Note: The result of self.agent.invoke is usually the final state,
        # but here it seems the primary goal is to update the state,
        # and then fetch the response using get_agent_response.
        self.agent.invoke({"messages": [("user", query)]}, config)
        return self.get_agent_response(config)

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
                                        (Currently hardcoded to True, may need refinement)
            - 'require_user_input' (bool): Indicates if user input is required.
                                           (Currently hardcoded to False)
            - 'content' (str): The content of the latest message in the stream.
        """
        inputs = {'messages': [('user', query)]}
        config = {'configurable': {'thread_id': sessionId}}
        async for item in self.agent.astream(inputs, config=config):
            yield {
                'is_task_complete': True,  # Or make this smarter if you want partial results
                'require_user_input': False,
                'content': item["messages"][-1].content if "messages" in item and item["messages"] else "",
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
        messages = state.values.get("messages", [])
        if messages:
            last_msg = messages[-1]
            return {
                "is_task_complete": True, # Assuming task is complete if there's a final message
                "require_user_input": False,
                "content": getattr(last_msg, "content", str(last_msg))
            }
        return {
            "is_task_complete": False, # No message, so task is not considered complete
            "require_user_input": True, # Likely needs input or something went wrong
            "content": "Unable to process your request at the moment."
        }
