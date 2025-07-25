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
COPILOT_CONFIG_FILE = "mcp.json"  # Add this for Copilot configuration

class MCPServerConfig:
    """
    Configuration class for individual MCP servers.
    
    Handles server configuration data and provides methods to convert
    configurations between different formats (manager format vs proxy format).
    """
    
    def __init__(self, name: str, command: str, args: Optional[List[str]] = None, 
                 env: Optional[Dict[str, str]] = None, cwd: Optional[str] = None):
        """
        Initialize MCP server configuration.
        
        Args:
            name (str): Server name/identifier
            command (str): Command to execute the server
            args (List[str], optional): Command line arguments
            env (Dict[str, str], optional): Environment variables
            cwd (str, optional): Working directory for the server process
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
        config = {
            "enabled": True,
            "command": self.command,
            "args": self.args,
            "env": self.env,
            "transportType": "stdio"
        }
        
        # Add working directory if specified
        if self.cwd:
            config["cwd"] = self.cwd
            
        return config

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
    - Automatic Copilot mcp.json configuration management
    
    Attributes:
        popular_servers (Dict[str, dict]): Pre-configured servers that are always available
        dynamic_servers (Dict[str, dict]): Dynamically added servers
        last_used (Dict[str, float]): Timestamp tracking for idle cleanup
        proxy_port (int): Port number for the mcp-proxy server
        proxy_proc (subprocess.Popen): Process handle for the running proxy
        copilot_config_path (str): Path to Copilot's mcp.json configuration file
    """
    
    def __init__(self, popular_servers: Dict[str, dict], proxy_port: int = 9000, 
                 copilot_config_path: str = None):
        """
        Initialize the MCP Server Manager.
        
        Args:
            popular_servers (Dict[str, dict]): Dictionary of pre-configured servers
                Format: {server_name: {command, args, env, cwd}}
            proxy_port (int, optional): Port for mcp-proxy server. Defaults to 9000.
            copilot_config_path (str, optional): Path to Copilot's mcp.json. Auto-detected if None.
        """
        self.popular_servers = popular_servers
        self.dynamic_servers = {}  # name -> config
        self.last_used = {}        # name -> timestamp
        self.proxy_port = proxy_port
        self.proxy_proc = None
        
        # Copilot configuration management
        self.copilot_config_path = copilot_config_path or self._find_copilot_config()

    def _find_copilot_config(self):
        """
        Auto-detect Copilot's MCP configuration file location.
        
        Returns:
            str: Path to the mcp.json configuration file
        """
        possible_paths = [
            os.path.expanduser("~/.config/cursor/mcp.json"),
            os.path.expanduser("~/.cursor/mcp.json"), 
            os.path.expanduser("~/Library/Application Support/Cursor/mcp.json"),
            "./.vscode/mcp.json",  # VS Code workspace configuration
            "./mcp.json"  # Local development/testing
        ]
        
        for path in possible_paths:
            if os.path.exists(path):
                logger.info(f"Found Copilot MCP config at: {path}")
                return path
                
        # Default to local if not found
        default_path = "./mcp.json"
        logger.info(f"Using default MCP config path: {default_path}")
        return default_path

    def _build_copilot_config(self):
        """
        Build Copilot's mcp.json configuration with proxy URLs.
        
        Returns:
            Dict: Configuration dictionary for Copilot with servers containing
                  HTTP endpoints for all managed servers
        """
        servers = {}
        all_servers = {**self.popular_servers, **self.dynamic_servers}
        
        for server_name in all_servers.keys():
            servers[server_name] = {
                "url": f"http://localhost:{self.proxy_port}/servers/{server_name}/sse",
                "type": "http"
            }
        
        return {
            "servers": servers,
            "inputs": []
        }

    def _write_copilot_config(self):
        """
        Write/update Copilot's mcp.json configuration file.
        
        Creates or updates the mcp.json file that Copilot reads to discover
        available MCP servers. Each server is configured to connect through
        the proxy's SSE endpoints.
        """
        try:
            # Read existing config to preserve any manual settings
            existing_config = {}
            if os.path.exists(self.copilot_config_path):
                try:
                    with open(self.copilot_config_path, 'r') as f:
                        existing_config = json.load(f)
                except Exception as e:
                    logger.warning(f"Could not read existing Copilot config: {e}")
            
            # Build new configuration
            new_config = self._build_copilot_config()
            
            # Merge with existing config (preserve other settings, update servers)
            merged_config = {**existing_config}
            merged_config["servers"] = {**existing_config.get("servers", {}), **new_config["servers"]}
            merged_config["inputs"] = new_config.get("inputs", existing_config.get("inputs", []))
            
            # Write updated configuration
            os.makedirs(os.path.dirname(self.copilot_config_path), exist_ok=True)
            with open(self.copilot_config_path, 'w') as f:
                json.dump(merged_config, f, indent=2)
            
            server_count = len(new_config["servers"])
            logger.info(f"Updated Copilot MCP config at {self.copilot_config_path}")
            logger.info(f"Configured {server_count} servers: {list(new_config['servers'].keys())}")
            
        except Exception as e:
            logger.error(f"Failed to write Copilot config: {e}")

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
        
        # Also write client configuration and Copilot configuration
        self._write_client_config()
        self._write_copilot_config()

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
        logger.info("Starting MCP Server Manager...")
        self._write_proxy_config()  # This will also write Copilot config
        self._start_proxy()
        logger.info("MCP Server Manager started successfully")

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
        
        The server will be immediately available through the proxy after addition
        and will be added to Copilot's configuration.
        """
        logger.info(f"Adding server {name}")
        self.dynamic_servers[name] = config
        self.last_used[name] = time.time()
        self._write_proxy_config()  # This updates both proxy and Copilot configs
        self._start_proxy()

    def remove_server(self, name):
        """
        Remove a dynamically added server from the manager.
        
        Args:
            name (str): Name of the server to remove
        
        Note: Popular servers cannot be removed through this method.
        The proxy will be restarted and Copilot config updated to reflect the change.
        """
        logger.info(f"Removing server {name}")
        if name in self.dynamic_servers:
            del self.dynamic_servers[name]
        if name in self.last_used:
            del self.last_used[name]
        self._write_proxy_config()  # This updates both proxy and Copilot configs
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

    def get_copilot_config_path(self):
        """
        Get the path to Copilot's mcp.json configuration file.
        
        Returns:
            str: Path to the Copilot configuration file
        """
        return self.copilot_config_path

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
                "type": "http",
                "url": f"http://localhost:{self.proxy_port}/servers/{name}/sse"
            }
        return {"servers": servers, "inputs": []}

    def _write_client_config(self):
        """
        Write client configuration file for MCP clients to connect to servers.
        
        Generates a JSON configuration file that MCP clients can use to discover
        and connect to all available servers through their SSE endpoints.
        """
        config = self._build_client_config()
        with open(CLIENT_CONFIG_FILE, "w") as f:
            json.dump(config, f, indent=2)
        logger.info(f"Wrote MCP client config with {len(config['servers'])} server endpoints")

    def update_client_config(self):
        """
        Manually trigger an update of the client configuration file.
        
        This method can be called to refresh the client configuration without
        restarting the proxy server, useful for external integrations.
        """
        self._write_client_config()

    def update_copilot_config(self):
        """
        Manually trigger an update of Copilot's mcp.json configuration.
        
        This method can be called to refresh Copilot's configuration without
        restarting the proxy server.
        """
        self._write_copilot_config()

    def list_configured_servers(self):
        """
        Get a summary of all configured servers and their status.
        
        Returns:
            Dict: Summary containing popular and dynamic servers with their endpoints
        """
        return {
            "popular_servers": list(self.popular_servers.keys()),
            "dynamic_servers": list(self.dynamic_servers.keys()),
            "total_servers": len(self.popular_servers) + len(self.dynamic_servers),
            "proxy_port": self.proxy_port,
            "copilot_config_path": self.copilot_config_path,
            "endpoints": self.get_client_endpoints()
        }

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
        
        # Display server summary
        summary = manager.list_configured_servers()
        logger.info("=== MCP Server Manager Status ===")
        logger.info(f"Popular servers: {summary['popular_servers']}")
        logger.info(f"Total servers: {summary['total_servers']}")
        logger.info(f"Proxy port: {summary['proxy_port']}")
        logger.info(f"Copilot config: {summary['copilot_config_path']}")
        
        logger.info("\n=== Available endpoints for Copilot ===")
        for name, endpoint in summary['endpoints'].items():
            logger.info(f"  {name}: {endpoint}")
        
        logger.info(f"\nCopilot configuration written to: {manager.get_copilot_config_path()}")
        logger.info("MCP Proxy Manager running. Press Ctrl+C to stop.")
        
        # Main loop with periodic cleanup
        while True:
            time.sleep(60)
            manager.cleanup_idle(ttl=600)  # Clean up servers idle for 10+ minutes
            
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    finally:
        manager.stop()