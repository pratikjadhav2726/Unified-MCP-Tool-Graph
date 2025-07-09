import os
import contextlib
import asyncio
import logging
import time
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, List, Optional
from mcp.server.fastmcp import FastMCP
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
from mcp.client.stdio import stdio_client, StdioServerParameters
from mcp.client.session import ClientSession

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MCPServerConfig(BaseModel):
    name: str
    command: str
    args: Optional[List[str]] = []
    env: Optional[Dict[str, str]] = {}
    cwd: Optional[str] = None

class MCPServerManager:
    def __init__(self, popular_servers: Dict[str, dict] | None = None):
        """Manage multiple MCP servers and expose them via Streamable HTTP."""

        self.popular_servers = popular_servers or {}

        self.apps = {}
        self.session_managers = {}
        self.session_contexts = {}
        self.routes_added = set()
        self.sessions = {}  # name -> (session, stdio_ctx)
        self.last_used = {}
    
    async def start_backend(self, config: MCPServerConfig):
        # Prepare environment
        env = os.environ.copy()
        if config.env:
            env.update(config.env)
        
        # For npm packages, ensure NODE_ENV is set
        if config.command in ["npx", "npm"]:
            env.setdefault("NODE_ENV", "production")
            env.setdefault("NPM_CONFIG_LOGLEVEL", "warn")
        
        params = StdioServerParameters(
            command=config.command,
            args=config.args,
            env=env,
            cwd=config.cwd or os.getcwd()
        )
        
        # Use MCP SDK's stdio_client to launch the subprocess and get streams
        stdio_ctx = stdio_client(params)
        read_stream, write_stream = await stdio_ctx.__aenter__()
        session = ClientSession(read_stream, write_stream)
        await session.__aenter__()
        
        try:
            # Add a small delay to let the server start
            await asyncio.sleep(1.0)
            await asyncio.wait_for(session.initialize(), timeout=30.0)
            logger.info(f"Session initialized successfully for '{config.name}'")
        except Exception as e:
            logger.error(f"Session initialization failed for '{config.name}': {e}")
            await session.__aexit__(None, None, None)
            await stdio_ctx.__aexit__(None, None, None)
            raise
        
        return session, stdio_ctx

    async def add_server(self, config: MCPServerConfig, fastapi_app: FastAPI):
        name = config.name
        if name in self.apps:
            endpoint = f"/mcp/{name}/"
            return endpoint

        session, stdio_ctx = await self.start_backend(config)
        self.sessions[name] = (session, stdio_ctx)

        # Create the FastMCP app with stateless HTTP
        mcp_app = FastMCP(name, stateless_http=True)

        # Get available tools and register a proxy for each
        try:
            tools_response = await session.list_tools()
            tools = tools_response.tools if hasattr(tools_response, 'tools') else []
            logger.info(f"Server '{name}' has {len(tools)} tools available: {[t.name for t in tools]}")
            
            # Register a single proxy tool that handles all tool calls
            @mcp_app.tool(description=f"Proxy to persistent {name} MCP server")
            async def proxy_tool(tool_name: str, **kwargs):
                """Proxy tool that forwards calls to the persistent MCP server"""
                try:
                    result = await session.call_tool(tool_name, kwargs)
                    return result
                except Exception as e:
                    logger.error(f"Error calling tool {tool_name} on {name}: {e}")
                    raise
                    
        except Exception as e:
            logger.warning(f"Could not list tools for '{name}': {e}")
            
            # Register a generic proxy tool even if we can't list tools
            @mcp_app.tool(description=f"Proxy to persistent {name} MCP server")
            async def proxy_tool(tool_name: str, **kwargs):
                """Proxy tool that forwards calls to the persistent MCP server"""
                try:
                    result = await session.call_tool(tool_name, kwargs)
                    return result
                except Exception as e:
                    logger.error(f"Error calling tool {tool_name} on {name}: {e}")
                    raise

        # Create session manager
        session_manager = StreamableHTTPSessionManager(app=mcp_app)
        endpoint = f"/mcp/{name}/"

        async def streamable_http_asgi(scope, receive, send):
            try:
                await session_manager.handle_request(scope, receive, send)
            except Exception as e:
                logger.error(f"ASGI error for {name}: {e}")
                if scope.get('type') == 'http':
                    try:
                        await send({
                            'type': 'http.response.start',
                            'status': 500,
                            'headers': [(b'content-type', b'application/json')],
                        })
                        await send({
                            'type': 'http.response.body',
                            'body': f'{{"error": "Server error: {str(e)}"}}'.encode(),
                        })
                    except Exception:
                        pass

        # Start the session manager
        run_ctx = session_manager.run()
        await run_ctx.__aenter__()
        self.session_managers[name] = session_manager
        self.session_contexts[name] = run_ctx

        if endpoint not in self.routes_added:
            fastapi_app.mount(endpoint, streamable_http_asgi)
            self.routes_added.add(endpoint)

        self.apps[name] = mcp_app
        self.last_used[name] = time.time()
        return endpoint

    async def ensure_server(self, name: str, cfg: dict, fastapi_app: FastAPI) -> str:
        """Ensure a server from config is running and return its endpoint."""
        if name in self.sessions:
            self.last_used[name] = time.time()
            return f"/mcp/{name}/"

        config = MCPServerConfig(
            name=name,
            command=cfg.get("command"),
            args=cfg.get("args", []),
            env=cfg.get("env"),
            cwd=cfg.get("cwd"),
        )
        return await self.add_server(config, fastapi_app)

    async def start_popular_servers(self, fastapi_app: FastAPI):
        for name, cfg in self.popular_servers.items():
            try:
                await self.ensure_server(name, cfg, fastapi_app)
            except Exception as e:
                logger.error(f"Failed to start popular server {name}: {e}")

    async def cleanup_loop(self, ttl: int = 600, check_interval: int = 60):
        while True:
            now = time.time()
            for name, last in list(self.last_used.items()):
                if name in self.popular_servers:
                    continue
                if now - last > ttl:
                    try:
                        await self.remove_server(name)
                    except Exception as e:
                        logger.error(f"Cleanup failed for {name}: {e}")
            await asyncio.sleep(check_interval)

    async def remove_server(self, name: str):
        """Remove a server and clean up its resources"""
        if name not in self.sessions:
            raise ValueError(f"Server '{name}' not found")
        
        logger.info(f"Removing server '{name}'")
        
        # Clean up session
        session, stdio_ctx = self.sessions[name]
        try:
            await session.__aexit__(None, None, None)
        except Exception as e:
            logger.debug(f"Error closing session for {name}: {e}")

        try:
            await stdio_ctx.__aexit__(None, None, None)
        except Exception as e:
            logger.debug(f"Error closing stdio context for {name}: {e}")

        # Stop session manager
        ctx = self.session_contexts.get(name)
        if ctx is not None:
            try:
                await ctx.__aexit__(None, None, None)
            except Exception as e:
                logger.debug(f"Error closing session manager for {name}: {e}")
        
        # Remove from tracking
        del self.sessions[name]
        if name in self.apps:
            del self.apps[name]
        if name in self.session_managers:
            del self.session_managers[name]
        if name in self.session_contexts:
            del self.session_contexts[name]
        if name in self.last_used:
            del self.last_used[name]
        
        logger.info(f"Server '{name}' removed successfully")

    async def shutdown(self):
        """Clean up all MCP sessions and subprocesses"""
        logger.info("Shutting down all servers")
        server_names = list(self.sessions.keys())
        for name in server_names:
            try:
                await self.remove_server(name)
            except Exception as e:
                logger.error(f"Error during shutdown of server {name}: {e}")
        
        # Clear all tracking dictionaries
        self.sessions = {}
        self.apps = {}
        self.session_managers = {}
        self.routes_added = set()

    def get_running_servers(self):
        return list(self.apps.keys())

    async def call_tool_direct(self, server_name: str, tool_name: str, params: dict):
        """Direct tool call via the session (bypass HTTP)"""
        if server_name not in self.sessions:
            raise ValueError(f"Server '{server_name}' not found")
        
        session, _ = self.sessions[server_name]
        try:
            result = await session.call_tool(tool_name, params)
            return result
        except Exception as e:
            logger.error(f"Tool call failed for '{tool_name}' on '{server_name}': {e}")
            raise

    async def list_tools_direct(self, server_name: str):
        """List tools directly via the session"""
        if server_name not in self.sessions:
            raise ValueError(f"Server '{server_name}' not found")
        
        session, _ = self.sessions[server_name]
        try:
            result = await session.list_tools()
            return result
        except Exception as e:
            logger.error(f"List tools failed for '{server_name}': {e}")
            raise

# --- FastAPI App wiring ---

app = FastAPI(title="Dynamic MCP Server Manager")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_headers=["*"],
    allow_methods=["*"]
)
manager = MCPServerManager()

@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    await manager.start_popular_servers(app)
    cleanup_task = asyncio.create_task(manager.cleanup_loop())
    try:
        yield
    finally:
        cleanup_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await cleanup_task
        await manager.shutdown()

app.router.lifespan_context = lifespan

@app.post("/add_server")
async def add_mcp_server(config: MCPServerConfig, request: Request):
    try:
        endpoint = await manager.add_server(config, app)
        return {
            "endpoint": str(request.base_url).rstrip("/") + endpoint,
            "name": config.name,
            "status": "success"
        }
    except Exception as e:
        logger.error(f"Failed to add server '{config.name}': {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/remove_server/{name}")
async def remove_mcp_server(name: str):
    try:
        await manager.remove_server(name)
        return {"status": "success", "message": f"Server '{name}' removed"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to remove server '{name}': {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/list_servers")
def list_servers():
    return {
        "servers": [
            {"name": name, "endpoint": f"/mcp/{name}/"}
            for name in manager.apps
        ]
    }

@app.post("/call_tool/{server_name}")
async def call_tool_direct(server_name: str, payload: dict):
    """Direct tool call endpoint (bypass HTTP streaming)"""
    tool_name = payload.get("tool")
    params = payload.get("params", {})
    
    if not tool_name:
        raise HTTPException(status_code=400, detail="Missing 'tool' in payload")
    
    try:
        result = await manager.call_tool_direct(server_name, tool_name, params)
        return {
            "status": "success",
            "tool": tool_name,
            "server": server_name,
            "result": result
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Tool call failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/list_tools/{server_name}")
async def list_tools_endpoint(server_name: str):
    """List tools for a specific server"""
    try:
        result = await manager.list_tools_direct(server_name)
        return {
            "status": "success",
            "server": server_name,
            "tools": result
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"List tools failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "running_servers": len(manager.get_running_servers()),
        "servers": manager.get_running_servers()
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=9000)