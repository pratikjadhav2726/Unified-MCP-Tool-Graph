import asyncio
import subprocess
import time
import os
from typing import Dict, Optional
from urllib.parse import urlparse  # new import

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
            # Merge provided env with current environment
            env = dict(os.environ)
            env.update(self.env)
            self.process = subprocess.Popen([self.command] + self.args, env=env)
            print(f"[MCP] Started {self.name} MCP server.")
        self.last_used = time.time()

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

    def _assign_endpoint(self, name, cfg):
        # If endpoint is provided, use it; otherwise, assign a new port
        endpoint = cfg.get("endpoint")
        if not endpoint:
            if name not in self._name_to_port:
                self._name_to_port[name] = self._next_port
                self._next_port += 1
            port = self._name_to_port[name]
            endpoint = f"http://localhost:{port}/sse"
            cfg["endpoint"] = endpoint  # Mutate config so downstream code sees it
        return endpoint

    def start_popular_servers(self):
        for name, cfg in self.popular_servers.items():
            self.add_and_start_server(name, cfg)

    def add_and_start_server(self, name, cfg):
        env = cfg.get("env", {})
        endpoint = self._assign_endpoint(name, cfg)

        # parse the assigned endpoint to get the port
        parsed = urlparse(endpoint)
        port = parsed.port

        # docker: inject -p host:container mapping if missing
        if cfg["command"] == "docker":
            args = list(cfg["args"])
            if "-p" not in args:
                try:
                    idx = args.index("run") + 1
                except ValueError:
                    idx = 0
                args[idx:idx] = ["-p", f"{port}:{port}"]
            cfg["args"] = args

        # npx: inject --port <port> if missing
        if cfg["command"] == "npx":
            args = list(cfg["args"])
            if "--port" not in args and "-p" not in args:
                args += ["--port", str(port)]
            cfg["args"] = args

        if name not in self.servers:
            proc = MCPServerProcess(
                name=name,
                command=cfg["command"],
                args=cfg["args"],
                endpoint=endpoint,
                env=env
            )
            proc.start()
            print(f"[MCP] {name} endpoint: {endpoint}")
            self.servers[name] = proc
        else:
            self.servers[name].start()
        cfg["endpoint"] = endpoint  # Ensure cfg has the endpoint
        cfg["transport"] = "sse"
        return cfg

    def ensure_server(self, name, cfg):
        if name not in self.servers or not self.servers[name].is_alive():
            cfg = self.add_and_start_server(name, cfg)
            return cfg
        else:
            self.servers[name].touch()
            return {"endpoint":self.servers[name].endpoint, "transport": "sse"}

    def get_active_endpoints(self):
        return {name: proc.endpoint for name, proc in self.servers.items() if proc.is_alive()}

    async def cleanup_loop(self):
        while True:
            now = time.time()
            for name, proc in list(self.servers.items()):
                if proc.is_alive() and now - proc.last_used > proc.keep_alive_secs:
                    proc.stop()
            await asyncio.sleep(60)

if __name__ == "__main__":
    import time
    print("[TEST] Starting MCPServerManager test...")
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
    print("[TEST] Ensuring server 'tavily-mcp' is started...")
    manager.ensure_server("tavily-mcp", test_config)
    print("[TEST] Active endpoints:", manager.get_active_endpoints())
    print("[TEST] Sleeping for 5 seconds to keep server alive...")
    time.sleep(5)
    print("[TEST] Stopping server...")
    manager.servers["tavily-mcp"].stop()
    print("[TEST] Done.")
