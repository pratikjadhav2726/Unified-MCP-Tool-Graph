import asyncio
import subprocess
import time
import os
from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)
# Optional: Add basicConfig for testing the script directly,
# but usually the application using this manager should configure logging.
# logging.basicConfig(level=logging.INFO)

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

    def start(self):
        if self.process is None or self.process.poll() is not None:
            logger.info(f"[MCP] Attempting to start {self.name} MCP server with command: {' '.join([self.command] + self.args)}")
            try:
                env = dict(os.environ)
                env.update(self.env)
                self.process = subprocess.Popen([self.command] + self.args, env=env)
                logger.info(f"[MCP] Successfully started {self.name} MCP server (PID: {self.process.pid}).")
            except Exception as e:
                logger.error(f"[MCP] Failed to start {self.name} MCP server. Error: {e}")
                self.process = None # Ensure process is None if start failed
        else:
            logger.info(f"[MCP] Server {self.name} is already running (PID: {self.process.pid}). Touching last_used time.")
        self.last_used = time.time()

    def touch(self):
        self.last_used = time.time()

    def stop(self):
        if self.process and self.process.poll() is None:
            logger.info(f"[MCP] Attempting to stop {self.name} MCP server (PID: {self.process.pid}).")
            try:
                self.process.terminate()
                # Optionally, add wait and kill logic if terminate is not enough
                logger.info(f"[MCP] Successfully sent terminate signal to {self.name} MCP server.")
            except Exception as e:
                logger.error(f"[MCP] Error stopping {self.name} MCP server (PID: {self.process.pid}). Error: {e}")
        else:
            logger.info(f"[MCP] Server {self.name} not running or already stopped.")

    def is_alive(self):
        return self.process and self.process.poll() is None

class MCPServerManager:
    def __init__(self, popular_servers: Dict[str, dict]):
        self.servers: Dict[str, MCPServerProcess] = {}
        self.popular_servers = popular_servers
        self._base_port = 8000
        self._next_port = self._base_port
        self._name_to_port = {}

    def _assign_endpoint(self, name, cfg):
        # If endpoint is provided, use it; otherwise, assign a new port
        endpoint = cfg.get("endpoint")
        if not endpoint:
            if name not in self._name_to_port:
                self._name_to_port[name] = self._next_port
                self._next_port += 1
            port = self._name_to_port[name]
            endpoint = f"http://localhost:{port}"
            cfg["endpoint"] = endpoint  # Mutate config so downstream code sees it
        return endpoint

    def start_popular_servers(self):
        for name, cfg in self.popular_servers.items():
            self.add_and_start_server(name, cfg)

    def add_and_start_server(self, name, cfg):
        env = cfg.get("env", {})
        endpoint = self._assign_endpoint(name, cfg) # Endpoint assignment should be robust

        # Basic check for command and args in cfg
        if "command" not in cfg or "args" not in cfg:
            logger.error(f"[MCP] Cannot start server {name} due to missing 'command' or 'args' in configuration: {cfg}")
            return

        logger.info(f"[MCP] Adding and starting server: {name}. Endpoint: {endpoint}. Config: {cfg}")
        if name not in self.servers:
            proc = MCPServerProcess(
                name=name,
                command=cfg["command"],
                args=cfg["args"],
                endpoint=endpoint,
                env=env
            )
            self.servers[name] = proc
            # Start is called on the next line by self.servers[name].start()

        self.servers[name].start() # This will call MCPServerProcess.start() which now has logging
        # Redundant log after start if MCPServerProcess.start logs success.
        # if self.servers[name].is_alive():
        #     logger.info(f"[MCP] {name} server is now active. Endpoint: {endpoint}")
        # else:
        #     logger.warning(f"[MCP] {name} server failed to start or is not alive after start attempt.")


    def ensure_server(self, name, cfg):
        if name not in self.servers or not self.servers[name].is_alive():
            self.add_and_start_server(name, cfg)
        else:
            self.servers[name].touch()

    def get_active_endpoints(self):
        return {name: proc.endpoint for name, proc in self.servers.items() if proc.is_alive()}

    async def cleanup_loop(self):
        while True:
            now = time.time()
            for name, proc in list(self.servers.items()): # Use list() for safe iteration if modifying dict
                if proc.is_alive() and now - proc.last_used > proc.keep_alive_secs:
                    logger.info(f"[MCP] Server {name} exceeded keep_alive_secs. Attempting to stop due to inactivity.")
                    proc.stop()
            await asyncio.sleep(60)

if __name__ == "__main__":
    import time
    logging.basicConfig(level=logging.INFO) # Add basicConfig for testing the script directly
    logger.info("[TEST] Starting MCPServerManager test...")
    # Example config for Tavily MCP
    test_config = {
        "command": "npx",
        "args": ["-y", "tavily-mcp@0.2.1"],
        "endpoint": "http://localhost:8080",  # Example endpoint
        "env": {
            "TAVILY_API_KEY": os.getenv("TAVILY_API_KEY", "test-key-from-env")
        }
    }
    manager = MCPServerManager({})
    logger.info("[TEST] Ensuring server 'tavily-mcp' is started...")
    manager.ensure_server("tavily-mcp", test_config)
    logger.info(f"[TEST] Active endpoints: {manager.get_active_endpoints()}")
    logger.info("[TEST] Sleeping for 5 seconds to keep server alive...")
    time.sleep(5)
    logger.info("[TEST] Stopping server...")
    if "tavily-mcp" in manager.servers:
        manager.servers["tavily-mcp"].stop()
    logger.info("[TEST] Done.")
