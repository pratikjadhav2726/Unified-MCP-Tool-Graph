import sys
import os
import asyncio
import logging
import traceback
from contextlib import AsyncExitStack

# Add parent directory to Python path to import MCP_Server_Manager
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mcp.server.fastmcp import FastMCP
from mcp.client.session_group import ClientSessionGroup, SseServerParameters
from MCP_Server_Manager.mcp_server_manager import MCPServerManager
from mcp.client.session import ClientSession
from mcp.client.sse import sse_client
from mcp.client.stdio import stdio_client, StdioServerParameters

logger = logging.getLogger("UnifiedMCPGateway")
logging.basicConfig(level=logging.INFO)

def component_name_hook(name, server_info):
    return f"{server_info.name}.{name}"

class ProxiedServer:
    def __init__(self, name, config):
        self.name = name
        self.config = config
        self.session = None
        self.exit_stack = AsyncExitStack()
        self.tools = []

    async def start(self):
        params = StdioServerParameters(
            command=self.config.get("command", ""),
            args=self.config.get("args", []),
            env=self.config.get("env", None),
        )
        client_cm = stdio_client(params)
        read, write = await self.exit_stack.enter_async_context(client_cm)
        session_cm = ClientSession(read, write)
        self.session = await self.exit_stack.enter_async_context(session_cm)
        await self.session.initialize()
        self.tools = (await self.session.list_tools()).tools

    async def stop(self):
        await self.exit_stack.aclose()
        self.session = None

class UnifiedMCPGateway:
    def __init__(self, server_manager: MCPServerManager):
        self.server = FastMCP("UnifiedMCPGateway")
        self.server_manager = server_manager
        self.servers = {}  # name -> ProxiedServer
        self.tool_catalog = {}  # tool_name -> (server_name, tool)
        self.dynamic_tool_retriever_name = "dynamic-tool-retriever"
        self.dynamic_tool_retriever_url = f"http://localhost:{self.server_manager.proxy_port}/servers/{self.dynamic_tool_retriever_name}/sse"
        self.register_meta_tools()

    async def initialize(self):
        # Start all popular servers and cache their tools
        for name, config in self.server_manager.popular_servers.items():
            logger.info(f"Starting and connecting to server: {name}")
            server = ProxiedServer(name, config)
            await server.start()
            self.servers[name] = server
        # Aggregate all tools for routing
        self.tool_catalog = {
            f"{name}.{tool.name}": (name, tool)
            for name, server in self.servers.items()
            for tool in server.tools
        }
        logger.info(f"Unified tool catalog initialized with {len(self.tool_catalog)} tools.")
        logger.info(f"Tool catalog: {list(self.tool_catalog.keys())}")

    async def route_tool_call(self, tool_name, args):
        logger.info(f"Routing tool call: {tool_name} with args: {args}")
        if tool_name not in self.tool_catalog:
            logger.error(f"Tool '{tool_name}' not found in unified catalog. Available: {list(self.tool_catalog.keys())}")
            return {"error": f"Tool '{tool_name}' not found in unified catalog."}
        try:
            server_name, tool = self.tool_catalog[tool_name]
            logger.info(f"Tool: {tool}")
            server = self.servers[server_name]
            if server.session is None:
                logger.error(f"Session for server '{server_name}' is not active.")
                return {"error": f"Session for server '{server_name}' is not active."}
            logger.info(f"Using persistent session for server: {server_name}")
            # Wrap args in input object as per MCP protocol
            formatted_args = {"input": args} if args else {"input": {}}
            logger.info(f"Calling tool '{tool_name}' with formatted args: {formatted_args}")
            result = await server.session.call_tool(tool, formatted_args)
            logger.info(f"Result from backend: {result}")
            return result
        except Exception as e:
            logger.error(f"Error calling tool '{tool_name}': {e}\n{traceback.format_exc()}")
            return {"error": str(e)}

    def register_meta_tools(self):
        @self.server.tool("list_tools")
        async def list_tools():
            logger.info("list_tools called")
            return [
                {
                    "tool_name": name,
                    "description": getattr(tool, "description", ""),
                    "parameters": getattr(tool, "parameters", None),
                }
                for name, (server_name, tool) in self.tool_catalog.items()
            ]

        @self.server.tool("call_tool")
        async def call_tool(tool_name: str, args: dict):
            logger.info(f"call_tool meta-tool called for: {tool_name} with args: {args}")
            return await self.route_tool_call(tool_name, args)

async def call_tool_on_server(server_name, tool_name, args):
    url = f"http://localhost:9000/servers/{server_name}/sse"
    async with sse_client(url) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            return await session.call_tool(tool_name, args)

if __name__ == "__main__":
    PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    POPULAR_SERVERS = {
        "tavily-mcp": {
            "command": "npx",
            "args": ["-y", "tavily-mcp@latest"],
            "env": {"TAVILY_API_KEY": "your-api-key-here"}
        },
        "sequential-thinking": {
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-sequential-thinking"]
        },
        "time": {
            "command": "uvx",
            "args": ["mcp-server-time"]
        },
        "dynamic-tool-retriever": {
            "command": "python",
            "args": [os.path.join(PROJECT_ROOT, "Dynamic_tool_retriever_MCP", "server.py")]
        }
    }
    manager = MCPServerManager(popular_servers=POPULAR_SERVERS, proxy_port=9000)
    manager.start()
    gateway = UnifiedMCPGateway(manager)
    asyncio.run(gateway.initialize())
    gateway.server.run() 