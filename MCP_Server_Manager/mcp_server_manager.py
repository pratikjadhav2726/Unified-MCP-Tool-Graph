"""
MCP Server Manager

A comprehensive management system for Model Context Protocol (MCP) servers that provides
dynamic server configuration, proxy management, and client endpoint generation.

This module enables:
- Dynamic addition and removal of MCP servers
- Automatic proxy configuration and restart
- Client endpoint management for SSE connections
- Idle server cleanup and lifecycle management
- Configuration file generation for both proxy and client connections

Author: Pratik Jadhav
Date: July 2025
"""

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
    """
    Configuration class for MCP server instances.
    
    This class encapsulates the configuration details needed to run an MCP server,
    including command, arguments, environment variables, and working directory.
    
    Attributes:
        name (str): Unique identifier for the server
        command (str): The executable command to run the server
        args (List[str]): Command line arguments for the server
        env (Dict[str, str]): Environment variables for the server process
        cwd (Optional[str]): Working directory for the server process
    """
    
    def __init__(self, name, command, args=None, env=None, cwd=None):
        """
        Initialize MCP server configuration.
        
        Args:
            name (str): Unique name identifier for the server
            command (str): Command to execute the server (e.g., 'uvx', 'npx')
            args (List[str], optional): Arguments to pass to the command. Defaults to [].
            env (Dict[str, str], optional): Environment variables. Defaults to {}.
            cwd (str, optional): Working directory for server execution. Defaults to None.
        """
        self.name = name
        self.command = command
        self.args = args or []
        self.env = env or {}
        self.cwd = cwd

    def to_proxy_dict(self):
        """
        Convert configuration to mcp-proxy compatible dictionary format.
        
        Returns:
            Dict: Configuration dictionary for mcp-proxy with keys:
                - enabled: Always True for active servers
                - command: Server execution command
                - args: Command arguments list
                - env: Environment variables
                - transportType: Communication protocol (stdio)
        """
        return {
            "enabled": True,
            "command": self.command,
            "args": self.args,
            "env": self.env,
            "transportType": "stdio"
        }

class MCPServerManager:
    """
    Main manager class for MCP servers with dynamic configuration and proxy management.
    
    This class provides a comprehensive solution for managing multiple MCP servers through
    a unified proxy interface. It handles server lifecycle, configuration generation,
    and client endpoint management.
    
    Features:
    - Dynamic server addition/removal
    - Automatic proxy restart on configuration changes
    - Idle server cleanup with configurable TTL
    - Client configuration generation for SSE connections
    - Popular server pre-configuration
    
    Attributes:
        popular_servers (Dict[str, dict]): Pre-configured servers that are always available
        dynamic_servers (Dict[str, dict]): Dynamically added servers
        last_used (Dict[str, float]): Timestamp tracking for idle cleanup
        proxy_port (int): Port number for the mcp-proxy server
        proxy_proc (subprocess.Popen): Process handle for the running proxy
    """
    
    def __init__(self, popular_servers: Dict[str, dict], proxy_port: int = 9000):
        """
        Initialize the MCP Server Manager.
        
        Args:
            popular_servers (Dict[str, dict]): Dictionary of pre-configured servers
                Format: {server_name: {command, args, env, cwd}}
            proxy_port (int, optional): Port for mcp-proxy server. Defaults to 9000.
        """
        self.popular_servers = popular_servers
        self.dynamic_servers = {}  # name -> config
        self.last_used = {}        # name -> timestamp
        self.proxy_port = proxy_port
        self.proxy_proc = None

    def _build_proxy_config(self):
        """
        Build the configuration dictionary for mcp-proxy.
        
        Combines both popular and dynamic servers into a unified configuration
        that can be consumed by the mcp-proxy server.
        
        Returns:
            Dict: Complete proxy configuration with 'mcpServers' key containing
                  all server configurations in proxy-compatible format
        """
        servers = {}
        for name, cfg in {**self.popular_servers, **self.dynamic_servers}.items():
            servers[name] = MCPServerConfig(name, **cfg).to_proxy_dict()
        return {"mcpServers": servers}

    def _write_proxy_config(self):
        """
        Write the proxy configuration to file and update client config.
        
        Generates the mcp_proxy_servers.json file required by mcp-proxy and
        also triggers client configuration update for SSE endpoints.
        """
        config = self._build_proxy_config()
        with open(CONFIG_FILE, "w") as f:
            json.dump(config, f, indent=2)
        logger.info(f"Wrote mcp-proxy config with servers: {list(config['mcpServers'].keys())}")
        
        # Also write client configuration
        self._write_client_config()

    def _start_proxy(self):
        """
        Start or restart the mcp-proxy server process.
        
        Terminates any existing proxy process and starts a new one with the current
        configuration. The proxy will serve on the configured port and load server
        configurations from the generated config file.
        """
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
        """
        Initialize and start the MCP proxy manager.
        
        This method writes the initial configuration and starts the proxy server.
        Should be called once during manager initialization.
        """
        self._write_proxy_config()
        self._start_proxy()

    def stop(self):
        """
        Stop the MCP proxy server and clean up resources.
        
        Terminates the proxy process gracefully and sets the process handle to None.
        Should be called during manager shutdown.
        """
        if self.proxy_proc:
            logger.info("Stopping mcp-proxy...")
            self.proxy_proc.terminate()
            self.proxy_proc.wait()
            self.proxy_proc = None

    def add_server(self, name, config):
        """
        Dynamically add a new MCP server to the manager.
        
        Args:
            name (str): Unique identifier for the server
            config (dict): Server configuration containing command, args, env, etc.
                          Format: {command: str, args: List[str], env: Dict, cwd: str}
        
        The server will be immediately available through the proxy after addition.
        """
        logger.info(f"Adding server {name}")
        self.dynamic_servers[name] = config
        self.last_used[name] = time.time()
        self._write_proxy_config()
        self._start_proxy()

    def remove_server(self, name):
        """
        Remove a dynamically added server from the manager.
        
        Args:
            name (str): Name of the server to remove
        
        Note: Popular servers cannot be removed through this method.
        The proxy will be restarted to reflect the configuration change.
        """
        logger.info(f"Removing server {name}")
        if name in self.dynamic_servers:
            del self.dynamic_servers[name]
        if name in self.last_used:
            del self.last_used[name]
        self._write_proxy_config()
        self._start_proxy()

    def mark_used(self, name):
        """
        Update the last used timestamp for a server.
        
        Args:
            name (str): Name of the server that was accessed
        
        This is used for idle cleanup to prevent removal of actively used servers.
        """
        self.last_used[name] = time.time()

    def cleanup_idle(self, ttl=600):
        """
        Remove idle servers that haven't been used within the TTL period.
        
        Args:
            ttl (int, optional): Time-to-live in seconds. Defaults to 600 (10 minutes).
        
        Only dynamically added servers are subject to cleanup. Popular servers
        are never removed by this method.
        """
        now = time.time()
        to_remove = [name for name, last in self.last_used.items()
                     if name not in self.popular_servers and now - last > ttl]
        for name in to_remove:
            self.remove_server(name)

    def get_endpoints(self):
        """
        Get HTTP endpoints for all managed servers.
        
        Returns:
            Dict[str, str]: Mapping of server names to their HTTP endpoints
                           Format: {server_name: "http://localhost:port/servers/name/"}
        
        These endpoints can be used for direct HTTP communication with individual servers.
        """
        return {
            name: f"http://localhost:{self.proxy_port}/servers/{name}/"
            for name in {**self.popular_servers, **self.dynamic_servers}
        }

    def get_client_endpoints(self):
        """
        Get SSE endpoints for MCP clients to connect to.
        
        Returns:
            Dict[str, str]: Mapping of server names to their SSE endpoints
                           Format: {server_name: "http://localhost:port/servers/name/sse"}
        
        These endpoints are specifically designed for MCP client connections using
        Server-Sent Events (SSE) transport.
        """
        return {
            name: f"http://localhost:{self.proxy_port}/servers/{name}/sse"
            for name in {**self.popular_servers, **self.dynamic_servers}
        }

    def get_client_config_path(self):
        """
        Get the path to the generated client configuration file.
        
        Returns:
            str: Path to the JSON configuration file for MCP clients
        
        This file contains all server endpoints in a format that MCP clients
        can directly consume.
        """
        return CLIENT_CONFIG_FILE

    def _build_client_config(self):
        """
        Build client configuration for connecting to MCP servers via proxy.
        
        Returns:
            Dict: Complete client configuration with server endpoints, timeouts,
                  and connection parameters optimized for SSE transport
        """
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
        """
        Write client configuration file for MCP clients to connect to servers.
        
        Generates a JSON configuration file that MCP clients can use to discover
        and connect to all available servers through their SSE endpoints.
        """
        config = self._build_client_config()
        with open(CLIENT_CONFIG_FILE, "w") as f:
            json.dump(config, f, indent=2)
        logger.info(f"Wrote MCP client config with {len(config['mcpServers'])} server endpoints")

    def update_client_config(self):
        """
        Manually trigger an update of the client configuration file.
        
        This method can be called to refresh the client configuration without
        restarting the proxy server, useful for external integrations.
        """
        self._write_client_config()

if __name__ == "__main__":
    # Example configuration for popular MCP servers
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
    
    # Initialize and start the MCP Server Manager
    manager = MCPServerManager(popular_servers=POPULAR_SERVERS, proxy_port=9000)
    
    try:
        # Start the manager with popular servers
        manager.start()
        
        # Demonstrate dynamic server addition
        fetch_server_config = {
            "command": "uvx",
            "args": ["mcp-server-fetch"]
        }
        manager.add_server("fetch", fetch_server_config)
        
        # Display available client endpoints
        client_endpoints = manager.get_client_endpoints()
        logger.info("Available MCP client endpoints:")
        for name, endpoint in client_endpoints.items():
            logger.info(f"  {name}: {endpoint}")
        
        logger.info(f"Client configuration written to: {manager.get_client_config_path()}")
        logger.info("MCP Proxy Manager running. Press Ctrl+C to stop.")
        
        # Main loop with periodic cleanup
        while True:
            time.sleep(60)
            manager.cleanup_idle(ttl=600)  # Clean up servers idle for 10+ minutes
            
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    finally:
        manager.stop()