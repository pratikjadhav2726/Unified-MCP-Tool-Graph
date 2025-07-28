import sys
import os
import asyncio
import logging
from contextlib import AsyncExitStack
from typing import Dict, Any, Optional

# Add parent directory to Python path to import MCP_Server_Manager
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mcp.server.fastmcp import FastMCP
from mcp.client.session import ClientSession
from mcp.client.sse import sse_client
from MCP_Server_Manager.mcp_server_manager import MCPServerManager

logger = logging.getLogger("FixedUnifiedMCPGateway")
logging.basicConfig(level=logging.INFO)

class MCPServerConnection:
    """Manages a single MCP server connection with proper lifecycle management."""
    
    def __init__(self, name: str, url: str):
        self.name = name
        self.url = url
        self.session: Optional[ClientSession] = None
        self.exit_stack = AsyncExitStack()
        self.tools = []
        self.resources = []
        self.prompts = []
        self._connected = False
    
    async def connect(self):
        """Establish connection to the MCP server."""
        try:
            logger.info(f"Connecting to server: {self.name} at {self.url}")
            
            # Create SSE client connection
            client_cm = sse_client(url=self.url, timeout=10.0, sse_read_timeout=300.0)
            read, write = await self.exit_stack.enter_async_context(client_cm)
            
            # Create and initialize session
            session_cm = ClientSession(read, write)
            self.session = await self.exit_stack.enter_async_context(session_cm)
            
            # Initialize the session
            await self.session.initialize()
            
            # Fetch server capabilities
            await self._fetch_capabilities()
            
            self._connected = True
            logger.info(f"✓ Successfully connected to {self.name}")
            
        except Exception as e:
            logger.error(f"✗ Failed to connect to {self.name}: {e}")
            await self.disconnect()
            raise
    
    async def _fetch_capabilities(self):
        """Fetch tools, resources, and prompts from the server."""
        if not self.session:
            return
            
        try:
            # Get tools
            tools_response = await self.session.list_tools()
            self.tools = getattr(tools_response, "tools", [])
            logger.info(f"  - Loaded {len(self.tools)} tools from {self.name}")
        except Exception as e:
            logger.warning(f"Could not fetch tools from {self.name}: {e}")
        
        try:
            # Get resources
            resources_response = await self.session.list_resources()
            self.resources = getattr(resources_response, "resources", [])
            logger.info(f"  - Loaded {len(self.resources)} resources from {self.name}")
        except Exception as e:
            logger.warning(f"Could not fetch resources from {self.name}: {e}")
        
        try:
            # Get prompts
            prompts_response = await self.session.list_prompts()
            self.prompts = getattr(prompts_response, "prompts", [])
            logger.info(f"  - Loaded {len(self.prompts)} prompts from {self.name}")
        except Exception as e:
            logger.warning(f"Could not fetch prompts from {self.name}: {e}")
    
    async def call_tool(self, tool_name: str, arguments: dict) -> Any:
        """Call a tool on this server."""
        if not self.session or not self._connected:
            raise RuntimeError(f"Server {self.name} is not connected")
        
        # Find the tool
        tool = None
        for t in self.tools:
            if t.name == tool_name:
                tool = t
                break
        
        if not tool:
            raise ValueError(f"Tool {tool_name} not found on server {self.name}")
        
        logger.info(f"Calling tool {tool_name} on {self.name} with args: {arguments}")
        result = await self.session.call_tool(tool.name, arguments)
        return result
    
    async def disconnect(self):
        """Properly disconnect from the server."""
        if self._connected:
            logger.info(f"Disconnecting from {self.name}")
        self._connected = False
        await self.exit_stack.aclose()
        self.session = None
    
    @property
    def is_connected(self) -> bool:
        return self._connected

class FixedUnifiedMCPGateway:
    """A fixed unified MCP gateway that properly manages connections."""
    
    def __init__(self, server_manager: MCPServerManager):
        self.server = FastMCP("FixedUnifiedMCPGateway")
        self.server_manager = server_manager
        self.connections: Dict[str, MCPServerConnection] = {}
        self.tool_catalog: Dict[str, str] = {}  # tool_name -> server_name
        self.register_meta_tools()
    
    async def initialize(self):
        """Initialize connections to all available servers."""
        logger.info("Initializing MCP Gateway...")
        
        # Connect to all popular servers
        for name, config in self.server_manager.popular_servers.items():
            url = f"http://localhost:{self.server_manager.proxy_port}/servers/{name}/sse"
            connection = MCPServerConnection(name, url)
            
            try:
                await connection.connect()
                self.connections[name] = connection
            except Exception as e:
                logger.error(f"Failed to connect to {name}: {e}")
        
        # Build unified tool catalog
        self._build_tool_catalog()
        
        logger.info(f"Gateway initialized with {len(self.connections)} servers and {len(self.tool_catalog)} tools")
    
    def _build_tool_catalog(self):
        """Build a unified catalog of all available tools."""
        self.tool_catalog.clear()
        
        for server_name, connection in self.connections.items():
            for tool in connection.tools:
                tool_key = f"{server_name}.{tool.name}"
                self.tool_catalog[tool_key] = server_name
                logger.debug(f"Registered tool: {tool_key}")
    
    async def route_tool_call(self, tool_name: str, args: dict) -> Any:
        """Route a tool call to the appropriate server."""
        logger.info(f"Routing tool call: {tool_name} with args: {args}")
        
        if tool_name not in self.tool_catalog:
            available_tools = list(self.tool_catalog.keys())
            logger.error(f"Tool '{tool_name}' not found. Available: {available_tools}")
            return {"error": f"Tool '{tool_name}' not found", "available_tools": available_tools}
        
        server_name = self.tool_catalog[tool_name]
        connection = self.connections.get(server_name)
        
        if not connection or not connection.is_connected:
            logger.error(f"Server {server_name} is not connected")
            return {"error": f"Server {server_name} is not connected"}
        
        try:
            # Extract the actual tool name (remove server prefix)
            actual_tool_name = tool_name.split('.', 1)[1] if '.' in tool_name else tool_name
            result = await connection.call_tool(actual_tool_name, args)
            logger.info(f"Tool call successful: {tool_name}")
            return result
        except Exception as e:
            logger.error(f"Error calling tool '{tool_name}': {e}")
            return {"error": str(e)}
    
    async def dynamic_tool_discovery(self, task_description: str, top_k: int = 3) -> Any:
        """Perform dynamic tool discovery using the dummy tool retriever."""
        logger.info(f"Dynamic tool discovery for: {task_description}, top_k={top_k}")
        
        # Check if dummy tool retriever is connected
        if "dummy-tool-retriever" not in self.connections:
            logger.error("Dummy tool retriever not connected")
            return {"error": "Dynamic tool retriever not available"}
        
        try:
            # Call the dynamic tool retriever
            result = await self.route_tool_call(
                "dummy-tool-retriever.dynamic_tool_retriever",
                {"task_description": task_description, "top_k": top_k}
            )
            
            logger.info(f"Dynamic tool discovery returned: {result}")
            return result
            
        except Exception as e:
            logger.error(f"Error in dynamic tool discovery: {e}")
            return {"error": str(e)}
    
    def register_meta_tools(self):
        """Register meta-tools for the gateway."""
        
        @self.server.tool()
        async def list_tools() -> list:
            """List all available tools across all connected servers."""
            logger.info("list_tools called")
            tools = []
            for server_name, connection in self.connections.items():
                for tool in connection.tools:
                    tools.append({
                        "name": f"{server_name}.{tool.name}",
                        "description": getattr(tool, "description", ""),
                        "server": server_name,
                        "input_schema": getattr(tool, "inputSchema", None)
                    })
            return tools
        
        @self.server.tool()
        async def call_tool(tool_name: str, args: dict) -> Any:
            """Call a specific tool by name."""
            logger.info(f"call_tool meta-tool called for: {tool_name}")
            return await self.route_tool_call(tool_name, args)
        
        @self.server.tool()
        async def dynamic_tool_discovery(task_description: str, top_k: int = 3) -> Any:
            """Discover tools dynamically based on task description."""
            logger.info(f"dynamic_tool_discovery meta-tool called for: {task_description}")
            return await self.dynamic_tool_discovery(task_description, top_k)
        
        @self.server.tool()
        async def get_server_status() -> dict:
            """Get the status of all connected servers."""
            status = {}
            for name, connection in self.connections.items():
                status[name] = {
                    "connected": connection.is_connected,
                    "tools_count": len(connection.tools),
                    "resources_count": len(connection.resources),
                    "prompts_count": len(connection.prompts)
                }
            return status
    
    async def shutdown(self):
        """Properly shutdown all connections."""
        logger.info("Shutting down gateway...")
        for name, connection in self.connections.items():
            await connection.disconnect()
        self.connections.clear()
        self.tool_catalog.clear()

async def main():
    """Main function to run the gateway."""
    # Define popular servers including the dummy tool retriever
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
        "dummy-tool-retriever": {
            "command": "python3",
            "args": [os.path.join(PROJECT_ROOT, "gateway", "dummy_tool_retriever.py")]
        }
    }
    
    # Initialize server manager
    manager = MCPServerManager(popular_servers=POPULAR_SERVERS, proxy_port=9000)
    
    # Only start if not already running
    try:
        manager.start()
        logger.info("MCP Server Manager started")
    except Exception as e:
        logger.info(f"MCP Server Manager may already be running: {e}")
    
    # Wait a moment for servers to start
    await asyncio.sleep(5)
    
    # Initialize gateway
    gateway = FixedUnifiedMCPGateway(manager)
    
    try:
        await gateway.initialize()
        logger.info("Gateway initialized successfully")
        
        # Run the FastMCP server
        logger.info("Starting FastMCP server on port 8000...")
        gateway.server.run()
        
    except KeyboardInterrupt:
        logger.info("Received shutdown signal")
    except Exception as e:
        logger.error(f"Gateway error: {e}")
    finally:
        await gateway.shutdown()
        manager.stop()

if __name__ == "__main__":
    asyncio.run(main())