import os
import json
import subprocess
import logging
import time
from typing import Dict, List, Optional

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

CONFIG_FILE = "mcp_proxy_servers.json"
CLIENT_CONFIG_FILE = "mcp_client_config.json"

class MCPServerConfig:
    def __init__(self, name, command, args=None, env=None, cwd=None):
        self.name = name
        self.command = command
        self.args = args or []
        self.env = env or {}
        self.cwd = cwd

    def to_proxy_dict(self):
        return {
            "enabled": True,
            "command": self.command,
            "args": self.args,
            "env": self.env,
            "transportType": "stdio"
        }

class MCPServerManager:
    def __init__(self, popular_servers: Dict[str, dict], proxy_port: int = 9000):
        self.popular_servers = popular_servers
        self.dynamic_servers = {}  # name -> config
        self.last_used = {}        # name -> timestamp
        self.proxy_port = proxy_port
        self.proxy_proc = None

    def _build_proxy_config(self):
        servers = {}
        for name, cfg in {**self.popular_servers, **self.dynamic_servers}.items():
            servers[name] = MCPServerConfig(name, **cfg).to_proxy_dict()
        return {"mcpServers": servers}

    def _write_proxy_config(self):
        config = self._build_proxy_config()
        with open(CONFIG_FILE, "w") as f:
            json.dump(config, f, indent=2)
        logger.info(f"Wrote mcp-proxy config with servers: {list(config['mcpServers'].keys())}")
        
        # Also write client configuration
        self._write_client_config()

    def _start_proxy(self):
        if self.proxy_proc:
            logger.info("Stopping existing mcp-proxy...")
            self.proxy_proc.terminate()
            self.proxy_proc.wait()
        cmd = [
            "mcp-proxy",
            f"--port={self.proxy_port}",
            "--named-server-config", CONFIG_FILE
        ]
        logger.info(f"Starting mcp-proxy: {' '.join(cmd)}")
        self.proxy_proc = subprocess.Popen(cmd)
        logger.info(f"mcp-proxy started on port {self.proxy_port}")

    def start(self):
        self._write_proxy_config()
        self._start_proxy()

    def stop(self):
        if self.proxy_proc:
            logger.info("Stopping mcp-proxy...")
            self.proxy_proc.terminate()
            self.proxy_proc.wait()
            self.proxy_proc = None

    def add_server(self, name, config):
        logger.info(f"Adding server {name}")
        self.dynamic_servers[name] = config
        self.last_used[name] = time.time()
        self._write_proxy_config()
        self._start_proxy()

    def remove_server(self, name):
        logger.info(f"Removing server {name}")
        if name in self.dynamic_servers:
            del self.dynamic_servers[name]
        if name in self.last_used:
            del self.last_used[name]
        self._write_proxy_config()
        self._start_proxy()

    def mark_used(self, name):
        self.last_used[name] = time.time()

    def cleanup_idle(self, ttl=600):
        now = time.time()
        to_remove = [name for name, last in self.last_used.items()
                     if name not in self.popular_servers and now - last > ttl]
        for name in to_remove:
            self.remove_server(name)

    def get_endpoints(self):
        return {
            name: f"http://localhost:{self.proxy_port}/servers/{name}/"
            for name in {**self.popular_servers, **self.dynamic_servers}
        }

    def get_client_endpoints(self):
        """Get SSE endpoints for MCP clients to connect to."""
        return {
            name: f"http://localhost:{self.proxy_port}/servers/{name}/sse"
            for name in {**self.popular_servers, **self.dynamic_servers}
        }

    def get_client_config_path(self):
        """Get the path to the generated client configuration file."""
        return CLIENT_CONFIG_FILE

    def _build_client_config(self):
        """Build client configuration for connecting to MCP servers via proxy."""
        servers = {}
        for name in {**self.popular_servers, **self.dynamic_servers}.keys():
            servers[name] = {
                "type": "sse",
                "url": f"http://localhost:{self.proxy_port}/servers/{name}/sse",
                "timeout": 5,
                "sse_read_timeout": 300
            }
        return {"mcpServers": servers}

    def _write_client_config(self):
        """Write client configuration file for MCP clients to connect to servers."""
        config = self._build_client_config()
        with open(CLIENT_CONFIG_FILE, "w") as f:
            json.dump(config, f, indent=2)
        logger.info(f"Wrote MCP client config with {len(config['mcpServers'])} server endpoints")

    def update_client_config(self):
        self._write_client_config()

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
        }
    }
    manager = MCPServerManager(popular_servers=POPULAR_SERVERS, proxy_port=9000)
    try:
        manager.start()
        
        # Add the fetch server dynamically
        fetch_server_config = {
            "command": "uvx",
            "args": ["mcp-server-fetch"]
        }
        manager.add_server("fetch", fetch_server_config)
        
        # Display client endpoints
        client_endpoints = manager.get_client_endpoints()
        logger.info("Available MCP client endpoints:")
        for name, endpoint in client_endpoints.items():
            logger.info(f"  {name}: {endpoint}")
        
        logger.info(f"Client configuration written to: {manager.get_client_config_path()}")
        logger.info("MCP Proxy Manager running. Press Ctrl+C to stop.")
        while True:
            time.sleep(60)
            manager.cleanup_idle(ttl=600)
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    finally:
        manager.stop()