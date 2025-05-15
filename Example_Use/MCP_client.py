from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_mcp_adapters.tools import load_mcp_tools
from langgraph.prebuilt import create_react_agent
import os
import asyncio
import json
from langchain_groq import ChatGroq
import dotenv
import pprint
dotenv.load_dotenv()
model = ChatGroq(
            temperature=0, 
            groq_api_key=os.getenv("GROQ_API_KEY"), 
            model_name="qwen-qwq-32b"
        )

class ReactAgent:
    def __init__(self, config_path):
        self.config = self.load_config(config_path)
        self.client = None
        self.agent = None

    def load_config(self, config_path):
        try:
            with open(config_path, "r") as config_file:
                return json.load(config_file)
        except FileNotFoundError:
            raise FileNotFoundError(f"Configuration file '{config_path}' not found.")
        except json.JSONDecodeError as e:
            raise ValueError(f"Error decoding JSON from '{config_path}': {e}")

    async def initialize_client(self):
        self.client = MultiServerMCPClient(self.config.get("mcpServers"))
        await self.client.__aenter__()
        tools = self.client.get_tools()
        prompt= "your task is to break down the user task into sub-tasks and retrieve best tools to solve the task. give just the tools summary and workflow"
        self.agent = create_react_agent(model,tools=tools,prompt=prompt)

    async def process_message(self, message):
        response = await self.agent.ainvoke({"messages": [{"role": "user", "content": message}]})
        # Extract relevant parts
        messages = response.get("messages", response)  # fallback if response is a list
        tool_calls = []
        tool_responses = []
        ai_messages = []
        for msg in messages:
            # Tool call (AIMessage with tool_calls)
            if hasattr(msg, "tool_calls") and msg.tool_calls:
                tool_calls.extend(msg.tool_calls)
            # Tool response (ToolMessage)
            if msg.__class__.__name__ == "ToolMessage":
                tool_responses.append(msg.content)
            # AI message (AIMessage with content)
            if msg.__class__.__name__ == "AIMessage" and msg.content:
                ai_messages.append(msg.content)
        return tool_calls, tool_responses, ai_messages

    async def run(self):
        pp = pprint.PrettyPrinter(indent=2, width=30, compact=True)
        await self.initialize_client()
        while True:
            user_input = input("Enter your message (or 'exit' to quit): ")
            if user_input.lower() == 'exit':
                break
            tool_calls, tool_responses, ai_messages = await self.process_message(user_input)
            if tool_calls:
                print("Tool Calls:")
                for call in tool_calls:
                    pp.pprint(call)
                    # prettyprint(call)
            if tool_responses:
                print("Tool Responses:")
                for resp in tool_responses:
                    pp.pprint(resp)
            if ai_messages:
                print("AI Messages:")
                for msg in ai_messages:
                    print(msg)
        await self.client.__aexit__(None, None, None)

if __name__ == "__main__":
    config_path = "Example_Use/mcp_server_config.json"
    agent = ReactAgent(config_path)
    asyncio.run(agent.run())