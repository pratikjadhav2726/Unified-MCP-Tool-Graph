# agent.py
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
    status: Literal['input_required', 'completed', 'error'] = 'input_required'
    message: str

class ReactAgent:
    SYSTEM_INSTRUCTION = (
        "You are an agent that decomposes the user's task into sub-tasks and retrieves the best tools to solve it. "
        "Give just the tools summary and workflow."
    )

    SUPPORTED_CONTENT_TYPES = ['text', 'text/plain']

    def __init__(self, config_path):
        self.config = self.load_config(config_path)
        self.memory = InMemorySaver()
        self.model = ChatGroq(
            temperature=0,
            groq_api_key=os.getenv("GROQ_API_KEY"),
            model_name="qwen-qwq-32b"
        )
        self.client = None
        self.agent = None

    def load_config(self, config_path):
        print(f"Loading config from {config_path}")
        with open(config_path, "r") as config_file:
            return json.load(config_file)
    def sync_initialize_client(self):
        asyncio.run(self.initialize_client())
    async def initialize_client(self):
        self.client = MultiServerMCPClient(self.config.get("mcpServers"))
        await self.client.__aenter__()
        tools = self.client.get_tools()
        self.agent = create_react_agent(
            self.model, tools=tools, prompt=self.SYSTEM_INSTRUCTION,
            checkpointer=self.memory
        )

    def invoke(self, query, sessionId) -> dict:
        config = {"configurable": {"thread_id": sessionId}}
        self.agent.invoke({"messages": [("user", query)]}, config)
        return self.get_agent_response(config)

    async def stream(self, query, sessionId) -> AsyncIterable[dict[str, Any]]:
        inputs = {'messages': [('user', query)]}
        config = {'configurable': {'thread_id': sessionId}}
        async for item in self.agent.astream(inputs, config=config):
            yield {
                'is_task_complete': True,  # Or make this smarter if you want partial results
                'require_user_input': False,
                'content': item["messages"][-1].content if "messages" in item else "",
            }

    def get_agent_response(self, config):
        state = self.agent.get_state(config)
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