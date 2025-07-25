import sys
import os
import asyncio
import logging

# Add parent directory to Python path to import MCP_Server_Manager
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mcp.server.fastmcp import FastMCP
from mcp.client.session_group import ClientSessionGroup, SseServerParameters
from MCP_Server_Manager.mcp_server_manager import MCPServerManager

logger = logging.getLogger("UnifiedMCPGateway")
logging.basicConfig(level=logging.INFO)

def component_name_hook(name, server_info):
    return f"{server_info.name}.{name}"

class UnifiedMCPGateway:
    def __init__(self, server_manager: MCPServerManager):
        self.server = FastMCP("UnifiedMCPGateway")
        self.client_group = ClientSessionGroup(None, component_name_hook)  # type: ignore
        self.server_manager = server_manager
        self.tool_catalog = {}
        self.dynamic_tool_retriever_name = "dynamic-tool-retriever"
        self.dynamic_tool_retriever_url = f"http://localhost:{self.server_manager.proxy_port}/servers/{self.dynamic_tool_retriever_name}/sse"
        self.register_meta_tools()

    async def initialize(self):
        # Connect to all popular servers at startup
        for name, config in self.server_manager.popular_servers.items():
            url = f"http://localhost:{self.server_manager.proxy_port}/servers/{name}/sse"
            params = SseServerParameters(url=url)
            logger.info(f"Connecting to server: {name} at {url}")
            await self.client_group.connect_to_server(params)
        # Optionally connect to dynamic tool retriever if configured
        try:
            params = SseServerParameters(url=self.dynamic_tool_retriever_url)
            logger.info(f"Connecting to dynamic tool retriever at {self.dynamic_tool_retriever_url}")
            await self.client_group.connect_to_server(params)
        except Exception as e:
            logger.warning(f"Could not connect to dynamic tool retriever: {e}")
        self.tool_catalog = dict(self.client_group.tools)
        logger.info(f"Unified tool catalog initialized with {len(self.tool_catalog)} tools.")
        logger.info(f"Tool catalog: {list(self.tool_catalog.keys())}")
        logger.info(f"Tool to session mapping: {self.client_group._tool_to_session}")

    async def route_tool_call(self, tool_name, args):
        logger.info(f"Routing tool call: {tool_name} with args: {args}")
        if tool_name not in self.tool_catalog:
            logger.error(f"Tool '{tool_name}' not found in unified catalog. Available: {list(self.tool_catalog.keys())}")
            return {"error": f"Tool '{tool_name}' not found in unified catalog."}
        try:
            session = self.client_group._tool_to_session.get(tool_name)
            logger.info(f"Using session: {session}")
            result = await self.client_group.call_tool(tool_name, args)
            logger.info(f"Result from backend: {result}")
            return result
        except Exception as e:
            logger.error(f"Error calling tool '{tool_name}': {e}")
            return {"error": str(e)}

    async def dynamic_tool_discovery(self, task_description: str, top_k: int = 3):
        logger.info(f"Dynamic tool discovery for: {task_description}, top_k={top_k}")
        dtr_tool_name = f"{self.dynamic_tool_retriever_name}.dynamic_tool_retriever"
        input_args = {"task_description": task_description, "top_k": top_k}
        results = await self.route_tool_call(dtr_tool_name, input_args)
        new_servers = []
        for tool in results:
            mcp_server_config = tool.get("mcp_server_config")
            if mcp_server_config and "mcpServers" in mcp_server_config:
                for name, config in mcp_server_config["mcpServers"].items():
                    if name not in self.server_manager.dynamic_servers and name not in self.server_manager.popular_servers:
                        logger.info(f"Adding and connecting to new server: {name}")
                        self.server_manager.add_server(name, config)
                        url = f"http://localhost:{self.server_manager.proxy_port}/servers/{name}/sse"
                        params = SseServerParameters(url=url)
                        await self.client_group.connect_to_server(params)
                        new_servers.append(name)
        self.tool_catalog = dict(self.client_group.tools)
        logger.info(f"Dynamic tool discovery added servers: {new_servers}")
        logger.info(f"Updated tool catalog: {list(self.tool_catalog.keys())}")
        logger.info(f"Updated tool to session mapping: {self.client_group._tool_to_session}")
        return results

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
                for name, tool in self.tool_catalog.items()
            ]

        @self.server.tool("call_tool")
        async def call_tool(tool_name: str, args: dict):
            logger.info(f"call_tool meta-tool called for: {tool_name} with args: {args}")
            return await self.route_tool_call(tool_name, args)

        @self.server.tool("dynamic_tool_discovery")
        async def dynamic_tool_discovery(task_description: str, top_k: int = 3):
            logger.info(f"dynamic_tool_discovery meta-tool called for: {task_description}, top_k={top_k}")
            return await self.dynamic_tool_discovery(task_description, top_k)

if __name__ == "__main__":
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
            "args": ["Dynamic_tool_retriever_MCP/server.py"]
        }
    }
    manager = MCPServerManager(popular_servers=POPULAR_SERVERS, proxy_port=9000)
    manager.start()
    gateway = UnifiedMCPGateway(manager)
    asyncio.run(gateway.initialize())
    gateway.server.run() 