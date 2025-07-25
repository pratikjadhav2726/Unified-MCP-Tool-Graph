import asyncio
import logging
import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from contextlib import AsyncExitStack
from mcp.server.fastmcp import FastMCP
from mcp.client.session_group import ClientSessionGroup, SseServerParameters
from MCP_Server_Manager.mcp_server_manager import MCPServerManager

# Optional: import your dynamic tool retriever if needed
# from Dynamic_tool_retriever_MCP.server import ...

logger = logging.getLogger("UnifiedMCPGateway")

def component_name_hook(name, server_info):
    return f"{server_info.name}.{name}"

class UnifiedMCPGateway:
    def __init__(self, server_manager: MCPServerManager):
        # MCP server exposed to clients
        self.server = FastMCP("UnifiedMCPGateway")
        # Backend session group for all managed servers (official SDK)
        self.client_group = ClientSessionGroup(None, component_name_hook)  # type: ignore
        # Server manager for orchestration
        self.server_manager = server_manager
        # Tool catalog: tool_name -> tool_obj
        self.tool_catalog = {}
        self.dynamic_tool_retriever_name = "dynamic-tool-retriever"
        self.dynamic_tool_retriever_url = f"http://localhost:{self.server_manager.proxy_port}/servers/{self.dynamic_tool_retriever_name}/sse"
        # Register meta-tools
        self.register_meta_tools()

    async def initialize(self):
        # Connect to all popular servers at startup
        for name, config in self.server_manager.popular_servers.items():
            url = f"http://localhost:{self.server_manager.proxy_port}/servers/{name}/sse"
            params = SseServerParameters(url=url)
            await self.client_group.connect_to_server(params)
        # Optionally connect to dynamic tool retriever if configured
        try:
            params = SseServerParameters(url=self.dynamic_tool_retriever_url)
            await self.client_group.connect_to_server(params)
        except Exception as e:
            logger.warning(f"Could not connect to dynamic tool retriever: {e}")
        # Aggregate all tools into self.tool_catalog
        self.tool_catalog = dict(self.client_group.tools)
        logger.info(f"Unified tool catalog initialized with {len(self.tool_catalog)} tools.")

    async def route_tool_call(self, tool_name, args):
        """Route a tool call to the correct backend server using the session group."""
        if tool_name not in self.tool_catalog:
            raise ValueError(f"Tool '{tool_name}' not found in unified catalog.")
        return await self.client_group.call_tool(tool_name, args)

    async def dynamic_tool_discovery(self, task_description: str, top_k: int = 3):
        """Query the dynamic tool retriever, add new servers, connect, and update catalog."""
        # Call the dynamic tool retriever tool
        dtr_tool_name = f"{self.dynamic_tool_retriever_name}.dynamic_tool_retriever"
        input_args = {"task_description": task_description, "top_k": top_k}
        results = await self.route_tool_call(dtr_tool_name, input_args)
        # For each discovered tool, add and connect to new servers if needed
        new_servers = []
        for tool in results:
            mcp_server_config = tool.get("mcp_server_config")
            if mcp_server_config and "mcpServers" in mcp_server_config:
                for name, config in mcp_server_config["mcpServers"].items():
                    if name not in self.server_manager.dynamic_servers and name not in self.server_manager.popular_servers:
                        self.server_manager.add_server(name, config)
                        url = f"http://localhost:{self.server_manager.proxy_port}/servers/{name}/sse"
                        params = SseServerParameters(url=url)
                        await self.client_group.connect_to_server(params)
                        new_servers.append(name)
        # Update tool catalog
        self.tool_catalog = dict(self.client_group.tools)
        logger.info(f"Dynamic tool discovery added servers: {new_servers}")
        return results

    def register_meta_tools(self):
        """Register meta-tools for tool discovery and dynamic execution."""
        @self.server.tool("list_tools")
        async def list_tools():
            """List all available tools in the unified catalog."""
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
            """Call a tool by name, routing to the correct backend server."""
            return await self.route_tool_call(tool_name, args)

        @self.server.tool("dynamic_tool_discovery")
        async def dynamic_tool_discovery(task_description: str, top_k: int = 3):
            return await self.dynamic_tool_discovery(task_description, top_k)

if __name__ == "__main__":
    # Example usage
    logging.basicConfig(level=logging.INFO)
    # Initialize server manager (reuse your config logic)
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
    # Start FastMCP server
    gateway.server.run() 