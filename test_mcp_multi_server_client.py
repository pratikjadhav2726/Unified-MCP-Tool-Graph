import asyncio
import json
import logging
from typing import Dict, Any, Optional
from pydantic import BaseModel

# Try to import the full ClientSessionGroup implementation
try:
    from mcp.client.session_group import ClientSessionGroup, SseServerParameters
    FULL_SESSION_GROUP_AVAILABLE = True
    print("Using full ClientSessionGroup implementation")
except ImportError:
    # Fallback to our simplified implementation
    FULL_SESSION_GROUP_AVAILABLE = False
    print("Using simplified ClientSessionGroup implementation")
    
    import mcp
    from mcp.client.session import ClientSession
    
    class SseServerParameters(BaseModel):
        """Parameters for initializing a sse_client."""
        url: str
        headers: dict[str, Any] | None = None
        timeout: float = 5
        sse_read_timeout: float = 60 * 5
    
    class ClientSessionGroup:
        """Simplified ClientSessionGroup implementation for testing multiple MCP servers."""
        
        def __init__(self):
            self.sessions: Dict[str, ClientSession] = {}
            self.tools: Dict[str, Any] = {}
            self.resources: Dict[str, Any] = {}
            self.prompts: Dict[str, Any] = {}
            self._session_contexts = {}
        
        async def __aenter__(self):
            return self
        
        async def __aexit__(self, exc_type, exc_val, exc_tb):
            # Clean up sessions
            for session_name, context in self._session_contexts.items():
                try:
                    await context.__aexit__(exc_type, exc_val, exc_tb)
                except Exception as e:
                    logging.warning(f"Error closing session {session_name}: {e}")
        
        async def connect_to_server(self, server_name: str, server_params: SseServerParameters):
            """Connect to a single MCP server using SSE."""
            try:
                from mcp.client.sse import sse_client
                
                print(f"Connecting to {server_name} at {server_params.url}...")
                
                # Create SSE client context
                client_context = sse_client(
                    url=server_params.url,
                    timeout=server_params.timeout,
                    sse_read_timeout=server_params.sse_read_timeout
                )
                
                # Enter the context and store it for cleanup
                read, write = await client_context.__aenter__()
                self._session_contexts[server_name] = client_context
                
                # Create and initialize session
                session = ClientSession(read, write)
                await session.__aenter__()
                
                # Initialize the session
                result = await session.initialize()
                server_info = result.serverInfo
                print(f"✓ Connected to {server_name} - {server_info.name} v{server_info.version}")
                
                # Store the session
                self.sessions[server_name] = session
                
                # Get tools, resources, and prompts
                await self._aggregate_components(server_name, session)
                
                return session
                
            except Exception as e:
                print(f"✗ Failed to connect to {server_name}: {e}")
                # Clean up on failure
                if server_name in self._session_contexts:
                    try:
                        await self._session_contexts[server_name].__aexit__(None, None, None)
                        del self._session_contexts[server_name]
                    except:
                        pass
                return None
        
        async def _aggregate_components(self, server_name: str, session: ClientSession):
            """Aggregate tools, resources, and prompts from a session."""
            try:
                # Get tools
                tools_response = await session.list_tools()
                tools = getattr(tools_response, "tools", [])
                for tool in tools:
                    tool_name = f"{server_name}.{tool.name}"
                    self.tools[tool_name] = tool
                    print(f"  - Tool: {tool.name} - {tool.description}")
            except Exception as e:
                logging.warning(f"Could not fetch tools from {server_name}: {e}")
            
            try:
                # Get resources
                resources_response = await session.list_resources()
                resources = getattr(resources_response, "resources", [])
                for resource in resources:
                    resource_name = f"{server_name}.{resource.name}"
                    self.resources[resource_name] = resource
                    print(f"  - Resource: {resource.name} - {resource.description}")
            except Exception as e:
                logging.warning(f"Could not fetch resources from {server_name}: {e}")
            
            try:
                # Get prompts
                prompts_response = await session.list_prompts()
                prompts = getattr(prompts_response, "prompts", [])
                for prompt in prompts:
                    prompt_name = f"{server_name}.{prompt.name}"
                    self.prompts[prompt_name] = prompt
                    print(f"  - Prompt: {prompt.name} - {prompt.description}")
            except Exception as e:
                logging.warning(f"Could not fetch prompts from {server_name}: {e}")

def load_mcp_config(config_file: str = "mcp_client_config.json") -> Dict[str, Any]:
    """Load MCP server configuration from JSON file."""
    try:
        with open(config_file, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Configuration file {config_file} not found!")
        return {"mcpServers": {}}
    except json.JSONDecodeError as e:
        print(f"Error parsing configuration file: {e}")
        return {"mcpServers": {}}

async def test_with_full_session_group(servers_config: Dict[str, Any]):
    """Test using the full ClientSessionGroup implementation."""
    from mcp.client.session_group import ClientSessionGroup, SseServerParameters
    
    # Custom naming function to avoid conflicts
    def component_name_hook(name: str, server_info) -> str:
        return f"{server_info.name}.{name}"
    
    async with ClientSessionGroup(component_name_hook=component_name_hook) as group:
        connected_servers = []
        
        # Connect to all configured servers
        for server_name, server_config in servers_config.items():
            if server_config.get("type") == "sse":
                server_params = SseServerParameters(
                    url=server_config["url"],
                    timeout=server_config.get("timeout", 5),
                    sse_read_timeout=server_config.get("sse_read_timeout", 300)
                )
                
                try:
                    session = await group.connect_to_server(server_params)
                    print(f"✓ Connected to {server_name} at {server_params.url}")
                    connected_servers.append(server_name)
                except Exception as e:
                    print(f"✗ Failed to connect to {server_name}: {e}")
                print()  # Add spacing between servers
        
        # Summary using the full session group
        print("=" * 60)
        print(f"Connection Summary (Full SessionGroup):")
        print(f"  Connected servers: {len(connected_servers)}")
        print(f"  Total sessions: {len(group.sessions)}")
        print(f"  Total tools: {len(group.tools)}")
        print(f"  Total resources: {len(group.resources)}")
        print(f"  Total prompts: {len(group.prompts)}")
        
        if group.tools:
            print(f"\nAll available tools:")
            for tool_name, tool in group.tools.items():
                print(f"  - {tool_name}: {tool.description}")

async def test_with_simplified_session_group(servers_config: Dict[str, Any]):
    """Test using the simplified ClientSessionGroup implementation."""
    async with ClientSessionGroup() as group:
        connected_servers = []
        
        # Connect to all configured servers
        for server_name, server_config in servers_config.items():
            if server_config.get("type") == "sse":
                server_params = SseServerParameters(
                    url=server_config["url"],
                    timeout=server_config.get("timeout", 5),
                    sse_read_timeout=server_config.get("sse_read_timeout", 300)
                )
                
                session = await group.connect_to_server(server_name, server_params)
                if session:
                    connected_servers.append(server_name)
                print()  # Add spacing between servers
        
        # Summary
        print("=" * 60)
        print(f"Connection Summary (Simplified SessionGroup):")
        print(f"  Connected servers: {len(connected_servers)}")
        print(f"  Total tools: {len(group.tools)}")
        print(f"  Total resources: {len(group.resources)}")
        print(f"  Total prompts: {len(group.prompts)}")
        
        if connected_servers:
            print(f"\nSuccessfully connected to: {', '.join(connected_servers)}")
            
            # Show all available tools across servers
            if group.tools:
                print(f"\nAll available tools:")
                for tool_name, tool in group.tools.items():
                    print(f"  - {tool_name}: {tool.description}")
        else:
            print("\nNo servers were successfully connected.")

async def main():
    logging.basicConfig(level=logging.INFO)
    
    # Load configuration
    config = load_mcp_config()
    servers_config = config.get("mcpServers", {})

    if not servers_config:
        print("No servers configured in mcp_client_config.json")
        return
    
    print(f"Testing {len(servers_config)} MCP servers from configuration...")
    print("=" * 60)
    
    # Use the appropriate implementation
    if FULL_SESSION_GROUP_AVAILABLE:
        await test_with_full_session_group(servers_config)
    else:
        await test_with_simplified_session_group(servers_config)

if __name__ == "__main__":
    asyncio.run(main())
