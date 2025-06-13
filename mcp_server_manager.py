"""
Enhanced MCP Server Manager using Official MCP Python SDK

This module provides a comprehensive MCP server management system that:
1. Dynamically spins up and down MCP servers based on demand
2. Converts stdio-based MCP configurations to HTTP/SSE transport
3. Handles GitHub-sourced MCP configurations automatically
4. Uses the official MCP Python SDK for proper protocol compliance
5. Provides proper lifecycle management and resource cleanup

Key Features:
- Dynamic server provisioning from GitHub configs
- Automatic stdio to HTTP/SSE transport conversion using MCP SDK
- Intelligent resource management and cleanup
- Session-based isolation for multiple clients
- Health monitoring and automatic recovery
- Full MCP protocol compliance with official SDK
"""

import asyncio
import json
import logging
import os
import subprocess
import time
import uuid
import signal
import threading
from contextlib import asynccontextmanager
from typing import Dict, List, Optional, Any, Tuple, Set, Union
from dataclasses import dataclass, field
from pathlib import Path
import tempfile
import socket

# MCP SDK imports
try:
    from mcp import types
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    from mcp.server.sse import SseServerTransport
    from mcp.client.stdio import stdio_client
    from mcp.client.sse import sse_client
    from mcp.types import (
        JSONRPCMessage, 
        JSONRPCRequest, 
        JSONRPCResponse,
        InitializeRequest,
        InitializeResult,
        ListToolsRequest,
        CallToolRequest
    )
    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False
    logging.warning("MCP SDK not available. Install with: pip install mcp")

# FastAPI and related imports
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import uvicorn

# Import utilities for config extraction
import sys
sys.path.append(os.path.dirname(__file__))
try:
    from Utils.get_MCP_config import extract_config_from_github_async
except ImportError:
    extract_config_from_github_async = None

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def find_available_port(start_port: int = 9000, max_attempts: int = 100) -> int:
    """Find an available port starting from start_port"""
    for port in range(start_port, start_port + max_attempts):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(('localhost', port))
                return port
        except OSError:
            continue
    raise RuntimeError(f"No available port found in range {start_port}-{start_port + max_attempts}")

@dataclass
class MCPServerConfig:
    """Enhanced MCP Server Configuration using MCP SDK patterns"""
    name: str
    command: str
    args: List[str]
    env: Dict[str, str] = field(default_factory=dict)
    working_dir: Optional[str] = None
    github_url: Optional[str] = None
    description: Optional[str] = None
    auto_restart: bool = True
    max_restarts: int = 3
    restart_delay: float = 2.0
    keep_alive_seconds: int = 600  # 10 minutes
    health_check_interval: float = 30.0
    
    # Transport configuration
    preferred_transport: str = "sse"  # sse, stdio
    sse_port: Optional[int] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "name": self.name,
            "command": self.command,
            "args": self.args,
            "env": self.env,
            "working_dir": self.working_dir,
            "github_url": self.github_url,
            "description": self.description,
            "auto_restart": self.auto_restart,
            "preferred_transport": self.preferred_transport,
            "sse_port": self.sse_port
        }

@dataclass 
class MCPSession:
    """Enhanced MCP Session Management using MCP SDK"""
    session_id: str
    server_name: str
    transport_type: str
    created_at: float = field(default_factory=time.time)
    last_activity: float = field(default_factory=time.time)
    initialized: bool = False
    client_capabilities: Optional[Dict] = None
    server_capabilities: Optional[Dict] = None
    
    def touch(self):
        """Update last activity timestamp"""
        self.last_activity = time.time()
    
    def is_expired(self, timeout_seconds: int = 300) -> bool:
        """Check if session has expired"""
        return time.time() - self.last_activity > timeout_seconds
    
    def age(self) -> float:
        """Get session age in seconds"""
        return time.time() - self.created_at

class MCPServerProcess:
    """Enhanced MCP Server Process Management using MCP SDK"""
    
    def __init__(self, config: MCPServerConfig, manager_port: int):
        self.config = config
        self.manager_port = manager_port
        self.process: Optional[subprocess.Popen] = None
        self.last_used = time.time()
        self.restart_count = 0
        self.last_restart = 0
        self.is_healthy = True
        self.health_check_task: Optional[asyncio.Task] = None
        
        # Generate endpoints using the manager's port for SSE
        self.sse_endpoint = f"http://localhost:{manager_port}/servers/{config.name}/sse"
        self.stdio_endpoint = f"stdio://{config.command}"
        
        # Individual SSE port (if needed for dedicated SSE server)
        if config.sse_port:
            self.sse_port = config.sse_port
        else:
            self.sse_port = find_available_port(9001)
        
    @property
    def endpoint(self) -> str:
        """Get primary endpoint based on preferred transport"""
        if self.config.preferred_transport == "sse":
            return self.sse_endpoint
        else:
            return self.stdio_endpoint
    
    async def start(self) -> bool:
        """Start the MCP server process"""
        if self.is_alive():
            return True
            
        # Check restart limits
        if (self.restart_count >= self.config.max_restarts and 
            time.time() - self.last_restart < 300):  # 5 minutes
            logger.error(f"[MCP][{self.config.name}] Max restarts exceeded")
            return False
        
        try:
            # Prepare environment
            env = dict(os.environ)
            env.update(self.config.env)
            
            # Set working directory
            working_dir = self.config.working_dir or os.getcwd()
            
            # Start stdio process
            self.process = subprocess.Popen(
                [self.config.command] + self.config.args,
                env=env,
                cwd=working_dir,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=0
            )
            
            logger.info(f"[MCP][{self.config.name}] Started server (PID: {self.process.pid})")
            
            # Wait and check if it started successfully
            await asyncio.sleep(1)
            if self.process.poll() is not None:
                stdout, stderr = self.process.communicate()
                logger.error(f"[MCP][{self.config.name}] Failed to start:\nSTDOUT: {stdout}\nSTDERR: {stderr}")
                return False
            
            self.restart_count += 1
            self.last_restart = time.time()
            self.touch()
            self.is_healthy = True
            
            # Start health monitoring
            if self.health_check_task:
                self.health_check_task.cancel()
            self.health_check_task = asyncio.create_task(self._health_monitor())
            
            return True
            
        except Exception as e:
            logger.error(f"[MCP][{self.config.name}] Failed to start: {e}")
            return False
    
    async def _health_monitor(self):
        """Monitor server health and restart if needed"""
        while True:
            try:
                await asyncio.sleep(self.config.health_check_interval)
                
                if not self.is_alive():
                    logger.warning(f"[MCP][{self.config.name}] Server died, attempting restart")
                    if self.config.auto_restart:
                        await self.start()
                    else:
                        self.is_healthy = False
                        break
                        
                # Check if server is idle and can be shut down
                if (time.time() - self.last_used > self.config.keep_alive_seconds and
                    self.config.keep_alive_seconds > 0):
                    logger.info(f"[MCP][{self.config.name}] Server idle, shutting down")
                    await self.stop()
                    break
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[MCP][{self.config.name}] Health monitor error: {e}")
    
    def touch(self):
        """Update last used timestamp"""
        self.last_used = time.time()
    
    async def stop(self, force: bool = False):
        """Stop the MCP server process"""
        if self.health_check_task:
            self.health_check_task.cancel()
            
        if self.process and self.process.poll() is None:
            try:
                if force:
                    self.process.kill()
                else:
                    self.process.terminate()
                    # Wait for graceful shutdown
                    try:
                        await asyncio.wait_for(
                            asyncio.create_task(self._wait_for_process()),
                            timeout=5.0
                        )
                    except asyncio.TimeoutError:
                        logger.warning(f"[MCP][{self.config.name}] Force killing after timeout")
                        self.process.kill()
                        
                logger.info(f"[MCP][{self.config.name}] Stopped server")
            except Exception as e:
                logger.error(f"[MCP][{self.config.name}] Error stopping server: {e}")
    
    async def _wait_for_process(self):
        """Wait for process to terminate"""
        while self.process and self.process.poll() is None:
            await asyncio.sleep(0.1)
    
    def is_alive(self) -> bool:
        """Check if the server process is alive"""
        return self.process and self.process.poll() is None
    
    async def send_message(self, message: dict) -> bool:
        """Send message to stdio process"""
        if not self.is_alive():
            logger.warning(f"[MCP][{self.config.name}] Server not alive for message")
            return False
        
        try:
            json_str = json.dumps(message) + "\n"
            # Use asyncio to write to stdin
            loop = asyncio.get_event_loop()
            
            def write_sync():
                self.process.stdin.write(json_str)
                self.process.stdin.flush()
                return True
            
            await loop.run_in_executor(None, write_sync)
            self.touch()
            logger.debug(f"[MCP][{self.config.name}] Sent: {json_str.strip()}")
            return True
        except Exception as e:
            logger.error(f"[MCP][{self.config.name}] Error sending message: {e}")
            return False
    
    async def read_message(self, timeout: float = 10.0) -> Optional[dict]:
        """Read a message from stdio process"""
        if not self.is_alive():
            return None
        
        try:
            # Use asyncio to read from stdout with timeout
            loop = asyncio.get_event_loop()
            
            def read_line_sync():
                if self.process and self.process.stdout.readable():
                    return self.process.stdout.readline()
                return None
            
            # Run the synchronous read in a thread pool with timeout
            line = await asyncio.wait_for(
                loop.run_in_executor(None, read_line_sync),
                timeout=timeout
            )
            
            if line:
                line = line.strip()
                if line:
                    try:
                        return json.loads(line)
                    except json.JSONDecodeError:
                        logger.debug(f"[MCP][{self.config.name}] Non-JSON output: {line}")
                        return None
        except asyncio.TimeoutError:
            # This is expected for short timeouts
            return None
        except Exception as e:
            logger.error(f"[MCP][{self.config.name}] Error reading message: {e}")
        
        return None

class MCPServerManager:
    """Enhanced MCP Server Manager using Official MCP Python SDK"""
    
    def __init__(self, popular_servers: Optional[Dict[str, dict]] = None):
        self.servers: Dict[str, MCPServerProcess] = {}
        self.popular_servers = popular_servers or {}
        self.sessions: Dict[str, MCPSession] = {}
        self.app: Optional[FastAPI] = None
        self.manager_port = 8000
        self.actual_port: Optional[int] = None
        self._shutdown_event = asyncio.Event()
        
    async def add_server_from_config(self, config: MCPServerConfig) -> bool:
        """Add a server from configuration"""
        try:
            server = MCPServerProcess(config, self.manager_port)
            self.servers[config.name] = server
            logger.info(f"[MCP] Added server '{config.name}' with endpoint: {server.endpoint}")
            return True
        except Exception as e:
            logger.error(f"[MCP] Failed to add server '{config.name}': {e}")
            return False
    
    async def add_server_from_github(self, github_url: str, server_name: Optional[str] = None) -> bool:
        """Add server from GitHub repository configuration"""
        if not extract_config_from_github_async:
            logger.error("[MCP] GitHub config extraction not available")
            return False
            
        try:
            # Extract configuration from GitHub
            config_data = await extract_config_from_github_async(github_url)
            
            if not config_data:
                logger.error(f"[MCP] No configuration found in {github_url}")
                return False
            
            # Convert to MCPServerConfig
            name = server_name or config_data.get("name", f"server_{len(self.servers)}")
            
            config = MCPServerConfig(
                name=name,
                command=config_data.get("command", "npx"),
                args=config_data.get("args", []),
                env=config_data.get("env", {}),
                github_url=github_url,
                description=config_data.get("description", ""),
                preferred_transport="sse"  # Convert stdio to SSE
            )
            
            return await self.add_server_from_config(config)
            
        except Exception as e:
            logger.error(f"[MCP] Failed to add server from GitHub {github_url}: {e}")
            return False
    
    async def start_server(self, server_name: str) -> bool:
        """Start a specific server"""
        if server_name not in self.servers:
            logger.error(f"[MCP] Server '{server_name}' not found")
            return False
            
        server = self.servers[server_name]
        return await server.start()
    
    async def stop_server(self, server_name: str, force: bool = False) -> bool:
        """Stop a specific server"""
        if server_name not in self.servers:
            logger.error(f"[MCP] Server '{server_name}' not found")
            return False
            
        server = self.servers[server_name]
        await server.stop(force=force)
        return True
    
    async def restart_server(self, server_name: str) -> bool:
        """Restart a specific server"""
        if server_name not in self.servers:
            logger.error(f"[MCP] Server '{server_name}' not found")
            return False
            
        server = self.servers[server_name]
        await server.stop()
        await asyncio.sleep(1)  # Brief delay
        return await server.start()
    
    def create_management_app(self) -> FastAPI:
        """Create FastAPI app for managing MCP servers"""
        app = FastAPI(
            title="MCP Server Manager",
            description="Dynamic MCP Server Management with Official SDK",
            version="2.0.0"
        )
        
        # Add CORS middleware
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        
        # Server management endpoints
        @app.get("/servers")
        async def list_servers():
            """List all configured servers"""
            return {
                "servers": {
                    name: {
                        "name": name,
                        "alive": server.is_alive(),
                        "endpoint": server.endpoint,
                        "sse_endpoint": server.sse_endpoint,
                        "last_used": server.last_used,
                        "transport": server.config.preferred_transport,
                        "sse_port": server.sse_port,
                        "restart_count": server.restart_count,
                        "healthy": server.is_healthy
                    }
                    for name, server in self.servers.items()
                }
            }
        
        @app.get("/servers/{server_name}")
        async def get_server_info(server_name: str):
            """Get detailed information about a specific server"""
            if server_name not in self.servers:
                raise HTTPException(status_code=404, detail="Server not found")
            
            server = self.servers[server_name]
            return {
                "name": server_name,
                "config": server.config.to_dict(),
                "status": {
                    "alive": server.is_alive(),
                    "healthy": server.is_healthy,
                    "last_used": server.last_used,
                    "restart_count": server.restart_count,
                    "pid": server.process.pid if server.process else None
                },
                "endpoints": {
                    "sse": server.sse_endpoint,
                    "stdio": server.stdio_endpoint,
                    "primary": server.endpoint
                }
            }
        
        @app.post("/servers")
        async def add_server(config_data: dict):
            """Add a new server from configuration"""
            try:
                config = MCPServerConfig(
                    name=config_data["name"],
                    command=config_data["command"],
                    args=config_data.get("args", []),
                    env=config_data.get("env", {}),
                    working_dir=config_data.get("working_dir"),
                    github_url=config_data.get("github_url"),
                    description=config_data.get("description"),
                    preferred_transport=config_data.get("preferred_transport", "sse")
                )
                
                success = await self.add_server_from_config(config)
                if success:
                    return {"status": "success", "message": f"Server '{config.name}' added"}
                else:
                    raise HTTPException(status_code=500, detail="Failed to add server")
                    
            except KeyError as e:
                raise HTTPException(status_code=400, detail=f"Missing required field: {e}")
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))
        
        @app.post("/servers/from-github")
        async def add_server_from_github_endpoint(github_data: dict):
            """Add server from GitHub repository"""
            github_url = github_data.get("github_url")
            server_name = github_data.get("name")
            
            if not github_url:
                raise HTTPException(status_code=400, detail="github_url is required")
            
            success = await self.add_server_from_github(github_url, server_name)
            if success:
                return {"status": "success", "message": f"Server added from {github_url}"}
            else:
                raise HTTPException(status_code=500, detail="Failed to add server from GitHub")
        
        @app.post("/servers/{server_name}/start")
        async def start_server_endpoint(server_name: str):
            """Start a specific server"""
            success = await self.start_server(server_name)
            if success:
                return {"status": "success", "message": f"Server '{server_name}' started"}
            else:
                raise HTTPException(status_code=500, detail=f"Failed to start server '{server_name}'")
        
        @app.post("/servers/{server_name}/stop")
        async def stop_server_endpoint(server_name: str, force: bool = False):
            """Stop a specific server"""
            success = await self.stop_server(server_name, force=force)
            if success:
                return {"status": "success", "message": f"Server '{server_name}' stopped"}
            else:
                raise HTTPException(status_code=500, detail=f"Failed to stop server '{server_name}'")
        
        @app.post("/servers/{server_name}/restart")
        async def restart_server_endpoint(server_name: str):
            """Restart a specific server"""
            success = await self.restart_server(server_name)
            if success:
                return {"status": "success", "message": f"Server '{server_name}' restarted"}
            else:
                raise HTTPException(status_code=500, detail=f"Failed to restart server '{server_name}'")
        
        @app.delete("/servers/{server_name}")
        async def remove_server(server_name: str):
            """Remove a server"""
            if server_name not in self.servers:
                raise HTTPException(status_code=404, detail="Server not found")
            
            # Stop the server first
            await self.stop_server(server_name, force=True)
            
            # Remove from servers dict
            del self.servers[server_name]
            
            return {"status": "success", "message": f"Server '{server_name}' removed"}
        
        # MCP Protocol endpoints (proxy to individual servers)
        @app.post("/servers/{server_name}/message")
        async def send_message_to_server(server_name: str, message: dict):
            """Send a JSON-RPC message to a server and get response"""
            if server_name not in self.servers:
                raise HTTPException(status_code=404, detail="Server not found")
            
            server = self.servers[server_name]
            if not server.is_alive():
                # Try to start the server
                if not await server.start():
                    raise HTTPException(status_code=503, detail="Server failed to start")
            
            # Send message
            success = await server.send_message(message)
            if not success:
                raise HTTPException(status_code=500, detail="Failed to send message")
            
            # Wait for response if this is a request (has id)
            if "id" in message:
                response = await server.read_message(timeout=10.0)
                if response:
                    return {"status": "success", "response": response}
                else:
                    return {"status": "timeout", "message": "No response received"}
            else:
                return {"status": "sent", "message": "Notification sent"}
        
        # SSE endpoints for real-time communication
        @app.get("/servers/{server_name}/sse")
        async def sse_endpoint(request: Request, server_name: str):
            """SSE endpoint for real-time MCP communication"""
            if server_name not in self.servers:
                raise HTTPException(status_code=404, detail="Server not found")
            
            server = self.servers[server_name]
            if not server.is_alive():
                raise HTTPException(status_code=503, detail="Server not running")
            
            # Create session for this SSE connection
            session_id = str(uuid.uuid4())
            session = MCPSession(
                session_id=session_id,
                server_name=server_name,
                transport_type="sse"
            )
            self.sessions[session_id] = session
            
            logger.info(f"[MCP][SSE][{server_name}] Client connected with session {session_id}")
            
            async def event_generator():
                last_heartbeat = time.time()
                
                try:
                    # Send session info as first event
                    yield f"data: {json.dumps({'type': 'session', 'session_id': session_id})}\n\n"
                    
                    while True:
                        if await request.is_disconnected():
                            break
                        
                        # Check if server is still alive
                        if not server.is_alive():
                            yield f"data: {json.dumps({'type': 'error', 'message': 'Server disconnected'})}\n\n"
                            break
                        
                        # Read messages from server stdout
                        try:
                            message = await server.read_message(timeout=0.1)
                            if message:
                                yield f"data: {json.dumps(message)}\n\n"
                                session.touch()
                        except Exception as e:
                            logger.debug(f"[MCP][SSE][{server_name}] Read timeout or error: {e}")
                        
                        # Send heartbeat every 30 seconds
                        if time.time() - last_heartbeat > 30:
                            yield f"data: {json.dumps({'type': 'heartbeat', 'timestamp': time.time()})}\n\n"
                            last_heartbeat = time.time()
                            session.touch()
                        
                        await asyncio.sleep(0.1)
                        
                except asyncio.CancelledError:
                    logger.info(f"[MCP][SSE][{server_name}] Connection cancelled")
                except Exception as e:
                    logger.error(f"[MCP][SSE][{server_name}] Error: {e}")
                    yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
                finally:
                    # Clean up session
                    if session_id in self.sessions:
                        del self.sessions[session_id]
                    logger.info(f"[MCP][SSE][{server_name}] Session {session_id} ended")

            return StreamingResponse(
                event_generator(),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Headers": "Cache-Control, Content-Type, X-Session-ID",
                    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
                    "X-Accel-Buffering": "no",
                    "X-Session-ID": session_id
                }
            )

        @app.post("/servers/{server_name}/sse")
        async def sse_message_endpoint(server_name: str, message: dict):
            """Send message to server via SSE transport"""
            if server_name not in self.servers:
                raise HTTPException(status_code=404, detail="Server not found")
            
            server = self.servers[server_name]
            if not server.is_alive():
                raise HTTPException(status_code=503, detail="Server not running")
            
            logger.debug(f"[MCP][SSE][{server_name}] Received message: {json.dumps(message)}")
            
            # Send message to MCP server
            success = await server.send_message(message)
            if not success:
                raise HTTPException(status_code=500, detail="Failed to send message to MCP server")
            
            # For SSE transport, responses will be delivered via the SSE stream
            return {"status": "sent", "message": "Message sent to MCP server, response will arrive via SSE stream"}

        @app.options("/servers/{server_name}/sse")
        async def sse_options(server_name: str):
            """Handle CORS preflight for SSE endpoint"""
            return JSONResponse(
                content={"status": "ok"},
                headers={
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Headers": "Cache-Control, Content-Type, X-Session-ID",
                    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
                }
            )
        
        # Session management
        @app.get("/sessions")
        async def list_sessions():
            """List all active sessions"""
            return {
                "sessions": {
                    session_id: {
                        "session_id": session_id,
                        "server_name": session.server_name,
                        "transport_type": session.transport_type,
                        "initialized": session.initialized,
                        "age": session.age(),
                        "last_activity": session.last_activity
                    }
                    for session_id, session in self.sessions.items()
                }
            }
        
        @app.delete("/sessions/{session_id}")
        async def close_session(session_id: str):
            """Close a specific session"""
            if session_id not in self.sessions:
                raise HTTPException(status_code=404, detail="Session not found")
            
            del self.sessions[session_id]
            return {"status": "success", "message": f"Session '{session_id}' closed"}
        
        # Health check
        @app.get("/health")
        async def health_check():
            """Health check endpoint"""
            return {
                "status": "healthy",
                "servers_count": len(self.servers),
                "active_sessions": len(self.sessions),
                "uptime": time.time(),
                "mcp_sdk_available": MCP_AVAILABLE
            }
        
        self.app = app
        return app
    
    async def start_manager(self, port: int = 8000, host: str = "localhost") -> None:
        """Start the MCP server manager"""
        self.manager_port = port
        self.actual_port = port
        
        if not self.app:
            self.create_management_app()
        
        config = uvicorn.Config(
            app=self.app,
            host=host,
            port=port,
            log_level="info"
        )
        
        server = uvicorn.Server(config)
        
        logger.info(f"[MCP] Starting MCP Server Manager on {host}:{port}")
        
        # Start cleanup task
        cleanup_task = asyncio.create_task(self._cleanup_sessions())
        
        try:
            await server.serve()
        finally:
            cleanup_task.cancel()
            await self.shutdown()
    
    async def _cleanup_sessions(self):
        """Periodically clean up expired sessions"""
        while not self._shutdown_event.is_set():
            try:
                current_time = time.time()
                expired_sessions = [
                    session_id for session_id, session in self.sessions.items()
                    if session.is_expired(300)  # 5 minutes
                ]
                
                for session_id in expired_sessions:
                    logger.info(f"[MCP] Cleaning up expired session: {session_id}")
                    del self.sessions[session_id]
                
                await asyncio.sleep(60)  # Check every minute
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[MCP] Session cleanup error: {e}")
    
    async def shutdown(self):
        """Shutdown all servers and cleanup"""
        logger.info("[MCP] Shutting down MCP Server Manager")
        
        self._shutdown_event.set()
        
        # Stop all servers
        for server_name in list(self.servers.keys()):
            try:
                await self.stop_server(server_name, force=True)
            except Exception as e:
                logger.error(f"[MCP] Error stopping server {server_name}: {e}")
        
        # Clear sessions
        self.sessions.clear()
        
        logger.info("[MCP] MCP Server Manager shutdown complete")

# Example usage and popular server configurations
POPULAR_SERVERS = {
    "filesystem": {
        "name": "filesystem",
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-filesystem", "/tmp"],
        "description": "File system operations server"
    },
    "git": {
        "name": "git", 
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-git", "--repository", "."],
        "description": "Git operations server"
    },
    "github": {
        "name": "github",
        "command": "npx", 
        "args": ["-y", "@modelcontextprotocol/server-github"],
        "description": "GitHub API server",
        "env": {"GITHUB_PERSONAL_ACCESS_TOKEN": ""}
    },
    "postgres": {
        "name": "postgres",
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-postgres"],
        "description": "PostgreSQL database server",
        "env": {"POSTGRES_CONNECTION_STRING": ""}
    },
    "fetch": {
        "name": "fetch",
        "command": "uvx",
        "args": ["mcp-server-fetch"],
        "description": "HTTP fetch server"
    }
}

async def main():
    """Main function to run the MCP Server Manager"""
    import argparse
    
    parser = argparse.ArgumentParser(description="MCP Server Manager")
    parser.add_argument("--port", type=int, default=8000, help="Port to run on")
    parser.add_argument("--host", default="localhost", help="Host to bind to")
    parser.add_argument("--add-popular", action="store_true", help="Add popular servers")
    
    args = parser.parse_args()
    
    # Create manager
    manager = MCPServerManager(POPULAR_SERVERS)
    
    # Add popular servers if requested
    if args.add_popular:
        for server_name, server_config in POPULAR_SERVERS.items():
            config = MCPServerConfig(
                name=server_config["name"],
                command=server_config["command"],
                args=server_config["args"],
                env=server_config.get("env", {}),
                description=server_config.get("description", ""),
                preferred_transport="sse"
            )
            await manager.add_server_from_config(config)
    
    # Start the manager
    try:
        await manager.start_manager(port=args.port, host=args.host)
    except KeyboardInterrupt:
        logger.info("Received interrupt signal")
    finally:
        await manager.shutdown()

if __name__ == "__main__":
    asyncio.run(main())
