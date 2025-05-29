import asyncio
import subprocess
import time
from typing import Dict, Optional

class MCPServerProcess:
    def __init__(self, name, command, args, endpoint=None):
        self.name = name
        self.command = command
        self.args = args
        self.endpoint = endpoint
        self.process: Optional[subprocess.Popen] = None
        self.last_used = time.time()
        self.keep_alive_secs = 600  # 10 minutes

    def start(self):
        if self.process is None or self.process.poll() is not None:
            self.process = subprocess.Popen([self.command] + self.args)
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

    def start_popular_servers(self):
        for name, cfg in self.popular_servers.items():
            self.add_and_start_server(name, cfg)

    def add_and_start_server(self, name, cfg):
        if name not in self.servers:
            proc = MCPServerProcess(
                name=name,
                command=cfg["command"],
                args=cfg["args"],
                endpoint=cfg.get("endpoint")
            )
            proc.start()
            self.servers[name] = proc
        else:
            self.servers[name].start()

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
            for name, proc in list(self.servers.items()):
                if proc.is_alive() and now - proc.last_used > proc.keep_alive_secs:
                    proc.stop()
            await asyncio.sleep(60)
