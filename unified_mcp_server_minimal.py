#!/usr/bin/env python3
"""
Unified MCP Tool Server - Minimal Version

A minimal implementation that demonstrates the knowledge graph MCP integration
using only Python standard library modules. No external dependencies required.

Key Features:
- HTTP server using standard library
- Mock knowledge graph with real MCP server data from GitHub
- Tool discovery and execution simulation
- Health checks and metrics endpoints
- JSON-RPC 2.0 protocol support
"""

import asyncio
import os
import sys
import logging
import time
import json
import uuid
import subprocess
import tempfile
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading
from urllib.parse import urlparse, parse_qs

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@dataclass
class ServerConfig:
    """Configuration for the unified MCP server"""
    server_name: str = field(default_factory=lambda: os.getenv('MCP_SERVER_NAME', 'unified-tool-server'))
    server_version: str = field(default_factory=lambda: os.getenv('MCP_SERVER_VERSION', '2.0.0'))
    protocol_version: str = field(default_factory=lambda: os.getenv('MCP_PROTOCOL_VERSION', '2024-11-05'))
    host: str = field(default_factory=lambda: os.getenv('HOST', '0.0.0.0'))
    port: int = field(default_factory=lambda: int(os.getenv('PORT', '8000')))
    log_level: str = field(default_factory=lambda: os.getenv('LOG_LEVEL', 'INFO'))

class MockGraphDatabase:
    """Mock Neo4j graph database with realistic MCP server data from GitHub"""
    
    def __init__(self):
        self.logger = logger.getChild("graph_db")
        
        # Real MCP servers from GitHub with actual configurations
        self.mock_tools = [
            {
                "name": "mcp-server-fetch",
                "description": "A server for fetching web content and files",
                "mcp_config": json.dumps({
                    "command": "uvx",
                    "args": ["mcp-server-fetch"],
                    "env": {},
                    "transport": "stdio",
                    "repository": "https://github.com/modelcontextprotocol/servers",
                    "install_command": "uvx mcp-server-fetch",
                    "github_config": {
                        "main_file": "src/fetch/index.ts",
                        "package_json": {
                            "name": "mcp-server-fetch",
                            "version": "0.1.0",
                            "dependencies": {
                                "@modelcontextprotocol/sdk": "^1.0.0"
                            }
                        }
                    }
                }),
                "vendor": "modelcontextprotocol",
                "categories": ["web", "utilities"],
                "popularity": 95.0,
                "github_url": "https://github.com/modelcontextprotocol/servers/tree/main/src/fetch",
                "tools": [
                    {
                        "name": "fetch",
                        "description": "Fetch a URL and return its contents",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "url": {"type": "string", "description": "URL to fetch"}
                            },
                            "required": ["url"]
                        }
                    }
                ]
            },
            {
                "name": "mcp-server-time",
                "description": "A server for time and date operations",
                "mcp_config": json.dumps({
                    "command": "uvx",
                    "args": ["mcp-server-time"],
                    "env": {},
                    "transport": "stdio",
                    "repository": "https://github.com/modelcontextprotocol/servers",
                    "install_command": "uvx mcp-server-time",
                    "github_config": {
                        "main_file": "src/time/index.ts",
                        "tools_implementation": {
                            "get_current_time": "new Date().toISOString()",
                            "format_time": "dayjs(input).format(format)"
                        }
                    }
                }),
                "vendor": "modelcontextprotocol",
                "categories": ["time", "utilities"],
                "popularity": 88.0,
                "github_url": "https://github.com/modelcontextprotocol/servers/tree/main/src/time",
                "tools": [
                    {
                        "name": "get_current_time",
                        "description": "Get current time in various formats",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "timezone": {"type": "string", "description": "Timezone (optional)"},
                                "format": {"type": "string", "description": "Time format (optional)"}
                            }
                        }
                    }
                ]
            },
            {
                "name": "mcp-server-filesystem",
                "description": "A server for file system operations",
                "mcp_config": json.dumps({
                    "command": "uvx",
                    "args": ["mcp-server-filesystem", "/tmp"],
                    "env": {},
                    "transport": "stdio",
                    "repository": "https://github.com/modelcontextprotocol/servers",
                    "install_command": "uvx mcp-server-filesystem",
                    "github_config": {
                        "security_model": "sandboxed",
                        "allowed_operations": ["read", "write", "list"],
                        "base_directory": "/tmp"
                    }
                }),
                "vendor": "modelcontextprotocol",
                "categories": ["filesystem", "utilities"],
                "popularity": 92.0,
                "github_url": "https://github.com/modelcontextprotocol/servers/tree/main/src/filesystem",
                "tools": [
                    {
                        "name": "read_file",
                        "description": "Read the contents of a file",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "path": {"type": "string", "description": "Path to the file to read"}
                            },
                            "required": ["path"]
                        }
                    },
                    {
                        "name": "write_file", 
                        "description": "Write content to a file",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "path": {"type": "string", "description": "Path where to write the file"},
                                "content": {"type": "string", "description": "Content to write"}
                            },
                            "required": ["path", "content"]
                        }
                    }
                ]
            },
            {
                "name": "mcp-server-postgres",
                "description": "A server for PostgreSQL database operations",
                "mcp_config": json.dumps({
                    "command": "uvx",
                    "args": ["mcp-server-postgres"],
                    "env": {
                        "POSTGRES_CONNECTION_STRING": "postgresql://user:password@localhost:5432/dbname"
                    },
                    "transport": "stdio",
                    "repository": "https://github.com/modelcontextprotocol/servers",
                    "install_command": "uvx mcp-server-postgres",
                    "github_config": {
                        "dependencies": ["pg", "@types/pg"],
                        "security": "connection_string_required",
                        "query_timeout": 30000
                    }
                }),
                "vendor": "modelcontextprotocol",
                "categories": ["database", "sql"],
                "popularity": 85.0,
                "github_url": "https://github.com/modelcontextprotocol/servers/tree/main/src/postgres",
                "tools": [
                    {
                        "name": "query",
                        "description": "Execute a PostgreSQL query",
                        "inputSchema": {
                            "type": "object", 
                            "properties": {
                                "query": {"type": "string", "description": "SQL query to execute"}
                            },
                            "required": ["query"]
                        }
                    }
                ]
            },
            {
                "name": "mcp-server-git",
                "description": "A server for Git repository operations",
                "mcp_config": json.dumps({
                    "command": "uvx",
                    "args": ["mcp-server-git"],
                    "env": {},
                    "transport": "stdio",
                    "repository": "https://github.com/modelcontextprotocol/servers",
                    "install_command": "uvx mcp-server-git",
                    "github_config": {
                        "git_commands": ["status", "log", "diff", "show"],
                        "safety_checks": True,
                        "working_directory_required": True
                    }
                }),
                "vendor": "modelcontextprotocol",
                "categories": ["git", "version-control"],
                "popularity": 90.0,
                "github_url": "https://github.com/modelcontextprotocol/servers/tree/main/src/git",
                "tools": [
                    {
                        "name": "git_status",
                        "description": "Get git status of repository",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "repo_path": {"type": "string", "description": "Path to git repository"}
                            },
                            "required": ["repo_path"]
                        }
                    },
                    {
                        "name": "git_log",
                        "description": "Get git commit history", 
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "repo_path": {"type": "string", "description": "Path to git repository"},
                                "limit": {"type": "integer", "description": "Number of commits to show", "default": 10}
                            },
                            "required": ["repo_path"]
                        }
                    }
                ]
            }
        ]
    
    def search_tools(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Search for relevant tools in the mock graph database"""
        start_time = time.time()
        
        try:
            # Filter tools based on query
            results = []
            for tool in self.mock_tools:
                if (query.lower() in tool['name'].lower() or 
                    query.lower() in tool['description'].lower() or
                    any(query.lower() in cat.lower() for cat in tool['categories'])):
                    results.append(tool)
            
            # Sort by popularity and limit
            results.sort(key=lambda x: x['popularity'], reverse=True)
            results = results[:limit]
            
            self.logger.info(f"Graph search completed: query='{query}', results={len(results)}, duration={time.time() - start_time:.3f}s")
            
            return results
            
        except Exception as e:
            self.logger.error(f"Graph search failed: query='{query}', error={str(e)}")
            raise

class ToolExecutor:
    """Handles execution of tools using MCP configurations from GitHub"""
    
    def __init__(self, graph_db: MockGraphDatabase):
        self.graph_db = graph_db
        self.logger = logger.getChild("tool_executor")
    
    def execute_dynamic_tool(self, tool_name: str, tool_config: Dict[str, Any], arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a dynamically discovered tool based on its GitHub MCP configuration"""
        start_time = time.time()
        
        try:
            # Parse MCP configuration
            mcp_config = json.loads(tool_config.get('mcp_config', '{}'))
            command = mcp_config.get('command', 'unknown')
            args = mcp_config.get('args', [])
            github_config = mcp_config.get('github_config', {})
            
            # Simulate tool execution based on tool type
            if 'fetch' in tool_name:
                result = self._simulate_fetch_execution(arguments, github_config, command, args)
            elif 'time' in tool_name:
                result = self._simulate_time_execution(arguments, github_config, command, args)
            elif 'filesystem' in tool_name:
                result = self._simulate_filesystem_execution(arguments, github_config, command, args)
            elif 'postgres' in tool_name:
                result = self._simulate_postgres_execution(arguments, github_config, command, args)
            elif 'git' in tool_name:
                result = self._simulate_git_execution(arguments, github_config, command, args)
            else:
                result = self._simulate_generic_execution(tool_name, arguments, mcp_config)
            
            self.logger.info(f"Tool executed successfully: {tool_name} in {time.time() - start_time:.3f}s")
            return result
            
        except Exception as e:
            self.logger.error(f"Tool execution failed: {tool_name}, error={str(e)}")
            raise
    
    def _simulate_fetch_execution(self, arguments: Dict[str, Any], github_config: Dict[str, Any], command: str, args: List[str]) -> Dict[str, Any]:
        """Simulate fetch tool execution using GitHub config"""
        url = arguments.get('url', 'https://example.com')
        main_file = github_config.get('main_file', 'unknown')
        
        return {
            "content": [
                {
                    "type": "text",
                    "text": f"Simulated fetch from {url}\n\nResponse would contain:\n- HTTP headers\n- Response body\n- Status code: 200\n\nGitHub Implementation: {main_file}\nCommand: {command} {' '.join(args)}\nSDK: {github_config.get('package_json', {}).get('dependencies', {}).get('@modelcontextprotocol/sdk', 'unknown')}"
                }
            ],
            "metadata": {
                "tool": "fetch",
                "url": url,
                "execution_time": time.time(),
                "github_source": github_config,
                "command": f"{command} {' '.join(args)}"
            }
        }
    
    def _simulate_time_execution(self, arguments: Dict[str, Any], github_config: Dict[str, Any], command: str, args: List[str]) -> Dict[str, Any]:
        """Simulate time tool execution using GitHub config"""
        timezone = arguments.get('timezone', 'UTC')
        format_str = arguments.get('format', 'ISO')
        
        impl_hints = github_config.get('tools_implementation', {})
        current_time_impl = impl_hints.get('get_current_time', 'new Date().toISOString()')
        
        return {
            "content": [
                {
                    "type": "text", 
                    "text": f"Current time: {time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime())}\nTimezone: {timezone}\nFormat: {format_str}\n\nGitHub Implementation: {current_time_impl}\nCommand: {command} {' '.join(args)}"
                }
            ],
            "metadata": {
                "tool": "get_current_time",
                "timezone": timezone,
                "format": format_str,
                "implementation": current_time_impl,
                "command": f"{command} {' '.join(args)}"
            }
        }
    
    def _simulate_filesystem_execution(self, arguments: Dict[str, Any], github_config: Dict[str, Any], command: str, args: List[str]) -> Dict[str, Any]:
        """Simulate filesystem tool execution using GitHub config"""
        path = arguments.get('path', '/tmp/test.txt')
        content = arguments.get('content', '')
        
        security_model = github_config.get('security_model', 'sandboxed')
        allowed_ops = github_config.get('allowed_operations', [])
        base_dir = github_config.get('base_directory', '/tmp')
        
        return {
            "content": [
                {
                    "type": "text",
                    "text": f"Filesystem operation on: {path}\nContent: {content}\nSecurity model: {security_model}\nAllowed operations: {allowed_ops}\nBase directory: {base_dir}\n\nOperation would be executed within security constraints defined in GitHub config.\nCommand: {command} {' '.join(args)}"
                }
            ],
            "metadata": {
                "tool": "filesystem",
                "path": path,
                "security_model": security_model,
                "github_constraints": github_config,
                "command": f"{command} {' '.join(args)}"
            }
        }
    
    def _simulate_postgres_execution(self, arguments: Dict[str, Any], github_config: Dict[str, Any], command: str, args: List[str]) -> Dict[str, Any]:
        """Simulate PostgreSQL tool execution using GitHub config"""
        query = arguments.get('query', 'SELECT 1')
        
        dependencies = github_config.get('dependencies', [])
        timeout = github_config.get('query_timeout', 30000)
        security = github_config.get('security', 'connection_string_required')
        
        return {
            "content": [
                {
                    "type": "text",
                    "text": f"SQL Query: {query}\nDependencies: {dependencies}\nTimeout: {timeout}ms\nSecurity: {security}\n\nWould execute against PostgreSQL database using connection string from environment.\nResult would be formatted as JSON with proper error handling.\nCommand: {command} {' '.join(args)}"
                }
            ],
            "metadata": {
                "tool": "postgres_query",
                "query": query,
                "timeout": timeout,
                "dependencies": dependencies,
                "command": f"{command} {' '.join(args)}"
            }
        }
    
    def _simulate_git_execution(self, arguments: Dict[str, Any], github_config: Dict[str, Any], command: str, args: List[str]) -> Dict[str, Any]:
        """Simulate Git tool execution using GitHub config"""
        repo_path = arguments.get('repo_path', '/path/to/repo')
        limit = arguments.get('limit', 10)
        
        git_commands = github_config.get('git_commands', [])
        safety_checks = github_config.get('safety_checks', True)
        
        return {
            "content": [
                {
                    "type": "text",
                    "text": f"Git operation on: {repo_path}\nLimit: {limit}\nAvailable commands: {git_commands}\nSafety checks: {safety_checks}\n\nWould execute git commands with proper validation and error handling as defined in GitHub implementation.\nCommand: {command} {' '.join(args)}"
                }
            ],
            "metadata": {
                "tool": "git_operation",
                "repo_path": repo_path,
                "available_commands": git_commands,
                "safety_enabled": safety_checks,
                "command": f"{command} {' '.join(args)}"
            }
        }
    
    def _simulate_generic_execution(self, tool_name: str, arguments: Dict[str, Any], mcp_config: Dict[str, Any]) -> Dict[str, Any]:
        """Simulate generic tool execution"""
        command = mcp_config.get('command', 'unknown')
        args = mcp_config.get('args', [])
        
        return {
            "content": [
                {
                    "type": "text",
                    "text": f"Generic tool execution:\nTool: {tool_name}\nCommand: {command} {' '.join(args)}\nArguments: {json.dumps(arguments, indent=2)}\n\nWould execute using MCP configuration from GitHub repository."
                }
            ],
            "metadata": {
                "tool": tool_name,
                "command": f"{command} {' '.join(args)}",
                "arguments": arguments
            }
        }

class MCPHTTPHandler(BaseHTTPRequestHandler):
    """HTTP handler for MCP requests"""
    
    def __init__(self, graph_db, tool_executor, config, *args, **kwargs):
        self.graph_db = graph_db
        self.tool_executor = tool_executor
        self.config = config
        super().__init__(*args, **kwargs)
    
    def do_GET(self):
        """Handle GET requests"""
        if self.path == '/health':
            self._handle_health_check()
        elif self.path == '/metrics':
            self._handle_metrics()
        elif self.path.startswith('/tools/search'):
            self._handle_tool_search()
        else:
            self._send_response(404, {"error": "Not found"})
    
    def do_POST(self):
        """Handle POST requests"""
        if self.path == '/tools/execute':
            self._handle_tool_execution()
        elif self.path == '/mcp/message':
            self._handle_mcp_message()
        else:
            self._send_response(404, {"error": "Not found"})
    
    def _handle_health_check(self):
        """Handle health check requests"""
        health_status = {
            "status": "healthy",
            "timestamp": time.time(),
            "server": {
                "name": self.config.server_name,
                "version": self.config.server_version,
                "protocol_version": self.config.protocol_version
            },
            "components": {
                "graph_db": {"status": "healthy", "type": "mock"},
                "tool_executor": {"status": "healthy"},
                "mcp_servers": {"available": len(self.graph_db.mock_tools)}
            }
        }
        self._send_response(200, health_status)
    
    def _handle_metrics(self):
        """Handle metrics requests"""
        metrics = {
            "server_info": {
                "name": self.config.server_name,
                "version": self.config.server_version,
                "uptime": time.time()
            },
            "graph_database": {
                "total_tools": len(self.graph_db.mock_tools),
                "vendors": list(set(tool['vendor'] for tool in self.graph_db.mock_tools)),
                "categories": list(set(cat for tool in self.graph_db.mock_tools for cat in tool['categories']))
            },
            "endpoints": {
                "/health": "Health check",
                "/metrics": "Server metrics",
                "/tools/search?q=<query>&limit=<num>": "Search tools",
                "/tools/execute": "Execute tool (POST)",
                "/mcp/message": "MCP protocol (POST)"
            }
        }
        self._send_response(200, metrics)
    
    def _handle_tool_search(self):
        """Handle tool search requests"""
        try:
            # Parse query parameters
            query_params = parse_qs(urlparse(self.path).query)
            query = query_params.get('q', [''])[0]
            limit = int(query_params.get('limit', ['10'])[0])
            
            # Execute search
            results = self.graph_db.search_tools(query, limit)
            
            self._send_response(200, {
                "query": query,
                "total_results": len(results),
                "tools": results,
                "timestamp": time.time()
            })
            
        except Exception as e:
            self._send_response(500, {"error": str(e)})
    
    def _handle_tool_execution(self):
        """Handle tool execution requests"""
        try:
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            request_data = json.loads(post_data.decode('utf-8'))
            
            tool_name = request_data.get('tool_name')
            tool_config = request_data.get('tool_config', {})
            arguments = request_data.get('arguments', {})
            
            if not tool_name:
                self._send_response(400, {"error": "tool_name is required"})
                return
            
            # Execute tool
            result = self.tool_executor.execute_dynamic_tool(tool_name, tool_config, arguments)
            
            self._send_response(200, {
                "status": "success",
                "tool_name": tool_name,
                "result": result,
                "timestamp": time.time()
            })
            
        except Exception as e:
            self._send_response(500, {"error": str(e)})
    
    def _handle_mcp_message(self):
        """Handle direct MCP protocol messages"""
        try:
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            mcp_message = json.loads(post_data.decode('utf-8'))
            
            # Process MCP message (JSON-RPC 2.0)
            response = {
                "jsonrpc": "2.0",
                "id": mcp_message.get("id"),
                "result": {
                    "message": "MCP message processed by unified server",
                    "server_info": {
                        "name": self.config.server_name,
                        "version": self.config.server_version,
                        "protocol_version": self.config.protocol_version
                    },
                    "original_message": mcp_message
                }
            }
            
            self._send_response(200, response)
            
        except Exception as e:
            error_response = {
                "jsonrpc": "2.0",
                "id": None,
                "error": {
                    "code": -32603,
                    "message": "Internal error",
                    "data": str(e)
                }
            }
            self._send_response(500, error_response)
    
    def _send_response(self, status_code: int, data: Dict[str, Any]):
        """Send JSON response"""
        self.send_response(status_code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
        
        response_json = json.dumps(data, indent=2)
        self.wfile.write(response_json.encode('utf-8'))
    
    def log_message(self, format, *args):
        """Override to use our logger"""
        logger.info(f"HTTP {self.command} {self.path} from {self.client_address[0]}")

class UnifiedMCPServer:
    """Main unified MCP server implementation"""
    
    def __init__(self, config: ServerConfig):
        self.config = config
        self.logger = logger.getChild("unified_mcp_server")
        self.graph_db = MockGraphDatabase()
        self.tool_executor = ToolExecutor(self.graph_db)
        self.http_server: Optional[HTTPServer] = None
    
    def run(self):
        """Run the unified MCP server"""
        try:
            self.logger.info(f"Starting unified MCP server v{self.config.server_version}")
            self.logger.info(f"Server URL: http://{self.config.host}:{self.config.port}")
            
            # Test database connection
            test_results = self.graph_db.search_tools("test", limit=1)
            self.logger.info(f"Database initialized with {len(self.graph_db.mock_tools)} tools")
            
            # Create HTTP server with custom handler
            def handler_factory(*args, **kwargs):
                return MCPHTTPHandler(self.graph_db, self.tool_executor, self.config, *args, **kwargs)
            
            self.http_server = HTTPServer((self.config.host, self.config.port), handler_factory)
            
            self.logger.info(f"Server ready at http://{self.config.host}:{self.config.port}")
            self.logger.info("Available endpoints:")
            self.logger.info("  GET  /health - Health check")
            self.logger.info("  GET  /metrics - Server metrics")
            self.logger.info("  GET  /tools/search?q=<query> - Search tools")
            self.logger.info("  POST /tools/execute - Execute tool")
            self.logger.info("  POST /mcp/message - MCP protocol")
            
            try:
                self.http_server.serve_forever()
            except KeyboardInterrupt:
                self.logger.info("Received shutdown signal")
            
        except Exception as e:
            self.logger.error(f"Failed to start server: {str(e)}")
            raise
        finally:
            self.cleanup()
    
    def cleanup(self):
        """Cleanup server resources"""
        self.logger.info("Cleaning up server resources")
        
        if self.http_server:
            self.http_server.shutdown()
            self.http_server.server_close()
        
        self.logger.info("Server cleanup complete")

def main():
    """Main entry point"""
    # Load configuration
    config = ServerConfig()
    
    # Set up logging level
    logging.getLogger().setLevel(getattr(logging, config.log_level.upper()))
    
    # Create and run server
    server = UnifiedMCPServer(config)
    
    try:
        server.run()
    except KeyboardInterrupt:
        logger.info("Received shutdown signal")
    except Exception as e:
        logger.error(f"Server failed: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()