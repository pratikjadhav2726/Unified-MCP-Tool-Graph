"""
Comprehensive Error Handling and Process Management for MCP Gateway

This module provides:
- Robust error handling for server failures
- Orphaned process detection and cleanup
- Circuit breaker pattern for failing servers
- Graceful degradation strategies
- Process monitoring and recovery
"""

import asyncio
import logging
import psutil
import signal
import time
from typing import Dict, List, Optional, Any, Callable
from enum import Enum
from dataclasses import dataclass, field
from contextlib import asynccontextmanager
import subprocess

logger = logging.getLogger(__name__)

class ServerState(Enum):
    """Possible states for MCP servers."""
    STARTING = "starting"
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    FAILED = "failed"
    STOPPED = "stopped"

@dataclass
class ServerHealth:
    """Health information for an MCP server."""
    name: str
    state: ServerState
    last_success: Optional[float] = None
    last_failure: Optional[float] = None
    failure_count: int = 0
    success_count: int = 0
    process_id: Optional[int] = None
    error_messages: List[str] = field(default_factory=list)
    
    def record_success(self):
        """Record a successful operation."""
        self.last_success = time.time()
        self.success_count += 1
        self.failure_count = 0  # Reset failure count on success
        if self.state == ServerState.FAILED:
            self.state = ServerState.HEALTHY
            logger.info(f"Server {self.name} recovered from failure")
    
    def record_failure(self, error_message: str):
        """Record a failed operation."""
        self.last_failure = time.time()
        self.failure_count += 1
        self.error_messages.append(f"{time.time()}: {error_message}")
        
        # Keep only last 10 error messages
        if len(self.error_messages) > 10:
            self.error_messages = self.error_messages[-10:]
        
        # Update state based on failure count
        if self.failure_count >= 5:
            self.state = ServerState.FAILED
        elif self.failure_count >= 2:
            self.state = ServerState.DEGRADED

class CircuitBreaker:
    """Circuit breaker implementation for failing servers."""
    
    def __init__(self, failure_threshold: int = 5, recovery_timeout: int = 60):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failure_count = 0
        self.last_failure_time = 0
        self.state = "closed"  # closed, open, half-open
    
    def can_execute(self) -> bool:
        """Check if execution is allowed."""
        if self.state == "closed":
            return True
        elif self.state == "open":
            if time.time() - self.last_failure_time > self.recovery_timeout:
                self.state = "half-open"
                return True
            return False
        else:  # half-open
            return True
    
    def record_success(self):
        """Record successful execution."""
        self.failure_count = 0
        self.state = "closed"
    
    def record_failure(self):
        """Record failed execution."""
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.failure_count >= self.failure_threshold:
            self.state = "open"

class ProcessMonitor:
    """Monitor and manage MCP server processes."""
    
    def __init__(self):
        self.monitored_processes: Dict[str, subprocess.Popen] = {}
        self.process_health: Dict[str, ServerHealth] = {}
        self.circuit_breakers: Dict[str, CircuitBreaker] = {}
    
    def register_process(self, name: str, process: subprocess.Popen):
        """Register a process for monitoring."""
        self.monitored_processes[name] = process
        self.process_health[name] = ServerHealth(name, ServerState.STARTING, process_id=process.pid)
        self.circuit_breakers[name] = CircuitBreaker()
        logger.info(f"Registered process {name} with PID {process.pid}")
    
    def unregister_process(self, name: str):
        """Unregister a process from monitoring."""
        if name in self.monitored_processes:
            del self.monitored_processes[name]
        if name in self.process_health:
            self.process_health[name].state = ServerState.STOPPED
        logger.info(f"Unregistered process {name}")
    
    async def check_process_health(self, name: str) -> ServerHealth:
        """Check health of a specific process."""
        if name not in self.process_health:
            raise ValueError(f"Process {name} not registered")
        
        health = self.process_health[name]
        
        if name in self.monitored_processes:
            process = self.monitored_processes[name]
            
            # Check if process is still running
            if process.poll() is None:
                # Process is running, check if it's responsive
                try:
                    # Try to get process info using psutil
                    proc = psutil.Process(process.pid)
                    if proc.status() == psutil.STATUS_ZOMBIE:
                        health.record_failure("Process is zombie")
                    elif proc.status() == psutil.STATUS_STOPPED:
                        health.record_failure("Process is stopped")
                    else:
                        # Process seems healthy
                        if health.state == ServerState.STARTING:
                            health.state = ServerState.HEALTHY
                except psutil.NoSuchProcess:
                    health.record_failure("Process no longer exists")
                    self.unregister_process(name)
            else:
                # Process has terminated
                return_code = process.returncode
                health.record_failure(f"Process terminated with code {return_code}")
                self.unregister_process(name)
        
        return health
    
    async def cleanup_orphaned_processes(self):
        """Find and clean up orphaned MCP server processes."""
        orphaned_count = 0
        
        try:
            # Look for processes that might be orphaned MCP servers
            for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'ppid']):
                try:
                    proc_info = proc.info
                    cmdline = proc_info.get('cmdline', [])
                    
                    # Check if this looks like an MCP server process
                    if self._is_mcp_process(cmdline):
                        # Check if parent process still exists
                        ppid = proc_info.get('ppid')
                        if ppid and not psutil.pid_exists(ppid):
                            logger.warning(f"Found orphaned MCP process: PID {proc_info['pid']}, CMD: {' '.join(cmdline)}")
                            
                            # Try to terminate gracefully first
                            try:
                                proc.terminate()
                                proc.wait(timeout=5)
                                orphaned_count += 1
                            except (psutil.TimeoutExpired, psutil.AccessDenied):
                                # Force kill if graceful termination fails
                                try:
                                    proc.kill()
                                    orphaned_count += 1
                                except psutil.AccessDenied:
                                    logger.error(f"Cannot kill orphaned process {proc_info['pid']}: Access denied")
                
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        
        except Exception as e:
            logger.error(f"Error during orphaned process cleanup: {e}")
        
        if orphaned_count > 0:
            logger.info(f"Cleaned up {orphaned_count} orphaned MCP processes")
        
        return orphaned_count
    
    def _is_mcp_process(self, cmdline: List[str]) -> bool:
        """Check if a command line indicates an MCP server process."""
        if not cmdline:
            return False
        
        cmd_str = ' '.join(cmdline).lower()
        mcp_indicators = [
            'mcp-server',
            'tavily-mcp',
            'server-sequential-thinking',
            'mcp-server-time',
            'server-everything',
            'dynamic-tool-retriever'
        ]
        
        return any(indicator in cmd_str for indicator in mcp_indicators)
    
    async def restart_failed_process(self, name: str, restart_command: Callable) -> bool:
        """Attempt to restart a failed process."""
        if name not in self.process_health:
            return False
        
        health = self.process_health[name]
        circuit_breaker = self.circuit_breakers[name]
        
        if not circuit_breaker.can_execute():
            logger.warning(f"Circuit breaker open for {name}, not attempting restart")
            return False
        
        try:
            logger.info(f"Attempting to restart failed process: {name}")
            
            # Clean up old process if it exists
            if name in self.monitored_processes:
                old_process = self.monitored_processes[name]
                try:
                    old_process.terminate()
                    old_process.wait(timeout=5)
                except (subprocess.TimeoutExpired, ProcessLookupError):
                    try:
                        old_process.kill()
                    except ProcessLookupError:
                        pass
                
                self.unregister_process(name)
            
            # Start new process
            new_process = await restart_command()
            if new_process:
                self.register_process(name, new_process)
                circuit_breaker.record_success()
                health.record_success()
                logger.info(f"Successfully restarted process: {name}")
                return True
            else:
                raise Exception("Restart command returned None")
        
        except Exception as e:
            error_msg = f"Failed to restart process {name}: {e}"
            logger.error(error_msg)
            health.record_failure(error_msg)
            circuit_breaker.record_failure()
            return False

class ErrorHandler:
    """Centralized error handling for the MCP Gateway."""
    
    def __init__(self):
        self.process_monitor = ProcessMonitor()
        self.error_callbacks: Dict[str, List[Callable]] = {}
        self.recovery_strategies: Dict[str, Callable] = {}
    
    def register_error_callback(self, error_type: str, callback: Callable):
        """Register a callback for specific error types."""
        if error_type not in self.error_callbacks:
            self.error_callbacks[error_type] = []
        self.error_callbacks[error_type].append(callback)
    
    def register_recovery_strategy(self, server_name: str, strategy: Callable):
        """Register a recovery strategy for a specific server."""
        self.recovery_strategies[server_name] = strategy
    
    async def handle_server_error(self, server_name: str, error: Exception, context: Dict[str, Any] = None):
        """Handle an error from a specific server."""
        error_type = type(error).__name__
        error_msg = str(error)
        
        logger.error(f"Server {server_name} error ({error_type}): {error_msg}")
        
        # Record the error in process health
        if server_name in self.process_monitor.process_health:
            self.process_monitor.process_health[server_name].record_failure(error_msg)
        
        # Execute error callbacks
        if error_type in self.error_callbacks:
            for callback in self.error_callbacks[error_type]:
                try:
                    await callback(server_name, error, context)
                except Exception as e:
                    logger.error(f"Error callback failed: {e}")
        
        # Attempt recovery if strategy is available
        if server_name in self.recovery_strategies:
            try:
                recovery_strategy = self.recovery_strategies[server_name]
                success = await recovery_strategy()
                if success:
                    logger.info(f"Recovery successful for server: {server_name}")
                else:
                    logger.warning(f"Recovery failed for server: {server_name}")
            except Exception as e:
                logger.error(f"Recovery strategy failed for {server_name}: {e}")
    
    @asynccontextmanager
    async def error_context(self, server_name: str, operation: str):
        """Context manager for handling errors in server operations."""
        try:
            yield
            # Record success if no exception occurred
            if server_name in self.process_monitor.process_health:
                self.process_monitor.process_health[server_name].record_success()
        except Exception as e:
            await self.handle_server_error(server_name, e, {"operation": operation})
            raise
    
    async def get_system_health(self) -> Dict[str, Any]:
        """Get overall system health status."""
        health_status = {
            "overall_status": "healthy",
            "timestamp": time.time(),
            "servers": {},
            "orphaned_processes": 0
        }
        
        # Check all monitored processes
        for name in self.process_monitor.process_health:
            server_health = await self.process_monitor.check_process_health(name)
            health_status["servers"][name] = {
                "state": server_health.state.value,
                "failure_count": server_health.failure_count,
                "success_count": server_health.success_count,
                "last_success": server_health.last_success,
                "last_failure": server_health.last_failure,
                "recent_errors": server_health.error_messages[-3:] if server_health.error_messages else []
            }
        
        # Check for orphaned processes
        orphaned_count = await self.process_monitor.cleanup_orphaned_processes()
        health_status["orphaned_processes"] = orphaned_count
        
        # Determine overall status
        failed_servers = [name for name, info in health_status["servers"].items() 
                         if info["state"] == "failed"]
        degraded_servers = [name for name, info in health_status["servers"].items() 
                          if info["state"] == "degraded"]
        
        if failed_servers:
            health_status["overall_status"] = "degraded"
            health_status["failed_servers"] = failed_servers
        elif degraded_servers:
            health_status["overall_status"] = "degraded"
            health_status["degraded_servers"] = degraded_servers
        
        return health_status
    
    async def start_health_monitoring(self, check_interval: int = 60):
        """Start background health monitoring."""
        logger.info(f"Starting health monitoring with {check_interval}s interval")
        
        while True:
            try:
                await asyncio.sleep(check_interval)
                health_status = await self.get_system_health()
                
                # Log any issues
                if health_status["overall_status"] != "healthy":
                    logger.warning(f"System health degraded: {health_status}")
                
                # Clean up orphaned processes
                if health_status["orphaned_processes"] > 0:
                    logger.info(f"Cleaned up {health_status['orphaned_processes']} orphaned processes")
                
            except Exception as e:
                logger.error(f"Health monitoring error: {e}")

# Global error handler instance
error_handler = ErrorHandler()