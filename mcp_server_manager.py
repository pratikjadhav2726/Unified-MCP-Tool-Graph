import asyncio
import subprocess
import time
import os
import json
import threading
import uuid
import socket
import traceback
from typing import Dict, Optional, List, Any
from urllib.parse import urlparse
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import queue
from pydantic import BaseModel

# Optional imports for testing
try:
    import websockets
    WEBSOCKETS_AVAILABLE = True
except ImportError:
    WEBSOCKETS_AVAILABLE = False
    print("[WARNING] websockets package not available - WebSocket tests will be skipped")

try:
    import aiohttp
    AIOHTTP_AVAILABLE = True
except ImportError:
    AIOHTTP_AVAILABLE = False
    print("[WARNING] aiohttp package not available - HTTP/SSE tests will be skipped")

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

class MCPMessage(BaseModel):
    """Pydantic model for MCP JSON-RPC messages"""
    jsonrpc: str = "2.0"
    id: Optional[Any] = None
    method: Optional[str] = None
    params: Optional[Dict[str, Any]] = None
    result: Optional[Any] = None
    error: Optional[Dict[str, Any]] = None

class MCPSession:
    """Manages MCP protocol state for a client session"""
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.initialized = False
        self.protocol_version = None
        self.client_capabilities = {}
        self.server_capabilities = {}
        self.created_at = time.time()
        self.last_activity = time.time()
        self.message_queue = None  # Will be set for SSE sessions
    
    def touch(self):
        self.last_activity = time.time()
    
    def is_expired(self, timeout_seconds: int = 300) -> bool:
        return time.time() - self.last_activity > timeout_seconds

class MCPServerProcess:
    def __init__(self, name, command, args, endpoint=None, env=None):
        self.name = name
        self.command = command
        self.args = args
        self.endpoint = endpoint
        self.env = env or {}
        self.process: Optional[subprocess.Popen] = None
        self.last_used = time.time()
        self.keep_alive_secs = 600  # 10 minutes
        self.message_queue = queue.Queue()
        self.reader_thread = None
        self.session_manager = None  # Will be set by MCPServerManager

    def start(self):
        if self.process is None or self.process.poll() is not None:
            env = dict(os.environ)
            env.update(self.env)
            self.process = subprocess.Popen(
                [self.command] + self.args,
                env=env,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=0  # Unbuffered
            )
            print(f"[MCP] Started {self.name} MCP server.")
            
            # Start reader thread for stdout
            self.reader_thread = threading.Thread(target=self._read_stdout, daemon=True)
            self.reader_thread.start()
            
            # Wait briefly to see if it crashes
            time.sleep(3)
            if self.process.poll() is not None:
                out, err = self.process.communicate()
                print(f"[MCP][ERROR] {self.name} failed to start.\nSTDOUT:\n{out}\nSTDERR:\n{err}")
                return False
        self.last_used = time.time()
        return True

    def _read_stdout(self):
        """Read stdout from the MCP server and queue messages"""
        try:
            while self.process and self.process.poll() is None:
                line = self.process.stdout.readline()
                if line:
                    line = line.strip()
                    if line:
                        try:
                            # Try to parse as JSON-RPC message
                            message = json.loads(line)
                            print(f"[MCP][{self.name}] Received: {json.dumps(message)}")
                            
                            # Put in main queue for compatibility
                            try:
                                self.message_queue.put_nowait(message)
                            except queue.Full:
                                # If queue is full, remove old messages and add new one
                                try:
                                    self.message_queue.get_nowait()
                                    self.message_queue.put_nowait(message)
                                except queue.Empty:
                                    pass
                            
                            # Also distribute to all active SSE sessions
                            if self.session_manager:
                                self.distribute_message_to_sessions(message, self.session_manager)
                        except json.JSONDecodeError:
                            # Non-JSON output, log it with more details
                            print(f"[MCP][{self.name}] Non-JSON stdout: {repr(line)}")
        except Exception as e:
            print(f"[MCP][{self.name}] Reader thread error: {e}")
            
        # Also start reading stderr in a separate thread
        def read_stderr():
            try:
                while self.process and self.process.poll() is None:
                    line = self.process.stderr.readline()
                    if line:
                        line = line.strip()
                        if line:
                            print(f"[MCP][{self.name}] STDERR: {line}")
            except Exception as e:
                print(f"[MCP][{self.name}] STDERR reader error: {e}")
                
        stderr_thread = threading.Thread(target=read_stderr, daemon=True)
        stderr_thread.start()

    def send_message(self, message: dict) -> bool:
        """Send a JSON-RPC message to the MCP server"""
        if not self.is_alive():
            print(f"[MCP][{self.name}] Server not alive, attempting restart...")
            if not self.start():
                print(f"[MCP][{self.name}] Failed to restart server")
                return False
        try:
            json_str = json.dumps(message) + "\n"
            self.process.stdin.write(json_str)
            self.process.stdin.flush()
            self.touch()
            print(f"[MCP][{self.name}] Sent: {json_str.strip()}")
            return True
        except Exception as e:
            print(f"[MCP][{self.name}] Error sending message: {e}")
            # Try to restart and send again
            if self.start():
                try:
                    json_str = json.dumps(message) + "\n"
                    self.process.stdin.write(json_str)
                    self.process.stdin.flush()
                    self.touch()
                    print(f"[MCP][{self.name}] Sent after restart: {json_str.strip()}")
                    return True
                except Exception as e2:
                    print(f"[MCP][{self.name}] Error sending message after restart: {e2}")
            return False

    def get_messages(self) -> List[dict]:
        """Get all pending messages from the server - for test/polling clients"""
        messages = []
        try:
            # Get all messages without putting them back to avoid infinite loops
            temp_messages = []
            while not self.message_queue.empty():
                message = self.message_queue.get_nowait()
                temp_messages.append(message)
            
            # Return copy and put messages back for other consumers
            messages = temp_messages.copy()
            for message in temp_messages:
                try:
                    self.message_queue.put_nowait(message)
                except queue.Full:
                    # Queue is full, skip this message
                    pass
        except queue.Empty:
            pass
        return messages

    def get_messages_once(self) -> List[dict]:
        """Get all pending messages from the server (consume once) - DEPRECATED"""
        # Don't consume messages here to avoid conflicts with SSE
        # Use get_messages() for non-destructive reading
        return self.get_messages()

    def distribute_message_to_sessions(self, message: dict, session_manager):
        """Distribute a message to all active SSE sessions"""
        if not session_manager:
            return
            
        print(f"[MCP][{self.name}] Distributing message to {len(session_manager.sessions)} sessions")
        
        for session_id, session in list(session_manager.sessions.items()):
            if hasattr(session, 'message_queue') and session.message_queue:
                try:
                    session.message_queue.put_nowait(message)
                    print(f"[MCP][{self.name}] Message sent to session {session_id}")
                except queue.Full:
                    print(f"[MCP][{self.name}] Session {session_id} queue full, skipping")
                    pass
            else:
                print(f"[MCP][{self.name}] Session {session_id} has no message queue")

    def touch(self):
        self.last_used = time.time()

    def stop(self):
        if self.process and self.process.poll() is None:
            self.process.terminate()
            print(f"[MCP] Stopped {self.name} MCP server.")

    def is_alive(self):
        return self.process and self.process.poll() is None

class MCPServerManager:
    def __init__(self, popular_servers: Dict[str, dict]):
        self.servers: Dict[str, MCPServerProcess] = {}
        self.popular_servers = popular_servers
        self._base_port = 8000
        self._next_port = self._base_port
        self._name_to_port = {}
        self.http_app = None
        self.http_server_task = None
        self.sessions: Dict[str, MCPSession] = {}  # Track client sessions
        self.actual_port = None  # Will be set when HTTP server starts

    def create_http_app(self):
        """Create FastAPI app with SSE endpoints for all servers"""
        app = FastAPI(title="MCP Server Manager", version="1.0.0")
        
        # Add CORS middleware
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

        @app.get("/servers")
        async def list_servers():
            """List all available servers"""
            return {
                "servers": {
                    name: {
                        "alive": server.is_alive(),
                        "endpoint": server.endpoint,
                        "last_used": server.last_used
                    }
                    for name, server in self.servers.items()
                }
            }

        @app.get("/servers/{server_name}")
        async def get_server_info(server_name: str):
            """Get information about a specific server"""
            if server_name not in self.servers:
                raise HTTPException(status_code=404, detail="Server not found")
            
            server = self.servers[server_name]
            return {
                "name": server_name,
                "alive": server.is_alive(),
                "endpoint": server.endpoint,
                "last_used": server.last_used,
                "protocol": "MCP",
                "transport_options": {
                    "websocket": f"ws://localhost:{getattr(self, 'actual_port', 9000)}/servers/{server_name}/ws",
                    "sse": f"http://localhost:{getattr(self, 'actual_port', 9000)}/servers/{server_name}/sse",
                    "http": f"http://localhost:{getattr(self, 'actual_port', 9000)}/servers/{server_name}/message"
                }
            }

        @app.post("/servers/{server_name}/message")
        async def send_message(server_name: str, message: dict):
            """Send a JSON-RPC message to a specific server"""
            if server_name not in self.servers:
                raise HTTPException(status_code=404, detail="Server not found")
            
            server = self.servers[server_name]
            if not server.is_alive():
                print(f"[MCP] Restarting {server_name} server...")
                if not server.start():
                    raise HTTPException(status_code=503, detail="Server failed to start")
            
            success = server.send_message(message)
            if not success:
                raise HTTPException(status_code=500, detail="Failed to send message")
            
            # Wait for response and return it
            timeout = 10.0  # 10 second timeout
            start_time = time.time()
            expected_id = message.get("id")
            
            while time.time() - start_time < timeout:
                # Read from the main message queue to find our response
                temp_messages = []
                try:
                    # Get all available messages
                    while not server.message_queue.empty():
                        msg = server.message_queue.get_nowait()
                        temp_messages.append(msg)
                    
                    # Look for our response
                    response_found = None
                    for msg in temp_messages:
                        if msg.get("id") == expected_id:
                            response_found = msg
                            break
                    
                    # Put back all messages except our response
                    for msg in temp_messages:
                        if msg != response_found:
                            try:
                                server.message_queue.put_nowait(msg)
                            except queue.Full:
                                pass
                    
                    if response_found:
                        return {"status": "success", "response": response_found}
                        
                except queue.Empty:
                    pass
                    
                await asyncio.sleep(0.1)  # Check less frequently
            
            # If we get here, we timed out
            return {"status": "timeout", "message": "No response received within timeout period"}

        @app.post("/servers/{server_name}/initialize")
        async def initialize_server(server_name: str, init_params: dict):
            """Initialize MCP server with proper protocol handshake"""
            if server_name not in self.servers:
                raise HTTPException(status_code=404, detail="Server not found")
            
            server = self.servers[server_name]
            if not server.is_alive():
                raise HTTPException(status_code=503, detail="Server not running")
            
            # Create initialization message
            init_message = {
                "jsonrpc": "2.0",
                "id": init_params.get("id", 1),
                "method": "initialize",
                "params": {
                    "protocolVersion": init_params.get("protocolVersion", "2024-11-05"),
                    "capabilities": init_params.get("capabilities", {}),
                    "clientInfo": init_params.get("clientInfo", {"name": "mcp-manager", "version": "1.0.0"})
                }
            }
            
            success = server.send_message(init_message)
            if not success:
                raise HTTPException(status_code=500, detail="Failed to send initialization")
            
            # Wait for initialization response
            timeout = 10.0
            start_time = time.time()
            
            while time.time() - start_time < timeout:
                # Check for messages
                temp_messages = []
                try:
                    while not server.message_queue.empty():
                        msg = server.message_queue.get_nowait()
                        temp_messages.append(msg)
                    
                    response_found = None
                    for msg in temp_messages:
                        if msg.get("id") == init_message["id"] and "result" in msg:
                            response_found = msg
                            break
                    
                    # Put back other messages
                    for msg in temp_messages:
                        if msg != response_found:
                            try:
                                server.message_queue.put_nowait(msg)
                            except queue.Full:
                                pass
                    
                    if response_found:
                        # Send initialized notification
                        initialized_notification = {
                            "jsonrpc": "2.0",
                            "method": "notifications/initialized"
                        }
                        server.send_message(initialized_notification)
                        return {"status": "initialized", "response": response_found}
                        
                except queue.Empty:
                    pass
                    
                await asyncio.sleep(0.05)
            
            return {"status": "timeout", "message": "Initialization timeout"}

        @app.websocket("/servers/{server_name}/ws")
        async def websocket_endpoint(websocket: WebSocket, server_name: str):
            """Enhanced WebSocket endpoint for bidirectional MCP communication"""
            if server_name not in self.servers:
                await websocket.close(code=1000, reason="Server not found")
                return
            
            server = self.servers[server_name]
            if not server.is_alive():
                print(f"[MCP] Restarting {server_name} server for WebSocket connection...")
                if not server.start():
                    await websocket.close(code=1000, reason="Server failed to start")
                    return

            await websocket.accept()
            session_id = str(uuid.uuid4())
            session = MCPSession(session_id)
            self.sessions[session_id] = session
            
            # Clear any stale messages from previous sessions
            while not server.message_queue.empty():
                try:
                    server.message_queue.get_nowait()
                except queue.Empty:
                    break
            
            print(f"[MCP][WS] Client connected to {server_name} (session: {session_id})")
            print(f"[MCP][WS] Cleared stale messages for fresh session")

            try:
                # Create a task to read from MCP server and send to WebSocket
                async def mcp_to_websocket():
                    processed_ids = set()  # Track processed message IDs to avoid duplicates
                    while server.is_alive():
                        messages = server.get_messages()
                        for message in messages:
                            try:
                                # Validate message format and avoid duplicates
                                message_id = message.get('id', str(uuid.uuid4()))
                                if isinstance(message, dict) and "jsonrpc" in message and message_id not in processed_ids:
                                    print(f"[MCP][{server_name}] -> Client: {json.dumps(message)}")
                                    await websocket.send_text(json.dumps(message))
                                    processed_ids.add(message_id)
                                    session.touch()
                                    # Limit the size of processed_ids to prevent memory growth
                                    if len(processed_ids) > 1000:
                                        processed_ids.clear()
                                else:
                                    if not isinstance(message, dict) or "jsonrpc" not in message:
                                        print(f"[MCP][{server_name}] Invalid message format: {message}")
                            except Exception as e:
                                print(f"[MCP][{server_name}] Error sending to WebSocket: {e}")
                                break
                        await asyncio.sleep(0.05)  # Check for messages frequently

                # Start the MCP->WebSocket task
                mcp_task = asyncio.create_task(mcp_to_websocket())

                # Handle WebSocket->MCP messages
                while True:
                    try:
                        data = await websocket.receive_text()
                        message = json.loads(data)
                        
                        # Validate MCP message format
                        if not isinstance(message, dict) or "jsonrpc" not in message:
                            await websocket.send_text(json.dumps({
                                "jsonrpc": "2.0",
                                "error": {"code": -32600, "message": "Invalid Request"}
                            }))
                            continue
                            
                        print(f"[MCP][{server_name}] Client -> : {json.dumps(message)}")
                        
                        # Track initialization state
                        if message.get("method") == "initialize":
                            session.protocol_version = message.get("params", {}).get("protocolVersion")
                            session.client_capabilities = message.get("params", {}).get("capabilities", {})
                        elif message.get("method") == "notifications/initialized":
                            session.initialized = True
                        
                        success = server.send_message(message)
                        if not success:
                            await websocket.send_text(json.dumps({
                                "jsonrpc": "2.0",
                                "id": message.get("id"),
                                "error": {"code": -32603, "message": "Internal error - failed to send message to MCP server"}
                            }))
                        
                        session.touch()
                        
                    except WebSocketDisconnect:
                        print(f"[MCP][WS] Client disconnected from {server_name} (session: {session_id})")
                        break
                    except json.JSONDecodeError:
                        await websocket.send_text(json.dumps({
                            "jsonrpc": "2.0",
                            "error": {"code": -32700, "message": "Parse error"}
                        }))
                    except Exception as e:
                        print(f"[MCP][WS] Error: {e}")
                        break

            except Exception as e:
                print(f"[MCP][WS] Connection error: {e}")
            finally:
                if 'mcp_task' in locals():
                    mcp_task.cancel()
                if session_id in self.sessions:
                    del self.sessions[session_id]
                print(f"[MCP][WS] Session {session_id} ended")

        @app.get("/servers/{server_name}/sse")
        async def sse_endpoint(server_name: str, request: Request):
            """Streamable HTTP SSE endpoint for MCP Inspector"""
            if server_name not in self.servers:
                raise HTTPException(status_code=404, detail="Server not found")
            
            server = self.servers[server_name]
            if not server.is_alive():
                raise HTTPException(status_code=503, detail="Server not running")

            # Create a dedicated message queue for this SSE session
            session_id = str(uuid.uuid4())
            session = MCPSession(session_id)
            
            # Create a dedicated queue for this session with reasonable size limit
            session_queue = queue.Queue(maxsize=100)
            session.message_queue = session_queue
            
            # Register session BEFORE starting event generator
            self.sessions[session_id] = session

            async def event_generator():
                try:
                    print(f"[MCP][SSE][{server_name}] New streamable HTTP connection, session: {session_id}")
                    
                    # Send session info to client
                    yield f"data: {json.dumps({'type': 'session', 'sessionId': session_id})}\n\n"
                    
                    # Stream responses from the server
                    last_message_time = time.time()
                    consecutive_empty_checks = 0
                    
                    while server.is_alive():
                        # Check if connection is still alive
                        if await request.is_disconnected():
                            print(f"[MCP][SSE][{server_name}] Client disconnected")
                            break
                        
                        # Check for messages in session queue
                        messages_found = False
                        try:
                            while not session_queue.empty():
                                message = session_queue.get_nowait()
                                print(f"[MCP][SSE][{server_name}] -> Client: {json.dumps(message)}")
                                yield f"data: {json.dumps(message)}\n\n"
                                last_message_time = time.time()
                                messages_found = True
                                consecutive_empty_checks = 0
                        except queue.Empty:
                            pass
                        
                        if not messages_found:
                            consecutive_empty_checks += 1
                        
                        # Send heartbeat every 30 seconds if no messages
                        if time.time() - last_message_time > 30:
                            yield f"data: {json.dumps({'type': 'heartbeat', 'timestamp': time.time()})}\n\n"
                            last_message_time = time.time()
                        
                        session.touch()
                        
                        # Dynamic sleep - faster when we expect messages
                        if consecutive_empty_checks < 20:
                            await asyncio.sleep(0.05)  # Check frequently when active
                        else:
                            await asyncio.sleep(0.2)   # Slower when idle
                        
                except asyncio.CancelledError:
                    print(f"[MCP][SSE][{server_name}] Connection cancelled")
                except Exception as e:
                    print(f"[MCP][SSE][{server_name}] Error: {e}")
                    yield f"data: {json.dumps({'error': str(e)})}\n\n"
                finally:
                    # Clean up session
                    if session_id in self.sessions:
                        del self.sessions[session_id]
                    print(f"[MCP][SSE][{server_name}] Session {session_id} ended")

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
        async def sse_message_endpoint(server_name: str, message: dict, session_id: str = None):
            """Handle POST messages for streamable HTTP transport"""
            if server_name not in self.servers:
                raise HTTPException(status_code=404, detail="Server not found")
            
            server = self.servers[server_name]
            if not server.is_alive():
                raise HTTPException(status_code=503, detail="Server not running")
            
            print(f"[MCP][SSE][{server_name}] Received message: {json.dumps(message)}")
            
            # Send message to MCP server
            success = server.send_message(message)
            if not success:
                raise HTTPException(status_code=500, detail="Failed to send message to MCP server")
            
            # For SSE transport, we don't wait for responses here
            # The responses will be delivered via the SSE stream
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

        self.http_app = app
        return app

    async def start_http_server(self, port: int = 9000):
        """Start the HTTP server for SSE endpoints"""
        if not self.http_app:
            self.create_http_app()
        
        # Find an available port if the requested one is in use
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(('localhost', port))
        except OSError:
            print(f"[MCP] Port {port} is in use, finding alternative...")
            port = find_available_port(port)
            print(f"[MCP] Using port {port} instead")
        
        config = uvicorn.Config(self.http_app, host="0.0.0.0", port=port, log_level="info")
        server = uvicorn.Server(config)
        
        print(f"[MCP] Starting HTTP server on http://localhost:{port}")
        print(f"[MCP] SSE endpoints will be available at http://localhost:{port}/servers/<server_name>/sse")
        
        # Store the actual port being used
        self.actual_port = port
        
        self.http_server_task = asyncio.create_task(server.serve())

    def _assign_endpoint(self, name, cfg):
        # For our HTTP/SSE implementation, endpoint points to our WebSocket endpoint (preferred for MCP)
        if name not in self._name_to_port:
            self._name_to_port[name] = self._next_port
            self._next_port += 1
        
        # Use actual port if available, otherwise fall back to base port
        actual_port = getattr(self, 'actual_port', 9000)
        
        # Return WebSocket endpoint for this server (MCP Inspector can use this)
        ws_endpoint = f"ws://localhost:{actual_port}/servers/{name}/ws"
        sse_endpoint = f"http://localhost:{actual_port}/servers/{name}/sse"
        cfg["ws_endpoint"] = ws_endpoint
        cfg["sse_endpoint"] = sse_endpoint
        cfg["endpoint"] = ws_endpoint  # Default to WebSocket for MCP protocol
        return ws_endpoint

    def start_popular_servers(self):
        for name, cfg in self.popular_servers.items():
            self.add_and_start_server(name, cfg)

    def add_and_start_server(self, name, cfg):
        env = cfg.get("env", {})
        endpoint = self._assign_endpoint(name, cfg)

        command = cfg["command"]
        args = cfg["args"]

        if name not in self.servers:
            proc = MCPServerProcess(
                name=name,
                command=command,
                args=args,
                endpoint=endpoint,
                env=env
            )
            # Set session manager reference for message distribution
            proc.session_manager = self
            self.servers[name] = proc

        server = self.servers[name]
        if not server.is_alive():
            success = server.start()
            if not success:
                print(f"[MCP][ERROR] {name} failed to start.")
                return None
        
        server.touch()
        print(f"[MCP] {name} endpoint: {endpoint}")
        return endpoint

    def ensure_server(self, name, cfg):
        if name not in self.servers or not self.servers[name].is_alive():
            result = self.add_and_start_server(name, cfg)
            return result
        else:
            self.servers[name].touch()
            return self.servers[name].endpoint

    def get_active_endpoints(self):
        return {name: proc.endpoint for name, proc in self.servers.items() if proc.is_alive()}

    def stop_all_servers(self):
        for server in self.servers.values():
            server.stop()

    async def cleanup_loop(self):
        while True:
            now = time.time()
            for name, proc in list(self.servers.items()):
                if proc.is_alive() and now - proc.last_used > proc.keep_alive_secs:
                    proc.stop()
            await asyncio.sleep(60)

async def test_fetch_mcp_interaction(port: int = 9000):
    """Test MCP protocol interaction with the fetch server"""
    if not WEBSOCKETS_AVAILABLE:
        print("[TEST] ⚠️  websockets package not available, skipping WebSocket test")
        return
        
    try:
        import websockets
        
        uri = f'ws://localhost:{port}/servers/fetch/ws'
        print(f"[TEST] Connecting to {uri}")
        
        async with websockets.connect(uri) as websocket:
            print("[TEST] ✅ Connected to fetch server WebSocket")
            
            # Send MCP initialize message with proper protocol version
            init_message = {
                'jsonrpc': '2.0',
                'id': 1,
                'method': 'initialize',
                'params': {
                    'protocolVersion': '2024-11-05',
                    'capabilities': {
                        'roots': {'listChanged': True},
                        'sampling': {}
                    },
                    'clientInfo': {'name': 'test-client', 'version': '1.0.0'}
                }
            }
            
            await websocket.send(json.dumps(init_message))
            print("[TEST] ✅ Sent initialize message")
            
            # Wait for response with better error handling
            try:
                response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                init_response = json.loads(response)
                print(f"[TEST] ✅ Received initialize response: {init_response.get('result', {}).get('serverInfo', {})}")
                print(f"[TEST] ✅ Server protocol version: {init_response.get('result', {}).get('protocolVersion')}")
                
                # Send initialized notification (required by MCP spec)
                initialized_notification = {
                    'jsonrpc': '2.0',
                    'method': 'notifications/initialized'
                }
                await websocket.send(json.dumps(initialized_notification))
                print("[TEST] ✅ Sent initialized notification")
                
            except asyncio.TimeoutError:
                print("[TEST] ❌ Timeout waiting for initialize response")
                return
            except json.JSONDecodeError as e:
                print(f"[TEST] ❌ Failed to parse initialize response: {e}")
                print(f"[TEST] Raw response: {response}")
                return
            
            # List tools
            tools_message = {
                'jsonrpc': '2.0',
                'id': 2,
                'method': 'tools/list'
            }
            
            await websocket.send(json.dumps(tools_message))
            print("[TEST] ✅ Sent tools/list request")
            
            try:
                tools_response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                tools_data = json.loads(tools_response)
                tools = tools_data.get('result', {}).get('tools', [])
                print(f"[TEST] ✅ Available tools: {[tool['name'] for tool in tools]}")
            except asyncio.TimeoutError:
                print("[TEST] ❌ Timeout waiting for tools/list response")
                return
            except json.JSONDecodeError as e:
                print(f"[TEST] ❌ Failed to parse tools response: {e}")
                print(f"[TEST] Raw response: {tools_response}")
                return
            
            # Test fetch tool if available
            if any(tool['name'] == 'fetch' for tool in tools):
                fetch_message = {
                    'jsonrpc': '2.0',
                    'id': 3,
                    'method': 'tools/call',
                    'params': {
                        'name': 'fetch',
                        'arguments': {
                            'url': 'https://httpbin.org/json'
                        }
                    }
                }
                
                await websocket.send(json.dumps(fetch_message))
                print("[TEST] ✅ Sent fetch tool call (httpbin.org/json)")
                
                try:
                    fetch_response = await asyncio.wait_for(websocket.recv(), timeout=10.0)
                    fetch_data = json.loads(fetch_response)
                    
                    if 'result' in fetch_data:
                        print("[TEST] ✅ Fetch tool executed successfully!")
                        content = fetch_data['result'].get('content', [])
                        if content:
                            print(f"[TEST] ✅ Response contains {len(content)} content items")
                    else:
                        print(f"[TEST] ❌ Fetch tool error: {fetch_data.get('error', 'Unknown error')}")
                except asyncio.TimeoutError:
                    print("[TEST] ❌ Timeout waiting for fetch tool response")
                except json.JSONDecodeError as e:
                    print(f"[TEST] ❌ Failed to parse fetch response: {e}")
                    print(f"[TEST] Raw response: {fetch_response}")
            else:
                print("[TEST] ❌ Fetch tool not found in available tools")
                
    except websockets.exceptions.ConnectionClosed as e:
        print(f"[TEST] ❌ WebSocket connection closed: {e}")
    except ConnectionRefusedError:
        print("[TEST] ❌ Connection refused - server not running")
    except Exception as e:
        import traceback
        print(f"[TEST] ❌ MCP interaction failed: {e}")
        print(f"[TEST] ❌ Exception type: {type(e).__name__}")
        print(f"[TEST] ❌ Traceback: {traceback.format_exc()}")

async def test_http_mcp_interaction(port: int = 9000):
    """Test MCP protocol interaction via HTTP endpoints (like MCP Inspector)"""
    if not AIOHTTP_AVAILABLE:
        print("[TEST] ⚠️  aiohttp package not available, skipping HTTP test")
        return
        
    try:
        import aiohttp
        
        base_url = f'http://localhost:{port}/servers/fetch'
        print(f"[TEST] Testing HTTP endpoints at {base_url}")
        
        async with aiohttp.ClientSession() as session:
            # Test initialization via HTTP
            init_message = {
                'jsonrpc': '2.0',
                'id': 1,
                'method': 'initialize',
                'params': {
                    'protocolVersion': '2025-03-26',  # Test latest protocol
                    'capabilities': {
                        'roots': {'listChanged': True},
                        'sampling': {}
                    },
                    'clientInfo': {'name': 'mcp-inspector', 'version': '0.14.0'}
                }
            }
            
            async with session.post(f"{base_url}/message", json=init_message) as resp:
                if resp.status == 200:
                    result = await resp.json()
                    print(f"[TEST] ✅ HTTP initialize successful: {result.get('status')}")
                    if 'response' in result:
                        server_info = result['response'].get('result', {}).get('serverInfo', {})
                        print(f"[TEST] ✅ Server info: {server_info}")
                else:
                    print(f"[TEST] ❌ HTTP initialize failed: {resp.status}")
            
            # Test tools listing via HTTP
            tools_message = {
                'jsonrpc': '2.0',
                'id': 2,
                'method': 'tools/list'
            }
            
            async with session.post(f"{base_url}/message", json=tools_message) as resp:
                if resp.status == 200:
                    result = await resp.json()
                    print(f"[TEST] ✅ HTTP tools/list successful")
                    if 'response' in result and 'result' in result['response']:
                        tools = result['response']['result'].get('tools', [])
                        print(f"[TEST] ✅ Available tools via HTTP: {[tool['name'] for tool in tools]}")
                else:
                    print(f"[TEST] ❌ HTTP tools/list failed: {resp.status}")
                    
    except Exception as e:
        print(f"[TEST] ❌ HTTP interaction failed: {e}")

async def test_sse_mcp_interaction(port: int = 9000):
    """Test MCP protocol interaction via SSE endpoints (for MCP Inspector)"""
    if not AIOHTTP_AVAILABLE:
        print("[TEST] ⚠️  aiohttp package not available, skipping SSE test")
        return
        
    try:
        import aiohttp
        import asyncio
        
        base_url = f'http://localhost:{port}/servers/fetch'
        print(f"[TEST] Testing SSE endpoints at {base_url}")
        
        async with aiohttp.ClientSession() as session:
            print(f"[TEST] Opening SSE connection...")
            
            # Start SSE connection
            async with session.get(f"{base_url}/sse") as resp:
                if resp.status != 200:
                    print(f"[TEST] ❌ SSE connection failed: {resp.status}")
                    return
                
                print(f"[TEST] ✅ SSE connection established")
                session_id = None
                
                # Read initial session message
                async for line in resp.content:
                    if line:
                        line_str = line.decode('utf-8').strip()
                        if line_str.startswith('data: '):
                            data_str = line_str[6:]  # Remove 'data: ' prefix
                            try:
                                data = json.loads(data_str)
                                if data.get('type') == 'session':
                                    session_id = data.get('sessionId')
                                    print(f"[TEST] ✅ Got session ID: {session_id}")
                                    break
                            except json.JSONDecodeError:
                                pass
                
                if not session_id:
                    print(f"[TEST] ❌ Failed to get session ID from SSE")
                    return
                
                # Test initialization via POST
                init_message = {
                    'jsonrpc': '2.0',
                    'id': 1,
                    'method': 'initialize',
                    'params': {
                        'protocolVersion': '2024-11-05',
                        'capabilities': {
                            'roots': {'listChanged': True},
                            'sampling': {}
                        },
                        'clientInfo': {'name': 'sse-test-client', 'version': '1.0.0'}
                    }
                }
                
                # Send via POST in a separate task
                async def send_init():
                    await asyncio.sleep(0.1)  # Small delay
                    async with session.post(f"{base_url}/sse", json=init_message) as post_resp:
                        if post_resp.status == 200:
                            result = await post_resp.json()
                            print(f"[TEST] ✅ Initialize message sent: {result.get('status')}")
                        else:
                            print(f"[TEST] ❌ Initialize POST failed: {post_resp.status}")
                
                send_task = asyncio.create_task(send_init())
                
                # Read initialize response from SSE
                init_received = False
                timeout_counter = 0
                
                async for line in resp.content:
                    if timeout_counter > 100:  # Timeout after ~10 seconds
                        break
                    timeout_counter += 1
                    
                    if line:
                        line_str = line.decode('utf-8').strip()
                        if line_str.startswith('data: '):
                            data_str = line_str[6:]
                            try:
                                data = json.loads(data_str)
                                print(f"[TEST] 📨 SSE received: {json.dumps(data)}")
                                
                                if data.get('id') == 1 and 'result' in data:
                                    print(f"[TEST] ✅ Initialize response received via SSE!")
                                    server_info = data.get('result', {}).get('serverInfo', {})
                                    print(f"[TEST] ✅ Server info: {server_info.get('name', 'unknown')}")
                                    init_received = True
                                    break
                                    
                            except json.JSONDecodeError as e:
                                print(f"[TEST] ⚠️  SSE parse error: {e} - data: {data_str}")
                    
                    await asyncio.sleep(0.1)
                
                # Give a bit more time for the message to arrive
                if not init_received:
                    await asyncio.sleep(2)
                    async for line in resp.content:
                        if line:
                            line_str = line.decode('utf-8').strip()
                            if line_str.startswith('data: '):
                                data_str = line_str[6:]
                                try:
                                    data = json.loads(data_str)
                                    print(f"[TEST] 📨 SSE received (retry): {json.dumps(data)}")
                                    
                                    if data.get('id') == 1 and 'result' in data:
                                        print(f"[TEST] ✅ Initialize response received via SSE!")
                                        server_info = data.get('result', {}).get('serverInfo', {})
                                        print(f"[TEST] ✅ Server info: {server_info.get('name', 'unknown')}")
                                        init_received = True
                                        break
                                        
                                except json.JSONDecodeError as e:
                                    print(f"[TEST] ⚠️  SSE parse error: {e} - data: {data_str}")
                        
                        timeout_counter += 1
                        if timeout_counter > 20:  # Additional timeout
                            break
                        await asyncio.sleep(0.1)
                
                await send_task
                
                if init_received:
                    print(f"[TEST] ✅ SSE transport working correctly!")
                else:
                    print(f"[TEST] ❌ SSE transport not receiving responses properly")
                    
    except Exception as e:
        print(f"[TEST] ❌ SSE test failed: {e}")
        print(f"[TEST] ❌ Traceback: {traceback.format_exc()}")

# ...existing code...

async def main():
    print("[TEST] Starting Enhanced MCP Server Manager...")
    print("[TEST] Features: Full MCP Protocol Compliance | WebSocket & SSE Support | MCP Inspector Compatible")
    
    # Configuration for multiple MCP servers (you can expand this)
    server_configs = {
        "fetch": {
            "command": "uvx",
            "args": ["mcp-server-fetch"]
        },
        # Add more servers here as needed
        # "filesystem": {
        #     "command": "npx",
        #     "args": ["-y", "@modelcontextprotocol/server-filesystem", "/tmp"]
        # }
    }
    
    manager = MCPServerManager(server_configs)
    
    # Start HTTP server first to get the actual port
    await manager.start_http_server(port=9000)
    
    # Give the server a moment to start
    await asyncio.sleep(1)
    
    # Start configured servers
    endpoints = {}
    for name, config in server_configs.items():
        print(f"[TEST] Starting '{name}' server...")
        endpoint = manager.add_and_start_server(name, config)
        if endpoint:
            endpoints[name] = endpoint
            print(f"[TEST] ✅ {name} server started successfully!")
        else:
            print(f"[TEST] ❌ Failed to start {name} server.")
    
    if endpoints:
        actual_port = getattr(manager, 'actual_port', 9000)
        print(f"\n[TEST] 🚀 MCP Server Manager is running!")
        print(f"[TEST] Active servers: {list(endpoints.keys())}")
        print(f"[TEST] Management UI: http://localhost:{actual_port}/servers")
        
        for name, endpoint in endpoints.items():
            print(f"\n[TEST] === {name.upper()} SERVER ENDPOINTS ===")
            print(f"[TEST] WebSocket (MCP Inspector): {endpoint}")
            print(f"[TEST] SSE Stream: http://localhost:{actual_port}/servers/{name}/sse")
            print(f"[TEST] HTTP API: http://localhost:{actual_port}/servers/{name}/message")
            print(f"[TEST] Initialize: http://localhost:{actual_port}/servers/{name}/initialize")
        
        # Wait a moment for servers to be ready
        print(f"\n[TEST] Waiting 3 seconds for servers to be ready...")
        await asyncio.sleep(3)
        
        # Run automated tests with the actual port
        print(f"\n[TEST] === RUNNING AUTOMATED TESTS ===")
        print(f"[TEST] Testing WebSocket MCP protocol...")
        await test_fetch_mcp_interaction(actual_port)
        
        print(f"\n[TEST] Testing HTTP MCP protocol...")
        await test_http_mcp_interaction(actual_port)
        
        print(f"\n[TEST] Testing SSE MCP protocol...")
        await test_sse_mcp_interaction(actual_port)
        
        print(f"\n[TEST] === MCP INSPECTOR INSTRUCTIONS ===")
        print(f"[TEST] 1. Open MCP Inspector")
        print(f"[TEST] 2. Choose 'WebSocket' transport")
        print(f"[TEST] 3. Enter URL: ws://localhost:{actual_port}/servers/fetch/ws")
        print(f"[TEST] 4. Connect and test the fetch tool!")
        print(f"[TEST] 5. Alternative: Use SSE transport with http://localhost:{actual_port}/servers/fetch/sse")
        
        print(f"\n[TEST] Server will stay alive indefinitely for testing...")
        print(f"[TEST] Press Ctrl+C to stop.")
        
        try:
            # Keep the server running indefinitely for production use
            while True:
                await asyncio.sleep(60)
                # Optional: Add periodic health checks here
                alive_servers = [name for name, server in manager.servers.items() if server.is_alive()]
                if len(alive_servers) != len(endpoints):
                    print(f"[TEST] Health check - Active servers: {alive_servers}")
                
        except KeyboardInterrupt:
            print(f"\n[TEST] Received interrupt signal.")
    else:
        print(f"[TEST] ❌ No servers started successfully.")
    
    print(f"[TEST] Stopping all servers...")
    manager.stop_all_servers()
    print(f"[TEST] ✅ Done.")

if __name__ == "__main__":
    asyncio.run(main())
