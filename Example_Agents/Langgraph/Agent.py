from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_mcp_adapters.tools import load_mcp_tools
from langgraph.prebuilt import create_react_agent
import os
import asyncio
import json
from langchain_groq import ChatGroq
from langgraph.checkpoint.memory import InMemorySaver
import dotenv
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
        self.memory = InMemorySaver()
    def pretty_print_stream_chunk(self,chunk):
        for node, updates in chunk.items():
            print(f"Update from node: {node}")
            if "messages" in updates:
                updates["messages"][-1].pretty_print()
            else:
                print(updates)

            print("\n")
        return chunk
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
        self.agent = create_react_agent(model,tools=tools,prompt=prompt,checkpointer=self.memory)

    async def process_message(self, message):
        config = {"configurable": {"thread_id": "1"}}
        async for chunk in self.agent.astream({"messages": [{"role": "user", "content": message}]},config=config):
        # Extract relevant parts
            self.pretty_print_stream_chunk(chunk)

    async def run(self):
        # pp = pprint.PrettyPrinter(indent=2, width=30, compact=True)
        await self.initialize_client()
        while True:
            user_input = input("Enter your message (or 'exit' to quit): ")
            if user_input.lower() == 'exit':
                break
            ai_messages = await self.process_message(user_input)
        await self.client.__aexit__(None, None, None)

if __name__ == "__main__":
    config_path = "Example_Agents/Langgraph/mcp_server_config.json"
    agent = ReactAgent(config_path)
    asyncio.run(agent.run())