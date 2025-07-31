#!/usr/bin/env python3
"""
End-to-End Test Script for Unified MCP Gateway

This script validates the complete production-ready workflow including:
- Server startup and initialization
- Tool discovery from all popular servers
- Dynamic tool retrieval with fallback
- Tool invocation and result processing
- Error handling and recovery
- Health monitoring and metrics
- Authentication and security
- Process management and cleanup

Usage:
    python run_end_to_end_test.py [--no-auth] [--quick] [--verbose]
"""

import asyncio
import argparse
import logging
import os
import sys
import time
import json
from pathlib import Path
from typing import Dict, List, Any, Optional

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from gateway.unified_gateway_v2 import UnifiedMCPGateway
from gateway.config import config, create_env_template
from examples.python_client import UnifiedMCPClient, GatewayConfig

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("EndToEndTest")

class EndToEndTestSuite:
    """
    Comprehensive end-to-end test suite for the Unified MCP Gateway.
    
    This test suite validates the complete production workflow and ensures
    all components work together correctly.
    """
    
    def __init__(self, use_auth: bool = False, quick_mode: bool = False):
        self.use_auth = use_auth
        self.quick_mode = quick_mode
        self.gateway: Optional[UnifiedMCPGateway] = None
        self.client: Optional[UnifiedMCPClient] = None
        self.test_results: Dict[str, Any] = {
            "passed": 0,
            "failed": 0,
            "skipped": 0,
            "details": []
        }
        
    async def setup(self):
        """Setup the test environment."""
        logger.info("Setting up end-to-end test environment...")
        
        # Create environment template if needed
        if not Path(".env").exists() and not Path(".env.template").exists():
            create_env_template()
            logger.info("Created .env.template - using default configuration")
        
        # Initialize gateway
        self.gateway = UnifiedMCPGateway()
        
        # Setup client configuration
        client_config = GatewayConfig(
            base_url=f"http://{config.host}:{config.port}",
            api_key=config.api_key if self.use_auth else None,
            timeout=60
        )
        self.client = UnifiedMCPClient(client_config)
        
        logger.info("Test environment setup complete")
    
    async def teardown(self):
        """Cleanup the test environment."""
        logger.info("Cleaning up test environment...")
        
        if self.client:
            await self.client.disconnect()
        
        if self.gateway:
            await self.gateway.shutdown()
        
        logger.info("Test environment cleanup complete")
    
    def record_test_result(self, test_name: str, passed: bool, details: str = "", duration: float = 0):
        """Record the result of a test."""
        status = "PASSED" if passed else "FAILED"
        
        result = {
            "test": test_name,
            "status": status,
            "details": details,
            "duration": duration
        }
        
        self.test_results["details"].append(result)
        
        if passed:
            self.test_results["passed"] += 1
            logger.info(f"✓ {test_name} - {status} ({duration:.2f}s)")
        else:
            self.test_results["failed"] += 1
            logger.error(f"✗ {test_name} - {status}: {details} ({duration:.2f}s)")
    
    async def test_gateway_startup(self):
        """Test gateway startup and initialization."""
        test_name = "Gateway Startup and Initialization"
        start_time = time.time()
        
        try:
            # Initialize the gateway
            await self.gateway.initialize()
            
            # Wait for initialization to complete
            await asyncio.sleep(10)
            
            # Connect client
            await self.client.connect()
            
            # Verify gateway is responding
            info = await self.client.get_info()
            assert info["name"] == "Unified MCP Gateway"
            assert info["version"] == "2.0.0"
            
            duration = time.time() - start_time
            self.record_test_result(test_name, True, f"Gateway started successfully", duration)
            
        except Exception as e:
            duration = time.time() - start_time
            self.record_test_result(test_name, False, str(e), duration)
            raise
    
    async def test_health_monitoring(self):
        """Test health monitoring and metrics."""
        test_name = "Health Monitoring and Metrics"
        start_time = time.time()
        
        try:
            # Get health status
            health = await self.client.health_check()
            
            # Validate health structure
            assert "status" in health
            assert "timestamp" in health
            assert "components" in health
            assert "metrics" in health
            
            # Check components
            components = health["components"]
            assert "system" in components
            assert "tool_retriever" in components
            assert "servers" in components
            
            # Check metrics
            metrics = health["metrics"]
            assert "total_servers" in metrics
            assert "healthy_servers" in metrics
            assert "total_tools" in metrics
            
            # Validate metrics are reasonable
            assert metrics["total_servers"] >= 0
            assert metrics["healthy_servers"] >= 0
            assert metrics["total_tools"] >= 0
            assert metrics["healthy_servers"] <= metrics["total_servers"]
            
            duration = time.time() - start_time
            status_msg = f"Health: {health['status']}, Tools: {metrics['total_tools']}, Servers: {metrics['healthy_servers']}/{metrics['total_servers']}"
            self.record_test_result(test_name, True, status_msg, duration)
            
        except Exception as e:
            duration = time.time() - start_time
            self.record_test_result(test_name, False, str(e), duration)
    
    async def test_tool_discovery(self):
        """Test tool discovery from all servers."""
        test_name = "Tool Discovery from All Servers"
        start_time = time.time()
        
        try:
            # List all tools
            tools = await self.client.list_tools()
            
            # Validate we have tools
            assert len(tools) > 0, "No tools discovered"
            
            # List all servers
            servers = await self.client.list_servers()
            
            # Validate we have servers
            assert len(servers) > 0, "No servers configured"
            
            # Check that we have expected popular servers
            expected_servers = ["time", "sequential-thinking", "dynamic-tool-retriever"]
            found_servers = list(servers.keys())
            
            for expected in expected_servers:
                if expected not in found_servers:
                    logger.warning(f"Expected server '{expected}' not found in {found_servers}")
            
            # Validate tool structure
            for tool in tools[:5]:  # Check first 5 tools
                assert "name" in tool
                assert "description" in tool
                assert "server" in tool
                assert "actual_name" in tool
            
            duration = time.time() - start_time
            details = f"Discovered {len(tools)} tools from {len(servers)} servers"
            self.record_test_result(test_name, True, details, duration)
            
        except Exception as e:
            duration = time.time() - start_time
            self.record_test_result(test_name, False, str(e), duration)
    
    async def test_tool_invocation(self):
        """Test tool invocation with popular servers."""
        test_name = "Tool Invocation (Popular Servers)"
        start_time = time.time()
        
        try:
            tools = await self.client.list_tools()
            successful_calls = 0
            tested_tools = []
            
            # Test time tool
            time_tools = [t for t in tools if "time" in t["name"].lower()]
            if time_tools:
                tool_name = time_tools[0]["name"]
                try:
                    result = await self.client.call_tool(tool_name, {"timezone": "UTC"})
                    successful_calls += 1
                    tested_tools.append(tool_name)
                    logger.info(f"Time tool result: {result}")
                except Exception as e:
                    logger.warning(f"Time tool call failed: {e}")
            
            # Test sequential thinking tool
            thinking_tools = [t for t in tools if "sequential" in t["name"].lower() or "thinking" in t["name"].lower()]
            if thinking_tools and not self.quick_mode:
                tool_name = thinking_tools[0]["name"]
                try:
                    result = await self.client.call_tool(tool_name, {"query": "What is 2+2?"})
                    successful_calls += 1
                    tested_tools.append(tool_name)
                    logger.info(f"Thinking tool completed successfully")
                except Exception as e:
                    logger.warning(f"Thinking tool call failed: {e}")
            
            # Require at least one successful tool call
            assert successful_calls > 0, f"No tool calls succeeded. Tested: {tested_tools}"
            
            duration = time.time() - start_time
            details = f"Successfully called {successful_calls} tools: {tested_tools}"
            self.record_test_result(test_name, True, details, duration)
            
        except Exception as e:
            duration = time.time() - start_time
            self.record_test_result(test_name, False, str(e), duration)
    
    async def test_dynamic_tool_retrieval(self):
        """Test dynamic tool retrieval with both real and dummy retrievers."""
        test_name = "Dynamic Tool Retrieval (Real + Fallback)"
        start_time = time.time()
        
        try:
            test_queries = [
                "search the web for information",
                "get current time",
                "read and process files",
                "general purpose assistant"
            ]
            
            successful_retrievals = 0
            
            for query in test_queries:
                try:
                    tools = await self.client.retrieve_tools(query, top_k=2)
                    
                    # Validate we got tools back
                    assert len(tools) > 0, f"No tools retrieved for query: {query}"
                    
                    # Validate tool structure
                    for tool in tools:
                        assert "tool_name" in tool, f"Missing tool_name in {tool}"
                        assert "tool_description" in tool, f"Missing tool_description in {tool}"
                    
                    successful_retrievals += 1
                    logger.info(f"Retrieved {len(tools)} tools for: {query}")
                    
                except Exception as e:
                    logger.warning(f"Tool retrieval failed for '{query}': {e}")
                
                # Quick mode - test fewer queries
                if self.quick_mode and successful_retrievals >= 2:
                    break
            
            # Require at least one successful retrieval
            assert successful_retrievals > 0, "No tool retrievals succeeded"
            
            duration = time.time() - start_time
            details = f"Successfully retrieved tools for {successful_retrievals}/{len(test_queries)} queries"
            self.record_test_result(test_name, True, details, duration)
            
        except Exception as e:
            duration = time.time() - start_time
            self.record_test_result(test_name, False, str(e), duration)
    
    async def test_error_handling(self):
        """Test error handling and recovery."""
        test_name = "Error Handling and Recovery"
        start_time = time.time()
        
        try:
            error_tests = [
                ("Invalid tool call", lambda: self.client.call_tool("nonexistent.tool")),
                ("Empty task description", lambda: self.client.retrieve_tools("")),
                ("Invalid arguments", lambda: self.client.call_tool("time.get_current_time", {"invalid": "param"}))
            ]
            
            handled_errors = 0
            
            for test_desc, test_func in error_tests:
                try:
                    await test_func()
                    logger.warning(f"Expected error for {test_desc} but got success")
                except Exception as e:
                    handled_errors += 1
                    logger.info(f"Correctly handled error for {test_desc}: {e}")
            
            # Verify system is still healthy after errors
            health = await self.client.health_check()
            assert health["status"] in ["healthy", "degraded"], f"System unhealthy after errors: {health['status']}"
            
            duration = time.time() - start_time
            details = f"Handled {handled_errors}/{len(error_tests)} error conditions, system remains {health['status']}"
            self.record_test_result(test_name, True, details, duration)
            
        except Exception as e:
            duration = time.time() - start_time
            self.record_test_result(test_name, False, str(e), duration)
    
    async def test_authentication(self):
        """Test authentication and authorization."""
        test_name = "Authentication and Authorization"
        start_time = time.time()
        
        if not self.use_auth:
            self.test_results["skipped"] += 1
            logger.info(f"⊝ {test_name} - SKIPPED (authentication disabled)")
            return
        
        try:
            # Test authenticated request (should work)
            tools = await self.client.list_tools()
            assert len(tools) >= 0  # Should succeed
            
            # Test unauthenticated request (should fail)
            unauth_client = UnifiedMCPClient(GatewayConfig(
                base_url=f"http://{config.host}:{config.port}",
                api_key=None  # No API key
            ))
            
            await unauth_client.connect()
            
            try:
                await unauth_client.list_tools()
                assert False, "Unauthenticated request should have failed"
            except Exception as e:
                assert "401" in str(e) or "unauthorized" in str(e).lower()
                logger.info("Correctly rejected unauthenticated request")
            finally:
                await unauth_client.disconnect()
            
            duration = time.time() - start_time
            self.record_test_result(test_name, True, "Authentication working correctly", duration)
            
        except Exception as e:
            duration = time.time() - start_time
            self.record_test_result(test_name, False, str(e), duration)
    
    async def test_complete_workflow(self):
        """Test a complete end-to-end workflow."""
        test_name = "Complete End-to-End Workflow"
        start_time = time.time()
        
        try:
            # Step 1: Wait for system to be healthy
            logger.info("Step 1: Waiting for system health...")
            healthy = await self.client.wait_for_healthy(max_wait=30)
            if not healthy:
                logger.warning("System not fully healthy, continuing test...")
            
            # Step 2: Discover available tools and servers
            logger.info("Step 2: Discovering available capabilities...")
            tools = await self.client.list_tools()
            servers = await self.client.list_servers()
            
            assert len(tools) > 0, "No tools available"
            assert len(servers) > 0, "No servers available"
            
            # Step 3: Retrieve relevant tools for a task
            logger.info("Step 3: Retrieving relevant tools...")
            task = "get current time and date information"
            relevant_tools = await self.client.retrieve_tools(task, top_k=3)
            
            assert len(relevant_tools) > 0, "No relevant tools found"
            
            # Step 4: Execute a tool
            logger.info("Step 4: Executing a tool...")
            time_tools = [t for t in tools if "time" in t["name"].lower()]
            
            if time_tools:
                tool_name = time_tools[0]["name"]
                result = await self.client.call_tool(tool_name, {"timezone": "UTC"})
                assert result is not None, "Tool execution returned no result"
                logger.info(f"Tool execution result: {result}")
            else:
                logger.warning("No time tool available for execution")
            
            # Step 5: Verify system health after workflow
            logger.info("Step 5: Verifying system health...")
            final_health = await self.client.health_check()
            
            assert final_health["status"] in ["healthy", "degraded"], "System unhealthy after workflow"
            
            duration = time.time() - start_time
            details = f"Workflow completed: {len(tools)} tools, {len(servers)} servers, system {final_health['status']}"
            self.record_test_result(test_name, True, details, duration)
            
        except Exception as e:
            duration = time.time() - start_time
            self.record_test_result(test_name, False, str(e), duration)
    
    async def run_all_tests(self):
        """Run all end-to-end tests."""
        logger.info("Starting comprehensive end-to-end test suite...")
        
        test_suite = [
            self.test_gateway_startup,
            self.test_health_monitoring,
            self.test_tool_discovery,
            self.test_tool_invocation,
            self.test_dynamic_tool_retrieval,
            self.test_error_handling,
            self.test_authentication,
            self.test_complete_workflow
        ]
        
        for test_func in test_suite:
            try:
                await test_func()
            except Exception as e:
                logger.error(f"Test {test_func.__name__} failed with unhandled exception: {e}")
                # Continue with other tests
        
        # Print summary
        self.print_test_summary()
    
    def print_test_summary(self):
        """Print a summary of test results."""
        total_tests = self.test_results["passed"] + self.test_results["failed"] + self.test_results["skipped"]
        
        print("\n" + "=" * 80)
        print("END-TO-END TEST SUMMARY")
        print("=" * 80)
        
        print(f"Total Tests: {total_tests}")
        print(f"✓ Passed: {self.test_results['passed']}")
        print(f"✗ Failed: {self.test_results['failed']}")
        print(f"⊝ Skipped: {self.test_results['skipped']}")
        
        success_rate = (self.test_results["passed"] / total_tests * 100) if total_tests > 0 else 0
        print(f"Success Rate: {success_rate:.1f}%")
        
        print("\nDetailed Results:")
        print("-" * 80)
        
        for result in self.test_results["details"]:
            status_icon = "✓" if result["status"] == "PASSED" else "✗"
            print(f"{status_icon} {result['test']}: {result['status']} ({result['duration']:.2f}s)")
            if result["details"]:
                print(f"   {result['details']}")
        
        print("-" * 80)
        
        if self.test_results["failed"] == 0:
            print("🎉 ALL TESTS PASSED! The Unified MCP Gateway is production-ready.")
        else:
            print(f"⚠️  {self.test_results['failed']} tests failed. Please review and fix issues.")
        
        print("=" * 80)

async def main():
    """Main function to run end-to-end tests."""
    parser = argparse.ArgumentParser(description="End-to-end test suite for Unified MCP Gateway")
    parser.add_argument("--no-auth", action="store_true", help="Disable authentication tests")
    parser.add_argument("--quick", action="store_true", help="Run quick tests only")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Initialize test suite
    test_suite = EndToEndTestSuite(
        use_auth=not args.no_auth,
        quick_mode=args.quick
    )
    
    try:
        # Setup test environment
        await test_suite.setup()
        
        # Run all tests
        await test_suite.run_all_tests()
        
        # Exit with appropriate code
        exit_code = 0 if test_suite.test_results["failed"] == 0 else 1
        
    except KeyboardInterrupt:
        logger.info("Test suite interrupted by user")
        exit_code = 130
    except Exception as e:
        logger.error(f"Test suite failed with unexpected error: {e}")
        exit_code = 1
    finally:
        # Cleanup
        await test_suite.teardown()
    
    sys.exit(exit_code)

if __name__ == "__main__":
    asyncio.run(main())